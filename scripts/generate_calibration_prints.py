from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

import cv2
import numpy as np
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cv.calibration import (
    ARUCO_DICT_TYPE,
    ARUCO_EXPECTED_IDS,
    ARUCO_MARKER_SIZE_MM,
    MARKER_SPACING_MM,
)
from src.cv.stereo_calibration import (
    LARGE_MARKER_CHARUCO_BOARD_SPEC,
    STEREO_CHARUCO_DICT,
    STEREO_SQUARES_X,
    STEREO_SQUARES_Y,
    STEREO_SQUARE_LENGTH,
    STEREO_MARKER_LENGTH,
)


OUT_DIR = ROOT / "output" / "pdf"
DPI = 300

ARUCO_PDF = OUT_DIR / "aruco_markers_4x4_50_ids_0-1-2-3_75mm_a4.pdf"
CHARUCO_PDF = OUT_DIR / "charuco_board_7x5_40mm_20mm_a4_landscape.pdf"
CHARUCO_PDF_LARGE_MARKERS = OUT_DIR / "charuco_board_7x5_40mm_28mm_a4_landscape.pdf"
NOTES_MD = OUT_DIR / "calibration_print_notes.md"


def mm_to_px(value_mm: float, dpi: int = DPI) -> int:
    return int(round((value_mm / 25.4) * dpi))


def _encode_png(image: np.ndarray) -> BytesIO:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return BytesIO(buf.tobytes())


def generate_aruco_marker(marker_id: int, edge_mm: float) -> BytesIO:
    side_px = mm_to_px(edge_mm)
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)

    if hasattr(cv2.aruco, "generateImageMarker"):
        image = cv2.aruco.generateImageMarker(dictionary, marker_id, side_px, borderBits=1)
    else:
        image = np.zeros((side_px, side_px), dtype=np.uint8)
        cv2.aruco.drawMarker(dictionary, marker_id, side_px, image, 1)

    return _encode_png(image)


def generate_charuco_board(
    squares_x: int,
    squares_y: int,
    square_mm: float,
    marker_mm: float,
) -> BytesIO:
    board_w_mm = squares_x * square_mm
    board_h_mm = squares_y * square_mm
    board_w_px = mm_to_px(board_w_mm)
    board_h_px = mm_to_px(board_h_mm)

    dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (squares_x, squares_y),
        square_mm / 1000.0,
        marker_mm / 1000.0,
        dictionary,
    )
    image = board.generateImage((board_w_px, board_h_px), marginSize=0, borderBits=1)
    return _encode_png(image)


def create_aruco_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4

    title_y = page_h - 18 * mm
    c.setFont("Helvetica-Bold", 15)
    c.drawString(15 * mm, title_y, "ArUco calibration markers")
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, title_y - 5 * mm, "Print at 100% / actual size. Do not use fit-to-page.")
    c.drawString(15 * mm, title_y - 9 * mm, "Dictionary: DICT_4X4_50. Black marker edge: 75 mm.")

    tile_size_mm = 85.0
    quiet_margin_mm = (tile_size_mm - ARUCO_MARKER_SIZE_MM) / 2.0
    marker_reader = {
        marker_id: ImageReader(generate_aruco_marker(marker_id, ARUCO_MARKER_SIZE_MM))
        for marker_id in ARUCO_EXPECTED_IDS
    }

    lefts_mm = [20.0, 105.0]
    bottoms_mm = [132.0, 37.0]
    positions = [
        (ARUCO_EXPECTED_IDS[0], lefts_mm[0], bottoms_mm[0]),
        (ARUCO_EXPECTED_IDS[1], lefts_mm[1], bottoms_mm[0]),
        (ARUCO_EXPECTED_IDS[2], lefts_mm[0], bottoms_mm[1]),
        (ARUCO_EXPECTED_IDS[3], lefts_mm[1], bottoms_mm[1]),
    ]

    for marker_id, left_mm, bottom_mm in positions:
        c.setDash(3, 2)
        c.setLineWidth(0.5)
        c.rect(left_mm * mm, bottom_mm * mm, tile_size_mm * mm, tile_size_mm * mm)
        c.setDash()

        c.drawImage(
            marker_reader[marker_id],
            (left_mm + quiet_margin_mm) * mm,
            (bottom_mm + quiet_margin_mm) * mm,
            width=ARUCO_MARKER_SIZE_MM * mm,
            height=ARUCO_MARKER_SIZE_MM * mm,
            preserveAspectRatio=True,
            mask="auto",
        )

        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(
            (left_mm + tile_size_mm / 2.0) * mm,
            (bottom_mm - 4.5) * mm,
            f"ID {marker_id}",
        )

    c.setFont("Helvetica", 8)
    c.drawString(
        15 * mm,
        16 * mm,
        "Optional cut line = dashed box. The black square itself is exactly 75 mm.",
    )
    c.drawString(15 * mm, 11 * mm, "Recommended printer setting: actual size / 100%.")
    c.showPage()

    c.setFont("Helvetica-Bold", 15)
    c.drawString(15 * mm, page_h - 18 * mm, "Placement guide for board alignment")
    c.setFont("Helvetica", 10)
    c.drawString(15 * mm, page_h - 26 * mm, "Use marker IDs 0-3 in this order around the board:")
    c.drawString(15 * mm, page_h - 32 * mm, "0 = top left, 1 = top right, 2 = bottom right, 3 = bottom left")
    c.drawString(
        15 * mm,
        page_h - 38 * mm,
        f"Required center-to-center spacing: {MARKER_SPACING_MM} mm. Marker edge: {ARUCO_MARKER_SIZE_MM} mm.",
    )
    c.drawString(
        15 * mm,
        page_h - 44 * mm,
        "Print at 100%. Measure one black edge after printing before first use.",
    )

    diag_left = 48 * mm
    diag_bottom = 70 * mm
    diag_size = 110 * mm
    c.setLineWidth(1)
    c.rect(diag_left, diag_bottom, diag_size, diag_size)
    marker_box = 16 * mm
    corners = {
        0: (diag_left + 3 * mm, diag_bottom + diag_size - marker_box - 3 * mm),
        1: (diag_left + diag_size - marker_box - 3 * mm, diag_bottom + diag_size - marker_box - 3 * mm),
        2: (diag_left + diag_size - marker_box - 3 * mm, diag_bottom + 3 * mm),
        3: (diag_left + 3 * mm, diag_bottom + 3 * mm),
    }
    for marker_id, (x, y) in corners.items():
        c.rect(x, y, marker_box, marker_box)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + marker_box / 2.0, y + marker_box / 2.0 - 4, str(marker_id))

    c.setFont("Helvetica", 9)
    c.drawCentredString(diag_left + diag_size / 2.0, diag_bottom - 8 * mm, "Board/frame schematic, not to scale")
    c.drawCentredString(diag_left + diag_size / 2.0, diag_bottom - 14 * mm, "Center spacing between marker centers: 410 mm")
    c.save()


def create_charuco_pdf(
    path: Path,
    squares_x: int,
    squares_y: int,
    square_mm: float,
    marker_mm: float,
) -> None:
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    page_w, page_h = landscape(A4)
    board_w_mm = squares_x * square_mm
    board_h_mm = squares_y * square_mm

    board_x = (page_w - board_w_mm * mm) / 2.0
    board_y = (page_h - board_h_mm * mm) / 2.0
    board_reader = ImageReader(generate_charuco_board(squares_x, squares_y, square_mm, marker_mm))

    c.drawImage(
        board_reader,
        board_x,
        board_y,
        width=board_w_mm * mm,
        height=board_h_mm * mm,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.save()


def write_notes(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Calibration print notes",
                "",
                "Generated files:",
                f"- `{ARUCO_PDF.name}`",
                f"- `{CHARUCO_PDF.name}`",
                f"- `{CHARUCO_PDF_LARGE_MARKERS.name}`",
                "",
                "ArUco board-alignment markers:",
                "- Dictionary: `DICT_4X4_50`",
                "- Marker IDs: `0, 1, 2, 3`",
                f"- Black marker edge: `{ARUCO_MARKER_SIZE_MM} mm`",
                f"- Required center-to-center spacing on the board/frame: `{MARKER_SPACING_MM} mm`",
                "- Placement order: `0 = top left, 1 = top right, 2 = bottom right, 3 = bottom left`",
                "",
                "ChArUco board for lens/stereo calibration:",
                "- Dictionary: `DICT_6X6_250`",
                f"- Squares: `{STEREO_SQUARES_X} x {STEREO_SQUARES_Y}`",
                f"- Standard square length: `{STEREO_SQUARE_LENGTH * 1000:.0f} mm`",
                f"- Standard marker length: `{STEREO_MARKER_LENGTH * 1000:.0f} mm`",
                "- Additional print variant: `40 mm squares / 28 mm markers`",
                "- Intended print format: `A4 landscape`",
                "- Important: board geometry in calibration code or config must match the printed board.",
                "- Browser/API preset for the larger board: `40x28` on lens and stereo calibration.",
                "",
                "Print instructions:",
                "- Print at `100%` or `actual size`.",
                "- Disable `fit to page`, `shrink oversized pages`, and similar scaling options.",
                "- Measure one printed black marker edge before first calibration run.",
                "- Use matte paper if possible and keep the sheets flat.",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    create_aruco_pdf(ARUCO_PDF)
    create_charuco_pdf(
        CHARUCO_PDF,
        STEREO_SQUARES_X,
        STEREO_SQUARES_Y,
        STEREO_SQUARE_LENGTH * 1000.0,
        STEREO_MARKER_LENGTH * 1000.0,
    )
    create_charuco_pdf(
        CHARUCO_PDF_LARGE_MARKERS,
        LARGE_MARKER_CHARUCO_BOARD_SPEC.squares_x,
        LARGE_MARKER_CHARUCO_BOARD_SPEC.squares_y,
        LARGE_MARKER_CHARUCO_BOARD_SPEC.square_length_m * 1000.0,
        LARGE_MARKER_CHARUCO_BOARD_SPEC.marker_length_m * 1000.0,
    )
    write_notes(NOTES_MD)
    print(f"Created {ARUCO_PDF}")
    print(f"Created {CHARUCO_PDF}")
    print(f"Created {CHARUCO_PDF_LARGE_MARKERS}")
    print(f"Created {NOTES_MD}")


if __name__ == "__main__":
    main()
