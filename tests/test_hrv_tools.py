"""src/signals/hrv_tools.py: lectura de RR desde archivo y Poincaré."""
import numpy as np
import pytest

from src.signals.hrv_tools import RR_PLAUSIBLE_MS, parse_rr_file, poincare_sd1_sd2


def test_one_value_per_line_in_ms():
    r = parse_rr_file("812\n795\n830\n\n801\n")
    assert r.rr_ms.tolist() == [812, 795, 830, 801]
    assert r.unit_detected == "ms" and r.lines_skipped == 1 and r.column_used is None


def test_seconds_are_converted_to_ms():
    r = parse_rr_file(b"0.812\n0.795\n0.830\n")
    assert r.unit_detected == "s"
    assert r.rr_ms == pytest.approx([812, 795, 830])


def test_csv_with_header_uses_last_column():
    r = parse_rr_file("tiempo_s,rr_ms\n0.0,812\n0.812,795\n1.607,830\n")
    assert r.rr_ms.tolist() == [812, 795, 830]
    assert r.lines_skipped == 1 and r.column_used == 2


def test_single_line_comma_list_and_european_decimals():
    assert parse_rr_file("800, 820, 790, 810").rr_ms.tolist() == [800, 820, 790, 810]
    r = parse_rr_file("idx;rr\n1;812,5\n2;799,5\n")
    assert r.rr_ms.tolist() == [812.5, 799.5]


def test_out_of_range_values_are_reported_and_only_dropped_on_request():
    content = "800\n150\n810\n2600\n790\n"
    kept = parse_rr_file(content)
    assert kept.n_out_of_range == 2 and len(kept.rr_ms) == 5
    dropped = parse_rr_file(content, exclude_out_of_range=True)
    assert dropped.rr_ms.tolist() == [800, 810, 790]
    lo, hi = RR_PLAUSIBLE_MS
    assert lo < 800 < hi


def test_empty_file():
    r = parse_rr_file("encabezado sin números\n")
    assert r.rr_ms.size == 0


def test_poincare_matches_definitions():
    rng = np.random.default_rng(3)
    rr = 800 + np.cumsum(rng.normal(0, 5, 400)) + rng.normal(0, 20, 400)
    sd1, sd2 = poincare_sd1_sd2(rr)
    diffs = np.diff(rr)
    assert sd1 == pytest.approx(np.std(diffs, ddof=1) / np.sqrt(2))
    assert sd2 == pytest.approx(np.sqrt(2 * np.std(rr, ddof=1) ** 2 - sd1 ** 2))
    # SD1 ≈ RMSSD/√2 cuando la media de las diferencias es ~0
    rmssd = np.sqrt(np.mean(diffs ** 2))
    assert sd1 == pytest.approx(rmssd / np.sqrt(2), rel=0.05)


def test_poincare_short_and_alternating_series():
    assert poincare_sd1_sd2([800, 810]) is None
    sd1, sd2 = poincare_sd1_sd2([700, 900] * 50)  # alternancia pura: todo es corto plazo
    assert sd1 > sd2
