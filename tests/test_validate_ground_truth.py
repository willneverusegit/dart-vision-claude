"""Tests for scripts/validate_ground_truth.py — ground truth YAML validation."""

import pytest
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from validate_ground_truth import (
    validate_throw,
    validate_video,
    validate_ground_truth,
    load_and_validate,
    ValidationError,
)


# --- validate_throw ---

class TestValidateThrow:
    def test_valid_single(self):
        assert validate_throw("v.mp4", 0, {"sector": 20, "ring": "single"}) == []

    def test_valid_double(self):
        assert validate_throw("v.mp4", 0, {"sector": 3, "ring": "double"}) == []

    def test_valid_triple(self):
        assert validate_throw("v.mp4", 0, {"sector": 19, "ring": "triple"}) == []

    def test_valid_bull_inner(self):
        assert validate_throw("v.mp4", 0, {"sector": 25, "ring": "bull_inner"}) == []

    def test_valid_bull_outer(self):
        assert validate_throw("v.mp4", 0, {"sector": 25, "ring": "bull_outer"}) == []

    def test_valid_miss(self):
        assert validate_throw("v.mp4", 0, {"sector": 0, "ring": "miss"}) == []

    def test_valid_with_timestamp(self):
        assert validate_throw("v.mp4", 0, {"sector": 5, "ring": "single", "timestamp_s": 3.2}) == []

    def test_missing_sector(self):
        errs = validate_throw("v.mp4", 0, {"ring": "single"})
        assert len(errs) == 1
        assert "sector" in str(errs[0])

    def test_missing_ring(self):
        errs = validate_throw("v.mp4", 0, {"sector": 5})
        assert len(errs) == 1
        assert "ring" in str(errs[0])

    def test_invalid_sector_value(self):
        errs = validate_throw("v.mp4", 0, {"sector": 22, "ring": "single"})
        assert len(errs) == 1
        assert "not in valid range" in str(errs[0])

    def test_sector_string_type(self):
        errs = validate_throw("v.mp4", 0, {"sector": "20", "ring": "single"})
        assert any("must be int" in str(e) for e in errs)

    def test_invalid_ring_value(self):
        errs = validate_throw("v.mp4", 0, {"sector": 5, "ring": "quadruple"})
        assert len(errs) == 1
        assert "not valid" in str(errs[0])

    def test_bull_ring_wrong_sector(self):
        errs = validate_throw("v.mp4", 0, {"sector": 10, "ring": "bull_inner"})
        assert any("bull ring" in str(e) for e in errs)

    def test_sector25_wrong_ring(self):
        errs = validate_throw("v.mp4", 0, {"sector": 25, "ring": "single"})
        assert any("sector 25" in str(e) for e in errs)

    def test_sector25_triple_invalid(self):
        errs = validate_throw("v.mp4", 0, {"sector": 25, "ring": "triple"})
        assert len(errs) >= 1

    def test_miss_wrong_sector(self):
        errs = validate_throw("v.mp4", 0, {"sector": 5, "ring": "miss"})
        assert any("miss" in str(e) for e in errs)

    def test_sector0_wrong_ring(self):
        errs = validate_throw("v.mp4", 0, {"sector": 0, "ring": "single"})
        assert any("sector 0" in str(e) for e in errs)

    def test_negative_timestamp(self):
        errs = validate_throw("v.mp4", 0, {"sector": 5, "ring": "single", "timestamp_s": -1})
        assert any("non-negative" in str(e) for e in errs)

    def test_throw_not_dict(self):
        errs = validate_throw("v.mp4", 0, "invalid")
        assert len(errs) == 1
        assert "must be dict" in str(errs[0])

    def test_all_sectors_valid(self):
        for s in list(range(1, 21)) + [25]:
            ring = "bull_inner" if s == 25 else "single"
            assert validate_throw("v.mp4", 0, {"sector": s, "ring": ring}) == [], f"sector {s} failed"


# --- validate_video ---

class TestValidateVideo:
    def test_valid_video(self):
        entry = {"description": "test", "throws": [{"sector": 20, "ring": "single"}]}
        assert validate_video("v.mp4", entry) == []

    def test_empty_throws(self):
        entry = {"description": "", "throws": []}
        assert validate_video("v.mp4", entry) == []

    def test_missing_throws(self):
        errs = validate_video("v.mp4", {"description": ""})
        assert len(errs) == 1
        assert "throws" in str(errs[0])

    def test_throws_not_list(self):
        errs = validate_video("v.mp4", {"throws": "invalid"})
        assert any("list" in str(e) for e in errs)

    def test_entry_not_dict(self):
        errs = validate_video("v.mp4", "invalid")
        assert len(errs) == 1


# --- validate_ground_truth ---

class TestValidateGroundTruth:
    def test_valid_structure(self):
        data = {"videos": {"1.mp4": {"throws": [{"sector": 5, "ring": "single"}]}}}
        assert validate_ground_truth(data) == []

    def test_missing_videos_key(self):
        errs = validate_ground_truth({"foo": "bar"})
        assert any("videos" in str(e) for e in errs)

    def test_top_level_not_dict(self):
        errs = validate_ground_truth("string")
        assert len(errs) == 1

    def test_videos_not_dict(self):
        errs = validate_ground_truth({"videos": []})
        assert len(errs) == 1


# --- Integration: validate actual ground_truth.yaml ---

class TestActualGroundTruth:
    """Validate the real ground_truth.yaml in the repo."""

    GT_PATH = Path(__file__).resolve().parent.parent / "testvids" / "ground_truth.yaml"

    @pytest.mark.skipif(
        not (Path(__file__).resolve().parent.parent / "testvids" / "ground_truth.yaml").exists(),
        reason="ground_truth.yaml not present",
    )
    def test_actual_file_valid(self):
        errors = load_and_validate(self.GT_PATH)
        if errors:
            msg = "\n".join(f"  {e}" for e in errors)
            pytest.fail(f"ground_truth.yaml has {len(errors)} validation error(s):\n{msg}")


# --- ValidationError formatting ---

class TestValidationError:
    def test_str_with_throw(self):
        e = ValidationError("v.mp4", 2, "bad")
        assert "[v.mp4, throw #3]" in str(e)

    def test_str_without_throw(self):
        e = ValidationError("v.mp4", None, "bad")
        assert str(e) == "[v.mp4] bad"
