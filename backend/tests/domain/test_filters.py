import pytest

from app.domain.filters import count_title_words, filter_entries
from app.domain.models import Entry, EntryFilter


def entry(
    number: int,
    title: str,
    *,
    points: int | None = None,
    comments: int | None = None,
) -> Entry:
    return Entry(number=number, title=title, points=points, comments=comments)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("", 0),
        (" \t\n", 0),
        ("This is - a self-explained example", 5),
        ("C++ and Python", 3),
        ("Hello — world", 2),
        ("  one\t two\nthree\u2003four  ", 4),
        ("你好 café ١٢٣", 3),
        ("*** — 🙂", 0),
        ("state-of-the-art - 42", 2),
    ],
)
def test_count_title_words(title: str, expected: int) -> None:
    assert count_title_words(title) == expected


def test_all_restores_original_rank() -> None:
    entries = [
        entry(3, "third"),
        entry(1, "first"),
        entry(2, "second"),
    ]

    result = filter_entries(entries, EntryFilter.ALL)

    assert [item.number for item in result] == [1, 2, 3]


def test_long_requires_more_than_five_words_and_sorts_comments_descending() -> None:
    entries = (
        entry(1, "one two three four five", comments=100),
        entry(2, "one two three four five six", comments=2),
        entry(3, "one two three four five six seven", comments=15),
    )

    result = filter_entries(entries, EntryFilter.LONG)

    assert [item.number for item in result] == [3, 2]


def test_short_includes_five_words_and_sorts_points_descending() -> None:
    entries = (
        entry(1, "one two three four five six", points=100),
        entry(2, "one two three four five", points=2),
        entry(3, "one two three four", points=15),
    )

    assert [item.number for item in filter_entries(entries, EntryFilter.SHORT)] == [
        3,
        2,
    ]


@pytest.mark.parametrize(
    ("entry_filter", "metric"),
    [(EntryFilter.LONG, "comments"), (EntryFilter.SHORT, "points")],
)
def test_metric_ties_use_rank_and_nulls_sort_last(
    entry_filter: EntryFilter, metric: str
) -> None:
    title = (
        "one two three four five six"
        if entry_filter == EntryFilter.LONG
        else "short"
    )
    entries = (
        entry(5, title, **{metric: None}),
        entry(4, title, **{metric: 0}),
        entry(3, title, **{metric: 10}),
        entry(2, title, **{metric: 10}),
        entry(1, title, **{metric: None}),
    )

    assert [item.number for item in filter_entries(entries, entry_filter)] == [
        2,
        3,
        4,
        1,
        5,
    ]


def test_unknown_filter_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="unknown entry filter"):
        filter_entries((), "other")  # type: ignore[arg-type]


@pytest.mark.parametrize("entry_filter", list(EntryFilter))
def test_filters_leave_source_unchanged(entry_filter: EntryFilter) -> None:
    entries = [
        entry(3, "one two three four five six", points=20, comments=10),
        entry(1, "short", points=10, comments=20),
        entry(2, "another short", points=30, comments=None),
    ]
    original = tuple(entries)

    filter_entries(entries, entry_filter)

    assert tuple(entries) == original


@pytest.mark.parametrize("entry_filter", list(EntryFilter))
def test_empty_source_returns_no_entries(entry_filter: EntryFilter) -> None:
    assert filter_entries((), entry_filter) == ()


@pytest.mark.parametrize(
    ("entry_filter", "title"),
    [
        (EntryFilter.LONG, "one two three four five"),
        (EntryFilter.SHORT, "one two three four five six"),
    ],
)
def test_no_matching_entries_returns_empty_result(
    entry_filter: EntryFilter, title: str
) -> None:
    assert filter_entries((entry(1, title),), entry_filter) == ()
