"""
Build script to compile CSV interim data into data/dashboard_data.json
and inject it into index.html for static/serverless hosting.
"""

import csv
import json
import re
from pathlib import Path

REPOS_CSV = Path("data/interim/repos.csv")
ISSUES_CSV = Path("data/interim/issues.csv")
OUTPUT_JSON = Path("data/final/dashboard_data.json")
INDEX_HTML = Path("index.html")


def build_dashboard_data() -> dict:
    """
    Read interim CSV files and generate bundled dashboard dataset.

    :return: Dictionary containing repos and issues lists.
    """
    with open(REPOS_CSV, mode="r", encoding="utf-8") as f:
        repos = list(csv.DictReader(f))

    with open(ISSUES_CSV, mode="r", encoding="utf-8") as f:
        issues = list(csv.DictReader(f))

    data = {"repos": repos, "issues": issues}
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Created {OUTPUT_JSON} ({len(repos)} repos, {len(issues)} issues)")
    return data


def inject_into_html(data: dict) -> None:
    """
    Embed dataset directly into index.html for serverless deployment.

    :param data: Dashboard dictionary containing repos and issues.
    """
    if INDEX_HTML.exists():
        content = INDEX_HTML.read_text(encoding="utf-8")
        replacement = f"let DB = {json.dumps(data)};"
        INDEX_HTML.write_text(
            re.sub(r"let DB = .*?;", lambda _: replacement, content, count=1),
            encoding="utf-8",
        )
        print(f"Injected fresh data into {INDEX_HTML}")


def main() -> None:
    """Run data compilation and HTML injection pipeline."""
    data = build_dashboard_data()
    inject_into_html(data)
    print("Dashboard build complete!")


if __name__ == "__main__":
    main()
