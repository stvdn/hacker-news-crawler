export function StoryLoading() {
  return (
    <section className="results-panel loading-panel" aria-label="Loading story results" aria-busy="true">
      <div className="results-meta"><p role="status">Loading stories from Hacker News…</p></div>
      <div className="loading-rows" aria-hidden="true">
        {Array.from({ length: 5 }, (_, index) => (
          <div className="loading-row" key={index}>
            <span className="loading-rank" /><span className="loading-title" />
            <span className="loading-metric" /><span className="loading-metric" />
          </div>
        ))}
      </div>
    </section>
  );
}
