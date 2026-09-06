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
        # Escape characters that could break out of or prematurely terminate an HTML script tag
        raw_json = json.dumps(data)
        escaped_json = (
            raw_json.replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
        replacement = f"let DB = {escaped_json};"
        # Match let DB = <json>; across lines without stopping prematurely on internal semicolons
        new_content, count = re.subn(
            r"let DB = .*?;\s*(?=\n\s*(?:let|const|var|function|window|\binit\b|\brender))",
            lambda _: replacement + "\n    ",
            content,
            count=1,
            flags=re.DOTALL,
        )
        if count == 0:
            # Fallback for single-line format
            new_content = re.sub(
                r"let DB = .*?;",
                lambda _: replacement,
                content,
                count=1,
            )
        INDEX_HTML.write_text(new_content, encoding="utf-8")
        print(f"Injected fresh data into {INDEX_HTML}")


def main() -> None:
    """Run data compilation and HTML injection pipeline."""
    data = build_dashboard_data()
    inject_into_html(data)
    print("Dashboard build complete!")


if __name__ == "__main__":
    main()
