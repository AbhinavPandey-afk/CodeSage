# CodeSage

AI-powered software architecture intelligence platform. Point it at a GitHub
repository and it builds a structural knowledge graph (Tree-sitter → Neo4j),
indexes it for semantic search (FAISS), and answers questions about the
codebase with evidence (file/line citations) and a deterministic confidence
score — never an LLM guess presented as fact.

Full product spec: [`CLAUDE.md`](CLAUDE.md). Delivery plan: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Current status

Phase I (Foundation & MVP) is implemented: GitHub ingestion → Python parsing →
Neo4j knowledge graph → hybrid (graph + vector) evidence-backed Q&A. See
`docs/ROADMAP.md` for what's next.

## Architecture

```
GitHub URL → clone (sandboxed) → Tree-sitter parse → normalized IR
    → Neo4j knowledge graph
    → TF-IDF/FAISS vector index
    → hybrid retrieval + evidence fusion → Groq (via LLMProvider) → answer
```

- **Backend**: FastAPI, Python 3.12, Neo4j, FAISS, Tree-sitter
- **Frontend**: React + TypeScript (Vite)
- **LLM**: Groq (`api.groq.com`), behind an `LLMProvider` abstraction —
  see the note in `backend/.env.example` about the CLAUDE.md/Grok naming.

## Prerequisites

- Python 3.12 (a venv is checked into neither repo nor tracked — create your own)
- Node.js 20+
- A [Neo4j Aura Free](https://console.neo4j.io) instance (no local Docker/Java required)
- A [Groq](https://console.groq.com) API key

## Setup

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate      # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # then fill in GROQ_API_KEY, NEO4J_URI, NEO4J_PASSWORD
uvicorn app.main:app --reload --reload-exclude "workspace/**" --port 8000
```

> **Why `--reload-exclude`:** repository analysis clones repos into
> `backend/workspace/`. Without excluding it, `--reload` treats every file in
> a freshly-cloned repo as a source change and restarts the server mid- (or
> right after) analysis — which silently wipes the in-memory vector index
> even though the repository's status still shows "ready". If you hit
> "This repository has no vector index yet" on a repo that already finished
> analyzing, this is why — re-run without `--reload`, or with the flag above.

Run tests: `pytest -q`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). It talks to the
backend at `http://localhost:8000` by default (override with `VITE_API_URL`).

## Using it

1. Paste a GitHub URL (e.g. `https://github.com/pallets/flask`) and submit.
2. Watch the pipeline progress (clone → parse → graph → embed).
3. Once ready, ask a question — e.g. "How does authentication work?" — and get
   an answer with cited evidence (file:line + graph relationships) and a
   confidence label (Confirmed / Inferred / Uncertain).

## Security notes

- Only `https://github.com/<owner>/<repo>` URLs are accepted (blocks git's
  `ext::` transport, `file://`, path traversal, non-GitHub hosts).
- Cloned repos are size/file-count limited and never executed.
- Repository content is never treated as LLM instructions — see the prompt
  boundary in `backend/ai/prompts/qa_prompt.py`.
