"""
Pydantic schemas and domain invariant validators for ghpm datasets.
"""

import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ISO_WEEK_REGEX = re.compile(r"^\d{4}-W\d{2}$")


class RepoModel(BaseModel):
    """Schema representing a tracked GitHub repository entry."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    description: str = ""
    updatedAt: str = ""


class IssueModel(BaseModel):
    """Schema representing a tracked GitHub issue item."""

    model_config = ConfigDict(extra="ignore")

    repo_name: str = Field(..., min_length=1)
    issue_number: int | str
    title: str = ""
    labels: str = ""


class HistorySnapshot(BaseModel):
    """
    Schema representing a point-in-time weekly velocity and backlog snapshot.
    Enforces strict mathematical coherence between calendar dates and ISO weeks,
    and conservation of stock repository states.
    """

    model_config = ConfigDict(extra="ignore")

    date: str
    iso_week: str
    total_repos: int | None = Field(default=None, ge=0)
    total_issues: int | None = Field(default=None, ge=0)
    active_repos: int | None = Field(default=None, ge=0)
    zero_repos: int | None = Field(default=None, ge=0)
    concentration_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    opened: int = Field(default=0, ge=0)
    closed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_domain_invariants(self) -> Self:
        # 1. Format check
        if not ISO_WEEK_REGEX.match(self.iso_week):
            raise ValueError(f"Invalid iso_week format '{self.iso_week}', expected YYYY-Www")

        # 2. Mathematical coherence between date and ISO week (strptime verifies YYYY-MM-DD)
        dt = datetime.strptime(self.date, "%Y-%m-%d").date()
        iso_year, iso_week_num, _ = dt.isocalendar()
        expected_week = f"{iso_year}-W{iso_week_num:02d}"
        if self.iso_week != expected_week:
            raise ValueError(
                f"Coherence failure: date '{self.date}' belongs to ISO week '{expected_week}', "
                f"not '{self.iso_week}'"
            )

        # 3. Stock conservation invariant
        if (
            self.total_repos is not None
            and self.active_repos is not None
            and self.zero_repos is not None
            and (self.active_repos + self.zero_repos != self.total_repos)
        ):
            raise ValueError(
                f"Stock conservation invariant failed: active_repos ({self.active_repos}) + "
                f"zero_repos ({self.zero_repos}) != total_repos ({self.total_repos})"
            )

        return self
