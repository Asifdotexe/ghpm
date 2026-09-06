"""
Module responsible for fetching the github issues associated with a given list of github repositories.
"""

import csv
import json
from pathlib import Path
import re
import subprocess

USERNAME = "Asifdotexe"
CSV_FILE = Path("data/interim/repos.csv")
OUTPUT_FILE = Path("data/interim/issues.csv")
TEMP_OUTPUT_FILE = Path("data/interim/issues.csv.tmp")
REPO_NAME_REGEX = re.compile(r"^[a-zA-Z0-9._-]+$")


def sanitize_csv_cell(value: object) -> object:
    """
    Sanitize values to prevent CSV formula injection (DDE attacks) in spreadsheet tools.

    :param value: Cell value to sanitize.
    :return: Sanitized cell value.
    """
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{value}"
    return value


def handle_gh_error(repo_name: str, stderr: str) -> bool:
    """
    Handle GitHub CLI errors.

    :param repo_name: Name of the GitHub repository.
    :param stderr: Standard error output from the gh command.
    :return: True if error is benign and the repo should be skipped, False otherwise.
    """
    err = stderr.lower()

    if "disabled issues" in err or "issues are disabled" in err:
        print(f"Skipping '{repo_name}': repository has disabled issues.")
        return True

    if "could not resolve to a repository" in err or "not found" in err:
        print(f"Warning: '{repo_name}' not found or inaccessible. Skipping.")
        return True

    if "rate limit" in err:
        raise RuntimeError(f"GitHub API rate limit exceeded: {stderr.strip()}")

    if "authentication" in err or "credentials" in err:
        raise PermissionError(f"GitHub CLI authentication failed: {stderr.strip()}")

    raise RuntimeError(f"Failed to fetch issues for '{repo_name}': {stderr.strip()}")


def main() -> None:
    """
    Fetch github issue information for all the repository given under the repository CSV file.
    """
    fieldnames = ["repo_name", "issue_number", "title", "labels"]
    total_issues = 0

    try:
        with open(CSV_FILE, mode="r", encoding="utf-8") as in_f, \
             open(TEMP_OUTPUT_FILE, mode="w", encoding="utf-8", newline="") as out_f:
            reader = csv.DictReader(in_f)
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()

            for row_idx, row in enumerate(reader, start=2):
                repo_name = row.get("name")
                if not repo_name or not repo_name.strip():
                    raise ValueError(
                        f"Row {row_idx} in '{CSV_FILE}' is missing a valid 'name' value. "
                        "Ensure the CSV has a 'name' column and no blank entries."
                    )

                repo_name = repo_name.strip()
                if not REPO_NAME_REGEX.match(repo_name):
                    raise ValueError(
                        f"Row {row_idx} in '{CSV_FILE}' has invalid repo name '{repo_name}'. "
                        "Repo names must contain only alphanumeric characters, '.', '_', or '-'."
                    )

                print(f"Fetch issues. Repo: {repo_name}")
                cmd = ["gh", "issue", "list", "--repo", f"{USERNAME}/{repo_name}", "--json", "number,title,labels"]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    if handle_gh_error(repo_name, result.stderr):
                        continue

                for issue in json.loads(result.stdout):
                    writer.writerow({
                        "repo_name": sanitize_csv_cell(repo_name),
                        "issue_number": issue.get("number"),
                        "title": sanitize_csv_cell(issue.get("title")),
                        "labels": sanitize_csv_cell(", ".join(lbl["name"] for lbl in issue.get("labels", []))),
                    })
                    total_issues += 1

        TEMP_OUTPUT_FILE.replace(OUTPUT_FILE)
        print(f"Done. Saved {total_issues} issues to {OUTPUT_FILE}")
    except Exception:
        if TEMP_OUTPUT_FILE.exists():
            TEMP_OUTPUT_FILE.unlink()
        raise


if __name__ == "__main__":
    main()
