"use client";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="notice" role="alert">
      <h1>Something went wrong</h1>
      <p>The page could not be displayed. Please try again.</p>
      <Button className="mt-5" onClick={reset}>Try again</Button>
    </main>
  );
}
