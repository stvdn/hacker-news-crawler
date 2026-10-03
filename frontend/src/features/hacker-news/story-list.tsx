import { fetchEntries, filters, type EntryFilter } from "./entries";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function SortIndicator({ ascending = false }: { ascending?: boolean }) {
  return (
    <svg className="sort-indicator" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d={ascending ? "M8 13V3m-4 4 4-4 4 4" : "M8 3v10m-4-4 4 4 4-4"} />
    </svg>
  );
}

export async function StoryList({ filter }: { filter: EntryFilter }) {
  const result = await fetchEntries(filter);
  if (result.error) {
    return (
      <section className="notice" role="alert">
        <h2>Unable to load stories</h2>
        <p>{result.error.message}</p>
        <Button asChild className="mt-5"><a href={`/?filter=${filter}`}>Try again</a></Button>
        {result.error.requestId && <p className="request-id">Request ID: <code>{result.error.requestId}</code></p>}
      </section>
    );
  }
  const { data } = result;
  const timestamp = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "UTC",
  }).format(new Date(data.fetched_at));

  return (
    <section className="results-panel" aria-label="Story results">
      <div className="results-meta">
        <div className="result-summary">
          <p className="result-count"><strong>{data.result_count}</strong> of {data.source_count} stories</p>
          <p className="sort-description">{filters[filter].description}</p>
        </div>
        <p className="fetch-time">Fetched <time dateTime={data.fetched_at}>{timestamp} UTC</time></p>
      </div>
      {data.entries.length === 0 ? (
        <div className="empty-state">
          <h2>No matching stories</h2>
          <p>None of the fetched stories match this title length. Choose another view to explore the front page.</p>
          <Button asChild variant="outline" className="mt-5"><a href="/?filter=all">View all stories</a></Button>
        </div>
      ) : (
        <Table className="stories-table text-base" data-order={filters[filter].order}>
          <TableCaption className="sr-only">Hacker News stories with original rank, title, points, and comments</TableCaption>
          <TableHeader><TableRow>
            <TableHead scope="col" className="rank px-4 text-muted-foreground max-sm:px-2" aria-sort={filter === "all" ? "ascending" : undefined}>
              <span className="column-label">Rank {filter === "all" && <SortIndicator ascending />}</span>
            </TableHead>
            <TableHead scope="col" className="px-4 text-muted-foreground max-sm:px-2">Story</TableHead>
            <TableHead scope="col" className="metric px-4 text-right text-muted-foreground max-sm:px-2" aria-sort={filter === "short" ? "descending" : undefined}>
              <span className="column-label">Points {filter === "short" && <SortIndicator />}</span>
            </TableHead>
            <TableHead scope="col" className="metric px-4 text-right text-muted-foreground max-sm:px-2" aria-sort={filter === "long" ? "descending" : undefined}>
              <span className="column-label">Comments {filter === "long" && <SortIndicator />}</span>
            </TableHead>
          </TableRow></TableHeader>
          <TableBody>{data.entries.map((entry) => (
            <TableRow key={entry.number}>
              <TableCell className="rank px-4 py-4 align-top text-muted-foreground max-sm:px-2">{entry.number}</TableCell>
              <TableHead scope="row" className="story-title px-4 py-4 align-top font-medium whitespace-normal max-sm:px-2">{entry.title}</TableHead>
              <TableCell className="metric px-4 py-4 align-top max-sm:px-2">{entry.points ?? <span className="missing-metric" aria-label="Not available">—</span>}</TableCell>
              <TableCell className="metric px-4 py-4 align-top max-sm:px-2">{entry.comments ?? <span className="missing-metric" aria-label="Not available">—</span>}</TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
      )}
      <p className="table-note">Ranks reflect the original front page. <span className="note-divider" aria-hidden="true">/</span> <span>— means unavailable, not zero.</span></p>
    </section>
  );
}
