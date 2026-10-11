"""
Unit tests for Pydantic schema validation and domain invariants.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add code/src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "code" / "src"))

from schema import HistorySnapshot, IssueModel, RepoModel


def test_valid_history_snapshot():
    data = {
        "date": "2026-09-12",
        "iso_week": "2026-W37",
        "total_repos": 100,
        "total_issues": 116,
        "active_repos": 46,
        "zero_repos": 54,
        "concentration_pct": 42.2,
        "opened": 5,
        "closed": 9,
    }
    snapshot = HistorySnapshot.model_validate(data)
    assert snapshot.date == "2026-09-12"
    assert snapshot.iso_week == "2026-W37"
    assert snapshot.opened == 5
    assert snapshot.closed == 9


def test_valid_imputed_history_snapshot_with_null_stock():
    data = {
        "date": "2026-09-05",
        "iso_week": "2026-W36",
        "total_repos": None,
        "total_issues": None,
        "active_repos": None,
        "zero_repos": None,
        "concentration_pct": None,
        "opened": 6,
        "closed": 4,
    }
    snapshot = HistorySnapshot.model_validate(data)
    assert snapshot.date == "2026-09-05"
    assert snapshot.total_repos is None
    assert snapshot.opened == 6


def test_coherence_failure_between_date_and_iso_week():
    # 2026-09-12 is Saturday of 2026-W37, not 2026-W40
    data = {
        "date": "2026-09-12",
        "iso_week": "2026-W40",
        "total_repos": 100,
        "active_repos": 46,
        "zero_repos": 54,
    }
    with pytest.raises(ValidationError) as exc:
        HistorySnapshot.model_validate(data)
    assert "Coherence failure" in str(exc.value)


def test_stock_conservation_invariant_failure():
    # 60 + 30 = 90 != 100
    data = {
        "date": "2026-09-12",
        "iso_week": "2026-W37",
        "total_repos": 100,
        "active_repos": 60,
        "zero_repos": 30,
    }
    with pytest.raises(ValidationError) as exc:
        HistorySnapshot.model_validate(data)
    assert "Stock conservation invariant failed" in str(exc.value)


def test_negative_flux_validation_failure():
    data = {
        "date": "2026-09-12",
        "iso_week": "2026-W37",
        "opened": -1,
    }
    with pytest.raises(ValidationError) as exc:
        HistorySnapshot.model_validate(data)
    assert "greater_than_equal" in str(exc.value)


def test_concentration_pct_out_of_bounds():
    data = {
        "date": "2026-09-12",
        "iso_week": "2026-W37",
        "concentration_pct": 105.0,
    }
    with pytest.raises(ValidationError) as exc:
        HistorySnapshot.model_validate(data)
    assert "less_than_equal" in str(exc.value)


def test_repo_model_validation():
    valid = RepoModel.model_validate({"name": "ghpm", "description": "tool", "updatedAt": "2026-10-11T00:00:00Z"})
    assert valid.name == "ghpm"

    with pytest.raises(ValidationError):
        RepoModel.model_validate({"name": ""})


def test_issue_model_validation():
    valid = IssueModel.model_validate({"repo_name": "ghpm", "issue_number": 19, "title": "test"})
    assert valid.issue_number == 19

    with pytest.raises(ValidationError):
        IssueModel.model_validate({"repo_name": ""})
