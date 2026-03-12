/**
 * DartboardRenderer: Programmatic SVG dartboard with exact hit markers.
 * Supports pending (candidate) and confirmed hit states.
 */
class DartboardRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.svgNS = "http://www.w3.org/2000/svg";
        this.size = 400;
        this.cx = this.size / 2;
        this.cy = this.size / 2;
        this.hits = new Map(); // candidate_id -> SVG group element

        // Standard dartboard sector order (clockwise from top)
        this.sectors = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5];

        // Ring radii (proportional to board size)
        this.radii = {
            innerBull: this.size * 0.025,
            outerBull: this.size * 0.0475,
            innerSingle: this.size * 0.265,
            triple: this.size * 0.29,
            outerSingle: this.size * 0.47,
            double: this.size * 0.5,
        };

        // Legacy ROI fallback mapping (kept for backward compatibility)
        this.roiScale = this.radii.double / 141.7; // Default estimate
        this.roiSize = 400; // ROI image dimensions

        // Colors
        this.colors = {
            black: "#1a1a1a",
            white: "#f5f0e1",
            red: "#e94560",
            green: "#2ed573",
            bullRed: "#e94560",
            bullGreen: "#2ed573",
            wire: "#888",
            bg: "#16213e",
            number: "#eee",
        };

        this._render();
        this._loadCalibration();
    }

    async _loadCalibration() {
        try {
            const resp = await fetch("/api/board/geometry");
            const data = await resp.json();
            if (data.ok && data.radii_px && data.radii_px.length === 6) {
                const roiDoubleOuter = data.radii_px[5]; // double_outer in ROI pixels
                if (roiDoubleOuter > 0) {
                    this.roiScale = this.radii.double / roiDoubleOuter;
                }
            }
        } catch (e) {
            // Use default scale
        }
    }

    _render() {
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }

        const svg = document.createElementNS(this.svgNS, "svg");
        const pad = 20;
        svg.setAttribute("viewBox", `${-pad} ${-pad} ${this.size + 2 * pad} ${this.size + 2 * pad}`);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        this.svg = svg;

        // Background circle
        this._addCircle(this.cx, this.cy, this.radii.double + 5, this.colors.bg);

        // Draw sectors
        const sectorAngle = 360 / 20;
        const startOffset = -90 - sectorAngle / 2;

        for (let i = 0; i < 20; i++) {
            const angle1 = startOffset + i * sectorAngle;
            const angle2 = startOffset + (i + 1) * sectorAngle;
            const isEven = i % 2 === 0;

            this._addSector(angle1, angle2, this.radii.outerSingle, this.radii.double,
                isEven ? this.colors.red : this.colors.green);
            this._addSector(angle1, angle2, this.radii.triple, this.radii.outerSingle,
                isEven ? this.colors.black : this.colors.white);
            this._addSector(angle1, angle2, this.radii.innerSingle, this.radii.triple,
                isEven ? this.colors.red : this.colors.green);
            this._addSector(angle1, angle2, this.radii.outerBull, this.radii.innerSingle,
                isEven ? this.colors.black : this.colors.white);
        }

        // Bull rings
        this._addCircle(this.cx, this.cy, this.radii.outerBull, this.colors.bullGreen);
        this._addCircle(this.cx, this.cy, this.radii.innerBull, this.colors.bullRed);

        // Wire rings
        const wireRadii = [this.radii.innerBull, this.radii.outerBull,
                           this.radii.innerSingle, this.radii.triple,
                           this.radii.outerSingle, this.radii.double];
        wireRadii.forEach(r => this._addCircleStroke(this.cx, this.cy, r, this.colors.wire, 0.5));

        // Wire lines
        for (let i = 0; i < 20; i++) {
            const angle = (startOffset + i * sectorAngle) * Math.PI / 180;
            const x1 = this.cx + this.radii.outerBull * Math.cos(angle);
            const y1 = this.cy + this.radii.outerBull * Math.sin(angle);
            const x2 = this.cx + this.radii.double * Math.cos(angle);
            const y2 = this.cy + this.radii.double * Math.sin(angle);
            this._addLine(x1, y1, x2, y2, this.colors.wire, 0.5);
        }

        // Sector numbers
        for (let i = 0; i < 20; i++) {
            const angle = (startOffset + (i + 0.5) * sectorAngle) * Math.PI / 180;
            const r = this.radii.double + 14;
            const x = this.cx + r * Math.cos(angle);
            const y = this.cy + r * Math.sin(angle);
            this._addText(x, y, this.sectors[i].toString(), this.colors.number, 11);
        }

        // Hit markers group
        this.hitsGroup = document.createElementNS(this.svgNS, "g");
        this.hitsGroup.setAttribute("class", "hits-group");
        svg.appendChild(this.hitsGroup);

        this.container.appendChild(svg);
    }

    // --- Hit Marker Methods ---

    /**
     * Add a hit using normalized board coordinates (preferred).
     * boardXNorm / boardYNorm are relative to double-outer radius.
     */
    addHitNormalized(boardXNorm, boardYNorm, score, candidateId, pending) {
        const svgX = this.cx + boardXNorm * this.radii.double;
        const svgY = this.cy + boardYNorm * this.radii.double;
        this._createHitMarker(svgX, svgY, score, candidateId, pending);
    }

    /**
     * Add a hit using exact ROI coordinates.
     */
    addHitExact(roiX, roiY, score, candidateId, pending) {
        const roiCx = this.roiSize / 2;
        const roiCy = this.roiSize / 2;
        const svgX = this.cx + (roiX - roiCx) * this.roiScale;
        const svgY = this.cy + (roiY - roiCy) * this.roiScale;
        this._createHitMarker(svgX, svgY, score, candidateId, pending);
    }

    /**
     * Add a hit using sector/ring (fallback for non-exact data).
     */
    addHit(sector, ring, score, candidateId, pending) {
        const pos = this._getHitPosition(sector, ring);
        if (!pos) return;
        this._createHitMarker(pos.x, pos.y, score, candidateId, pending);
    }

    _createHitMarker(x, y, score, candidateId, pending) {
        const g = document.createElementNS(this.svgNS, "g");
        if (candidateId) g.setAttribute("data-candidate-id", candidateId);

        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", x);
        circle.setAttribute("cy", y);
        circle.setAttribute("r", pending ? 7 : 6);
        circle.setAttribute("fill", pending ? "rgba(255,165,0,0.8)" : "#ff0");
        circle.setAttribute("stroke", pending ? "#fff" : "#000");
        circle.setAttribute("stroke-width", pending ? 2 : 1.5);
        circle.setAttribute("opacity", pending ? 0.85 : 0.9);
        if (pending) circle.setAttribute("class", "hit-pending-pulse");
        g.appendChild(circle);

        const label = document.createElementNS(this.svgNS, "text");
        label.setAttribute("x", x);
        label.setAttribute("y", y + 1);
        label.setAttribute("fill", pending ? "#fff" : "#000");
        label.setAttribute("font-size", 7);
        label.setAttribute("font-weight", "bold");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("dominant-baseline", "central");
        label.textContent = score.toString();
        g.appendChild(label);

        this.hitsGroup.appendChild(g);
        if (candidateId) this.hits.set(candidateId, g);
    }

    confirmHit(candidateId) {
        const g = this.hits.get(candidateId);
        if (!g) return;
        const circle = g.querySelector("circle");
        if (circle) {
            circle.setAttribute("fill", "#ff0");
            circle.setAttribute("stroke", "#000");
            circle.setAttribute("stroke-width", 1.5);
            circle.setAttribute("r", 6);
            circle.setAttribute("opacity", 0.9);
            circle.removeAttribute("class");
        }
        const label = g.querySelector("text");
        if (label) label.setAttribute("fill", "#000");
    }

    removeHit(candidateId) {
        const g = this.hits.get(candidateId);
        if (g && g.parentNode) g.parentNode.removeChild(g);
        this.hits.delete(candidateId);
    }

    clearHits() {
        while (this.hitsGroup.firstChild) {
            this.hitsGroup.removeChild(this.hitsGroup.firstChild);
        }
        this.hits.clear();
    }

    // --- SVG Drawing Helpers ---

    _getHitPosition(sector, ring) {
        if (sector === 25 || ring === "inner_bull") return { x: this.cx, y: this.cy };
        if (ring === "outer_bull") return { x: this.cx + 8, y: this.cy + 3 };

        const idx = this.sectors.indexOf(sector);
        if (idx === -1) return null;

        const sectorAngle = 360 / 20;
        const startOffset = -90 - sectorAngle / 2;
        const angle = (startOffset + (idx + 0.5) * sectorAngle) * Math.PI / 180;
        let radius;

        switch (ring) {
            case "triple":
                radius = (this.radii.innerSingle + this.radii.triple) / 2;
                break;
            case "double":
                radius = (this.radii.outerSingle + this.radii.double) / 2;
                break;
            default:
                radius = (this.radii.triple + this.radii.outerSingle) / 2;
        }

        return {
            x: this.cx + radius * Math.cos(angle),
            y: this.cy + radius * Math.sin(angle),
        };
    }

    _addSector(startAngle, endAngle, innerR, outerR, color) {
        const a1 = startAngle * Math.PI / 180;
        const a2 = endAngle * Math.PI / 180;
        const x1i = this.cx + innerR * Math.cos(a1);
        const y1i = this.cy + innerR * Math.sin(a1);
        const x2i = this.cx + innerR * Math.cos(a2);
        const y2i = this.cy + innerR * Math.sin(a2);
        const x1o = this.cx + outerR * Math.cos(a1);
        const y1o = this.cy + outerR * Math.sin(a1);
        const x2o = this.cx + outerR * Math.cos(a2);
        const y2o = this.cy + outerR * Math.sin(a2);
        const largeArc = (endAngle - startAngle) > 180 ? 1 : 0;
        const d = [
            `M ${x1i} ${y1i}`, `L ${x1o} ${y1o}`,
            `A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2o} ${y2o}`,
            `L ${x2i} ${y2i}`,
            `A ${innerR} ${innerR} 0 ${largeArc} 0 ${x1i} ${y1i}`, "Z"
        ].join(" ");
        const path = document.createElementNS(this.svgNS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", color);
        this.svg.appendChild(path);
    }

    _addCircle(cx, cy, r, fill) {
        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", cx); circle.setAttribute("cy", cy);
        circle.setAttribute("r", r); circle.setAttribute("fill", fill);
        this.svg.appendChild(circle);
    }

    _addCircleStroke(cx, cy, r, stroke, width) {
        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", cx); circle.setAttribute("cy", cy);
        circle.setAttribute("r", r); circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", stroke); circle.setAttribute("stroke-width", width);
        this.svg.appendChild(circle);
    }

    _addLine(x1, y1, x2, y2, stroke, width) {
        const line = document.createElementNS(this.svgNS, "line");
        line.setAttribute("x1", x1); line.setAttribute("y1", y1);
        line.setAttribute("x2", x2); line.setAttribute("y2", y2);
        line.setAttribute("stroke", stroke); line.setAttribute("stroke-width", width);
        this.svg.appendChild(line);
    }

    _addText(x, y, text, fill, size) {
        const el = document.createElementNS(this.svgNS, "text");
        el.setAttribute("x", x); el.setAttribute("y", y);
        el.setAttribute("fill", fill); el.setAttribute("font-size", size);
        el.setAttribute("font-weight", "bold"); el.setAttribute("text-anchor", "middle");
        el.setAttribute("dominant-baseline", "central");
        el.textContent = text;
        this.svg.appendChild(el);
    }
}
