"""Pure title counting, selection, and ordering rules."""

from collections.abc import Sequence

from app.domain.models import Entry, EntryFilter


def count_title_words(title: str) -> int:
    """Count whitespace-delimited tokens containing a Unicode letter or digit."""
    return sum(
        any(character.isalpha() or character.isdigit() for character in token)
        for token in title.split()
    )


def filter_entries(
    entries: Sequence[Entry], entry_filter: EntryFilter
) -> tuple[Entry, ...]:
    """Select and order entries without changing their original snapshot."""
    if entry_filter == EntryFilter.ALL:
        return tuple(sorted(entries, key=lambda entry: entry.number))
    if entry_filter == EntryFilter.LONG:
        selected = (entry for entry in entries if count_title_words(entry.title) > 5)
        return tuple(
            sorted(
                selected,
                key=lambda entry: (
                    entry.comments is None,
                    -(entry.comments or 0),
                    entry.number,
                ),
            )
        )
    if entry_filter == EntryFilter.SHORT:
        selected = (entry for entry in entries if count_title_words(entry.title) <= 5)
        return tuple(
            sorted(
                selected,
                key=lambda entry: (
                    entry.points is None,
                    -(entry.points or 0),
                    entry.number,
                ),
            )
        )
    raise ValueError(f"unknown entry filter: {entry_filter}")
