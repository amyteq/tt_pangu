# h01_prototype — H0 "Zero Stack" demo backend

Tiny FastAPI app that backs the H0 Devpost prototype: a chat endpoint
that persists messages to Postgres (the "AWS Database" requirement)
and a `/health` probe a Vercel deploy can hit.

## Local run

```bash
export SUPABASE_DB_URL=postgresql://...
python -m uvicorn src.h01_prototype:app --reload --port 8000
```

## Deploy to Vercel (human step)

The agent does not have Vercel CLI access. To complete the hackathon
submission, a human must:

1. `vercel link` against a new project under the hackathon team id.
2. Set the `SUPABASE_DB_URL` env var in Vercel project settings.
3. `vercel deploy --prod`.
4. Paste the resulting URL into `submission_pack/published_vercel_project_link__vercel_team_id`.

Until step 4 lands, the corresponding checklist item stays `todo`.
