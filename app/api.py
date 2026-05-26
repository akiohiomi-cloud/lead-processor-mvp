from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from .classifier import classify
from .config import get_settings
from .normalizer import normalize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("lead-mvp")

app = FastAPI(title="Lead MVP", version="0.2.0")


class LeadIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=200)
    message: str | None = Field(default=None, max_length=5000)
    source: str | None = Field(default=None, max_length=200)


@app.get("/health")
def health() -> dict[str, str | bool]:
    s = get_settings()
    return {"status": "ok", "dry_run": s.dry_run}


def _process_lead(lead_id: str, payload: dict) -> None:
    """Background pipeline. Wired up across Stages 2-5."""
    log.info("lead.received id=%s name=%s", lead_id, payload.get("name"))
    n = normalize(
        name=payload["name"],
        phone=payload["phone"],
        email=payload["email"],
        message=payload.get("message"),
        source=payload.get("source"),
    )
    log.info(
        "lead.normalized id=%s valid=%s duplicate=%s phone=%s email=%s issues=%s",
        lead_id,
        n.is_valid,
        n.is_duplicate,
        n.phone_e164,
        n.email_normalized,
        n.issues,
    )
    c = classify(n)
    log.info(
        "lead.classified id=%s class=%s score=%d reason=%s",
        lead_id,
        c.lead_class,
        c.score,
        c.reason,
    )
    # Stage 4: storage.append(...)
    # Stage 5: notifier.notify(...)


@app.post("/lead", status_code=202)
def submit_lead(lead: LeadIn, background_tasks: BackgroundTasks) -> dict[str, str]:
    lead_id = str(uuid.uuid4())
    background_tasks.add_task(_process_lead, lead_id, lead.model_dump())
    return {"lead_id": lead_id, "status": "accepted"}
