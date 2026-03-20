# Pipeline-Patterns aus dart_vision_mvp

## 1. Motion Gating
Billige Bewegungserkennung (MOG2) als Vorfilter — teure Dart-Detection läuft nur bei erkannter Bewegung. Spart massiv CPU im Leerlauf.

## 2. Cascading Filter Pipeline
Mehrstufige Kandidaten-Filterung, jede Stufe günstiger als die nächste:
Contours → Shape-Metriken → Convexity Gate → Confidence Score → Temporal Confirmation → Cooldown.

## 3. Temporal Confirmation (Land-and-Stick)
Ein Kandidat muss 3 aufeinanderfolgende Frames innerhalb 14px Toleranz stabil bleiben, bevor er als Impact akzeptiert wird. Verhindert Fehlerkennungen durch Rauschen oder flüchtige Objekte.

## 4. Adaptive Schwellwerte
- Helligkeitsbasierter Otsu-Bias (dunkel → empfindlicher, hell → robuster)
- Search Mode: Nach 90 Frames Stille automatisch niedrigere Schwelle für 30 Frames
- Dual-Threshold Fusion (optional): niedrige + hohe Schwelle per OR vereinigt

## 5. Edge Cache
Canny-Kantenerkennung einmal pro Frame berechnen und für alle Konturen wiederverwenden. 15–25% Performance-Gewinn gegenüber Einzelberechnung pro Kontur.

## 6. Dirty Flag
Teure Berechnungen (z.B. effektive Homographie) nur bei tatsächlicher Parameteränderung neu ausführen. Flag wird bei Änderung gesetzt, nach Neuberechnung zurückgesetzt.

## 7. Cooldown-Management
Nach bestätigtem Impact: räumliche (50px Radius) und zeitliche (30 Frames) Sperrzone. Verhindert Mehrfacherkennung desselben Darts.

## 8. Multi-Kamera Fusion
Zwei Kameras erkennen unabhängig — bei Übereinstimmung (≤18px) werden Positionen confidence-gewichtet gemittelt. Optional: nur akzeptieren wenn beide Kameras erkennen.

## 9. Threaded Producer-Consumer
Kamera läuft in eigenem Thread, schreibt in Queue (max 5 Frames). Main Loop liest non-blocking das neueste Frame. +52% FPS gegenüber synchronem Lesen.

## 10. Modulare Detection-Komponenten
Jede Pipeline-Stufe ist eigenständig testbar und austauschbar:
- `MotionFilter` — Morphologische Reinigung + Blob-Entfernung
- `TemporalGate` — Search Mode nach Stille
- `ShapeAnalyzer` — Multi-Metrik Konturanalyse + Edge Cache
- `ConfirmationTracker` — Land-and-Stick Bestätigung
- `CooldownManager` — Räumlich-zeitliche Unterdrückung
