# AI Email Engine — Build Plan
> *Your inbox is a content pipeline, not a destination.*

## Project Overview

**Name:** AI Email Engine
**Repo:** `ai-email-engine`
**Purpose:** AI-powered email processor that treats your inbox as a knowledge extraction stream. Connects to Proton Mail Bridge via IMAP, classifies emails with local LLMs, extracts actionable links, proposes inbox cleanups, and feeds high-value content into the existing AI/ML pipeline.

**What this is NOT:** A full email client. No compose, no reply, no threading UI. Proton's web app handles communication. This handles *intelligence*.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Web UI (Next.js)                         │
│                                                              │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │  Inbox   │ │  Cleanup   │ │   Links    │ │  Sender    │  │
│  │  View    │ │  Proposals │ │   Queue    │ │  Intel     │  │
│  └──────────┘ └────────────┘ └────────────┘ └────────────┘  │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────────────────────┐
│                  Backend (FastAPI)                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Core Services                         │ │
│  │                                                         │ │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐ │ │
│  │  │  IMAP    │  │   AI     │  │   Action Engine       │ │ │
│  │  │  Sync    │  │ Classify │  │   (Proposals/Queue)   │ │ │
│  │  │ Service  │  │ Service  │  │                       │ │ │
│  │  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘ │ │
│  │       │              │                    │             │ │
│  │  ┌────▼──────────────▼────────────────────▼───────────┐ │ │
│  │  │              Shared Services                       │ │ │
│  │  │                                                    │ │ │
│  │  │  Link Extractor │ Sender Intel │ Email Parser     │ │ │
│  │  │  Cross-Email Synth │ Scheduler │ Metrics          │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────────────┘
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
    ┌──────────┐ ┌──────────┐  ┌──────────────────┐
    │PostgreSQL│ │  Ollama  │  │ Content Pipeline  │
    │  (Store) │ │  (LLMs)  │  │ Integration       │
    └──────────┘ └──────────┘  │ (Extractors,      │
                               │  Qdrant, ML)      │
                               └──────────────────┘
```

---

## Tech Stack

| Layer | Tech | Reason |
|---|---|---|
| **Backend** | Python 3.11+ / FastAPI | Matches existing ecosystem, async-native |
| **IMAP** | `aioimaplib` | Async IMAP client, handles Proton Bridge well |
| **Email Parsing** | `email` stdlib + `beautifulsoup4` | Parse MIME, extract HTML/text/links |
| **AI/LLM** | Ollama (local) | Already running 11 models, zero API cost |
| **Database** | PostgreSQL | Already running (port 5432), proven at scale |
| **Cache** | Redis | Already running (port 6379), for sync state |
| **Frontend** | Next.js / React | Modern, SSR-capable, good for dashboards |
| **Task Queue** | `apscheduler` or `celery` | Scheduled syncs, background processing |
| **Search** | Qdrant | Already running (port 6333), vector search across emails |

---

## Database Schema (PostgreSQL)

```sql
-- Core email storage
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(512) UNIQUE NOT NULL,
    folder VARCHAR(128) DEFAULT 'INBOX',
    from_address VARCHAR(256),
    from_name VARCHAR(256),
    to_addresses JSONB,
    cc_addresses JSONB,
    subject TEXT,
    body_text TEXT,
    body_html TEXT,
    date_sent TIMESTAMPTZ,
    date_received TIMESTAMPTZ,
    date_synced TIMESTAMPTZ DEFAULT NOW(),
    is_read BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    has_attachments BOOLEAN DEFAULT FALSE,
    raw_headers JSONB,
    size_bytes INTEGER
);

-- AI classification results
CREATE TABLE email_classifications (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    category VARCHAR(64) NOT NULL,        -- newsletter, transactional, personal, notification, noise, actionable
    confidence FLOAT,
    topics JSONB,                          -- ['crypto', 'ml_research', 'trading']
    relevance_score FLOAT,                -- 0-1, how relevant to user's interests
    summary TEXT,                          -- AI-generated one-liner
    classified_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(64)
);

-- Extracted links with scoring
CREATE TABLE extracted_links (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    anchor_text TEXT,
    domain VARCHAR(256),
    link_type VARCHAR(64),                -- article, github, arxiv, video, tool, docs
    relevance_score FLOAT,                -- AI-scored relevance
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    pipeline_status VARCHAR(32) DEFAULT 'pending',  -- pending, queued, extracted, skipped
    pipeline_result JSONB                 -- extraction output reference
);

-- Sender intelligence
CREATE TABLE sender_profiles (
    id SERIAL PRIMARY KEY,
    email_address VARCHAR(256) UNIQUE NOT NULL,
    display_name VARCHAR(256),
    sender_type VARCHAR(64),              -- newsletter, service, person, marketing
    total_emails INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    emails_acted_on INTEGER DEFAULT 0,
    links_extracted INTEGER DEFAULT 0,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    relevance_score FLOAT,                -- rolling average
    suggested_action VARCHAR(32),         -- keep, unsubscribe, filter, archive
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cleanup proposals (AI-generated batch actions)
CREATE TABLE cleanup_proposals (
    id SERIAL PRIMARY KEY,
    proposal_type VARCHAR(64),            -- unsubscribe, archive, categorize, extract
    title TEXT,
    description TEXT,
    affected_count INTEGER,
    affected_query JSONB,                 -- criteria used to select emails
    proposed_action JSONB,                -- what to do
    status VARCHAR(32) DEFAULT 'pending', -- pending, approved, rejected, executed, partial
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ
);

-- Proposal line items (individual emails in a proposal)
CREATE TABLE proposal_items (
    id SERIAL PRIMARY KEY,
    proposal_id INTEGER REFERENCES cleanup_proposals(id) ON DELETE CASCADE,
    email_id INTEGER REFERENCES emails(id),
    sender_id INTEGER REFERENCES sender_profiles(id),
    action VARCHAR(32),                   -- archive, delete, unsubscribe, extract, keep
    reason TEXT,
    item_status VARCHAR(32) DEFAULT 'pending'
);

-- Sync state tracking
CREATE TABLE sync_state (
    id SERIAL PRIMARY KEY,
    folder VARCHAR(128) NOT NULL,
    last_uid INTEGER DEFAULT 0,
    last_sync TIMESTAMPTZ,
    total_synced INTEGER DEFAULT 0,
    UNIQUE(folder)
);
```

---

## Phase Breakdown

### Phase 1: Foundation — IMAP Sync + Storage
**Goal:** Prove Proton Mail Bridge connectivity, sync emails to PostgreSQL.
**Estimated time:** 1 day

**Tasks:**
- [ ] Project scaffolding (FastAPI, deps, config)
- [ ] IMAP connection to Proton Mail Bridge (localhost:1143)
- [ ] Email parser (MIME → structured data)
- [ ] PostgreSQL schema + migrations (alembic)
- [ ] Incremental sync service (track UIDs, only fetch new)
- [ ] Initial full sync (backfill existing inbox)
- [ ] Basic health check / sync status API endpoint
- [ ] Config: IMAP credentials, sync interval, folders to watch

**Key risk:** Proton Mail Bridge IMAP quirks (some clients report issues with IDLE, search, or certain MIME types). Need to test early.

**Deliverable:** Running service that syncs Proton inbox to PostgreSQL. API endpoint returns email count + last sync time.

---

### Phase 2: AI Classification + Link Extraction
**Goal:** Every email gets classified and has links extracted/scored.
**Estimated time:** 1-2 days

**Tasks:**
- [ ] Ollama integration service (chat/classify endpoint)
- [ ] Email classifier prompt engineering
  - Categories: newsletter, transactional, personal, notification, noise, actionable
  - Topic tagging: crypto, ML/AI, trading, tools, career, other
  - Relevance scoring (0-1) based on user interests
  - One-line summary generation
- [ ] Link extractor (HTML + text body parsing)
  - URL extraction + deduplication
  - Domain classification (article, GitHub, arXiv, video, etc.)
  - AI relevance scoring per link
- [ ] Batch processor (classify backlog of existing emails)
- [ ] Real-time processor (classify on sync)
- [ ] Classification API endpoints

**LLM Strategy:**
- Use `qwen2.5:14b` for classification (good balance of speed + quality)
- Structured output (JSON mode) for reliable parsing
- Batch emails in groups of 5-10 for efficiency
- Cache classifications (don't re-classify unless email changes)

**Deliverable:** All synced emails classified. API returns emails with categories, topics, relevance, summaries, and extracted links.

---

### Phase 3: Sender Intelligence + Cleanup Proposals
**Goal:** Build sender profiles, generate actionable inbox cleanup proposals.
**Estimated time:** 1-2 days

**Tasks:**
- [ ] Sender profile builder (aggregate stats per sender)
  - Email frequency, open rate proxy, action rate
  - Auto-detect sender type (newsletter, service, person)
  - Rolling relevance score
- [ ] Cleanup proposal generator
  - **Unsubscribe proposals:** Senders with low relevance over time
  - **Archive proposals:** Old read emails by category
  - **Extraction proposals:** Emails with high-value unextracted links
  - **Categorization proposals:** Misclassified or uncategorized batches
- [ ] Proposal approval/rejection API
- [ ] Proposal execution engine (batch IMAP actions)
  - Archive (move to folder)
  - Mark as read
  - Flag for extraction
  - (Future: unsubscribe via link detection)
- [ ] Scheduled proposal generation (daily/weekly)

**Proposal Format:**
```json
{
  "id": 42,
  "type": "unsubscribe",
  "title": "3 newsletters you haven't opened in 90+ days",
  "description": "These senders have sent 147 total emails. You opened 2.",
  "affected_count": 147,
  "items": [
    {"sender": "noreply@medium.com", "count": 89, "opened": 1, "action": "unsubscribe"},
    {"sender": "digest@hackernews.com", "count": 34, "opened": 1, "action": "unsubscribe"},
    {"sender": "newsletter@coindesk.com", "count": 24, "opened": 0, "action": "unsubscribe"}
  ],
  "status": "pending"
}
```

**Deliverable:** System generates weekly cleanup proposals. API supports approve/reject/execute.

---

### Phase 4: Web UI
**Goal:** Read-only web interface with AI annotations and proposal management.
**Estimated time:** 2-3 days

**Tasks:**
- [ ] Next.js project setup
- [ ] **Inbox View**
  - Email list with AI category badges, relevance indicators
  - Click to read (rendered HTML, safe)
  - Filter by category, sender, topic, relevance
  - Search (text + semantic via Qdrant)
- [ ] **Cleanup Proposals Dashboard**
  - Active proposals list
  - Approve/reject individual items or entire proposals
  - Execution history
- [ ] **Link Queue**
  - All extracted links with scores
  - One-click "extract to pipeline"
  - Status tracking (pending → extracted → in training)
- [ ] **Sender Intelligence**
  - Sender list with profiles
  - Open/relevance/frequency stats
  - Suggested actions per sender
- [ ] **Insights Dashboard**
  - Email volume over time
  - Top topics this week
  - Links extracted vs total
  - Cleanup actions taken

**Design:** Clean, minimal. Think Linear/Superhuman — fast, keyboard-friendly, no clutter. Dark mode.

**Deliverable:** Working web UI at localhost:3100 (or similar). Full read-only inbox with AI superpowers.

---

### Phase 5: Pipeline Integration
**Goal:** Connect to existing AI/ML content extraction pipeline.
**Estimated time:** 1-2 days

**Tasks:**
- [ ] Content pipeline adapter
  - Map extracted links → appropriate extractor (Medium, Twitter, arXiv, GitHub, generic)
  - Queue links for extraction via existing `content_pipelines/` code
- [ ] Qdrant integration
  - Embed email summaries for semantic search
  - Cross-reference with existing knowledge base embeddings
- [ ] n8n webhook triggers
  - "New high-relevance email" trigger
  - "New extraction-worthy link" trigger
  - "Weekly digest" trigger
- [ ] Training data generation
  - Email classification → training pairs for fine-tuning
  - Link relevance → feedback loop for scoring model
- [ ] Cross-email synthesis
  - Detect when multiple emails cover same topic
  - Generate synthesis summaries
  - Surface unique links across duplicated coverage

**Deliverable:** Extracted links automatically flow into content pipelines. Email intelligence available in Qdrant for cross-system search.

---

## Future Phases (Post-MVP)

### Phase 6: Advanced Features
- **Smart notifications** — Only alert for truly important emails (not every newsletter)
- **Thread analysis** — Understand email conversations, extract decisions/action items
- **Attachment intelligence** — Parse PDFs, docs, images in emails
- **Calendar integration** — Extract events, deadlines from emails
- **Multi-account** — Support additional email accounts beyond Proton

### Phase 7: Autonomous Actions
- **Auto-archive rules** — Learn from approved proposals, suggest automation
- **Auto-extract** — High-confidence links auto-feed to pipeline
- **Unsubscribe execution** — Find and click unsubscribe links automatically
- **Email digest generation** — Daily AI summary of what came in

---

## Project Structure

```
ai-email-engine/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Settings (IMAP, DB, Ollama)
│   │   ├── database.py             # SQLAlchemy setup
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── email.py
│   │   │   ├── classification.py
│   │   │   ├── link.py
│   │   │   ├── sender.py
│   │   │   └── proposal.py
│   │   ├── services/
│   │   │   ├── imap_sync.py        # IMAP connection + sync
│   │   │   ├── email_parser.py     # MIME parsing
│   │   │   ├── classifier.py       # Ollama classification
│   │   │   ├── link_extractor.py   # URL extraction + scoring
│   │   │   ├── sender_intel.py     # Sender profile management
│   │   │   ├── proposal_engine.py  # Cleanup proposal generation
│   │   │   ├── action_executor.py  # Execute approved proposals
│   │   │   └── pipeline_adapter.py # Content pipeline integration
│   │   ├── api/
│   │   │   ├── emails.py           # Email CRUD endpoints
│   │   │   ├── classifications.py  # Classification endpoints
│   │   │   ├── links.py            # Link queue endpoints
│   │   │   ├── proposals.py        # Proposal management
│   │   │   ├── senders.py          # Sender intelligence
│   │   │   └── sync.py             # Sync control + status
│   │   └── prompts/
│   │       ├── classify_email.txt
│   │       ├── score_relevance.txt
│   │       ├── summarize_email.txt
│   │       └── generate_proposal.txt
│   ├── alembic/                    # DB migrations
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Inbox view
│   │   │   ├── proposals/
│   │   │   ├── links/
│   │   │   ├── senders/
│   │   │   └── insights/
│   │   ├── components/
│   │   └── lib/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml              # Optional: containerized deployment
├── .env.example
├── BUILD_PLAN.md                   # This file
└── README.md
```

---

## Configuration

```yaml
# .env
# IMAP (Proton Mail Bridge)
IMAP_HOST=127.0.0.1
IMAP_PORT=1143
IMAP_USER=NotYourBuddyFRIEND2@protonmail.com
IMAP_PASSWORD=<bridge-password>
IMAP_USE_SSL=true

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_email_engine

# Redis
REDIS_URL=redis://localhost:6379/2

# Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# Sync
SYNC_INTERVAL_MINUTES=5
SYNC_FOLDERS=INBOX,Sent,Archive
INITIAL_SYNC_LIMIT=5000

# Content Pipeline
PIPELINE_BASE_URL=http://localhost:8003
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=email_intelligence

# Web UI
FRONTEND_PORT=3100
API_PORT=8400
```

---

## Key Design Decisions

1. **Read-only first** — No compose/reply. Proton web app handles that. We handle intelligence.
2. **Local-only AI** — All classification via Ollama. No data leaves the machine. Privacy-first.
3. **Proposal-based cleanup** — AI proposes, human approves. No autonomous deletion.
4. **Incremental sync** — Track UIDs, only fetch new emails. Efficient on Bridge.
5. **PostgreSQL over MongoDB** — Structured data (emails have fixed schema), complex queries for proposals, already running.
6. **Separate from Knowledge Base repo** — This is its own product, not a subfolder of content_pipelines.

---

## Success Criteria

**Phase 1:** Can sync 1000+ emails from Proton Bridge in <5 minutes. Incremental sync catches new mail within configured interval.

**Phase 2:** 90%+ classification accuracy on email categories. Links extracted from >95% of newsletter emails.

**Phase 3:** First cleanup proposal generated that correctly identifies low-value senders. Proposal execution successfully archives emails via IMAP.

**Phase 4:** Web UI loads inbox in <2 seconds. Can filter, search, and view any email. Proposals manageable from UI.

**Phase 5:** At least 10 links auto-extracted from emails into content pipeline per week. Semantic search across emails returns relevant results.

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Proton Bridge IMAP quirks | High | Test connection in Phase 1 before building anything else |
| Ollama classification quality | Medium | Prompt iteration, fall back to larger model if needed |
| Email volume overwhelms Ollama | Medium | Batch processing, queue system, skip low-priority emails |
| Bridge password rotation | Low | Config-based, easy to update |
| Large inbox initial sync | Medium | Pagination, background processing, progress tracking |
| HTML email rendering XSS | Medium | Sanitize HTML before display, use iframe sandbox |

---

*Plan created: 2026-01-30*
*Status: APPROVED — Ready to build*
