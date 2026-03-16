# Calibration print notes

Generated files:
- `aruco_markers_4x4_50_ids_0-1-2-3_75mm_a4.pdf`
- `charuco_board_7x5_40mm_20mm_a4_landscape.pdf`
- `charuco_board_7x5_40mm_28mm_a4_landscape.pdf`

ArUco board-alignment markers:
- Dictionary: `DICT_4X4_50`
- Marker IDs: `0, 1, 2, 3`
- Black marker edge: `75 mm`
- Required center-to-center spacing on the board/frame: `410 mm`
- Placement order: `0 = top left, 1 = top right, 2 = bottom right, 3 = bottom left`

ChArUco board for lens/stereo calibration:
- Dictionary: `DICT_6X6_250`
- Squares: `7 x 5`
- Standard square length: `40 mm`
- Standard marker length: `20 mm`
- Additional print variant: `40 mm squares / 28 mm markers`
- Intended print format: `A4 landscape`
- Important: board geometry in calibration code or config must match the printed board.
- Browser/API preset for the larger board: `40x28` on lens and stereo calibration.

Print instructions:
- Print at `100%` or `actual size`.
- Disable `fit to page`, `shrink oversized pages`, and similar scaling options.
- Measure one printed black marker edge before first calibration run.
- Use matte paper if possible and keep the sheets flat.