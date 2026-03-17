#!/bin/bash
# Pre-Commit Quality Gate fuer dart-vision-claude
# Wird als Claude Code Hook vor jedem Commit ausgefuehrt

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

echo "=== Pre-Commit Quality Gate ==="

# 1. Tests laufen lassen
echo ""
echo "[1/3] Running pytest..."
cd "$REPO_ROOT"
python -m pytest -q --tb=short 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Tests failed — commit blocked"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Tests passed"
fi

# 2. Coverage pruefen (nur Warnung, kein Block)
echo ""
echo "[2/3] Checking coverage..."
COVERAGE_OUTPUT=$(python -m pytest --cov=src --cov-report=term -q --tb=no 2>&1 | tail -5)
echo "$COVERAGE_OUTPUT"

# 3. Pruefen ob priorities.md und current_state.md in staged files sind
echo ""
echo "[3/3] Checking documentation updates..."
STAGED=$(git diff --cached --name-only 2>/dev/null)

# Nur pruefen wenn src/ Dateien geaendert wurden
if echo "$STAGED" | grep -q "^src/"; then
    if ! echo "$STAGED" | grep -q "priorities.md\|current_state.md"; then
        echo "⚠️  WARNUNG: src/ Dateien geaendert aber priorities.md/current_state.md nicht aktualisiert"
        echo "   Vergessen die Dokumentation anzupassen? (kein Block, nur Hinweis)"
    else
        echo "✅ Dokumentation wird mit-committed"
    fi
else
    echo "✅ Keine src/ Aenderungen — Doku-Check uebersprungen"
fi

echo ""
if [ $ERRORS -gt 0 ]; then
    echo "❌ $ERRORS Fehler gefunden — bitte beheben vor dem Commit"
    exit 1
else
    echo "✅ Alle Checks bestanden"
    exit 0
fi
