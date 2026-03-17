# Session 2026-03-17: P20 Tip-Detection

- **Erledigt:** Tip-Detection-Algorithmus gebaut und in diff_detector integriert. Diagnostics-Modus genutzt um echte Dart-Aufnahmen zu sammeln (12x cam_right, 6x cam_left). Validierung 18/18 OK. P25-P27 als neue Prioritaeten angelegt.
- **Erledigt:** Echte Probewuerfe am Board aufgenommen und ausgewertet. Kamera-Qualitaetsunterschiede dokumentiert (cam_left schaerfer).
- **Probleme:** Keine Blocker. cam_right unscharfer als cam_left — Tip-Detection funktioniert trotzdem auf beiden.
- **Gelernt:** Daten-zuerst-Ansatz spart Iterationen — Algorithmus auf echten Konturen designen statt blind synthetisch. minAreaRect + Breitenvergleich ist robuster Ansatz fuer Tip-Lokalisierung.
- **CLAUDE.md-Anpassungen:** keine
