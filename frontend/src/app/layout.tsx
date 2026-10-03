import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hacker News Crawler",
  description: "Explore the first 30 Hacker News stories by title length, points, and comments.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to stories</a>
        <div className="page-shell">
          <header className="masthead">
            <a className="wordmark" href="/">
              <span className="brand-mark" aria-hidden="true">hn</span>
              <span>Hacker News <span className="brand-descriptor">Crawler</span></span>
            </a>
            <a className="source-link" href="https://news.ycombinator.com/">
              Visit Hacker News
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10" /></svg>
            </a>
          </header>
          {children}
          <footer className="page-footer">
            <p>Views may share a recent snapshot. Check the fetch time; stories and scores can change after a refresh.</p>
            <details className="view-guide">
              <summary>How these views work</summary>
              <div className="guide-content">
                <p><strong>Title length.</strong> A word is a space-separated token containing a letter or number. Punctuation alone does not count; hyphenated terms count as one word.</p>
                <p><strong>Ordering.</strong> Long titles are sorted by comments, short titles by points. Ties keep the original front-page rank. Missing metrics come last.</p>
              </div>
            </details>
          </footer>
        </div>
      </body>
    </html>
  );
}
