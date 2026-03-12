# Ground Truth Sidecars

Dieses Verzeichnis enthaelt die manuell gepflegte Wahrheit fuer Replay-Clips.

Regel:
- Jeder Clip in `tests/replays/` braucht eine JSON-Datei mit identischem Basisnamen.

Minimales Schema pro Eintrag:

```json
{
  "video": "clip_name.mp4",
  "events": [
    {
      "frame_index": 42,
      "raw_point_px": [713, 382],
      "expected": {
        "score": 60,
        "sector": 20,
        "ring": "triple",
        "multiplier": 3
      },
      "tag": "normal_impact"
    }
  ]
}
```

Hinweise:
- `raw_point_px` referenziert den Rohframe vor Remap.
- `tag` ist optional und hilft bei Sonderfaellen wie `bounce_out`, `occluded`, `remove_sequence`.
- Die Replay-Validation nutzt diese Sidecars fuer RMSE- und Score-Regression.
