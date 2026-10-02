from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models import Entry, EntrySnapshot


@pytest.mark.parametrize("number", [0, -1, True, 1.5])
def test_entry_requires_positive_integer_rank(number: int | float) -> None:
    with pytest.raises(ValueError, match="number"):
        Entry(number, "title", None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("title", ["", " \t\n"])
def test_entry_requires_nonblank_title(title: str) -> None:
    with pytest.raises(ValueError, match="title"):
        Entry(1, title, None, None)


@pytest.mark.parametrize(
    ("points", "comments", "metric"),
    [
        (-1, None, "points"),
        (True, None, "points"),
        (1.5, None, "points"),
        (None, -1, "comments"),
        (None, True, "comments"),
        (None, 1.5, "comments"),
    ],
)
def test_entry_rejects_invalid_metric(
    points: int | float | None, comments: int | float | None, metric: str
) -> None:
    with pytest.raises(ValueError, match=metric):
        Entry(1, "title", points, comments)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [None, 0, 12])
def test_entry_accepts_missing_and_nonnegative_metrics(value: int | None) -> None:
    entry = Entry(1, "title", value, value)

    assert entry.points == value
    assert entry.comments == value


def test_entries_and_snapshots_are_immutable() -> None:
    entry = Entry(1, "title", 0, None)
    snapshot = EntrySnapshot((entry,), datetime(2026, 1, 1, tzinfo=UTC), False)

    with pytest.raises(FrozenInstanceError):
        entry.points = 12  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.cache_hit = True  # type: ignore[misc]


def test_snapshot_rejects_mutable_entries() -> None:
    with pytest.raises(ValueError, match="tuple"):
        EntrySnapshot(
            entries=[Entry(1, "title", None, None)],  # type: ignore[arg-type]
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            cache_hit=False,
        )


@pytest.mark.parametrize(
    "fetched_at",
    [
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_snapshot_requires_utc_fetch_time(fetched_at: datetime) -> None:
    with pytest.raises(ValueError, match="UTC"):
        EntrySnapshot(entries=(), fetched_at=fetched_at, cache_hit=False)
