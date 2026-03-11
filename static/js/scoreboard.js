/**
 * Scoreboard: Renders player scores using safe DOM methods (no innerHTML).
 */
class Scoreboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.state = null;
    }

    /**
     * Update the scoreboard with new game state.
     * @param {Object} state - Game state from server
     */
    update(state) {
        this.state = state;
        this._render();
    }

    _render() {
        // Clear container safely
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }

        if (!this.state || !this.state.players || this.state.players.length === 0) {
            const placeholder = document.createElement("div");
            placeholder.className = "scoreboard-placeholder";
            placeholder.textContent = "Starte ein neues Spiel";
            placeholder.style.cssText = "text-align:center;color:#aab;padding:40px 0;";
            this.container.appendChild(placeholder);
            return;
        }

        this.state.players.forEach((player, index) => {
            const row = this._createPlayerRow(player, index);
            this.container.appendChild(row);
        });
    }

    _createPlayerRow(player, index) {
        const isActive = index === this.state.current_player_index;
        const row = document.createElement("div");
        row.className = "player-row" + (isActive ? " player-row--active" : "");

        // Left side: name + turn info
        const leftDiv = document.createElement("div");
        leftDiv.className = "player-info";

        const nameEl = document.createElement("div");
        nameEl.className = "player-name";
        nameEl.textContent = player.name;
        leftDiv.appendChild(nameEl);

        // Show current turn throws
        if (isActive && player.current_turn && player.current_turn.length > 0) {
            const turnEl = document.createElement("div");
            turnEl.className = "player-turn";
            turnEl.textContent = "Wurf: " + player.current_turn.join(", ");
            leftDiv.appendChild(turnEl);
        }

        // Cricket marks (if cricket mode)
        if (this.state.mode === "cricket" && player.cricket_marks) {
            const marksEl = this._createCricketMarks(player.cricket_marks);
            leftDiv.appendChild(marksEl);
        }

        row.appendChild(leftDiv);

        // Right side: score
        const scoreEl = document.createElement("div");
        scoreEl.className = "player-score";
        scoreEl.textContent = player.score.toString();
        row.appendChild(scoreEl);

        return row;
    }

    _createCricketMarks(marks) {
        const container = document.createElement("div");
        container.className = "cricket-marks";
        container.style.cssText = "display:flex;gap:6px;margin-top:4px;flex-wrap:wrap;";

        const cricketNumbers = [20, 19, 18, 17, 16, 15, 25];

        cricketNumbers.forEach(num => {
            const markCount = marks[num] || 0;
            const markEl = document.createElement("span");
            markEl.className = "cricket-mark" + (markCount >= 3 ? " cricket-mark--closed" : "");

            const numLabel = num === 25 ? "B" : num.toString();
            const markSymbol = markCount >= 3 ? "X" : markCount.toString();
            markEl.textContent = numLabel + ":" + markSymbol;
            markEl.style.cssText = "font-size:0.7rem;padding:2px 4px;border-radius:3px;background:rgba(255,255,255,0.1);";

            container.appendChild(markEl);
        });

        return container;
    }
}
