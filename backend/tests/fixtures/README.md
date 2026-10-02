# Scraper fixtures

`front_page.html` is synthetic HTML modeled on the Hacker News markup inspected
on 2026-10-02 (UTC). It preserves the relevant structure: nested layout tables,
`athing submission` story rows, voting links, `sitebit comhead` domain links,
`subline` metadata wrappers, `hnuser` links, age timestamps, spacer rows, and the
More link. The hiring entry has no voting link and only age metadata.

Titles, IDs, timestamps, and metrics are controlled test data, not a captured
live front page. There are deliberately 31 entries to check the 30-entry limit,
plus missing metrics, discuss, singular/plural metrics, nonbreaking spaces, and
HTML entities. Page chrome is abbreviated; styles and scripts are omitted.

`upstream_error.html` represents an HTML error page returned with HTTP 200.
Tests derive malformed variants of the front page in memory to exercise missing
or invalid required fields and missing metadata without duplicating the fixture.
Ordinary tests never access the network.
