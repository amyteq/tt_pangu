# M5-T001: DB layer — research items + citations + artifact attach

## Milestone
M5: research and browser workflow.

## Goal
Add psycopg3 helpers for `research_items` and `research_citations`, and a
small `attach_artifact` helper for the HTML/text snapshots that the browser
fetch tool will store.

## Read first
1. `tools/kca/db.py` — existing `__all__`, `_with_conn`, parameterised SQL
2. `supabase/migrations/0005_m5_research_citations.sql`
3. `docs/adr/0008-artifact-storage-local-first.md` — where `artifacts` rows live

## Functions to add (canonical names)

```python
def create_research_item(
    *,
    url: str,
    title: str | None = None,
    source_kind: str | None = None,
    trust: str = "unknown",
    summary: str | None = None,
    competition_id: str | None = None,
    fetcher: str | None = None,
    http_status: int | None = None,
    content_hash: str | None = None,
    html_artifact_id: str | None = None,
    text_artifact_id: str | None = None,
    source_policy: dict | None = None,
) -> str:
    """Insert one research_items row. Returns its id."""

def get_research_item(item_id: str) -> dict
def list_research_items(competition_id: str | None = None, limit: int = 50) -> list[dict]
def find_research_by_url(url: str) -> dict | None

def attach_artifact(
    kind: str, storage_path: str, *,
    content_hash: str | None = None,
    byte_size: int | None = None,
    metadata: dict | None = None,
) -> str:
    """Insert one artifacts row. Returns artifact_id."""

def cite_research(
    research_item_id: str, *,
    run_id: str | None = None,
    experiment_id: str | None = None,
    job_id: str | None = None,
    quote: str | None = None,
    page_anchor: str | None = None,
) -> str:
    """Insert one research_citations row. Returns citation_id."""

def list_citations(run_id: str | None = None, experiment_id: str | None = None) -> list[dict]
```

## Design rules
- No async. Parameterised SQL only.
- `find_research_by_url` returns the newest match (allow re-fetches without
  losing history).
- `content_hash`-based dedup is **caller's responsibility**; this layer does
  not silently merge rows.

## Acceptance criteria
- `python -c "from tools.kca import db; print([f for f in dir(db) if 'research' in f or 'artifact' in f or 'citation' in f])"`
  lists all the new symbols.
- Live-DB smoke (with `SUPABASE_DB_URL` set):
  - `attach_artifact` + `create_research_item` + `cite_research` round-trip.
  - `list_research_items(competition_id=…)` returns the inserted row.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 30 turns.
