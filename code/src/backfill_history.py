"""
Historical issue velocity backfill script.
Surgically imputes opened and closed issue counts for any requested date range
via the GitHub Search API without overwhelming rate limits.
"""

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from build_dashboard import inject_into_html

HISTORY_JSON = Path("data/final/history.json")
BASELINE_JSON = Path("data/raw/baseline_history.json")
OUTPUT_JSON = Path("data/final/dashboard_data.json")


def get_github_token() -> str:
    """Retrieve GitHub token from environment variables or gh CLI."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def fetch_search_issues(query: str, token: str, max_pages: int = 10) -> list[dict]:
    """
    Query GitHub Search API with pagination and rate limit protections.

    :param query: GitHub search query string.
    :param token: Personal Access Token or GitHub token.
    :param max_pages: Safety cap on pagination requests (max 1,000 results).
    :return: List of issue items returned by GitHub.
    """
    items = []
    base_url = "https://api.github.com/search/issues"

    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            "q": query,
            "per_page": 100,
            "page": page,
        })
        url = f"{base_url}?{params}"

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ghpm-backfill",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) <= 3:
                    print(f"Warning: Low rate limit remaining ({remaining}). Pausing 5s...")
                    time.sleep(5.0)

                payload = json.loads(resp.read().decode("utf-8"))
                batch = payload.get("items", [])
                total_count = payload.get("total_count", 0)
                items.extend(batch)

                print(f"  Search page {page}: fetched {len(batch)} items (total found: {total_count})")

                if len(batch) < 100 or len(items) >= total_count:
                    break

                # Respect Search API rate limit (30 req/min for authenticated)
                time.sleep(1.0)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset_time = e.headers.get("X-RateLimit-Reset")
                wait_sec = 60
                if reset_time:
                    wait_sec = max(1, int(reset_time) - int(time.time()))
                print(f"Rate limited by GitHub API (403). Reset in {wait_sec}s. Error: {e.read().decode('utf-8')}")
                raise
            raise

    return items


def enumerate_iso_weeks(start_date_str: str, end_date_str: str) -> list[dict]:
    """
    Enumerate all distinct ISO weeks overlapping the start and end dates.
    Returns list of dicts with iso_week and canonical Saturday date.
    """
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date_str}) must be <= end_date ({end_date_str})")

    curr = start_dt
    seen_weeks = set()
    weeks = []

    while curr <= end_dt:
        iso_year, iso_week, _ = curr.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        if week_key not in seen_weeks:
            seen_weeks.add(week_key)
            sat_date = date.fromisocalendar(iso_year, iso_week, 6).strftime("%Y-%m-%d")
            weeks.append({"iso_week": week_key, "date": sat_date})
        curr += timedelta(days=1)

    return weeks


def count_by_iso_week(issues: list[dict], field: str) -> Counter:
    """Bucket issues into ISO week strings by specified timestamp field."""
    counts = Counter()
    for issue in issues:
        raw = issue.get(field)
        if raw:
            dt = datetime.fromisoformat(raw)
            y, w, _ = dt.isocalendar()
            counts[f"{y}-W{w:02d}"] += 1
    return counts


def backfill_history(
    start_date: str,
    end_date: str,
    username: str = "Asifdotexe",
    overwrite_flux: bool = False,
    dry_run: bool = False,
) -> list[dict]:
    """
    Backfill opened and closed issue counts for weeks between start_date and end_date.

    :param start_date: ISO date string 'YYYY-MM-DD'.
    :param end_date: ISO date string 'YYYY-MM-DD'.
    :param username: GitHub username or organization name.
    :param overwrite_flux: If True, overwrite non-zero existing week flux counts.
    :param dry_run: If True, calculate and preview changes without modifying files.
    :return: Updated history snapshots list.
    """
    token = get_github_token()
    if not token:
        print("Warning: No GitHub token found (GH_TOKEN/GITHUB_TOKEN/gh auth). Search API rate limits will be restricted to 10 req/min.")

    print(f"Target date range: {start_date} to {end_date} (user: {username})")
    target_weeks = enumerate_iso_weeks(start_date, end_date)
    print(f"Target ISO weeks to impute/check ({len(target_weeks)}): {[w['iso_week'] for w in target_weeks]}")

    created_issues = fetch_search_issues(f"user:{username} type:issue created:{start_date}..{end_date}", token)
    closed_issues = fetch_search_issues(f"user:{username} type:issue closed:{start_date}..{end_date}", token)

    opened_by_week = count_by_iso_week(created_issues, "created_at")
    closed_by_week = count_by_iso_week(closed_issues, "closed_at")

    source = HISTORY_JSON if HISTORY_JSON.exists() else BASELINE_JSON
    history = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []

    existing_by_week = {e.get("iso_week"): e for e in history}

    imputed_count = 0
    updated_count = 0

    for w_info in target_weeks:
        w_key = w_info["iso_week"]
        op_count = opened_by_week.get(w_key, 0)
        cl_count = closed_by_week.get(w_key, 0)

        if w_key in existing_by_week:
            entry = existing_by_week[w_key]
            is_zero = entry.get("opened", 0) == 0 and entry.get("closed", 0) == 0
            if overwrite_flux or is_zero:
                print(f"  [Update] {w_key}: opened {entry.get('opened')} -> {op_count}, closed {entry.get('closed')} -> {cl_count}")
                entry["opened"] = op_count
                entry["closed"] = cl_count
                updated_count += 1
            else:
                print(f"  [Keep]   {w_key}: keeping existing flux opened={entry.get('opened')}, closed={entry.get('closed')}")
        else:
            print(f"  [Impute] {w_key} ({w_info['date']}): opened={op_count}, closed={cl_count}")
            new_entry = {
                "date": w_info["date"],
                "iso_week": w_key,
                "total_repos": None,
                "total_issues": None,
                "active_repos": None,
                "zero_repos": None,
                "concentration_pct": None,
                "opened": op_count,
                "closed": cl_count,
            }
            history.append(new_entry)
            existing_by_week[w_key] = new_entry
            imputed_count += 1

    history.sort(key=lambda x: (x.get("date", ""), x.get("iso_week", "")))

    print(f"\nSummary: {imputed_count} weeks imputed, {updated_count} weeks updated, total snapshots: {len(history)}")

    if dry_run:
        print("[Dry Run] No files modified.")
        return history

    HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_JSON.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Saved updated history to {HISTORY_JSON}")

    if OUTPUT_JSON.exists():
        dashboard_data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        dashboard_data["history"] = history
        OUTPUT_JSON.write_text(json.dumps(dashboard_data, indent=2), encoding="utf-8")
        inject_into_html(dashboard_data)
        print("Updated dashboard_data.json and injected into index.html")

    return history


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical issue velocity snapshots via GitHub Search API.")
    parser.add_argument("--start-date", default="2026-09-01", help="Start date YYYY-MM-DD (default: 2026-09-01)")
    parser.add_argument("--end-date", default="2026-09-30", help="End date YYYY-MM-DD (default: 2026-09-30)")
    parser.add_argument("--username", default="Asifdotexe", help="GitHub username or org (default: Asifdotexe)")
    parser.add_argument("--overwrite-flux", action="store_true", help="Overwrite existing opened/closed metrics with API values")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to disk")

    args = parser.parse_args()
    backfill_history(
        start_date=args.start_date,
        end_date=args.end_date,
        username=args.username,
        overwrite_flux=args.overwrite_flux,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
