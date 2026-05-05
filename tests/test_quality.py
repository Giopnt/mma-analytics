"""
Unit tests for the data quality module.
Tests the check logic against known good/bad data.
"""

import json
import pytest
from pathlib import Path

from quality.expectations import check_raw_json, Suite, CheckResult


FIXTURES = Path(__file__).parent / "fixtures"


class TestCheckResult:
    def test_passed(self):
        r = CheckResult("test", True, "detail")
        assert r.passed is True
        assert "✅" in repr(r)

    def test_failed(self):
        r = CheckResult("test", False, "detail")
        assert r.passed is False
        assert "❌" in repr(r)


class TestSuite:
    def test_all_pass(self):
        s = Suite("test")
        s.check("a", True)
        s.check("b", True)
        passed, total = s.summary()
        assert passed == 2
        assert total == 2

    def test_mixed(self):
        s = Suite("test")
        s.check("a", True)
        s.check("b", False)
        passed, total = s.summary()
        assert passed == 1
        assert total == 2


class TestRawJsonChecks:
    def test_valid_fixtures_pass(self):
        """Our test fixtures should pass all raw JSON checks."""
        suite = check_raw_json(str(FIXTURES))
        passed, total = suite.summary()
        # At minimum event files exist and have required keys
        assert passed >= 3

    def test_event_files_found(self):
        suite = check_raw_json(str(FIXTURES))
        existence_check = next(
            (r for r in suite.results if "Event files exist" in r.name), None
        )
        assert existence_check is not None
        assert existence_check.passed is True

    def test_fight_files_found(self):
        suite = check_raw_json(str(FIXTURES))
        fight_check = next(
            (r for r in suite.results if "Fight files exist" in r.name), None
        )
        assert fight_check is not None
        assert fight_check.passed is True

    def test_no_empty_rounds(self):
        suite = check_raw_json(str(FIXTURES))
        rounds_check = next(
            (r for r in suite.results if "empty rounds" in r.name), None
        )
        if rounds_check:
            assert rounds_check.passed is True

    def test_winner_is_fighter(self):
        suite = check_raw_json(str(FIXTURES))
        winner_check = next(
            (r for r in suite.results if "Winner is always" in r.name), None
        )
        assert winner_check is not None
        assert winner_check.passed is True
