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
        this._candidateTimers = new Map(); // candidate_id -> timeout ID
        this._countdownInterval = null;
        this.multiCamRunning = false;
        this.calibrationValid = false;
        this._pickingCenter = false;
        this.activeCameraIds = [];
        this.charucoPreset = "40x20";

        this._bindEvents();
        this._bindWebSocket();
        this._bindKeyboard();
        this._bindOverlayToggles();
        this._bindCaptureSettings();
        this._bindRecording();
        this._bindMultiCam();
        this._bindCharucoBoardSelectors();
        this._syncCharucoBoardSelectors(this.charucoPreset);
        this._refreshCharucoBoardPresetFromServer();
        this._telemetryData = [];
        this._telemetryVisible = false;
        this._bindTelemetry();
        this._bindTelemetryStatus();
        this._bindPipelineHealth();
        this._bindCvTuning();
        this.ws.connect();
        this._startStatsPolling();
    }

    _showError(message) {
        let toast = document.getElementById("error-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "error-toast";
            toast.style.cssText = "position:fixed;top:12px;left:50%;transform:translateX(-50%);background:#e94560;color:#fff;padding:10px 24px;border-radius:6px;font-size:0.95em;z-index:9999;opacity:0;transition:opacity 0.3s;pointer-events:none;";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = "1";
        clearTimeout(this._errorToastTimer);
        this._errorToastTimer = setTimeout(() => { toast.style.opacity = "0"; }, 3000);
    }

    _bindEvents() {
        // Hide loading spinner when video feed loads
        const videoFeed = document.getElementById("video-feed");
        const videoLoading = document.getElementById("video-loading");
        if (videoFeed && videoLoading) {
            videoFeed.addEventListener("load", () => { videoLoading.style.display = "none"; });
            videoFeed.addEventListener("error", () => { videoLoading.style.display = "none"; });
        }

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
        const calCameraSelect = document.getElementById("calibration-camera-select");
        if (calCameraSelect) {
            calCameraSelect.addEventListener("change", () => {
                this._updateCalibrationCameraSelector();
                this._refreshCharucoBoardPresetFromServer();
                this._refreshCalibrationStatus();
            });
        }

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

        // B1: Manual optical center override
        const btnSetCenter = document.getElementById("btn-cal-set-center");
        if (btnSetCenter) btnSetCenter.addEventListener("click", () => this._startManualCenterPick());
        const roiImg = document.getElementById("cal-roi-preview");
        if (roiImg) roiImg.addEventListener("click", (e) => this._onRoiImageClick(e));

        // Cancel
        const btnCalCancel = document.getElementById("btn-calibrate-cancel");
        if (btnCalCancel) btnCalCancel.addEventListener("click", () => this._closeCalibration());

        // Marker overlay toggle in calibration modal
        const toggleMarkers = document.getElementById("toggle-markers");
        if (toggleMarkers) {
            toggleMarkers.addEventListener("change", () => {
                this._setMarkerOverlay(toggleMarkers.checked);
            });
        }

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

        // Camera health
        this.ws.on("camera_state", (data) => this._onCameraStateChange(data));

        // Stereo calibration progress
        this.ws.on("stereo_progress", (data) => this._updateStereoProgress(data));
        this.ws.on("stereo_result", (data) => this._showStereoResult(data));

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

        // Marker overlay toggle (main video controls)
        const markerMain = document.getElementById("toggle-markers-main");
        if (markerMain) {
            markerMain.addEventListener("change", () => {
                this._setMarkerOverlay(markerMain.checked);
            });
        }
    }

    _bindCharucoBoardSelectors() {
        const selectors = document.querySelectorAll(".charuco-board-select");
        selectors.forEach((selector) => {
            selector.addEventListener("change", () => {
                this._syncCharucoBoardSelectors(selector.value || "40x20");
            });
        });
    }

    _normalizeCharucoPreset(value) {
        return value === "40x28" ? "40x28" : "40x20";
    }

    _syncCharucoBoardSelectors(value) {
        const preset = this._normalizeCharucoPreset(value);
        this.charucoPreset = preset;
        const selectors = document.querySelectorAll(".charuco-board-select");
        selectors.forEach((selector) => {
            if (selector.value !== preset) {
                selector.value = preset;
            }
        });
    }

    _getSelectedCharucoPreset() {
        const selector = document.getElementById("charuco-board-preset") ||
            document.getElementById("stereo-charuco-board-preset");
        return this._normalizeCharucoPreset(selector?.value || this.charucoPreset || "40x20");
    }

    _describeCharucoPreset(preset) {
        if (preset === "40x28") return "7x5 / 40x28 mm";
        return "7x5 / 40x20 mm";
    }

    async _refreshCharucoBoardPresetFromServer() {
        try {
            const response = await fetch(this._buildCalibrationUrl("/api/calibration/lens/info"));
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            const preset = data?.charuco_board?.preset;
            if (preset) {
                this._syncCharucoBoardSelectors(preset);
            }
        } catch (e) {
            console.error("Charuco board info error:", e);
        }
    }

    _getCalibrationCameraId() {
        if (!this.multiCamRunning) return null;
        const activeIds = (this.activeCameraIds || []).filter(Boolean);
        if (!activeIds.length) return null;
        const select = document.getElementById("calibration-camera-select");
        const selected = select?.value;
        return activeIds.includes(selected) ? selected : activeIds[0];
    }

    _buildCalibrationUrl(path) {
        const cameraId = this._getCalibrationCameraId();
        if (!cameraId) return path;
        const join = path.includes("?") ? "&" : "?";
        return path + join + "camera_id=" + encodeURIComponent(cameraId);
    }

    _buildCalibrationBody(extra = {}) {
        const body = { ...extra };
        const cameraId = this._getCalibrationCameraId();
        if (cameraId) body.camera_id = cameraId;
        return body;
    }

    _getCalibrationTargetLabel() {
        const cameraId = this._getCalibrationCameraId();
        return cameraId ? "Kamera " + cameraId : "Single-Cam";
    }

    _updateCalibrationCameraSelector() {
        const panel = document.getElementById("calibration-camera-panel");
        const select = document.getElementById("calibration-camera-select");
        const hint = document.getElementById("calibration-camera-hint");
        const title = document.getElementById("cal-status-overview-title");
        if (!panel || !select || !hint || !title) return;

        const cameraIds = this.multiCamRunning ? (this.activeCameraIds || []).filter(Boolean) : [];
        if (!cameraIds.length) {
            panel.style.display = "none";
            title.textContent = this.multiCamRunning ? "Aktueller Status (Multi-Cam):" : "Aktueller Status (Single-Cam):";
            return;
        }

        panel.style.display = "block";
        const previous = select.value;
        while (select.firstChild) select.removeChild(select.firstChild);
        cameraIds.forEach((cameraId) => {
            const option = document.createElement("option");
            option.value = cameraId;
            option.textContent = cameraId;
            select.appendChild(option);
        });
        select.value = cameraIds.includes(previous) ? previous : cameraIds[0];
        const activeCamera = select.value;
        hint.textContent = "Lens- und Board-Kalibrierung werden fuer " + activeCamera + " gespeichert.";
        title.textContent = "Aktueller Status (" + activeCamera + "):";
    }

    _setCalibrationAutoStatus(message, { showSpinner = true, isError = false } = {}) {
        const statusEl = document.getElementById("cal-auto-status");
        const spinner = document.getElementById("cal-auto-spinner");
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.style.color = isError ? "var(--danger, #ff6b6b)" : "";
        }
        if (spinner) spinner.style.display = showSpinner ? "block" : "none";
    }

    // --- Hit Candidate Flow ---

    _onHitCandidate(data) {
        data._addedAt = Date.now();
        this.pendingHits.set(data.candidate_id, data);

        // Auto-reject after 30 seconds
        const timerId = setTimeout(() => {
            this._candidateTimers.delete(data.candidate_id);
            if (this.pendingHits.has(data.candidate_id)) {
                this._rejectCandidate(data.candidate_id);
            }
        }, 30000);
        this._candidateTimers.set(data.candidate_id, timerId);

        // Start countdown interval if not running
        if (!this._countdownInterval) {
            this._countdownInterval = setInterval(() => this._updateCountdowns(), 1000);
        }

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
        this._clearCandidateTimer(data.candidate_id);
        this.pendingHits.delete(data.candidate_id);
        // Update marker style from pending to confirmed
        this.dartboard.confirmHit(data.candidate_id);
        this._playHitSound();
        this._renderCandidates();
    }

    _onHitRejected(data) {
        this._clearCandidateTimer(data.candidate_id);
        this.pendingHits.delete(data.candidate_id);
        // Remove marker from dartboard
        this.dartboard.removeHit(data.candidate_id);
        this._renderCandidates();
    }

    _clearCandidateTimer(candidateId) {
        const timerId = this._candidateTimers.get(candidateId);
        if (timerId !== undefined) {
            clearTimeout(timerId);
            this._candidateTimers.delete(candidateId);
        }
    }

    _updateCountdowns() {
        if (this.pendingHits.size === 0) {
            clearInterval(this._countdownInterval);
            this._countdownInterval = null;
            return;
        }
        this._renderCandidates();
    }

    _playHitSound() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = "sine";
            gain.gain.value = 0.15;
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.15);
        } catch (e) { /* Audio not available */ }
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

            const countdown = document.createElement("span");
            countdown.style.cssText = "color: var(--text-muted); font-size: 0.7rem; margin-left: 6px;";
            const remaining = Math.max(0, 30 - Math.floor((Date.now() - (candidate._addedAt || Date.now())) / 1000));
            countdown.textContent = remaining + "s";
            info.appendChild(countdown);

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
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            await response.json();
        } catch (e) {
            console.error("Confirm error:", e);
        }
    }

    async _rejectCandidate(candidateId) {
        try {
            const response = await fetch(`/api/hits/${candidateId}/reject`, { method: "POST" });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
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

        // Checkout suggestion
        const checkoutEl = document.getElementById("checkout-suggestion");
        if (checkoutEl) {
            const suggestions = state.checkout || [];
            if (suggestions.length > 0) {
                checkoutEl.textContent = suggestions[0];
                checkoutEl.style.display = "block";
            } else {
                checkoutEl.style.display = "none";
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
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            if (data.ok === false) {
                // A2: Show calibration error to user
                const msg = data.error || "Spiel konnte nicht gestartet werden.";
                alert("⚠ " + msg);
                return;
            }
            this._updateState(data);
        } catch (e) {
            console.error("New game error:", e);
        }
    }

    async _undo() {
        try {
            const response = await fetch("/api/game/undo", { method: "POST" });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            this._updateState(data);
        } catch (e) {
            console.error("Undo error:", e);
        }
    }

    async _nextPlayer() {
        try {
            const response = await fetch("/api/game/next-player", { method: "POST" });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
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
            const response = await fetch("/api/game/remove-darts", { method: "POST" });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
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
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
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
        this._updateCalibrationCameraSelector();
        this._refreshCharucoBoardPresetFromServer();
        this._refreshCalibrationStatus();
        // Enable marker overlay by default when calibration modal opens
        this._setMarkerOverlay(true);
    }

    async _refreshCalibrationStatus() {
        this._updateCalibrationCameraSelector();
        try {
            const resp = await fetch(this._buildCalibrationUrl("/api/calibration/info"));
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok) return;
            const lensEl = document.getElementById("cal-status-lens");
            const boardEl = document.getElementById("cal-status-board");
            if (lensEl) {
                const hasLens = !!data.lens_valid;
                lensEl.textContent = hasLens ? "Lens ✓" : "Lens ✗";
                lensEl.className = "cal-status-item " + (hasLens ? "cal-status-item--done" : "cal-status-item--pending");
            }
            if (boardEl) {
                const hasBoard = !!data.board_valid;
                boardEl.textContent = hasBoard ? "Board ✓" : "Board ✗";
                boardEl.className = "cal-status-item " + (hasBoard ? "cal-status-item--done" : "cal-status-item--pending");
            }
        } catch (e) { /* silent */ }
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
            const response = await fetch(this._buildCalibrationUrl("/api/calibration/frame"));
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
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
            } else if (data.error) {
                this._showError(data.error);
            }
        } catch (e) {
            console.error("Calibration frame error:", e);
            this._showError("Kalibrierbild konnte nicht geladen werden.");
        }
    }

    async _startArucoCalibration() {
        this._showCalStep("cal-step-auto");
        this._setCalibrationAutoStatus(
            this._getCalibrationTargetLabel() + ": Board-ArUco Alignment wird gestartet..."
        );

        try {
            const response = await fetch("/api/calibration/board/aruco", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this._buildCalibrationBody()),
            });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            if (data.ok) {
                await this._showCalibrationResult("Board-ArUco Alignment erfolgreich!");
            } else {
                this._setCalibrationAutoStatus("Fehler: " + (data.error || "Unbekannt"), {
                    showSpinner: false,
                    isError: true,
                });
                this._showError(data.error || "Board-ArUco Alignment fehlgeschlagen.");
                setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
            }
        } catch (e) {
            console.error("ArUco calibration error:", e);
            this._setCalibrationAutoStatus("Verbindungsfehler", {
                showSpinner: false,
                isError: true,
            });
            this._showError("Verbindungsfehler bei der Board-ArUco-Kalibrierung.");
            setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
        }
    }

    async _startLensCalibration() {
        this._showCalStep("cal-step-auto");
        const preset = this._getSelectedCharucoPreset();
        this._setCalibrationAutoStatus(
            this._getCalibrationTargetLabel() + ": Lens Setup per ChArUco (" +
            this._describeCharucoPreset(preset) + ", ca. 3 Sekunden)..."
        );

        try {
            const response = await fetch("/api/calibration/lens/charuco", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this._buildCalibrationBody({ preset })),
            });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            if (data.ok) {
                if (data.charuco_board?.preset) {
                    this._syncCharucoBoardSelectors(data.charuco_board.preset);
                }
                await this._showCalibrationResult("Lens Setup erfolgreich!");
            } else {
                this._setCalibrationAutoStatus("Fehler: " + (data.error || "Unbekannt"), {
                    showSpinner: false,
                    isError: true,
                });
                this._showError(data.error || "Lens Setup fehlgeschlagen.");
                setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
            }
        } catch (e) {
            console.error("Lens calibration error:", e);
            this._setCalibrationAutoStatus("Verbindungsfehler", {
                showSpinner: false,
                isError: true,
            });
            this._showError("Verbindungsfehler beim Lens Setup.");
            setTimeout(() => this._showCalStep("cal-step-mode"), 3000);
        }
    }

    _setupCalibrationClicks(canvas, ctx, img) {
        const MIN_POINT_DIST_PX = 50;
        const self = this;
        canvas.onclick = function(event) {
            if (self.calibrationPoints.length >= 4) return;
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const x = (event.clientX - rect.left) * scaleX;
            const y = (event.clientY - rect.top) * scaleY;

            // A4: Warn if new point is too close to an existing point
            const hint = document.getElementById("cal-manual-hint");
            let tooClose = false;
            for (const pt of self.calibrationPoints) {
                const dist = Math.hypot(x - pt[0], y - pt[1]);
                if (dist < MIN_POINT_DIST_PX) {
                    tooClose = true;
                    break;
                }
            }
            if (tooClose) {
                if (hint) {
                    hint.textContent = `⚠ Punkt zu nah an einem bestehenden Punkt (min. ${MIN_POINT_DIST_PX}px Abstand).`;
                    hint.style.color = "#ff6b6b";
                }
                return;  // reject the click
            }
            if (hint) { hint.textContent = ""; hint.style.color = "#aaa"; }

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
                body: JSON.stringify(this._buildCalibrationBody({ points: this.calibrationPoints })),
            });
            if (!response.ok) { this._showError(`Fehler: ${response.status}`); return; }
            const data = await response.json();
            if (data.ok) {
                await this._showCalibrationResult("Board-Alignment (manuell) erfolgreich!");
            } else {
                console.error("Calibration failed:", data.error);
                this._showError(data.error || "Board-Alignment fehlgeschlagen.");
            }
        } catch (e) {
            console.error("Calibration submit error:", e);
            this._showError("Board-Alignment konnte nicht gespeichert werden.");
        }
    }

    async _showCalibrationResult(message) {
        this._showCalStep("cal-step-result");
        const textEl = document.getElementById("cal-result-text");
        if (textEl) textEl.textContent = this._getCalibrationTargetLabel() + ": " + message;

        try {
            const roiResp = await fetch(this._buildCalibrationUrl("/api/calibration/roi-preview"));
            if (!roiResp.ok) { this._showError(`Fehler: ${roiResp.status}`); return; }
            const roiData = await roiResp.json();
            if (roiData.ok && roiData.image) {
                const roiImg = document.getElementById("cal-roi-preview");
                if (roiImg) roiImg.src = roiData.image;
            }
        } catch (e) {
            console.error("ROI preview error:", e);
        }

        try {
            const overlayResp = await fetch(this._buildCalibrationUrl("/api/calibration/overlay"));
            if (!overlayResp.ok) { this._showError(`Fehler: ${overlayResp.status}`); return; }
            const overlayData = await overlayResp.json();
            if (overlayData.ok && overlayData.image) {
                const overlayImg = document.getElementById("cal-overlay-preview");
                if (overlayImg) overlayImg.src = overlayData.image;
            }
        } catch (e) {
            console.error("Overlay preview error:", e);
        }

        // B2: Fetch and render ring deviation table
        try {
            const ringResp = await fetch("/api/calibration/verify-rings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this._buildCalibrationBody()),
            });
            if (!ringResp.ok) { this._showError(`Fehler: ${ringResp.status}`); return; }
            const ringData = await ringResp.json();
            this._renderRingDeviations(ringData);
        } catch (e) {
            console.error("Ring verify error:", e);
        }

        this._refreshCalibrationStatus();
        if (this.multiCamRunning) {
            this._refreshMultiCamStatus();
        }
    }

    _renderRingDeviations(data) {
        const container = document.getElementById("ring-deviations");
        if (!container) return;
        container.textContent = "";
        if (!data.ok || !data.deviations || Object.keys(data.deviations).length === 0) {
            container.style.display = "none";
            return;
        }

        const label = document.createElement("p");
        label.style.cssText = "margin:8px 0 4px; font-size:0.85em; color:#aaa;";
        label.textContent = "Ring-Abweichungen (Soll vs. Ist):";
        container.appendChild(label);

        const table = document.createElement("table");
        table.style.cssText = "font-size:0.85em; border-collapse:collapse; width:100%;";

        for (const [ring, devMm] of Object.entries(data.deviations)) {
            const abs = Math.abs(devMm);
            let color = "#4caf50"; // green: ≤1mm
            if (abs > 3) color = "#f44336";      // red: >3mm
            else if (abs > 1) color = "#ff9800"; // orange: 1–3mm

            const tr = document.createElement("tr");

            const tdRing = document.createElement("td");
            tdRing.style.padding = "2px 8px";
            tdRing.textContent = ring;

            const tdDev = document.createElement("td");
            tdDev.style.cssText = "padding:2px 8px; font-weight:bold; color:" + color + ";";
            tdDev.textContent = (devMm >= 0 ? "+" : "") + devMm.toFixed(1) + " mm";

            tr.appendChild(tdRing);
            tr.appendChild(tdDev);
            table.appendChild(tr);
        }

        container.appendChild(table);
        container.style.display = "block";
    }

    // B1: Manual optical center picking on ROI preview image
    _startManualCenterPick() {
        this._pickingCenter = true;
        const hint = document.getElementById("cal-center-hint");
        if (hint) hint.style.display = "block";
        const roiImg = document.getElementById("cal-roi-preview");
        if (roiImg) roiImg.style.cursor = "crosshair";
    }

    async _onRoiImageClick(event) {
        if (!this._pickingCenter) return;
        this._pickingCenter = false;

        const hint = document.getElementById("cal-center-hint");
        if (hint) hint.style.display = "none";
        const roiImg = document.getElementById("cal-roi-preview");
        if (roiImg) roiImg.style.cursor = "";

        // Map click position to image natural coordinates
        const rect = roiImg.getBoundingClientRect();
        const scaleX = (roiImg.naturalWidth || roiImg.clientWidth) / rect.width;
        const scaleY = (roiImg.naturalHeight || roiImg.clientHeight) / rect.height;
        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;

        try {
            const resp = await fetch("/api/calibration/optical-center/manual", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this._buildCalibrationBody({ x, y })),
            });
            if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
            const data = await resp.json();
            if (data.ok) {
                if (hint) {
                    hint.textContent = "Mittelpunkt gesetzt: (" + x.toFixed(0) + ", " + y.toFixed(0) + ")";
                    hint.style.color = "#4caf50";
                    hint.style.display = "block";
                }
            } else {
                console.error("Set optical center failed:", data.error);
                if (hint) {
                    hint.textContent = "Fehler: " + (data.error || "Unbekannt");
                    hint.style.color = "#f44336";
                    hint.style.display = "block";
                }
            }
        } catch (e) {
            console.error("Optical center manual error:", e);
        }
    }

    _closeCalibration() {
        this._pickingCenter = false;
        const modal = document.getElementById("calibration-modal");
        if (modal) modal.style.display = "none";
        this.calibrationPoints = [];
        // Disable marker overlay when calibration modal closes
        this._setMarkerOverlay(false);
    }

    _setMarkerOverlay(enabled) {
        // Sync both marker toggles (calibration modal + main controls)
        const toggle = document.getElementById("toggle-markers");
        if (toggle) toggle.checked = enabled;
        const toggleMain = document.getElementById("toggle-markers-main");
        if (toggleMain) toggleMain.checked = enabled;
        fetch("/api/overlays", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ markers: enabled }),
        }).catch(e => console.error("Marker overlay toggle error:", e));
    }

    // --- Capture Settings ---

    _bindCaptureSettings() {
        const btn = document.getElementById("btn-capture-settings");
        const panel = document.getElementById("capture-settings");
        if (btn && panel) {
            btn.addEventListener("click", () => {
                const visible = panel.style.display !== "none";
                panel.style.display = visible ? "none" : "block";
                if (!visible) this._loadCaptureConfig();
            });
        }
        const btnApply = document.getElementById("btn-apply-capture");
        if (btnApply) btnApply.addEventListener("click", () => this._applyCaptureSettings());

        // Camera ID selector: reload settings when changed
        const camSel = document.getElementById("capture-camera-id");
        if (camSel) camSel.addEventListener("change", () => this._onCameraIdChanged());

        // Single-cam switch button
        const btnSingle = document.getElementById("btn-switch-single");
        if (btnSingle) btnSingle.addEventListener("click", () => this._switchToSingle());
    }

    // --- Recording ---

    _bindRecording() {
        const btn = document.getElementById("btn-record");
        if (!btn) return;
        btn.addEventListener("click", () => this._toggleRecording(btn));
    }

    async _toggleRecording(btn) {
        try {
            const statusRes = await fetch("/api/recording/status");
            if (!statusRes.ok) { this._showError("Recording-Status nicht verfuegbar"); return; }
            const status = await statusRes.json();

            if (status.recording) {
                const res = await fetch("/api/recording/stop", { method: "POST" });
                if (!res.ok) { this._showError(`Stop-Fehler: ${res.status}`); return; }
                const data = await res.json();
                btn.textContent = "Rec";
                btn.classList.remove("btn--recording");
                if (data.ok) {
                    this._showError(`Aufnahme gespeichert: ${data.output_path} (${data.frame_count} Frames)`);
                }
            } else {
                const res = await fetch("/api/recording/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
                if (!res.ok) { this._showError(`Start-Fehler: ${res.status}`); return; }
                const data = await res.json();
                if (data.ok) {
                    btn.textContent = "Stop";
                    btn.classList.add("btn--recording");
                } else {
                    this._showError(data.error || "Aufnahme konnte nicht gestartet werden");
                }
            }
        } catch (e) {
            this._showError("Recording-Fehler: " + e.message);
        }
    }

    async _loadCaptureConfig() {
        const info = document.getElementById("capture-info");
        try {
            const res = await fetch("/api/capture/config");
            if (!res.ok) { this._showError(`Fehler: ${res.status}`); return; }
            const data = await res.json();
            if (!data.ok) {
                if (info) info.textContent = data.error || "Keine Kamera";
                return;
            }
            const camIds = Object.keys(data.cameras);
            if (camIds.length === 0) return;

            // Populate camera ID selector
            const camSel = document.getElementById("capture-camera-id");
            if (camSel) {
                const prevValue = camSel.value;
                while (camSel.firstChild) camSel.removeChild(camSel.firstChild);
                camIds.forEach(id => {
                    const opt = document.createElement("option");
                    opt.value = id;
                    opt.textContent = id;
                    camSel.appendChild(opt);
                });
                // Restore previous selection if still valid
                if (camIds.includes(prevValue)) camSel.value = prevValue;
            }

            // Store all camera configs for quick access
            this._captureConfigs = data.cameras;

            // Show selected camera's config
            this._showCameraConfig(camSel ? camSel.value : camIds[0]);
        } catch (e) {
            if (info) info.textContent = "Fehler beim Laden";
        }
    }

    _onCameraIdChanged() {
        const camSel = document.getElementById("capture-camera-id");
        if (camSel && this._captureConfigs) {
            this._showCameraConfig(camSel.value);
        }
    }

    _showCameraConfig(camId) {
        const info = document.getElementById("capture-info");
        const cfg = this._captureConfigs && this._captureConfigs[camId];
        if (!cfg) return;

        const actual = cfg.actual;
        const requested = cfg.requested;

        const resSel = document.getElementById("capture-resolution");
        if (resSel) resSel.value = requested.width + "x" + requested.height;
        const fpsSel = document.getElementById("capture-fps");
        if (fpsSel) fpsSel.value = String(requested.fps);

        if (info) {
            if (cfg.mismatch) {
                info.textContent = camId + ": Kamera liefert " + actual.width + "x" + actual.height +
                    " (angefordert: " + requested.width + "x" + requested.height + ")";
                info.className = "capture-settings__info capture-settings__info--mismatch";
            } else {
                info.textContent = camId + ": " + actual.width + "x" + actual.height + " @ " + actual.fps + " fps";
                info.className = "capture-settings__info";
            }
        }
    }

    async _applyCaptureSettings() {
        const info = document.getElementById("capture-info");
        const resSel = document.getElementById("capture-resolution");
        const fpsSel = document.getElementById("capture-fps");
        const camSel = document.getElementById("capture-camera-id");
        if (!resSel || !fpsSel) return;

        const [w, h] = resSel.value.split("x").map(Number);
        const fps = Number(fpsSel.value);
        const cameraId = camSel ? camSel.value : "default";

        if (info) {
            info.textContent = "Wird angewendet...";
            info.className = "capture-settings__info";
        }

        try {
            const res = await fetch("/api/capture/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ camera_id: cameraId, width: w, height: h, fps }),
            });
            if (!res.ok) { this._showError(`Fehler: ${res.status}`); return; }
            const data = await res.json();
            if (data.ok) {
                const actual = data.actual;
                const label = cameraId + ": ";
                if (data.mismatch) {
                    info.textContent = label + "Kamera liefert " + actual.width + "x" + actual.height +
                        " statt " + w + "x" + h + " — Hardware unterstuetzt diese Aufloesung nicht";
                    info.className = "capture-settings__info capture-settings__info--mismatch";
                } else {
                    info.textContent = label + actual.width + "x" + actual.height + " @ " + actual.fps + " fps";
                    info.className = "capture-settings__info";
                }
                // Update cached config
                if (this._captureConfigs) {
                    this._captureConfigs[cameraId] = { requested: { width: w, height: h, fps }, actual, mismatch: data.mismatch };
                }
            } else {
                if (info) info.textContent = "Fehler: " + (data.error || "Unbekannt");
            }
        } catch (e) {
            if (info) info.textContent = "Fehler beim Anwenden";
        }
    }

    async _switchToSingle() {
        const info = document.getElementById("capture-info");
        const srcInput = document.getElementById("single-cam-src");
        const src = srcInput ? parseInt(srcInput.value, 10) : 0;

        if (info) {
            info.textContent = "Wechsle zu Single-Cam (Quelle " + src + ")...";
            info.className = "capture-settings__info";
        }

        try {
            // If multi is running, stop it first (auto-restarts single)
            if (this.multiCamRunning) {
                const resp = await fetch("/api/multi/stop", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ restart_single: true, single_src: src }),
                });
                if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
                const data = await resp.json();
                if (data.ok) {
                    this.multiCamRunning = false;
                    this.activeCameraIds = [];
                    this._hideMultiVideoGrid();
                    if (info) info.textContent = "Single-Cam aktiv (Quelle " + src + ")";
                } else {
                    if (info) info.textContent = "Fehler: " + (data.error || "Unbekannt");
                }
            } else {
                // Just restart single with new source
                const resp = await fetch("/api/single/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ src }),
                });
                if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
                const data = await resp.json();
                if (data.ok) {
                    if (info) info.textContent = "Single-Cam aktiv (Quelle " + src + ")";
                } else {
                    if (info) info.textContent = "Fehler: " + (data.error || "Unbekannt");
                }
            }
            // Reload capture config after switch
            setTimeout(() => this._loadCaptureConfig(), 1000);
        } catch (e) {
            if (info) info.textContent = "Fehler beim Wechsel";
        }
    }

    _startStatsPolling() {
        setInterval(async () => {
            try {
                const response = await fetch("/api/stats");
                if (!response.ok) return;
                const data = await response.json();
                const fpsEl = document.getElementById("fps-display");
                if (fpsEl) fpsEl.textContent = "FPS: " + data.fps;
                // Telemetry indicators
                const dropEl = document.getElementById("dropped-display");
                if (dropEl) {
                    dropEl.textContent = "Drop: " + (data.dropped_frames || 0);
                    dropEl.classList.toggle("header__metric--warn", (data.dropped_frames || 0) > 10);
                }
                const qEl = document.getElementById("queue-display");
                if (qEl) {
                    const pct = Math.round((data.queue_pressure || 0) * 100);
                    qEl.textContent = "Q: " + pct + "%";
                    qEl.classList.toggle("header__metric--warn", pct > 60);
                }
                const memEl = document.getElementById("memory-display");
                if (memEl && data.memory_mb != null && data.memory_mb > 0) {
                    memEl.textContent = "RAM: " + data.memory_mb + "MB";
                }
                // Track multi-cam state for UI
                this.multiCamRunning = data.multi_pipeline_running || false;
                this.activeCameraIds = data.active_cameras || [];
                this._updateMultiCamUI();
                // Camera health from stats polling
                this._updateCameraHealthFromStats(data.camera_health);
                // Pipeline health dashboard
                if (this._pipelineHealthVisible && data.pipeline_health) {
                    this._updatePipelineHealth(data.pipeline_health);
                }
                // Homography age warning (P62)
                if (data.pipeline_health) {
                    this._updateHomographyWarning(data.pipeline_health.homography_age || 0);
                }
                // A2: Update calibration validity and "New Game" button state
                this.calibrationValid = data.board_calibrated || false;
                this._updateNewGameButton();
            } catch (e) {
                // Silent fail
            }
        }, 2000);
    }

    _onCameraStateChange(data) {
        const banner = document.getElementById("camera-warning-banner");
        const text = document.getElementById("camera-warning-text");
        if (!banner || !text) return;

        if (data.state === "connected") {
            banner.style.display = "none";
            banner.className = "camera-warning";
        } else if (data.state === "reconnecting") {
            text.textContent = `Kamera ${data.camera_id}: Verbindung unterbrochen — Reconnect läuft...`;
            banner.className = "camera-warning camera-warning--reconnecting";
            banner.style.display = "block";
        } else if (data.state === "disconnected") {
            text.textContent = `Kamera ${data.camera_id}: Nicht erreichbar — bitte USB-Verbindung prüfen`;
            banner.className = "camera-warning camera-warning--disconnected";
            banner.style.display = "block";
        }
    }

    _updateStereoProgress(data) {
        const bar = document.getElementById('stereo-progress-bar');
        const text = document.getElementById('stereo-progress-text');
        const container = document.getElementById('stereo-progress-container');
        if (container) container.style.display = 'block';
        if (bar) bar.style.width = data.percent + '%';
        if (data.phase === 'computing') {
            if (text) text.textContent = 'Berechne Stereo-Kalibrierung... (' + (data.valid_pairs || 0) + ' gueltige Paare)';
            if (bar) bar.style.background = 'var(--accent-color-secondary, #2196f3)';
            return;
        }
        // Color bar based on detection status
        if (data.both_detected) {
            if (bar) bar.style.background = 'var(--accent-color, #4caf50)';
        } else {
            if (bar) bar.style.background = '#ff9800';
        }
        if (text) {
            const iA = data.detected_a ? '\u2713' : '\u2717';
            const iB = data.detected_b ? '\u2713' : '\u2717';
            const valid = data.valid_pairs != null ? data.valid_pairs : '?';
            var line = 'Frame ' + (data.frame_idx + 1) + '/' + data.total +
                ' | Gueltige Paare: ' + valid +
                ' | Cam A: ' + iA + '  Cam B: ' + iB;
            if (data.error) {
                line += ' | ' + data.error;
            }
            text.textContent = line;
            text.style.color = data.error ? '#ff9800' : 'var(--text-secondary, #aaa)';
        }
    }

    _showStereoResult(data) {
        const el = document.getElementById('stereo-result-info');
        if (!el) return;
        const colors = {excellent: '#4caf50', good: '#8bc34a', acceptable: '#ff9800', poor: '#f44336'};
        const c = colors[data.quality] || '#999';
        // Build result display using DOM — data originates from our own server
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'margin-top:12px;padding:12px;border-radius:8px;border:1px solid ' + c + ';background:' + c + '22';
        const strong = document.createElement('strong');
        strong.style.color = c;
        strong.textContent = data.label;
        const rmsText = document.createTextNode(' (RMS: ' + data.rms.toFixed(4) + ')');
        const br1 = document.createElement('br');
        const rec = document.createElement('small');
        rec.textContent = data.recommendation;
        const br2 = document.createElement('br');
        const info = document.createElement('small');
        info.textContent = data.pairs_used + ' Frame-Paare (' + data.camera_a + ' / ' + data.camera_b + ')';
        wrapper.append(strong, rmsText, br1, rec, br2, info);
        el.textContent = '';
        el.appendChild(wrapper);
    }

    _updateCameraHealthFromStats(cameraHealth) {
        if (!cameraHealth) return;
        const banner = document.getElementById("camera-warning-banner");
        const text = document.getElementById("camera-warning-text");
        if (!banner || !text) return;

        // Check if any camera is not connected
        const entries = Object.entries(cameraHealth);
        const degraded = entries.filter(([, h]) => h.state !== "connected");
        if (degraded.length === 0) {
            banner.style.display = "none";
            return;
        }
        const [camId, health] = degraded[0];
        if (health.state === "reconnecting") {
            text.textContent = `Kamera ${camId}: Reconnect-Versuch ${health.reconnect_attempts}...`;
            banner.className = "camera-warning camera-warning--reconnecting";
        } else {
            text.textContent = `Kamera ${camId}: Nicht erreichbar (${health.seconds_since_last_frame}s ohne Frame)`;
            banner.className = "camera-warning camera-warning--disconnected";
        }
        banner.style.display = "block";
    }

    _updateNewGameButton() {
        const btn = document.getElementById("btn-new-game");
        if (!btn) return;
        if (this.calibrationValid) {
            btn.disabled = false;
            btn.title = "";
        } else {
            btn.disabled = true;
            btn.title = "Board nicht kalibriert — bitte zuerst kalibrieren";
        }
    }

    // --- Multi-Camera ---

    _bindMultiCam() {
        const btnMultiCam = document.getElementById("btn-multi-cam");
        if (btnMultiCam) btnMultiCam.addEventListener("click", () => this._openMultiCamModal());

        const btnMultiClose = document.getElementById("btn-multi-close");
        if (btnMultiClose) btnMultiClose.addEventListener("click", () => this._closeMultiCamModal());

        const btnMultiStart = document.getElementById("btn-multi-start");
        if (btnMultiStart) btnMultiStart.addEventListener("click", () => this._startMultiPipeline());

        const btnMultiStop = document.getElementById("btn-multi-stop");
        if (btnMultiStop) btnMultiStop.addEventListener("click", () => this._stopMultiPipeline());

        const btnMultiAddCam = document.getElementById("btn-multi-add-cam");
        if (btnMultiAddCam) btnMultiAddCam.addEventListener("click", () => this._addCameraEntry());

        const btnSetupRefresh = document.getElementById("btn-setup-refresh");
        if (btnSetupRefresh) btnSetupRefresh.addEventListener("click", () => this._refreshSetupGuide());

        // Stereo calibration buttons
        const btnStereoCalibrate = document.getElementById("btn-stereo-calibrate");
        if (btnStereoCalibrate) btnStereoCalibrate.addEventListener("click", () => this._runStereoCalibration());

        const btnStereoBack = document.getElementById("btn-stereo-back");
        if (btnStereoBack) btnStereoBack.addEventListener("click", () => {
            document.getElementById("multi-step-stereo").style.display = "none";
            document.getElementById("multi-step-config").style.display = "block";
        });

        // Stereo button in calibration modal
        const btnCalStereo = document.getElementById("btn-cal-stereo");
        if (btnCalStereo) btnCalStereo.addEventListener("click", () => {
            this._closeCalibration();
            this._openMultiCamModal();
            this._showStereoStep();
        });

        // Bind preview buttons on initial entries
        document.querySelectorAll(".multi-cam-preview-btn").forEach(btn => {
            btn.addEventListener("click", (e) => this._loadCameraPreview(e.target.closest(".multi-cam-entry")));
        });
    }

    _openMultiCamModal() {
        const modal = document.getElementById("multi-cam-modal");
        if (modal) modal.style.display = "flex";
        this._refreshCharucoBoardPresetFromServer();
        this._refreshMultiCamStatus();
        this._loadLastMultiConfig();
    }

    async _loadLastMultiConfig() {
        // Only populate if pipeline is not running and there's no user edits yet
        if (this.multiCamRunning) return;
        try {
            const resp = await fetch("/api/multi/last-config");
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok || !data.cameras || data.cameras.length < 2) return;
            const list = document.getElementById("multi-cam-list");
            if (!list) return;
            // Only overwrite if current entries still have defaults
            const entries = list.querySelectorAll(".multi-cam-entry");
            if (entries.length === 2) {
                const firstId = entries[0].querySelector(".multi-cam-id")?.value;
                if (firstId === "cam_left" || firstId === "") {
                    // Replace with saved config
                    while (list.firstChild) list.removeChild(list.firstChild);
                    data.cameras.forEach(cam => {
                        const entry = document.createElement("div");
                        entry.className = "multi-cam-entry";
                        const fields = document.createElement("div");
                        fields.className = "multi-cam-entry__fields";
                        const idInput = document.createElement("input");
                        idInput.type = "text";
                        idInput.className = "input multi-cam-id";
                        idInput.placeholder = "Kamera-ID";
                        idInput.value = cam.camera_id || "";
                        const srcInput = document.createElement("input");
                        srcInput.type = "number";
                        srcInput.className = "input multi-cam-src";
                        srcInput.placeholder = "Quelle (0,1,...)";
                        srcInput.value = String(cam.src || 0);
                        srcInput.min = "0";
                        const previewBtn = document.createElement("button");
                        previewBtn.type = "button";
                        previewBtn.className = "btn btn--secondary btn--tiny multi-cam-preview-btn";
                        previewBtn.title = "Vorschau laden";
                        previewBtn.textContent = "Vorschau";
                        previewBtn.addEventListener("click", () => this._loadCameraPreview(entry));
                        fields.appendChild(idInput);
                        fields.appendChild(srcInput);
                        fields.appendChild(previewBtn);
                        const previewWrap = document.createElement("div");
                        previewWrap.className = "multi-cam-preview-wrap";
                        const previewImg = document.createElement("img");
                        previewImg.className = "multi-cam-preview-img";
                        previewImg.alt = "Kamera-Vorschau";
                        previewImg.style.display = "none";
                        const placeholder = document.createElement("span");
                        placeholder.className = "multi-cam-preview-placeholder";
                        placeholder.textContent = "Kein Bild";
                        previewWrap.appendChild(previewImg);
                        previewWrap.appendChild(placeholder);
                        entry.appendChild(fields);
                        entry.appendChild(previewWrap);
                        list.appendChild(entry);
                    });
                }
            }
        } catch (e) {
            // Non-fatal
        }
    }

    _closeMultiCamModal() {
        const modal = document.getElementById("multi-cam-modal");
        if (modal) modal.style.display = "none";
    }

    _addCameraEntry() {
        const list = document.getElementById("multi-cam-list");
        if (!list) return;
        const idx = list.children.length;
        const entry = document.createElement("div");
        entry.className = "multi-cam-entry";

        const fields = document.createElement("div");
        fields.className = "multi-cam-entry__fields";

        const idInput = document.createElement("input");
        idInput.type = "text";
        idInput.className = "input multi-cam-id";
        idInput.placeholder = "Kamera-ID";
        idInput.value = "cam_" + idx;

        const srcInput = document.createElement("input");
        srcInput.type = "number";
        srcInput.className = "input multi-cam-src";
        srcInput.placeholder = "Quelle";
        srcInput.value = String(idx);
        srcInput.min = "0";

        const previewBtn = document.createElement("button");
        previewBtn.type = "button";
        previewBtn.className = "btn btn--secondary btn--tiny multi-cam-preview-btn";
        previewBtn.title = "Vorschau laden";
        previewBtn.textContent = "Vorschau";
        previewBtn.addEventListener("click", () => this._loadCameraPreview(entry));

        const removeBtn = document.createElement("button");
        removeBtn.className = "btn btn--small btn--reject";
        removeBtn.textContent = "\u2717";
        removeBtn.addEventListener("click", () => entry.remove());

        fields.appendChild(idInput);
        fields.appendChild(srcInput);
        fields.appendChild(previewBtn);
        fields.appendChild(removeBtn);

        const previewWrap = document.createElement("div");
        previewWrap.className = "multi-cam-preview-wrap";
        const previewImg = document.createElement("img");
        previewImg.className = "multi-cam-preview-img";
        previewImg.alt = "Kamera-Vorschau";
        previewImg.style.display = "none";
        const placeholder = document.createElement("span");
        placeholder.className = "multi-cam-preview-placeholder";
        placeholder.textContent = "Kein Bild";
        previewWrap.appendChild(previewImg);
        previewWrap.appendChild(placeholder);

        entry.appendChild(fields);
        entry.appendChild(previewWrap);
        list.appendChild(entry);
    }

    async _loadCameraPreview(entry) {
        if (!entry) return;
        const srcInput = entry.querySelector(".multi-cam-src");
        const img = entry.querySelector(".multi-cam-preview-img");
        const placeholder = entry.querySelector(".multi-cam-preview-placeholder");
        const btn = entry.querySelector(".multi-cam-preview-btn");
        if (!srcInput || !img) return;

        const source = parseInt(srcInput.value, 10);
        if (isNaN(source)) return;

        if (btn) { btn.disabled = true; btn.textContent = "..."; }
        if (placeholder) placeholder.textContent = "Lade...";

        try {
            const url = `/api/camera/preview/${source}?t=${Date.now()}`;
            const resp = await fetch(url);
            if (!resp.ok) {
                if (placeholder) placeholder.textContent = "Nicht verfuegbar";
                img.style.display = "none";
                return;
            }
            const blob = await resp.blob();
            img.src = URL.createObjectURL(blob);
            img.style.display = "block";
            if (placeholder) placeholder.style.display = "none";
        } catch (e) {
            if (placeholder) placeholder.textContent = "Fehler";
            img.style.display = "none";
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = "Vorschau"; }
        }
    }

    async _startMultiPipeline() {
        const entries = document.querySelectorAll(".multi-cam-entry");
        const cameras = [];
        entries.forEach(entry => {
            const id = entry.querySelector(".multi-cam-id").value.trim();
            const src = parseInt(entry.querySelector(".multi-cam-src").value, 10);
            if (id) cameras.push({ camera_id: id, src: src });
        });

        if (cameras.length < 2) {
            alert("Mindestens 2 Kameras erforderlich.");
            return;
        }

        const btnStart = document.getElementById("btn-multi-start");
        if (btnStart) {
            btnStart.disabled = true;
            btnStart.textContent = "Starte...";
        }

        try {
            const resp = await fetch("/api/multi/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cameras }),
            });
            if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
            const data = await resp.json();
            if (data.ok) {
                this.multiCamRunning = true;
                this.activeCameraIds = data.cameras || [];
                this._refreshMultiCamStatus();
                this._showMultiVideoGrid();
                // Close the modal so user sees the video grid
                this._closeMultiCamModal();
            } else {
                alert("Fehler: " + (data.error || "Unbekannt"));
            }
        } catch (e) {
            console.error("Multi-cam start error:", e);
            alert("Verbindungsfehler beim Starten der Multi-Kamera Pipeline.");
        } finally {
            if (btnStart) {
                btnStart.disabled = false;
                btnStart.textContent = "Starten";
            }
        }
    }

    async _stopMultiPipeline() {
        try {
            const resp = await fetch("/api/multi/stop", { method: "POST" });
            if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
            this.multiCamRunning = false;
            this.activeCameraIds = [];
            this._refreshMultiCamStatus();
            this._hideMultiVideoGrid();
        } catch (e) {
            console.error("Multi-cam stop error:", e);
        }
    }

    async _refreshMultiCamStatus() {
        try {
            const resp = await fetch("/api/multi/status");
            if (!resp.ok) return;
            const data = await resp.json();
            const info = document.getElementById("multi-status-info");
            const btnStart = document.getElementById("btn-multi-start");
            const btnStop = document.getElementById("btn-multi-stop");

            if (data.running) {
                if (btnStart) btnStart.style.display = "none";
                if (btnStop) btnStop.style.display = "inline-block";
                if (info) {
                    info.style.display = "block";
                    // Build status using safe DOM methods
                    while (info.firstChild) info.removeChild(info.firstChild);
                    const title = document.createElement("strong");
                    title.textContent = "Aktive Kameras:";
                    info.appendChild(title);
                    data.cameras.forEach(cam => {
                        info.appendChild(document.createElement("br"));
                        const line = document.createTextNode(
                            cam.camera_id + ": " + cam.fps + " FPS | Board " +
                            (cam.board_calibrated ? "\u2705" : "\u274C") +
                            " | Lens " +
                            (cam.lens_calibrated ? "\u2705" : "\u274C")
                        );
                        info.appendChild(line);
                    });
                    // Show camera errors if any
                    const errors = data.camera_errors || {};
                    const errorIds = Object.keys(errors);
                    if (errorIds.length > 0) {
                        info.appendChild(document.createElement("br"));
                        const errTitle = document.createElement("strong");
                        errTitle.style.color = "#ff4757";
                        errTitle.textContent = "Kamera-Fehler:";
                        info.appendChild(errTitle);
                        errorIds.forEach(camId => {
                            info.appendChild(document.createElement("br"));
                            const errLine = document.createElement("span");
                            errLine.style.color = "#ff4757";
                            errLine.textContent = camId + ": " + errors[camId];
                            info.appendChild(errLine);
                        });
                    }
                    // Fetch and show readiness info
                    this._fetchReadiness(info);
                    this._refreshSetupGuide();
                }
                // Populate stereo dropdowns
                this._populateStereoDropdowns(data.cameras.map(c => c.camera_id));
            } else {
                if (btnStart) btnStart.style.display = "inline-block";
                if (btnStop) btnStop.style.display = "none";
                if (info) info.style.display = "none";
                const guide = document.getElementById("multi-setup-guide");
                if (guide) guide.style.display = "none";
            }
            this._updateCameraHealth();
        } catch (e) {
            console.error("Multi status error:", e);
        }
    }

    async _updateCameraHealth() {
        try {
            const resp = await fetch('/api/multi/camera-health');
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok) return;
            for (const [camId, health] of Object.entries(data.cameras)) {
                let badge = document.getElementById('cam-health-' + camId);
                if (!badge) {
                    const entries = document.querySelectorAll('.multi-cam-entry');
                    for (const entry of entries) {
                        const idInput = entry.querySelector('input[placeholder*="cam_"]') || entry.querySelector('input');
                        if (idInput && idInput.value === camId) {
                            badge = document.createElement('span');
                            badge.id = 'cam-health-' + camId;
                            badge.className = 'cam-health-badge';
                            entry.appendChild(badge);
                            break;
                        }
                    }
                }
                if (badge) {
                    badge.className = 'cam-health-badge cam-health-' + health.status;
                    badge.title = health.error || (health.fps + ' FPS');
                }
            }
        } catch (e) { /* ignore */ }
    }

    async _fetchReadiness(infoEl) {
        try {
            const resp = await fetch("/api/multi/readiness");
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok || !data.running) return;

            // Show per-camera issues
            const cameras = data.cameras || [];
            const hasIssues = cameras.some(c => c.issues.length > 0);
            if (hasIssues || (data.issues && data.issues.length > 0)) {
                infoEl.appendChild(document.createElement("br"));
                const setupTitle = document.createElement("strong");
                setupTitle.style.color = "#ffa502";
                setupTitle.textContent = "Setup-Status:";
                infoEl.appendChild(setupTitle);

                cameras.forEach(cam => {
                    if (cam.issues.length === 0) return;
                    cam.issues.forEach(issue => {
                        infoEl.appendChild(document.createElement("br"));
                        const issueLine = document.createElement("span");
                        issueLine.style.color = "#ffa502";
                        issueLine.style.fontSize = "0.85em";
                        issueLine.textContent = cam.camera_id + ": " + issue;
                        infoEl.appendChild(issueLine);
                    });
                });

                // Overall issues
                (data.issues || []).forEach(issue => {
                    infoEl.appendChild(document.createElement("br"));
                    const line = document.createElement("span");
                    line.style.color = "#ffa502";
                    line.style.fontSize = "0.85em";
                    line.textContent = issue;
                    infoEl.appendChild(line);
                });
            }

            if (data.triangulation_possible) {
                infoEl.appendChild(document.createElement("br"));
                const triLine = document.createElement("span");
                triLine.style.color = "#2ed573";
                triLine.textContent = "\u2705 Triangulation aktiv";
                infoEl.appendChild(triLine);
            }
        } catch (e) {
            // Non-fatal
        }
    }

    async _refreshSetupGuide() {
        const guideEl = document.getElementById("multi-setup-guide");
        const checklist = document.getElementById("setup-checklist");
        if (!guideEl || !checklist) return;

        try {
            const resp = await fetch("/api/multi/readiness");
            if (!resp.ok) return;
            const data = await resp.json();

            if (!data.ok || !data.running) {
                guideEl.style.display = "none";
                return;
            }

            guideEl.style.display = "block";
            while (checklist.firstChild) checklist.removeChild(checklist.firstChild);

            const cameras = data.cameras || [];
            const stereoPairs = data.stereo_pairs || [];

            // Per-camera steps
            cameras.forEach(cam => {
                this._addSetupStep(checklist, cam.lens_calibrated,
                    cam.camera_id + ": Lens-Kalibrierung (ChArUco)",
                    cam.lens_calibrated ? null : "Oeffne Kalibrieren > Lens Setup");
                this._addSetupStep(checklist, cam.board_calibrated,
                    cam.camera_id + ": Board-Kalibrierung",
                    cam.board_calibrated ? null : "Oeffne Kalibrieren > Board Manuell/ArUco");
                this._addSetupStep(checklist, cam.board_pose,
                    cam.camera_id + ": Board-Pose (3D)",
                    cam.board_pose ? null : "Benoetigt Lens-Kalibrierung zuerst");
            });

            // Stereo pair steps
            stereoPairs.forEach(pair => {
                this._addSetupStep(checklist, pair.calibrated,
                    "Stereo: " + pair.camera_a + " \u2194 " + pair.camera_b,
                    pair.calibrated ? null : "Oeffne Stereo-Kalibrierung unten");
            });

            // Overall status
            if (data.triangulation_possible) {
                this._addSetupStep(checklist, true, "Triangulation aktiv", null);
            } else if (data.all_ready) {
                this._addSetupStep(checklist, false,
                    "Stereo fehlt — Voting-Fallback wird verwendet", null);
            }

            // Fetch detailed calibration validation
            this._fetchCalibrationDetails(checklist);
        } catch (e) {
            // Non-fatal
        }
    }

    _addSetupStep(container, done, text, hint) {
        const step = document.createElement("div");
        step.className = "setup-step " + (done ? "setup-step--done" : "setup-step--pending");

        const icon = document.createElement("span");
        icon.className = "setup-step__icon";
        icon.textContent = done ? "\u2705" : "\u26A0\uFE0F";

        const label = document.createElement("span");
        label.className = "setup-step__text";
        label.textContent = text;

        step.appendChild(icon);
        step.appendChild(label);

        if (hint && !done) {
            const hintEl = document.createElement("span");
            hintEl.className = "setup-step__action";
            hintEl.style.color = "#aaa";
            hintEl.textContent = hint;
            step.appendChild(hintEl);
        }

        container.appendChild(step);
    }

    async _fetchCalibrationDetails(checklist) {
        try {
            const resp = await fetch("/api/multi-cam/calibration/status");
            if (!resp.ok) return;
            const data = await resp.json();

            for (const [camId, status] of Object.entries(data.cameras || {})) {
                // Show warnings for intrinsics issues
                if (status.intrinsics_warnings && status.intrinsics_warnings.length > 0) {
                    status.intrinsics_warnings.forEach(w => {
                        this._addSetupStep(checklist, false, camId + ": " + w, null);
                    });
                }
                // Show viewing angle quality
                if (status.viewing_angle_quality !== null && status.viewing_angle_quality !== undefined) {
                    const q = status.viewing_angle_quality;
                    const pct = Math.round(q * 100);
                    const good = q >= 0.5;
                    this._addSetupStep(checklist, good,
                        camId + ": Blickwinkel-Qualitaet " + pct + "%",
                        good ? null : "Kamera frontaler zum Board ausrichten");
                }
            }

            // Overall readiness
            if (data.ready_for_multi) {
                this._addSetupStep(checklist, true, "Multi-Cam bereit", null);
            }
        } catch (e) {
            // Non-fatal — API may not be available
        }
    }

    _updateMultiCamUI() {
        // Show/hide stereo calibration section in calibration modal
        const stereoSection = document.getElementById("cal-stereo-section");
        if (stereoSection) {
            stereoSection.style.display = this.multiCamRunning ? "block" : "none";
        }
        this._updateCalibrationCameraSelector();
    }

    _showMultiVideoGrid() {
        const grid = document.getElementById("multi-video-grid");
        const single = document.getElementById("single-video-wrapper");
        if (!grid) return;

        // Hide single, show grid
        if (single) single.style.display = "none";
        grid.style.display = "grid";
        while (grid.firstChild) grid.removeChild(grid.firstChild);

        this.activeCameraIds.forEach(camId => {
            const container = document.createElement("div");
            container.className = "video-container multi-video-cell";

            const img = document.createElement("img");
            img.src = "/video/feed/" + encodeURIComponent(camId);
            img.alt = camId;
            img.className = "video-feed";

            const label = document.createElement("div");
            label.className = "multi-video-label";
            label.textContent = camId;

            container.appendChild(img);
            container.appendChild(label);
            grid.appendChild(container);
        });
    }

    _hideMultiVideoGrid() {
        const grid = document.getElementById("multi-video-grid");
        const single = document.getElementById("single-video-wrapper");
        if (grid) {
            grid.style.display = "none";
            while (grid.firstChild) grid.removeChild(grid.firstChild);
        }
        if (single) single.style.display = "block";
    }

    _showStereoStep() {
        document.getElementById("multi-step-config").style.display = "none";
        document.getElementById("multi-step-stereo").style.display = "block";
        this._refreshCharucoBoardPresetFromServer();
        this._populateStereoDropdowns(this.activeCameraIds);
        this._updateStereoFeeds();
    }

    _populateStereoDropdowns(cameraIds) {
        const selA = document.getElementById("stereo-cam-a");
        const selB = document.getElementById("stereo-cam-b");
        if (!selA || !selB) return;

        while (selA.firstChild) selA.removeChild(selA.firstChild);
        while (selB.firstChild) selB.removeChild(selB.firstChild);

        cameraIds.forEach(id => {
            const optA = document.createElement("option");
            optA.value = id;
            optA.textContent = id;
            selA.appendChild(optA);

            const optB = document.createElement("option");
            optB.value = id;
            optB.textContent = id;
            selB.appendChild(optB);
        });
        if (cameraIds.length >= 2) {
            selB.selectedIndex = 1;
        }

        selA.onchange = () => this._updateStereoFeeds();
        selB.onchange = () => this._updateStereoFeeds();
    }

    _updateStereoFeeds() {
        const camA = document.getElementById("stereo-cam-a")?.value;
        const camB = document.getElementById("stereo-cam-b")?.value;
        const feedA = document.getElementById("stereo-feed-a");
        const feedB = document.getElementById("stereo-feed-b");
        const labelA = document.getElementById("stereo-label-a");
        const labelB = document.getElementById("stereo-label-b");

        if (camA && feedA) feedA.src = "/video/feed/" + encodeURIComponent(camA);
        if (camB && feedB) feedB.src = "/video/feed/" + encodeURIComponent(camB);
        if (camA && labelA) labelA.textContent = camA;
        if (camB && labelB) labelB.textContent = camB;
    }

    async _runStereoCalibration() {
        const camA = document.getElementById("stereo-cam-a")?.value;
        const camB = document.getElementById("stereo-cam-b")?.value;
        const preset = this._getSelectedCharucoPreset();
        if (!camA || !camB || camA === camB) {
            alert("Bitte zwei verschiedene Kameras auswaehlen.");
            return;
        }

        const resultEl = document.getElementById("stereo-result");
        const btn = document.getElementById("btn-stereo-calibrate");
        if (btn) btn.disabled = true;
        if (resultEl) {
            resultEl.style.display = "block";
            resultEl.textContent =
                "Kalibrierung laeuft (" + this._describeCharucoPreset(preset) + ", ca. 10s)...";
        }

        try {
            const resp = await fetch("/api/calibration/stereo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ camera_a: camA, camera_b: camB, preset }),
            });
            if (!resp.ok) { this._showError(`Fehler: ${resp.status}`); return; }
            const data = await resp.json();
            if (data.ok) {
                if (data.charuco_board?.preset) {
                    this._syncCharucoBoardSelectors(data.charuco_board.preset);
                }
                if (resultEl) {
                    resultEl.textContent = "\u2705 Stereo-Kalibrierung erfolgreich! Reprojektion: " +
                        data.reprojection_error.toFixed(3) + " px, Paare: " + data.pairs_used +
                        " | Board: " + this._describeCharucoPreset(data.charuco_board?.preset || preset);
                }
            } else {
                if (resultEl) {
                    resultEl.textContent = "\u274C Fehler: " + data.error;
                }
            }
        } catch (e) {
            if (resultEl) resultEl.textContent = "\u274C Verbindungsfehler";
        } finally {
            if (btn) btn.disabled = false;
            const pc = document.getElementById('stereo-progress-container');
            if (pc) pc.style.display = 'none';
        }
    }
    // --- Telemetry ---

    _bindTelemetry() {
        const btn = document.getElementById("btn-telemetry");
        const closeBtn = document.getElementById("btn-close-telemetry");
        const panel = document.getElementById("telemetry-panel");
        if (btn && panel) {
            btn.addEventListener("click", () => {
                this._telemetryVisible = !this._telemetryVisible;
                panel.style.display = this._telemetryVisible ? "block" : "none";
                if (this._telemetryVisible) {
                    this._fetchTelemetryHistory();
                    this._fetchTelemetryStatus();
                }
            });
        }
        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                this._telemetryVisible = false;
                if (panel) panel.style.display = "none";
            });
        }
        const exportBtn = document.getElementById("btn-export-telemetry");
        if (exportBtn) {
            exportBtn.addEventListener("click", () => {
                const a = document.createElement("a");
                a.href = "/api/telemetry/export";
                a.download = "telemetry.json";
                a.click();
            });
        }
        const exportCsvBtn = document.getElementById("btn-export-telemetry-csv");
        if (exportCsvBtn) {
            exportCsvBtn.addEventListener("click", () => {
                const a = document.createElement("a");
                a.href = "/api/telemetry/export?format=csv";
                a.download = "telemetry.csv";
                a.click();
            });
        }
        // Listen for telemetry alerts via WebSocket
        this.ws.on("telemetry_alert", (data) => this._onTelemetryAlert(data));
        // Poll telemetry history when panel is open
        setInterval(() => {
            if (this._telemetryVisible) this._fetchTelemetryHistory();
        }, 2000);
    }

    _bindPipelineHealth() {
        this._pipelineHealthVisible = false;
        const btn = document.getElementById("btn-pipeline-health");
        const closeBtn = document.getElementById("btn-close-pipeline-health");
        const panel = document.getElementById("pipeline-health-panel");
        if (btn && panel) {
            btn.addEventListener("click", () => {
                this._pipelineHealthVisible = !this._pipelineHealthVisible;
                panel.style.display = this._pipelineHealthVisible ? "block" : "none";
            });
        }
        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                this._pipelineHealthVisible = false;
                if (panel) panel.style.display = "none";
            });
        }
    }

    _updatePipelineHealth(ph) {
        if (!ph) return;
        // State
        const stateEl = document.getElementById("ph-state");
        if (stateEl) {
            const labels = { active: "Aktiv", idle: "Idle", degraded: "Degraded" };
            stateEl.textContent = labels[ph.state] || ph.state;
            stateEl.className = "ph-card__value ph-state--" + ph.state;
        }
        // Camera
        const camEl = document.getElementById("ph-camera");
        if (camEl) {
            camEl.textContent = ph.state === "idle" ? "Aus" : "OK";
        }
        // Detection rate
        const rateEl = document.getElementById("ph-detection-rate");
        if (rateEl) {
            rateEl.textContent = ph.detection_rate + " hits/min";
        }
        // Calibration quality
        const calEl = document.getElementById("ph-calibration");
        const calBar = document.getElementById("ph-cal-bar");
        if (calEl) {
            if (ph.board_calibrated) {
                calEl.textContent = ph.calibration_quality + "%";
                calEl.style.color = "";
            } else {
                calEl.textContent = "Keine";
                calEl.style.color = "var(--warning)";
            }
        }
        if (calBar) {
            const q = ph.calibration_quality || 0;
            calBar.style.width = q + "%";
            calBar.className = "quality-fill " + (q >= 70 ? "quality--good" : q >= 40 ? "quality--medium" : "quality--low");
        }
        // Last hits (safe DOM construction)
        const hitsEl = document.getElementById("ph-last-hits");
        if (hitsEl) {
            const hits = ph.last_hits || [];
            hitsEl.textContent = "";
            if (hits.length === 0) {
                hitsEl.textContent = "Keine Treffer";
            } else {
                hits.forEach(function(h) {
                    const badge = document.createElement("span");
                    badge.className = "ph-hit-badge";
                    badge.textContent = h.ring + " " + h.score;
                    hitsEl.appendChild(badge);
                });
            }
        }
    }

    async _fetchTelemetryHistory() {
        try {
            const response = await fetch("/api/telemetry/history?last_n=60");
            if (!response.ok) return;
            const data = await response.json();
            if (!data.ok) return;
            this._telemetryData = data.history || [];
            this._drawTelemetryChart();
            this._updateTelemetrySummary(data.summary);
            this._onTelemetryAlert(data.alerts);
        } catch (e) {
            // Silent fail
        }
    }

    _drawTelemetryChart() {
        const canvas = document.getElementById("telemetry-chart");
        if (!canvas || !this._telemetryData.length) return;
        const ctx = canvas.getContext("2d");
        const w = canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
        const h = canvas.height = 120 * (window.devicePixelRatio || 1);
        ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
        const dw = canvas.offsetWidth;
        const dh = 120;

        ctx.clearRect(0, 0, dw, dh);

        const data = this._telemetryData;
        const n = data.length;
        if (n < 2) return;

        const maxFps = Math.max(35, ...data.map(d => d.fps));
        const xStep = dw / (n - 1);

        // FPS line (green)
        ctx.beginPath();
        ctx.strokeStyle = "#2ed573";
        ctx.lineWidth = 1.5;
        data.forEach((d, i) => {
            const x = i * xStep;
            const y = dh - (d.fps / maxFps) * (dh - 10) - 5;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Queue pressure line (orange)
        ctx.beginPath();
        ctx.strokeStyle = "#ffa502";
        ctx.lineWidth = 1.5;
        data.forEach((d, i) => {
            const x = i * xStep;
            const y = dh - d.queue * (dh - 10) - 5;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // FPS threshold line (red dashed)
        const threshY = dh - (15 / maxFps) * (dh - 10) - 5;
        ctx.beginPath();
        ctx.strokeStyle = "#e94560";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.moveTo(0, threshY);
        ctx.lineTo(dw, threshY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Legend
        ctx.font = "10px sans-serif";
        ctx.fillStyle = "#2ed573";
        ctx.fillText("FPS", 5, 12);
        ctx.fillStyle = "#ffa502";
        ctx.fillText("Queue", 35, 12);
        ctx.fillStyle = "#e94560";
        ctx.fillText("Limit", 75, 12);
    }

    _updateTelemetrySummary(summary) {
        const el = document.getElementById("telemetry-summary");
        if (!el || !summary || !summary.samples) return;
        while (el.firstChild) el.removeChild(el.firstChild);
        const items = [
            "FPS: " + summary.fps_avg + " (min " + summary.fps_min + ")",
            "Queue max: " + Math.round(summary.queue_max * 100) + "%",
            "Drops: " + (summary.total_drops || 0),
        ];
        items.forEach(text => {
            const span = document.createElement("span");
            span.textContent = text;
            el.appendChild(span);
        });
    }

    _onTelemetryAlert(data) {
        if (!data) return;
        const banner = document.getElementById("telemetry-alert-banner");
        const text = document.getElementById("telemetry-alert-text");
        if (!banner || !text) return;

        const messages = [];
        if (data.fps_low) messages.push("FPS unter " + data.fps_threshold + " — Performance-Problem!");
        if (data.queue_high) messages.push("Queue-Druck ueber " + Math.round(data.queue_threshold * 100) + "%");

        if (messages.length > 0) {
            text.textContent = messages.join(" | ");
            banner.style.display = "block";
        } else {
            banner.style.display = "none";
        }
    }

    // --- CV Tuning ---

    _bindCvTuning() {
        const btn = document.getElementById("btn-cv-tuning");
        const closeBtn = document.getElementById("btn-close-cv-tuning");
        const panel = document.getElementById("cv-tuning-panel");
        if (!btn || !panel) return;

        btn.addEventListener("click", () => {
            this._cvTuningVisible = !this._cvTuningVisible;
            panel.style.display = this._cvTuningVisible ? "block" : "none";
            if (this._cvTuningVisible) this._loadCvParams();
        });
        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                this._cvTuningVisible = false;
                panel.style.display = "none";
            });
        }

        // Slider bindings
        const sliders = [
            { id: "cv-diff-threshold", param: "diff_threshold" },
            { id: "cv-settle-frames", param: "settle_frames" },
            { id: "cv-min-diff-area", param: "min_diff_area" },
            { id: "cv-max-diff-area", param: "max_diff_area" },
            { id: "cv-min-elongation", param: "min_elongation" },
            { id: "cv-motion-threshold", param: "motion_threshold" },
        ];

        let debounceTimer = null;
        for (const { id, param } of sliders) {
            const slider = document.getElementById(id);
            const valSpan = document.getElementById(id + "-val");
            if (!slider) continue;
            slider.addEventListener("input", () => {
                if (valSpan) valSpan.textContent = slider.value;
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this._sendCvParam(param, Number(slider.value));
                }, 300);
            });
        }

        // Diagnostics toggle
        const diagToggle = document.getElementById("cv-diagnostics-toggle");
        if (diagToggle) {
            diagToggle.addEventListener("change", () => {
                const path = diagToggle.checked ? "./diagnostics" : null;
                fetch("/api/diagnostics/toggle", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path }),
                });
            });
        }
    }

    async _loadCvParams() {
        try {
            const resp = await fetch("/api/cv-params");
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok) return;
            const mapping = {
                diff_threshold: "cv-diff-threshold",
                settle_frames: "cv-settle-frames",
                min_diff_area: "cv-min-diff-area",
                max_diff_area: "cv-max-diff-area",
                min_elongation: "cv-min-elongation",
                motion_threshold: "cv-motion-threshold",
            };
            for (const [param, id] of Object.entries(mapping)) {
                const slider = document.getElementById(id);
                const valSpan = document.getElementById(id + "-val");
                if (slider && data[param] !== undefined) {
                    slider.value = data[param];
                    if (valSpan) valSpan.textContent = data[param];
                }
            }
            const diagToggle = document.getElementById("cv-diagnostics-toggle");
            if (diagToggle) diagToggle.checked = !!data.diagnostics_enabled;
        } catch (e) { /* silent */ }
    }

    async _sendCvParam(param, value) {
        try {
            const resp = await fetch("/api/cv-params", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [param]: value }),
            });
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.ok && data.error) {
                this._showError("CV Param: " + data.error);
            }
        } catch (e) { /* silent */ }
    }

    // --- Homography Age Warning (P62) ---

    _updateHomographyWarning(age) {
        var banner = document.getElementById("homography-warning-banner");
        if (!banner) return;
        if (age > 30) {
            banner.style.display = "block";
        } else {
            banner.style.display = "none";
        }
    }

    // --- Telemetry Status Widget (P62) ---

    _bindTelemetryStatus() {
        var rotateBtn = document.getElementById("btn-telemetry-rotate");
        if (rotateBtn) {
            rotateBtn.addEventListener("click", () => this._rotateTelemetry());
        }
    }

    async _fetchTelemetryStatus() {
        try {
            var resp = await fetch("/api/telemetry/status");
            if (!resp.ok) return;
            var data = await resp.json();
            var sizeEl = document.getElementById("telem-file-size");
            var retainEl = document.getElementById("telem-retain-days");
            var statusEl = document.getElementById("telem-active-status");
            if (sizeEl) {
                if (data.active && data.size_bytes != null) {
                    var kb = (data.size_bytes / 1024).toFixed(1);
                    sizeEl.textContent = "Groesse: " + kb + " KB";
                } else {
                    sizeEl.textContent = "Groesse: --";
                }
            }
            if (retainEl) {
                retainEl.textContent = "Aufbewahrung: " + (data.retain_days || "--") + " Tage";
            }
            if (statusEl) {
                statusEl.textContent = "Status: " + (data.active ? "Aktiv" : "Inaktiv");
            }
        } catch (e) { /* silent */ }
    }

    async _rotateTelemetry() {
        try {
            var resp = await fetch("/api/telemetry/rotate", { method: "POST" });
            if (!resp.ok) { this._showError("Rotation fehlgeschlagen: " + resp.status); return; }
            var data = await resp.json();
            if (data.ok) {
                this._showError("Telemetrie rotiert (" + (data.old_files_deleted || 0) + " alte Dateien entfernt)");
                this._fetchTelemetryStatus();
            } else {
                this._showError(data.error || "Rotation fehlgeschlagen");
            }
        } catch (e) {
            this._showError("Rotation-Fehler: " + e.message);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    window.dartApp = new DartApp();

    // Theme toggle (self-contained IIFE) — cycles: dark -> light -> high-contrast
    (function initThemeToggle() {
        const root = document.documentElement;
        const THEMES = ["dark", "light", "high-contrast"];
        const THEME_CLASSES = ["dark-theme", "light-theme", "high-contrast"];
        const ICONS = {dark: "\u{2600}\u{FE0F}", light: "\u{1F319}", "high-contrast": "\u{1F441}\u{FE0F}"};
        const LABELS = {dark: "Zum hellen Theme wechseln", light: "Zum Hochkontrast-Theme wechseln", "high-contrast": "Zum dunklen Theme wechseln"};

        function clearThemeClasses() {
            THEME_CLASSES.forEach(function(c) { root.classList.remove(c); });
        }

        function getCurrentTheme() {
            if (root.classList.contains("high-contrast")) return "high-contrast";
            if (root.classList.contains("light-theme")) return "light";
            if (root.classList.contains("dark-theme")) return "dark";
            // No explicit class — check system preference
            return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
        }

        var saved = localStorage.getItem("theme");
        if (saved && THEMES.indexOf(saved) !== -1) {
            clearThemeClasses();
            if (saved === "dark") root.classList.add("dark-theme");
            else if (saved === "light") root.classList.add("light-theme");
            else if (saved === "high-contrast") root.classList.add("high-contrast");
        }

        var btn = document.createElement("button");
        btn.className = "theme-toggle";
        btn.setAttribute("aria-label", "Toggle theme");
        btn.title = "Toggle theme";

        function updateIcon() {
            var current = getCurrentTheme();
            btn.textContent = ICONS[current] || ICONS.dark;
            btn.setAttribute("aria-label", LABELS[current] || "Toggle theme");
            btn.title = LABELS[current] || "Toggle theme";
        }

        btn.addEventListener("click", function() {
            var current = getCurrentTheme();
            var idx = THEMES.indexOf(current);
            var next = THEMES[(idx + 1) % THEMES.length];
            clearThemeClasses();
            if (next === "dark") root.classList.add("dark-theme");
            else if (next === "light") root.classList.add("light-theme");
            else if (next === "high-contrast") root.classList.add("high-contrast");
            localStorage.setItem("theme", next);
            updateIcon();
        });

        updateIcon();

        var container = document.querySelector(".header__stats");
        if (container) {
            container.appendChild(btn);
        }
    })();
});
