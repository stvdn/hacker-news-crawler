import "server-only";

export const filters = {
  all: { label: "All stories", hint: "First 30 entries", description: "Original front-page order", order: "rank" },
  long: { label: "Long titles", hint: "More than 5 words", description: "Most comments first", order: "comments" },
  short: { label: "Short titles", hint: "5 words or fewer", description: "Most points first", order: "points" },
} as const;

export type EntryFilter = keyof typeof filters;
export type Entry = {
  number: number;
  title: string;
  points?: number;
  comments?: number;
};

export type Entries = {
  request_id: string;
  fetched_at: string;
  cache_hit: boolean;
  filter: EntryFilter;
  source_count: number;
  result_count: number;
  entries: Entry[];
};

type EntryPayload = Omit<Entry, "points" | "comments"> & {
  points?: unknown;
  comments?: unknown;
};

type EntriesPayload = Omit<Entries, "entries"> & {
  entries: EntryPayload[];
};

export type EntriesResult = { data: Entries; error?: never } | {
  data?: never;
  error: { message: string; requestId?: string };
};

function optionalMetric(value: unknown): number | undefined {
  // JSON uses null for unavailable metrics; frontend models use undefined.
  if (value === null || value === undefined) return undefined;
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error("Invalid entry metric");
  }
  return value;
}

export function isFilter(value: unknown): value is EntryFilter {
  return value === "all" || value === "long" || value === "short";
}

const messages: Record<number, string> = {
  422: "This filter is unavailable. Choose one of the three views above.",
  502: "Hacker News could not be read. Please try again shortly.",
  503: "Usage recording is temporarily unavailable. Please try again shortly.",
  504: "Hacker News took too long to respond. Please try again.",
};

export async function fetchEntries(filter: EntryFilter): Promise<EntriesResult> {
  try {
    const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
    const url = new URL("/api/v1/entries", base);
    url.searchParams.set("filter", filter);
    const response = await fetch(url, {
      cache: "no-store",
      // Longer than the scraper's timeouts, allowing time for usage persistence.
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      const requestId = response.headers.get("x-request-id");
      return { error: {
        message: messages[response.status] ?? "The stories could not be loaded. Please try again.",
        requestId: requestId && /^[\da-f-]{36}$/i.test(requestId) ? requestId : undefined,
      } };
    }
    const data: EntriesPayload = await response.json();
    // Fail safely if a proxy or incompatible API returns a different payload.
    if (!Array.isArray(data.entries) || data.filter !== filter ||
        !Number.isFinite(Date.parse(data.fetched_at))) {
      throw new Error("Invalid entries response");
    }
    return { data: {
      ...data,
      entries: data.entries.map((entry) => ({
        ...entry,
        points: optionalMetric(entry.points),
        comments: optionalMetric(entry.comments),
      })),
    } };
  } catch {
    return { error: { message: "The stories service could not be reached. Please try again shortly." } };
  }
}
