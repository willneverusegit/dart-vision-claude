# Architektur-Entscheidungen (ADRs)

Dokumentiert warum bestimmte Loesungen so gewaehlt wurden.
Verhindert dass zukuenftige Agents Entscheidungen revertieren ohne den Kontext zu kennen.

---

## ADR-001: CPU-only, kein GPU-Pflicht (2026-03)

**Entscheidung:** Gesamtes System laeuft ohne GPU. Keine CUDA/OpenCL-Abhaengigkeit.
**Warum:** Zielhardware ist ein normaler Laptop am Dartboard. GPU wuerde Setup-Komplexitaet massiv erhoehen ohne proportionalen Nutzen — OpenCV reicht fuer die Bildverarbeitung.
**Konsequenz:** Keine Deep-Learning-Modelle fuer Erkennung. Klassische CV-Methoden (ArUco, Konturerkennung, Farbsegmentierung).

## ADR-002: Single-Camera als stabiler Hauptpfad (2026-03)

**Entscheidung:** Single-Cam ist der primaere und am besten getestete Pfad. Multi-Cam ist Zusatz.
**Warum:** Die meisten Nutzer haben eine Kamera. Multi-Cam erfordert Stereo-Kalibrierung und ist fehleranfaelliger. Single-Cam muss immer funktionieren.
**Konsequenz:** Aenderungen an Multi-Cam duerfen Single-Cam nie verschlechtern.

## ADR-003: ThreadedCamera mit Stop-Events statt Process-Pool (2026-03)

**Entscheidung:** Kamera-Capture laeuft in Threads mit expliziten Stop-Events, nicht in separaten Prozessen.
**Warum:** Threads sind leichtgewichtiger, teilen Speicher (fuer Frame-Queues), und Windows-IPC ist fehleranfaellig mit USB-Kameras. Stop-Events ermoeglichen sauberes Herunterfahren.
**Konsequenz:** GIL-Limitierung akzeptiert — Pipeline ist I/O-bound (Kamera-Read), nicht CPU-bound.

## ADR-004: FastAPI + Vanilla JS statt SPA-Framework (2026-03)

**Entscheidung:** Backend ist FastAPI, Frontend ist Vanilla JS ohne Framework.
**Warum:** Minimale Abhaengigkeiten, kein Build-Step noetig, einfaches Deployment auf dem Ziel-Laptop. Das Projekt ist kein Web-Produkt sondern ein Werkzeug.
**Konsequenz:** Kein React/Vue/Svelte. UI-Komplexitaet muss bewusst niedrig gehalten werden.

## ADR-005: Agent-Selbstverbesserung ueber Dokumentation (2026-03-17)

**Entscheidung:** Agents dokumentieren ihren Fortschritt in priorities.md, current_state.md, pitfalls.md und session_logs/. CLAUDE.md wird iterativ verbessert.
**Warum:** Ohne persistente Dokumentation verlieren Agents Kontext zwischen Sessions und wiederholen Fehler. Die Docs sind das Gedaechtnis des Projekts.
**Konsequenz:** Jede Session hat Doku-Overhead (~5 min), aber zukuenftige Sessions starten mit besserem Kontext.

---

*Neue ADRs am Ende anfuegen mit fortlaufender Nummer. Format: Entscheidung → Warum → Konsequenz.*
