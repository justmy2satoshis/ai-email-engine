# 📧 AI Email Engine

> Your inbox is a content pipeline, not a destination.

AI-powered email intelligence engine for **Proton Mail Bridge**. Not another email client — an email **brain** that classifies, extracts, and proposes cleanup actions using local LLMs.

## What This Does

- 🔌 **Connects to Proton Mail Bridge** via IMAP — syncs your inbox incrementally
- 🧠 **AI Classification** — Ollama classifies every email (newsletter, personal, noise, etc.)
- 🔗 **Link Extraction** — Finds and scores URLs for content pipeline extraction
- 📊 **Sender Intelligence** — Tracks who sends what, how often, and whether you care
- 🧹 **Cleanup Proposals** — AI proposes batch actions: unsubscribe, archive, extract
- 🔒 **100% Local** — All AI runs on your machine via Ollama. Nothing leaves your network.

## What This Is NOT

This is not a full email client. No compose, no reply, no threading. Use Proton's web app for communication. This handles **intelligence**.

## Quick Start

### Prerequisites

- [Proton Mail Bridge](https://proton.me/mail/bridge) running locally
- [Ollama](https://ollama.ai) with a model installed (default: `qwen2.5:14b`)
- PostgreSQL
- Python 3.11+

### Setup

```bash
# Clone
git clone https://github.com/justmy2satoshis/ai-email-engine.git
cd ai-email-engine/backend

# Virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Dependencies
pip install -r requirements.txt

# Config
cp ../.env.example .env
# Edit .env with your Proton Bridge credentials

# Database
createdb ai_email_engine  # or via psql

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8400 --reload
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/sync/connect` | Connect to IMAP |
| `POST` | `/api/sync/run` | Sync new emails |
| `GET` | `/api/sync/status` | Connection & sync status |
| `GET` | `/api/emails/` | List emails (filtered, paginated) |
| `GET` | `/api/emails/{id}` | Full email detail |
| `GET` | `/api/emails/stats` | Inbox analytics |
| `POST` | `/api/process` | Classify unprocessed emails |
| `GET` | `/api/process/stats` | Classification statistics |
| `GET` | `/api/links` | Extracted links with scores |
| `GET` | `/api/senders` | Sender intelligence profiles |
| `POST` | `/api/proposals/generate` | Generate cleanup proposals |
| `GET` | `/api/proposals/` | List proposals |
| `POST` | `/api/proposals/{id}/approve` | Approve a proposal |
| `POST` | `/api/proposals/{id}/reject` | Reject a proposal |

Visit `http://localhost:8400/docs` for interactive Swagger docs.

## Architecture

```
Proton Mail Bridge (IMAP)
    → Email Sync Service (FastAPI + aioimaplib)
        → AI Classification (Ollama - local LLM)
        → Link Extraction + Relevance Scoring
        → Sender Intelligence Profiles
        → Cleanup Proposal Generator
            → Approve/Reject → Execute
```

### Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python / FastAPI |
| IMAP | aioimaplib (async) |
| AI/LLM | Ollama (100% local) |
| Database | PostgreSQL + SQLAlchemy |
| Email Parsing | Python email + BeautifulSoup |

## Email Classification

Every email is classified into one of 7 categories:

| Category | Description |
|----------|-------------|
| `newsletter` | Recurring content subscriptions |
| `transactional` | Receipts, confirmations, password resets |
| `notification` | Service alerts, social notifications |
| `personal` | Direct human-to-human communication |
| `marketing` | Promotions, sales, ads |
| `actionable` | Requires action (meetings, requests) |
| `noise` | Junk that passed spam filters |

Each email also gets:
- **Topic tags** (crypto, ML, AI research, trading, etc.)
- **Relevance score** (0-1)
- **One-line AI summary**

## Cleanup Proposals

The engine generates three types of proposals:

### 🗑️ Unsubscribe
*"3 newsletters you haven't engaged with in 90+ days. They've sent 147 emails total."*

### 📦 Archive
*"412 read emails older than 30 days in noise/transactional categories."*

### 🔗 Extract
*"28 high-value links from newsletters that should be fed to your content pipeline."*

Proposals are reviewed and approved before execution. AI proposes, human disposes.

## Roadmap

- [x] Phase 1: IMAP Sync + Storage
- [x] Phase 2: AI Classification + Link Extraction
- [x] Phase 3: Cleanup Proposals + Sender Intelligence
- [ ] Phase 4: Web UI (dark mode, keyboard-friendly)
- [ ] Phase 5: Content Pipeline Integration

## Contributing

Issues and PRs welcome. This is an active build.

## License

MIT
