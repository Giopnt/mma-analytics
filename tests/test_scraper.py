"""
Unit tests for the ingestion (scraper) layer.
Tests pure functions that don't require network access.
"""

import pytest
from ingestion.events import _parse_date, _extract_event_id
from ingestion.fights import _parse_round, _classify_result
from ingestion.rounds import _parse_landed_attempted, _parse_time_seconds
from ingestion.utils  import content_hash


# ── events.py ─────────────────────────────────────────────────────────────────

class TestParseDate:
    def test_full_date(self):
        assert _parse_date("March 09, 2024") == "2024-03-09"

    def test_already_iso(self):
        assert _parse_date("2024-03-09") == "2024-03-09"

    def test_short_month(self):
        assert _parse_date("Jan. 01, 2023") == "2023-01-01"

    def test_empty_string(self):
        # Falls back to returning raw string
        assert _parse_date("") == ""

    def test_whitespace(self):
        assert _parse_date("  March 09, 2024  ") == "2024-03-09"


class TestExtractEventId:
    def test_valid_url(self):
        url = "http://ufcstats.com/event-details/abc123def456"
        assert _extract_event_id(url) == "abc123def456"

    def test_no_match(self):
        assert _extract_event_id("http://ufcstats.com/other") is None

    def test_empty(self):
        assert _extract_event_id("") is None


# ── fights.py ─────────────────────────────────────────────────────────────────

class TestParseRound:
    def test_valid_int(self):
        assert _parse_round("3") == 3

    def test_empty(self):
        assert _parse_round("") == 0

    def test_non_numeric(self):
        assert _parse_round("abc") == 0

    def test_whitespace(self):
        assert _parse_round("  2  ") == 2


class TestClassifyResult:
    def test_win(self):
        assert _classify_result("KO/TKO") == "win"
        assert _classify_result("U-DEC") == "win"
        assert _classify_result("SUB") == "win"

    def test_no_contest(self):
        assert _classify_result("No Contest") == "nc"
        assert _classify_result("no contest") == "nc"

    def test_draw(self):
        assert _classify_result("Draw") == "draw"

    def test_dq(self):
        assert _classify_result("DQ") == "dq"
        assert _classify_result("Disqualification") == "dq"


# ── rounds.py ─────────────────────────────────────────────────────────────────

class TestParseLandedAttempted:
    def test_standard_format(self):
        assert _parse_landed_attempted("34 of 78") == {"landed": 34, "attempted": 78}

    def test_case_insensitive(self):
        assert _parse_landed_attempted("34 Of 78") == {"landed": 34, "attempted": 78}

    def test_zero_values(self):
        assert _parse_landed_attempted("0 of 0") == {"landed": 0, "attempted": 0}

    def test_invalid(self):
        result = _parse_landed_attempted("N/A")
        assert result["landed"] == 0
        assert result["attempted"] == 0

    def test_landed_never_exceeds_attempted(self):
        result = _parse_landed_attempted("10 of 20")
        assert result["landed"] <= result["attempted"]


class TestParseTimeSeconds:
    def test_standard(self):
        assert _parse_time_seconds("4:32") == 272

    def test_zero(self):
        assert _parse_time_seconds("0:00") == 0

    def test_five_minutes(self):
        assert _parse_time_seconds("5:00") == 300

    def test_invalid(self):
        assert _parse_time_seconds("N/A") == 0

    def test_whitespace(self):
        assert _parse_time_seconds("  3:45  ") == 225


# ── utils.py ──────────────────────────────────────────────────────────────────

class TestContentHash:
    def test_same_content(self):
        a = {"event_id": "123", "fights": []}
        b = {"event_id": "123", "fights": []}
        assert content_hash(a) == content_hash(b)

    def test_different_content(self):
        a = {"event_id": "123"}
        b = {"event_id": "456"}
        assert content_hash(a) != content_hash(b)

    def test_key_order_irrelevant(self):
        a = {"b": 2, "a": 1}
        b = {"a": 1, "b": 2}
        assert content_hash(a) == content_hash(b)

    def test_returns_string(self):
        assert isinstance(content_hash({}), str)

    def test_hash_length(self):
        # SHA-256 hex = 64 chars
        assert len(content_hash({"x": 1})) == 64
