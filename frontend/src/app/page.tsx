import { Suspense } from "react";
import { filters, isFilter } from "@/features/hacker-news/entries";
import { StoryList } from "@/features/hacker-news/story-list";
import { Button } from "@/components/ui/button";
import { StoryLoading } from "@/features/hacker-news/story-loading";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { filter: parameter } = await searchParams;
  const filter = parameter === undefined ? "all" : parameter;
  const valid = isFilter(filter);

  return (
    <main id="main">
      <div className="intro">
        <h1>Explore the front page.</h1>
        <p>The first 30 Hacker News stories. Browse the original ranking, or filter by title length to surface the most discussed and highest-scoring entries.</p>
      </div>
      <nav className="filters" aria-label="Filter stories">
        {Object.entries(filters).map(([value, option]) => (
          <Button key={value} asChild variant="ghost" className="filter-control h-auto justify-start rounded-md whitespace-normal">
            <a href={`/?filter=${value}`} aria-current={filter === value ? "page" : undefined} aria-labelledby={`label-${value}`} aria-describedby={`hint-${value}`}>
              <span id={`label-${value}`}>{option.label}</span>
              <span id={`hint-${value}`} className="filter-hint">{option.hint}</span>
            </a>
          </Button>
        ))}
      </nav>
      {valid ? <>
        <Suspense key={filter} fallback={<StoryLoading />}>
          <StoryList filter={filter} />
        </Suspense>
      </> : (
        <section className="notice" role="alert">
          <h2>Unknown filter</h2><p>This view does not exist. Choose a title-length filter above to continue.</p>
        </section>
      )}
    </main>
  );
}
