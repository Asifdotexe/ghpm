"""
History tracking and velocity snapshot module.
Maintains data/final/history.json and tracks week-over-week opened/closed issues.
"""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

BASELINE_JSON = Path("data/raw/baseline_history.json")
HISTORY_JSON = Path("data/final/history.json")
OUTPUT_JSON = Path("data/final/dashboard_data.json")


def update_history(repos: list[dict], issues: list[dict]) -> list[dict]:
    """
    Update or append weekly metrics snapshot to data/final/history.json.
    Computes delta of opened and closed issues compared to previous snapshot.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    source = HISTORY_JSON if HISTORY_JSON.exists() else BASELINE_JSON
    history = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []

    prev_issues = set()
    if OUTPUT_JSON.exists():
        try:
            prev_data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
            prev_issues = {
                (x.get("repo_name"), str(x.get("issue_number")))
                for x in prev_data.get("issues", [])
            }
        except Exception:
            pass

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

    entry = next((e for e in history if e.get("date") == today), None)
    if not entry:
        entry = {"date": today}
        history.append(entry)
    elif opened == 0 and closed == 0:
        opened = entry.get("opened", 0)
        closed = entry.get("closed", 0)

    entry.update({
        "total_repos": total_repos,
        "total_issues": total_issues,
        "active_repos": active_repos,
        "zero_repos": zero_repos,
        "concentration_pct": conc_pct,
        "opened": opened,
        "closed": closed,
    })

    HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_JSON.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Updated {HISTORY_JSON} ({len(history)} snapshots recorded)")
    return history
