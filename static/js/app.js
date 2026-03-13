/**
 * DartApp: Main application logic connecting all components.
 * Supports hit candidate review flow and vision overlays.
 */
class DartApp {
    constructor() {
        this.ws = new DartWebSocket();
        this.dartboard = new DartboardRenderer("dartboard-container");
        this.scoreboard = new Scoreboard("scoreboard");
        this.state = null;
        this.calibrationPoints = [];
        this.pendingHits = new Map(); // candidate_id -> candidate

        this._bindEvents();
        this._bindWebSocket();
        this._bindKeyboard();
        this._bindOverlayToggles();
        this.ws.connect();
        this._startStatsPolling();
    }

    _bindEvents() {
        // New Game
        const btnNewGame = document.getElementById("btn-new-game");
        if (btnNewGame) btnNewGame.addEventListener("click", () => this._newGame());

        // Undo
        const btnUndo = document.getElementById("btn-undo");
        if (btnUndo) btnUndo.addEventListener("click", () => this._undo());

        // Next Player
        const btnNext = document.getElementById("btn-next");
        if (btnNext) btnNext.addEventListener("click", () => this._nextPlayer());

        // Remove Darts (no longer advances player)
        const btnRemove = document.getElementById("btn-remove-darts");
        if (btnRemove) btnRemove.addEventListener("click", () => this._removeDarts());

        // End Game
        const btnEndGame = document.getElementById("btn-end-game");
        if (btnEndGame) btnEndGame.addEventListener("click", () => this._endGame());

        // Calibrate
        const btnCalibrate = document.getElementById("btn-calibrate");
        if (btnCalibrate) btnCalibrate.addEventListener("click", () => this._openCalibration());

        // Mode selection
        const btnCalManual = document.getElementById("btn-cal-manual");
        if (btnCalManual) btnCalManual.addEventListener("click", () => this._startManualCalibration());
        const btnCalAruco = document.getElementById("btn-cal-aruco");
        if (btnCalAruco) btnCalAruco.addEventListener("click", () => this._startArucoCalibration());
        const btnCalLens = document.getElementById("btn-cal-lens");
        if (btnCalLens) btnCalLens.addEventListener("click", () => this._startLensCalibration());

        // Manual calibration confirm/reset
        const btnCalConfirm = document.getElementById("btn-calibrate-confirm");
        if (btnCalConfirm) btnCalConfirm.addEventListener("click", () => this._submitCalibration());
        const btnCalReset = document.getElementById("btn-calibrate-reset");
        if (btnCalReset) btnCalReset.addEventListener("click", () => this._resetManualPoints());
        const btnCalBack = document.getElementById("btn-cal-back");
        if (btnCalBack) btnCalBack.addEventListener("click", () => this._showCalStep("cal-step-mode"));

        // Result accept/retry
        const btnCalAccept = document.getElementById("btn-cal-accept");
        if (btnCalAccept) btnCalAccept.addEventListener("click", () => this._closeCalibration());
        const btnCalRetry = document.getElementById("btn-cal-retry");
        if (btnCalRetry) btnCalRetry.addEventListener("click", () => this._showCalStep("cal-step-mode"));

        // Cancel
        const btnCalCancel = document.getElementById("btn-calibrate-cancel");
        if (btnCalCancel) btnCalCancel.addEventListener("click", () => this._closeCalibration());

        // Toggle setup
        const btnToggleSetup = document.getElementById("btn-toggle-setup");
        if (btnToggleSetup) {
            btnToggleSetup.addEventListener("click", () => {
                const setupEl = document.getElementById("game-setup");
                if (setupEl) setupEl.classList.toggle("game-setup--collapsed");
            });
        }

        // Winner modal close
        const btnCloseModal = document.getElementById("btn-close-modal");
        if (btnCloseModal) {
            btnCloseModal.addEventListener("click", () => {
                document.getElementById("winner-modal").style.display = "none";
            });
        }
    }

    _bindWebSocket() {
        this.ws.on("connected", () => {
            const el = document.getElementById("ws-status");
            if (el) {
                el.textContent = "Online";
                el.className = "ws-status ws-status--connected";
            }
        });

        this.ws.on("disconnected", () => {
            const el = document.getElementById("ws-status");
            if (el) {
                el.textContent = "Offline";
                el.className = "ws-status ws-status--disconnected";
            }
        });

        this.ws.on("game_state", (data) => this._updateState(data));

        // Hit candidate flow
        this.ws.on("hit_candidate", (data) => this._onHitCandidate(data));
        this.ws.on("hit_confirmed", (data) => this._onHitConfirmed(data));
        this.ws.on("hit_rejected", (data) => this._onHitRejected(data));

        // Legacy score event (for manual scoring)
        this.ws.on("score", (data) => this._onScoreEvent(data));

        // Darts removed
        this.ws.on("darts_removed", () => {
            this.dartboard.clearHits();
            this.pendingHits.clear();
            this._renderCandidates();
        });
    }

    _bindKeyboard() {
        document.addEventListener("keydown", (e) => {
            // Don't trigger in input fields
            if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;

            if (e.key === "Enter") {
                // Confirm oldest pending hit
                e.preventDefault();
                this._confirmOldestCandidate();
            } else if (e.key === "Backspace" || e.key === "Delete") {
                // Reject oldest pending hit
                e.preventDefault();
                this._rejectOldestCandidate();
            } else if (e.key === "u" || e.key === "U") {
                this._undo();
            }
        });
    }

    _bindOverlayToggles() {
        const el = document.getElementById("toggle-motion");
        if (el) {
            el.addEventListener("change", () => {
                const container = document.getElementById("motion-container");
                const feed = document.getElementById("motion-feed");
                if (el.checked) {
                    if (feed) feed.src = "/video/motion";
                    if (container) container.style.display = "block";
                } else {
                    if (feed) feed.src = "";
                    if (container) container.style.display = "none";
                }
                fetch("/api/overlays", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ motion: el.checked }),
                }).catch(e => console.error("Overlay toggle error:", e));
            });
        }
    }

    // --- Hit Candidate Flow ---

    _onHitCandidate(data) {
        this.pendingHits.set(data.candidate_id, data);

        // Show candidate marker on dartboard (with pending style)
        if (data.board_x_norm !== undefined && data.board_y_norm !== undefined) {
            this.dartboard.addHitNormalized(
                data.board_x_norm, data.board_y_norm, data.score, data.candidate_id, true
            );
        } else if (data.roi_x !== undefined && data.roi_y !== undefined) {
            this.dartboard.addHitExact(data.roi_x, data.roi_y, data.score,
                                        data.candidate_id, true);
        } else {
            this.dartboard.addHit(data.sector, data.ring, data.score, data.candidate_id, true);
        }

        this._renderCandidates();
    }

    _onHitConfirmed(data) {
        this.pendingHits.delete(data.candidate_id);
        // Update marker style from pending to confirmed
        this.dartboard.confirmHit(data.candidate_id);
        this._renderCandidates();
    }

    _onHitRejected(data) {
        this.pendingHits.delete(data.candidate_id);
        // Remove marker from dartboard
        this.dartboard.removeHit(data.candidate_id);
        this._renderCandidates();
    }

    _renderCandidates() {
        const panel = document.getElementById("candidates-panel");
        const list = document.getElementById("candidates-list");
        const badge = document.getElementById("pending-count");
        if (!panel || !list) return;

        // Clear
        while (list.firstChild) list.removeChild(list.firstChild);

        if (this.pendingHits.size === 0) {
            panel.style.display = "none";
            if (badge) badge.style.display = "none";
            return;
        }

        panel.style.display = "block";
        if (badge) {
            badge.style.display = "inline";
            badge.textContent = this.pendingHits.size + " Kandidat" + (this.pendingHits.size > 1 ? "en" : "");
        }

        this.pendingHits.forEach((candidate) => {
            const row = document.createElement("div");
            row.className = "candidate-row";

            // Score info
            const info = document.createElement("div");
            info.className = "candidate-info";

            const scoreLabel = document.createElement("span");
            scoreLabel.className = "candidate-score";
            scoreLabel.textContent = candidate.ring.toUpperCase() + " " + candidate.score;
            info.appendChild(scoreLabel);

            const qualityBar = document.createElement("div");
            qualityBar.className = "quality-bar";
            const qualityFill = document.createElement("div");
            qualityFill.className = "quality-fill";
            qualityFill.style.width = candidate.quality + "%";
            if (candidate.quality >= 70) qualityFill.classList.add("quality--good");
            else if (candidate.quality >= 40) qualityFill.classList.add("quality--medium");
            else qualityFill.classList.add("quality--low");
            qualityBar.appendChild(qualityFill);
            info.appendChild(qualityBar);

            row.appendChild(info);

            // Buttons
            const actions = document.createElement("div");
            actions.className = "candidate-actions";

            const btnConfirm = document.createElement("button");
            btnConfirm.className = "btn btn--small btn--confirm";
            btnConfirm.textContent = "\u2713";
            btnConfirm.title = "Bestaetigen (Enter)";
            btnConfirm.addEventListener("click", () => this._confirmCandidate(candidate.candidate_id));
            actions.appendChild(btnConfirm);

            const btnReject = document.createElement("button");
            btnReject.className = "btn btn--small btn--reject";
            btnReject.textContent = "\u2717";
            btnReject.title = "Verwerfen (Backspace)";
            btnReject.addEventListener("click", () => this._rejectCandidate(candidate.candidate_id));
            actions.appendChild(btnReject);

            row.appendChild(actions);
            list.appendChild(row);
        });
    }

    async _confirmCandidate(candidateId) {
        try {
            const response = await fetch(`/api/hits/${candidateId}/confirm`, { method: "POST" });
            await response.json();
        } catch (e) {
            console.error("Confirm error:", e);
        }
    }

    async _rejectCandidate(candidateId) {
        try {
            const response = await fetch(`/api/hits/${candidateId}/reject`, { method: "POST" });
            await response.json();
        } catch (e) {
            console.error("Reject error:", e);
        }
    }

    _confirmOldestCandidate() {
        const first = this.pendingHits.keys().next();
        if (!first.done) this._confirmCandidate(first.value);
    }

    _rejectOldestCandidate() {
        const first = this.pendingHits.keys().next();
        if (!first.done) this._rejectCandidate(first.value);
    }

    // --- State Updates ---

    _updateState(state) {
        this.state = state;
        this.scoreboard.update(state);

        const turnTotalEl = document.getElementById("turn-total");
        if (turnTotalEl) turnTotalEl.textContent = (state.turn_total || 0).toString();

        const dartsThrown = state.darts_thrown || 0;
        for (let i = 1; i <= 3; i++) {
            const dartEl = document.getElementById("dart-" + i);
            if (dartEl) {
                if (i <= dartsThrown) dartEl.classList.add("dart-icon--used");
                else dartEl.classList.remove("dart-icon--used");
            }
        }

        // Collapse game setup during active game
        const setupEl = document.getElementById("game-setup");
        if (setupEl) {
            if (state.players && state.players.length > 0 && !state.winner) {
                setupEl.classList.add("game-setup--collapsed");
            } else {
                setupEl.classList.remove("game-setup--collapsed");
            }
        }

        if (state.winner) this._showWinner(state.winner);
    }

    _onScoreEvent(data) {
        // Legacy: direct score without candidate flow (manual entry)
        if (data.board_x_norm !== undefined && data.board_y_norm !== undefined) {
            this.dartboard.addHitNormalized(data.board_x_norm, data.board_y_norm, data.score);
        } else if (data.roi_x !== undefined && data.roi_y !== undefined) {
            this.dartboard.addHitExact(data.roi_x, data.roi_y, data.score);
        } else if (data.sector !== undefined && data.ring !== undefined) {
            this.dartboard.addHit(data.sector, data.ring, data.score);
        }
    }

    _showWinner(name) {
        const modal = document.getElementById("winner-modal");
        const text = document.getElementById("winner-text");
        if (modal && text) {
            text.textContent = name + " gewinnt!";
            modal.style.display = "flex";
            modal.classList.add("winner-pulse");
            setTimeout(() => modal.classList.remove("winner-pulse"), 2000);
        }
    }

    // --- Game Actions ---

    async _newGame() {
        const modeEl = document.getElementById("game-mode");
        const scoreEl = document.getElementById("starting-score");
        const playersEl = document.getElementById("player-names");

        const mode = modeEl ? modeEl.value : "x01";
        const startingScore = scoreEl ? parseInt(scoreEl.value, 10) : 501;
        const playersStr = playersEl ? playersEl.value : "Spieler 1";
        const players = playersStr.split(",").map(s => s.trim()).filter(s => s.length > 0);
        if (players.length === 0) players.push("Spieler 1");

        this.dartboard.clearHits();
        this.pendingHits.clear();
        this._renderCandidates();

        try {
            const response = await fetch("/api/game/new", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode, players, starting_score: startingScore }),
            });
            const data = await response.json();
            this._updateState(data);
        } catch (e) {
            console.error("New game error:", e);
        }
    }

    async _undo() {
        try {
            const response = await fetch("/api/game/undo", { method: "POST" });
            const data = await response.json();
            this._updateState(data);
        } catch (e) {
            console.error("Undo error:", e);
        }
    }

    async _nextPlayer() {
        try {
            const response = await fetch("/api/game/next-player", { method: "POST" });
            const data = await response.json();
            this._updateState(data);
            this.dartboard.clearHits();
            this.pendingHits.clear();
            this._renderCandidates();
        } catch (e) {
            console.error("Next player error:", e);
        }
    }

    async _removeDarts() {
        try {
            await fetch("/api/game/remove-darts", { method: "POST" });
            // UI update comes via WebSocket "darts_removed" event
        } catch (e) {
            console.error("Remove darts error:", e);
        }
    }

    async _endGame() {
        const confirmed = window.confirm("Spiel wirklich beenden?");
        if (!confirmed) return;
        try {
            const response = await fetch("/api/game/end", { method: "POST" });
            const data = await response.json();
            this._updateState(data);
            this.dartboard.clearHits();
            this.pendingHits.clear();
            this._renderCandidates();
        } catch (e) {
            console.error("End game error:", e);
        }
    }

    // --- Calibration Workflow ---

    _openCalibration() {
        this.calibrationPoints = [];
        const modal = document.getElementById("calibration-modal");
        if (!modal) return;
        modal.style.display = "flex";
        this._showCalStep("cal-step-mode");
    }

    _showCalStep(stepId) {
        const steps = document.querySelectorAll(".cal-step");
        steps.forEach(s => { s.style.display = "none"; });
        const target = document.getElementById(stepId);
        if (target) target.style.display = "block";
    }

    async _startManualCalibration() {
        this.calibrationPoints = [];
        this._showCalStep("cal-step-manual");
        const btn = document.getElementById("btn-calibrate-confirm");
        if (btn) btn.disabled = true;

        try {
            const response = await fetch("/api/calibration/frame");
            const data = await response.json();
            if (data.ok && data.image) {
                const canvas = document.getElementById("calibration-canvas");
                if (canvas) {
                    const ctx = canvas.getContext("2d");
                    const img = new Image();
                    img.onload = () => {
                        canvas.width = img.width;
                        canvas.height = img.height;
                        ctx.drawImage(img, 0, 0);
                        this._setupCalibrationClicks(canvas, ctx, img);
                    };
                    img.src = data.image;
                }
            }
        } catch (e) {
            console.error("Calibration frame error:", e);
        }
    }

    async _startArucoCalibration() {
        this._showCalStep("cal-step-auto");
        const statusEl = document.getElementById("cal-auto-status");
        if (statusEl) statusEl.textContent = "Board-ArUco Alignment wird gestartet...";

        try {
            const response = await fetch("/api/calibration/board/aruco", { method: "POST" });
            const data = await response.json();
            if (data.ok) {
                await this._showCalibrationResult("Board-ArUco Alignment erfolgreich!");
            } else {
                if (statusEl) statusEl.textContent = "Fehler: " + (data.error || "Unbekannt");
                setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
            }
        } catch (e) {
            console.error("ArUco calibration error:", e);
            if (statusEl) statusEl.textContent = "Verbindungsfehler";
            setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
        }
    }

    async _startLensCalibration() {
        this._showCalStep("cal-step-auto");
        const statusEl = document.getElementById("cal-auto-status");
        if (statusEl) statusEl.textContent = "Lens Setup per ChArUco (ca. 3 Sekunden)...";

        try {
            const response = await fetch("/api/calibration/lens/charuco", { method: "POST" });
            const data = await response.json();
            if (data.ok) {
                await this._showCalibrationResult("Lens Setup erfolgreich!");
            } else {
                if (statusEl) statusEl.textContent = "Fehler: " + (data.error || "Unbekannt");
                setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
            }
        } catch (e) {
            console.error("Lens calibration error:", e);
            if (statusEl) statusEl.textContent = "Verbindungsfehler";
            setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
        }
    }

    _setupCalibrationClicks(canvas, ctx, img) {
        const self = this;
        canvas.onclick = function(event) {
            if (self.calibrationPoints.length >= 4) return;
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const x = (event.clientX - rect.left) * scaleX;
            const y = (event.clientY - rect.top) * scaleY;
            self.calibrationPoints.push([x, y]);

            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = "#2ed573";
            ctx.fill();
            ctx.strokeStyle = "#fff";
            ctx.lineWidth = 2;
            ctx.stroke();

            if (self.calibrationPoints.length > 1) {
                const prev = self.calibrationPoints[self.calibrationPoints.length - 2];
                ctx.beginPath();
                ctx.moveTo(prev[0], prev[1]);
                ctx.lineTo(x, y);
                ctx.strokeStyle = "#2ed573";
                ctx.lineWidth = 2;
                ctx.stroke();
            }

            if (self.calibrationPoints.length === 4) {
                const first = self.calibrationPoints[0];
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(first[0], first[1]);
                ctx.strokeStyle = "#2ed573";
                ctx.lineWidth = 2;
                ctx.stroke();

                const btn = document.getElementById("btn-calibrate-confirm");
                if (btn) btn.disabled = false;
            }

            const labelNum = self.calibrationPoints.length;
            const labels = ["OL", "OR", "UR", "UL"];
            ctx.fillStyle = "#fff";
            ctx.font = "bold 14px sans-serif";
            ctx.fillText(labels[labelNum - 1], x + 8, y - 8);
        };
    }

    _resetManualPoints() {
        this.calibrationPoints = [];
        const btn = document.getElementById("btn-calibrate-confirm");
        if (btn) btn.disabled = true;
        this._startManualCalibration();
    }

    async _submitCalibration() {
        if (this.calibrationPoints.length !== 4) return;
        try {
            const response = await fetch("/api/calibration/board/manual", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ points: this.calibrationPoints }),
            });
            const data = await response.json();
            if (data.ok) {
                await this._showCalibrationResult("Board-Alignment (manuell) erfolgreich!");
            } else {
                console.error("Calibration failed:", data.error);
            }
        } catch (e) {
            console.error("Calibration submit error:", e);
        }
    }

    async _showCalibrationResult(message) {
        this._showCalStep("cal-step-result");
        const textEl = document.getElementById("cal-result-text");
        if (textEl) textEl.textContent = message;

        try {
            const roiResp = await fetch("/api/calibration/roi-preview");
            const roiData = await roiResp.json();
            if (roiData.ok && roiData.image) {
                const roiImg = document.getElementById("cal-roi-preview");
                if (roiImg) roiImg.src = roiData.image;
            }
        } catch (e) {
            console.error("ROI preview error:", e);
        }

        try {
            const overlayResp = await fetch("/api/calibration/overlay");
            const overlayData = await overlayResp.json();
            if (overlayData.ok && overlayData.image) {
                const overlayImg = document.getElementById("cal-overlay-preview");
                if (overlayImg) overlayImg.src = overlayData.image;
            }
        } catch (e) {
            console.error("Overlay preview error:", e);
        }
    }

    _closeCalibration() {
        const modal = document.getElementById("calibration-modal");
        if (modal) modal.style.display = "none";
        this.calibrationPoints = [];
    }

    _startStatsPolling() {
        setInterval(async () => {
            try {
                const response = await fetch("/api/stats");
                const data = await response.json();
                const fpsEl = document.getElementById("fps-display");
                if (fpsEl) fpsEl.textContent = "FPS: " + data.fps;
            } catch (e) {
                // Silent fail
            }
        }, 2000);
    }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    window.dartApp = new DartApp();
});
