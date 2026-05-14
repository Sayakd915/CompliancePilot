# CompliancePilot

AI-powered document compliance analysis backend. Upload a contract or policy document and get a streamed, clause-by-clause risk assessment with an executive summary — powered by a LangGraph agent and Groq's LLaMA-3.1 70B.

Built as a production-grade replacement for a Java/Swing prototype, this backend is designed to pair with a Flutter desktop frontend.

---

## What it does

- Accepts a PDF upload via a REST endpoint
- Extracts and chunks the text intelligently (respects sentence boundaries)
- Runs each chunk through a LangGraph agent concurrently (fan-out)
- Streams results back in real time via Server-Sent Events (SSE)
- Caches chunk results in Redis — identical clauses across documents are never re-analyzed
- Produces a final executive report with overall risk, top issues, and recommendations
- Persists all results to MongoDB for history retrieval

---

## Tech stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Agent | LangGraph (StateGraph with concurrent fan-out) |
| LLM | Groq — LLaMA-3.1 70B (free tier) |
| PDF extraction | pdfplumber |
| Chunking | LangChain RecursiveCharacterTextSplitter |
| Auth | JWT (python-jose + bcrypt) |
| Relational DB | Supabase Postgres |
| Document store | MongoDB Atlas (Motor async driver) |
| Cache | Upstash Redis (HTTP-based, free tier) |
| File storage | Supabase Storage |
| Observability | LangSmith |
| Deployment | Render.com — Singapore region |

---

## Project structure

```
compliancepilot/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, CORS, router registration
│   ├── config.py               # All environment variables via pydantic-settings
│   ├── models.py               # Pydantic schemas for requests, responses, SSE events
│   ├── auth/
│   │   ├── auth_service.py     # Password hashing, JWT creation/verification, user CRUD
│   │   └── dependency.py     # get_current_user FastAPI dependency (JWT guard)
│   ├── db/
│   │   ├── postgres.py         # Supabase Postgres client — users and documents
│   │   └── mongo.py            # Motor async client — conversation and chunk history
│   ├── services/
│   │   ├── cache.py            # Upstash Redis — content-addressed chunk cache
│   │   ├── pdf.py              # PDF text extraction and chunking
│   │   └── storage.py          # Supabase Storage — upload and signed URL generation
│   ├── agent/
│   │   ├── state.py            # ComplianceState TypedDict shared across graph nodes
│   │   ├── nodes.py            # parse, analyze, and synthesize node functions
│   │   └── graph.py            # LangGraph StateGraph definition and SSE stream runner
│   └── routers/
│       ├── auth.py             # POST /auth/signup, POST /auth/signin
│       ├── analysis.py         # POST /analysis/upload (SSE), GET/DELETE /analysis/*
│       └── profile.py          # GET /profile, PUT /profile
├── requirements.txt
├── Dockerfile
└── .gitignore
```

---

## Local setup

**Requirements:** Python 3.12, pip

```bash
git clone https://github.com/Sayakd915/CompliancePilot.git
cd CompliancePilot
python -m venv env
env\Scripts\activate        # Windows
# source env/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

Start the server:

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

---

## Environment variables

Copy `.env.example` to `.env` and fill in each value. All are required.

| Variable | Where to get it |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `MONGODB_URI` | Atlas → Connect → Drivers → copy URI, replace `<password>` |
| `UPSTASH_REDIS_REST_URL` | Upstash → your database → REST API tab |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash → your database → REST API tab |
| `JWT_SECRET` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `LANGCHAIN_API_KEY` | [smith.langchain.com](https://smith.langchain.com) |

---

## Database setup

### Supabase Postgres

Run the following in the Supabase SQL Editor (Dashboard → SQL Editor):

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            TEXT NOT NULL,
    storage_path        TEXT NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    overall_risk        TEXT,
    analyzed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
```

Then create a private Storage bucket named `pdf-documents` in the Supabase dashboard under Storage → New Bucket → set to Private.

### MongoDB Atlas

No manual setup needed. The Motor client creates the `conversations` collection and its indexes automatically on first startup.

Make sure your cluster allows connections from your IP:
Atlas → Network Access → Add IP Address → Allow Access from Anywhere (`0.0.0.0/0`)

---

## API reference

### Auth

```
POST /auth/signup    { "email": "...", "password": "...", "full_name": "..." }
POST /auth/signin    { "email": "...", "password": "..." }
```

Both return:
```json
{ "access_token": "eyJ...", "token_type": "bearer", "user_id": "...", "email": "..." }
```

All other endpoints require the header: `Authorization: Bearer <access_token>`

### Analysis

```
POST   /analysis/upload           Upload a PDF — returns SSE stream
GET    /analysis/history          List all documents for the current user
GET    /analysis/{document_id}    Full results + signed PDF download URL
DELETE /analysis/{document_id}    Delete document and all results
```

### SSE event format

Each message sent over the stream is a JSON object:

```
data: {"event": "started",        "data": {"chunk_count": 7}}
data: {"event": "chunk_done",     "data": {"chunk_index": 2, "risk": "Critical", "summary": "...", "suggestion": "...", "from_cache": false}}
data: {"event": "synthesis_done", "data": {"overall_risk": "Critical", "executive_summary": "...", "top_issues": [...], "recommendations": [...]}}
data: {"event": "error",          "data": "error message"}
data: {"event": "done",           "data": null}
```

### Profile

```
GET /profile      Returns user profile
PUT /profile      { "full_name": "..." }
```

---

## License

MIT