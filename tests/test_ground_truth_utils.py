"""Unit tests for ground truth validation and helper utilities."""

from __future__ import annotations

import os
import textwrap

import pytest
import yaml

from scripts.add_ground_truth import (
    VALID_RINGS,
    VALID_SECTORS,
    parse_throw_string,
    validate_ground_truth,
    validate_throw,
)


# ---------------------------------------------------------------------------
# validate_throw
# ---------------------------------------------------------------------------

class TestValidateThrow:
    def test_valid_single(self):
        assert validate_throw({"sector": 20, "ring": "triple"}, "v.mp4", 0) == []

    def test_valid_bull(self):
        assert validate_throw({"sector": 25, "ring": "bull_inner"}, "v.mp4", 0) == []

    def test_valid_miss(self):
        assert validate_throw({"sector": 0, "ring": "miss"}, "v.mp4", 0) == []

    def test_valid_with_timestamp(self):
        assert validate_throw({"sector": 5, "ring": "double", "timestamp_s": 12.5}, "v.mp4", 0) == []

    def test_missing_sector(self):
        errs = validate_throw({"ring": "single"}, "v.mp4", 0)
        assert len(errs) == 1
        assert "missing 'sector'" in errs[0]

    def test_missing_ring(self):
        errs = validate_throw({"sector": 10}, "v.mp4", 0)
        assert len(errs) == 1
        assert "missing 'ring'" in errs[0]

    def test_invalid_sector(self):
        errs = validate_throw({"sector": 99, "ring": "single"}, "v.mp4", 0)
        assert any("invalid sector" in e for e in errs)

    def test_invalid_ring(self):
        errs = validate_throw({"sector": 5, "ring": "quadruple"}, "v.mp4", 0)
        assert any("invalid ring" in e for e in errs)

    def test_sector_0_must_be_miss(self):
        errs = validate_throw({"sector": 0, "ring": "single"}, "v.mp4", 0)
        assert any("sector 0 must have ring 'miss'" in e for e in errs)

    def test_miss_must_be_sector_0(self):
        errs = validate_throw({"sector": 5, "ring": "miss"}, "v.mp4", 0)
        assert any("ring 'miss' must have sector 0" in e for e in errs)

    def test_bull_sector_ring_mismatch(self):
        errs = validate_throw({"sector": 25, "ring": "single"}, "v.mp4", 0)
        assert any("sector 25 must have ring" in e for e in errs)

    def test_bull_ring_wrong_sector(self):
        errs = validate_throw({"sector": 10, "ring": "bull_inner"}, "v.mp4", 0)
        assert any("ring 'bull_inner' must have sector 25" in e for e in errs)

    def test_negative_timestamp(self):
        errs = validate_throw({"sector": 1, "ring": "single", "timestamp_s": -5}, "v.mp4", 0)
        assert any("invalid timestamp_s" in e for e in errs)


# ---------------------------------------------------------------------------
# parse_throw_string
# ---------------------------------------------------------------------------

class TestParseThrowString:
    def test_basic(self):
        result = parse_throw_string("20 triple")
        assert result == {"sector": 20, "ring": "triple"}

    def test_with_timestamp(self):
        result = parse_throw_string("5 double 12.5")
        assert result == {"sector": 5, "ring": "double", "timestamp_s": 12.5}

    def test_bull(self):
        result = parse_throw_string("25 bull_outer 7")
        assert result == {"sector": 25, "ring": "bull_outer", "timestamp_s": 7.0}

    def test_too_few_parts(self):
        with pytest.raises(ValueError, match="Expected"):
            parse_throw_string("20")

    def test_invalid_combo(self):
        with pytest.raises(ValueError):
            parse_throw_string("25 single")  # sector 25 needs bull ring


# ---------------------------------------------------------------------------
# validate_ground_truth (file-level)
# ---------------------------------------------------------------------------

class TestValidateGroundTruth:
    def test_valid_file(self, tmp_path):
        gt = {
            "videos": {
                "test.mp4": {
                    "description": "",
                    "throws": [
                        {"sector": 20, "ring": "triple", "timestamp_s": 3},
                        {"sector": 5, "ring": "single", "timestamp_s": 6},
                    ],
                }
            }
        }
        p = tmp_path / "gt.yaml"
        p.write_text(yaml.dump(gt), encoding="utf-8")
        assert validate_ground_truth(str(p)) == []

    def test_missing_file(self, tmp_path):
        errs = validate_ground_truth(str(tmp_path / "nope.yaml"))
        assert len(errs) == 1
        assert "not found" in errs[0].lower()

    def test_missing_videos_key(self, tmp_path):
        p = tmp_path / "gt.yaml"
        p.write_text("foo: bar", encoding="utf-8")
        errs = validate_ground_truth(str(p))
        assert any("videos" in e for e in errs)

    def test_timestamp_order_violation(self, tmp_path):
        gt = {
            "videos": {
                "test.mp4": {
                    "throws": [
                        {"sector": 1, "ring": "single", "timestamp_s": 10},
                        {"sector": 2, "ring": "single", "timestamp_s": 5},
                    ],
                }
            }
        }
        p = tmp_path / "gt.yaml"
        p.write_text(yaml.dump(gt), encoding="utf-8")
        errs = validate_ground_truth(str(p))
        assert any("not in order" in e for e in errs)

    def test_invalid_throw_in_file(self, tmp_path):
        gt = {
            "videos": {
                "test.mp4": {
                    "throws": [
                        {"sector": 99, "ring": "single"},
                    ],
                }
            }
        }
        p = tmp_path / "gt.yaml"
        p.write_text(yaml.dump(gt), encoding="utf-8")
        errs = validate_ground_truth(str(p))
        assert any("invalid sector" in e for e in errs)

    def test_empty_throws_ok(self, tmp_path):
        gt = {"videos": {"empty.mp4": {"throws": []}}}
        p = tmp_path / "gt.yaml"
        p.write_text(yaml.dump(gt), encoding="utf-8")
        assert validate_ground_truth(str(p)) == []

    def test_real_ground_truth_valid(self):
        """The actual testvids/ground_truth.yaml passes validation."""
        gt_path = os.path.join(
            os.path.dirname(__file__), "..", "testvids", "ground_truth.yaml"
        )
        if not os.path.exists(gt_path):
            pytest.skip("ground_truth.yaml not present")
        errs = validate_ground_truth(gt_path)
        assert not errs, f"Validation errors: {errs}"


# ---------------------------------------------------------------------------
# _format_throw_report (from test_ground_truth_validation)
# ---------------------------------------------------------------------------

class TestFormatThrowReport:
    def test_report_shows_missed_throws(self):
        from tests.e2e.test_ground_truth_validation import _format_throw_report

        gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3}]
        report = _format_throw_report(gt, [], "test.mp4")
        assert "MISSED" in report

    def test_report_shows_false_positives(self):
        from tests.e2e.test_ground_truth_validation import _format_throw_report

        gt = []
        darts = [{"sector": 5, "ring": "single", "score": 5}]
        report = _format_throw_report(gt, darts, "test.mp4")
        assert "FALSE POSITIVES" in report

    def test_report_shows_hit(self):
        from tests.e2e.test_ground_truth_validation import _format_throw_report

        gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3}]
        darts = [{"sector": 20, "ring": "triple", "score": 60}]
        report = _format_throw_report(gt, darts, "test.mp4")
        assert "HIT" in report

    def test_report_shows_wrong(self):
        from tests.e2e.test_ground_truth_validation import _format_throw_report

        gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3}]
        darts = [{"sector": 5, "ring": "single", "score": 5}]
        report = _format_throw_report(gt, darts, "test.mp4")
        assert "WRONG" in report
