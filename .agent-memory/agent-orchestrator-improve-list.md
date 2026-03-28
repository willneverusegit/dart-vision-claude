# Dart-Vision Improvement List (Agent Orchestrator Analyse)

*Erstellt: 2026-03-28*
*Quelle: 5-Agent Brainstorming (CV-Pipeline, Multi-Cam, UI/UX, Game Logic, Hardware)*

## Gesamtbewertung

| Bereich | Score | Status |
|---------|-------|--------|
| Single-Cam Detection | 7/10 | Solide Basis, fragil bei spezifischer Hardware |
| Multi-Cam Stereo | 5/10 | Architektur gut, WLAN + Vibrationen = Risiko |
| UI/UX | 4/10 | Funktional, null Begeisterung |
| Spiellogik | 8/10 | X01 + Cricket fast komplett |
| Hardware-Tauglichkeit | 5/10 | Grundlagen da, nicht optimiert |

---

## Woche 1: Single-Cam robust machen

- [x] **1. `min_elongation` 1.2 -> 2.0** (1 Zeile, -80% False Positives)
- [x] **2. CLAHE conditional** (nur bei niedriger Helligkeit) -> -15% CPU
- [x] **3. Vibrations-Filter** (Temporal Median auf Motion-Mask, 3 Frames) — commit fda3cf1
- [x] **4. Threshold-Kalibrierung** scripts/calibrate_thresholds.py (--quick Mode) — commit 1880e95
- [x] **5. `settle_frames` dynamisch** (auto-raise bei Vibrations-Interrupts, max base+4) — commit 1880e95

## Woche 2: UI-Begeisterung

- [x] **1. Hit-Explosion** (SVG Particles bei Treffer-Confirm) — commit c18d0f6
- [x] **2. Score-Popup** (+N schwebt hoch, 1.2s Animation) — commit c18d0f6
- [x] **3. Sound-System** (Hit/Reject/Undo/Win — generalisiert) — commit c18d0f6
- [x] **4. Victory Confetti + Animation** (Full-Screen, Sound, Auto-Close 6s) — commit c18d0f6
- [x] **5. Leading-Player Glow** + Animated Score-Counter — commit c18d0f6
- [x] **6. Sektor-Highlight** bei Treffer auf SVG-Board — commit c18d0f6
- [x] **7. Double-In Checkbox** in Game-Setup UI + API — commit c18d0f6
- [x] **8. Spieleinstellungen erweitern** (Handicap per Player, Cricket Cut Throat) — commit 5635496

## Woche 3: Spiellogik + Polish

- [ ] **1. Auto-Next-Player nach 3 Darts**
- [ ] **2. Statistik-Panel nach Spielende** (AVG, Highest, Export)
- [ ] **3. Free Play Zielscore** (z.B. "Erste zu 1000")
- [ ] **4. Pause-Button**
- [ ] **5. Undo/Redo verbessern** (Turn-Ebene, Redo)

## Woche 4+: Multi-Cam (wenn Single stabil)

- [ ] **1. WLAN-Latenz-Profiling** pro Kamera
- [ ] **2. Vibrations-tolerante Depth-Tolerance** (Z-Oszillations-Heuristik)
- [ ] **3. Kalibrierungs-Kette: Blocking** statt nur Warning bei staler Calibration
- [ ] **4. UI-Feedback bei Kamera-Degradation** (Single-Cam Fallback sichtbar)
- [ ] **5. Reprojections-Fehler pro Kamera kalibrieren** (statt global 20px)
- [ ] **6. Frame-Sync Re-Synchronisation** (alle 10s, Timestamp-Drift verhindern)

---

## Hardware Quick-Wins (unabhaengig)

- [ ] Target-FPS auf 20 reduzieren (konfigurierbar machen)
- [ ] Resolution 480x360 als Emergency-Mode bei CPU > 80%
- [ ] Motion-Threshold auf 150+ wenn kein Dart fliegt
- [ ] Queue-Aware Detection (skip bei queue_pressure > 0.8)

---

## Kernerkenntnisse

- **Groesster Hebel Single-Cam:** Schwellwerte an spezifische Hardware kalibrieren
- **Groesster Hebel UI:** Hit-Explosion + Sound = billigster Wow-Effekt
- **Groesster Hebel Multi-Cam:** WLAN-Latenz-Profiling + Vibrations-Toleranz
- **CPU-Fresser:** CLAHE (~15-20%), FrameDiff-Contours (~25-30%), Remapping (~15-20%)
- **False-Positive-Killer:** min_elongation hochsetzen, Vibrations-Median-Filter
