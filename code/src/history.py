"""
History tracking and velocity snapshot module.
Maintains data/final/history.jsonl and tracks week-over-week opened/closed issues.
"""

import contextlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from schema import HistorySnapshot

BASELINE_JSONL = Path("data/raw/baseline_history.jsonl")
HISTORY_JSONL = Path("data/final/history.jsonl")
OUTPUT_JSON = Path("data/final/dashboard_data.json")


def load_history() -> list[dict]:
    """Load historical snapshots from data/final/history.jsonl or baseline."""
    source = HISTORY_JSONL if HISTORY_JSONL.exists() else BASELINE_JSONL
    if not source.exists():
        return []
    snapshots = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            snapshots.append(json.loads(line))
    return snapshots


def update_history(repos: list[dict], issues: list[dict]) -> list[dict]:
    """
    Update or append weekly metrics snapshot to data/final/history.jsonl.
    Computes delta of opened and closed issues compared to previous snapshot.
    """
    today_dt = datetime.now(UTC)
    today = today_dt.strftime("%Y-%m-%d")
    iso_year, iso_week_num, _ = today_dt.isocalendar()
    iso_week = f"{iso_year}-W{iso_week_num:02d}"

    history = load_history()

    prev_issues = set()
    if OUTPUT_JSON.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            prev_data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
            prev_issues = {
                (x.get("repo_name"), str(x.get("issue_number")))
                for x in prev_data.get("issues", [])
            }

    curr_issues = {(x.get("repo_name"), str(x.get("issue_number"))) for x in issues}
    opened = len(curr_issues - prev_issues) if prev_issues else 0
    closed = len(prev_issues - curr_issues) if prev_issues else 0

    issues_by_repo = Counter(iss.get("repo_name") for iss in issues)
    total_repos = len(repos)
    total_issues = len(issues)
    active_repos = sum(1 for r in repos if issues_by_repo.get(r.get("name"), 0) > 0)
    zero_repos = total_repos - active_repos

    counts = sorted(issues_by_repo.values(), reverse=True)
    top5_sum = sum(counts[:5])
    conc_pct = round((top5_sum / total_issues * 100), 1) if total_issues > 0 else 0.0

    existing_entry = next((e for e in history if e.get("iso_week") == iso_week), None)
    if not existing_entry:
        existing_entry = {"date": today, "iso_week": iso_week}
        history.append(existing_entry)
    elif opened == 0 and closed == 0:
        opened = existing_entry.get("opened", 0)
        closed = existing_entry.get("closed", 0)

    updated_snapshot = {
        "date": today,
        "iso_week": iso_week,
        "total_repos": total_repos,
        "total_issues": total_issues,
        "active_repos": active_repos,
        "zero_repos": zero_repos,
        "concentration_pct": conc_pct,
        "opened": opened,
        "closed": closed,
    }

    # Validate snapshot against schema invariants
    validated = HistorySnapshot.model_validate(updated_snapshot)
    existing_entry.update(validated.model_dump())

    HISTORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_JSONL, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(entry) + "\n" for entry in history)

    print(f"Updated {HISTORY_JSONL} ({len(history)} snapshots recorded)")
    return history
