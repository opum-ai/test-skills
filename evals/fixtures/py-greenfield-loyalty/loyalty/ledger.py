"""A loyalty member and the ledger of points they have earned."""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple


class LedgerError(ValueError):
    """Raised for an invalid ledger operation."""


@dataclass(frozen=True)
class Member:
    member_id: str
    name: str
    joined_on: date

    def __post_init__(self):
        if not self.member_id.strip():
            raise ValueError("member_id is required")


@dataclass
class PointsLedger:
    """Append-only record of points credited to one member."""

    member: Member
    _entries: List[Tuple[int, str]] = field(default_factory=list, repr=False)

    def earn(self, points: int, reason: str = "") -> int:
        """Credit `points` (a positive whole number) and return the new balance."""
        if isinstance(points, bool) or not isinstance(points, int):
            raise LedgerError("points must be a whole number")
        if points <= 0:
            raise LedgerError("points must be positive")
        self._entries.append((points, reason))
        return self.balance

    @property
    def balance(self) -> int:
        return sum(points for points, _ in self._entries)

    def entries(self) -> List[Tuple[int, str]]:
        """A copy of the ledger, oldest first."""
        return list(self._entries)
