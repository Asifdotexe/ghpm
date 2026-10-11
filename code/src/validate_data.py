"""
Validation CLI to enforce schema integrity on dataset files.
Fails fast with detailed diagnostics before dashboard compilation.
"""

import csv
import sys
from pathlib import Path

from pydantic import ValidationError
from schema import HistorySnapshot, IssueModel, RepoModel

REPOS_CSV = Path("data/interim/repos.csv")
ISSUES_CSV = Path("data/interim/issues.csv")
HISTORY_JSONL = Path("data/final/history.jsonl")


def _validate_rows(path: Path, model_cls, is_jsonl: bool, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"{path}: File does not exist")
        return
    with open(path, encoding="utf-8") as f:
        rows = (line.strip() for line in f if line.strip()) if is_jsonl else enumerate(csv.DictReader(f), start=2)
        for item in rows:
            idx, data = (None, item) if is_jsonl else item
            try:
                model_cls.model_validate_json(data) if is_jsonl else model_cls.model_validate(data)
            except ValidationError as e:
                loc = f"{path}:{idx}" if idx else path
                errors.append(f"{loc}: {e}")


def validate_all() -> bool:
    """
    Validate all repository, issue, and historical snapshot files against Pydantic schemas.

    :return: True if all datasets conform to schemas, False otherwise.
    """
    errors: list[str] = []
    _validate_rows(REPOS_CSV, RepoModel, False, errors)
    _validate_rows(ISSUES_CSV, IssueModel, False, errors)
    _validate_rows(HISTORY_JSONL, HistorySnapshot, True, errors)

    if errors:
        print(f"FAILED: {len(errors)} dataset validation error(s) found:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.")
        return False

    print("SUCCESS: All datasets (repos, issues, history.jsonl) conform strictly to schemas.")
    return True


if __name__ == "__main__":
    if not validate_all():
        sys.exit(1)
