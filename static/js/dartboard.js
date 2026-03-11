/**
 * DartboardRenderer: Programmatic SVG dartboard with hit markers.
 */
class DartboardRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.svgNS = "http://www.w3.org/2000/svg";
        this.size = 400;
        this.cx = this.size / 2;
        this.cy = this.size / 2;
        this.hits = [];

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
    }

    _render() {
        // Clear container
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
        const startOffset = -90 - sectorAngle / 2; // 20 is at the top

        for (let i = 0; i < 20; i++) {
            const angle1 = startOffset + i * sectorAngle;
            const angle2 = startOffset + (i + 1) * sectorAngle;
            const isEven = i % 2 === 0;

            // Double ring
            this._addSector(angle1, angle2, this.radii.outerSingle, this.radii.double,
                isEven ? this.colors.red : this.colors.green);

            // Outer single
            this._addSector(angle1, angle2, this.radii.triple, this.radii.outerSingle,
                isEven ? this.colors.black : this.colors.white);

            // Triple ring
            this._addSector(angle1, angle2, this.radii.innerSingle, this.radii.triple,
                isEven ? this.colors.red : this.colors.green);

            // Inner single
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

        // Wire lines (sector dividers)
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
            `M ${x1i} ${y1i}`,
            `L ${x1o} ${y1o}`,
            `A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2o} ${y2o}`,
            `L ${x2i} ${y2i}`,
            `A ${innerR} ${innerR} 0 ${largeArc} 0 ${x1i} ${y1i}`,
            "Z"
        ].join(" ");

        const path = document.createElementNS(this.svgNS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", color);
        this.svg.appendChild(path);
    }

    _addCircle(cx, cy, r, fill) {
        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", r);
        circle.setAttribute("fill", fill);
        this.svg.appendChild(circle);
    }

    _addCircleStroke(cx, cy, r, stroke, width) {
        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", r);
        circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", stroke);
        circle.setAttribute("stroke-width", width);
        this.svg.appendChild(circle);
    }

    _addLine(x1, y1, x2, y2, stroke, width) {
        const line = document.createElementNS(this.svgNS, "line");
        line.setAttribute("x1", x1);
        line.setAttribute("y1", y1);
        line.setAttribute("x2", x2);
        line.setAttribute("y2", y2);
        line.setAttribute("stroke", stroke);
        line.setAttribute("stroke-width", width);
        this.svg.appendChild(line);
    }

    _addText(x, y, text, fill, size) {
        const el = document.createElementNS(this.svgNS, "text");
        el.setAttribute("x", x);
        el.setAttribute("y", y);
        el.setAttribute("fill", fill);
        el.setAttribute("font-size", size);
        el.setAttribute("font-weight", "bold");
        el.setAttribute("text-anchor", "middle");
        el.setAttribute("dominant-baseline", "central");
        el.textContent = text;
        this.svg.appendChild(el);
    }

    /**
     * Add a hit marker to the dartboard.
     * @param {number} sector - The sector number (1-20, 25 for bull)
     * @param {string} ring - "single", "double", "triple", "inner_bull", "outer_bull"
     * @param {number} score - The score value
     */
    addHit(sector, ring, score) {
        const pos = this._getHitPosition(sector, ring);
        if (!pos) return;

        // Create hit marker
        const g = document.createElementNS(this.svgNS, "g");

        const circle = document.createElementNS(this.svgNS, "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", 6);
        circle.setAttribute("fill", "#ff0");
        circle.setAttribute("stroke", "#000");
        circle.setAttribute("stroke-width", 1.5);
        circle.setAttribute("opacity", 0.9);
        g.appendChild(circle);

        const label = document.createElementNS(this.svgNS, "text");
        label.setAttribute("x", pos.x);
        label.setAttribute("y", pos.y + 1);
        label.setAttribute("fill", "#000");
        label.setAttribute("font-size", 7);
        label.setAttribute("font-weight", "bold");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("dominant-baseline", "central");
        label.textContent = score.toString();
        g.appendChild(label);

        this.hitsGroup.appendChild(g);
        this.hits.push(g);
    }

    _getHitPosition(sector, ring) {
        let angle, radius;

        if (sector === 25 || ring === "inner_bull") {
            return { x: this.cx, y: this.cy };
        }
        if (ring === "outer_bull") {
            return { x: this.cx + 8, y: this.cy + 3 };
        }

        const idx = this.sectors.indexOf(sector);
        if (idx === -1) return null;

        const sectorAngle = 360 / 20;
        const startOffset = -90 - sectorAngle / 2;
        angle = (startOffset + (idx + 0.5) * sectorAngle) * Math.PI / 180;

        switch (ring) {
            case "triple":
                radius = (this.radii.innerSingle + this.radii.triple) / 2;
                break;
            case "double":
                radius = (this.radii.outerSingle + this.radii.double) / 2;
                break;
            default: // single
                radius = (this.radii.triple + this.radii.outerSingle) / 2;
        }

        return {
            x: this.cx + radius * Math.cos(angle),
            y: this.cy + radius * Math.sin(angle),
        };
    }

    clearHits() {
        while (this.hitsGroup.firstChild) {
            this.hitsGroup.removeChild(this.hitsGroup.firstChild);
        }
        this.hits = [];
    }
}
