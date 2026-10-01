"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Hacker News Crawler API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is accepting requests."""
    return {"status": "ok"}
