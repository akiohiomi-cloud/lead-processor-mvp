from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("lead-mvp")

app = FastAPI(title="Lead MVP", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str | bool]:
    s = get_settings()
    return {"status": "ok", "dry_run": s.dry_run}
