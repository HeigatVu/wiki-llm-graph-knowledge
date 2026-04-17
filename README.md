# LLM Wiki — Personal Knowledge Base

A personal knowledge management system that uses an LLM to ingest your notes and papers into a structured, interlinked wiki. Inspired by [Andrej Karpathy's llm-wiki concept](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and [SamurAIGPT's llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent).

## Why This Exists

When reading many papers or building up a body of knowledge, it's hard to see connections between ideas. This repo solves that by letting an LLM automatically extract entities, concepts, and relationships from your notes — then link them together into a queryable wiki. Each project or knowledge domain gets its own wiki instance.

> **Note:** This repo processes only Markdown files to keep token usage low and responses fast.

---

## How It Works

There are two layers:

- **Python pipeline** (`main.py` + `1_tools/`) — handles batch operations: ingesting files, building the knowledge graph, linting for issues, querying for answers.
- **Gemini CLI** (`GEMINI.md`) — an interactive conversational layer. Open the repo with `gemini` for multi-turn queries, follow-up questions, and exploration. The file `WIKI_STATUS.md` acts as the handoff state between the two layers.

---

## Directory Structure

```
wiki-llm-knowledge/
├── 20_raw/                    # Immutable source documents — never modify these
│   ├── 20.2_notes/            # Personal knowledge notes (.md)
│   └── 20.3_pdf/              # Original PDFs
├── 30_wiki/                   # Agent-managed wiki layer
│   ├── index.md               # Catalog of all pages
│   ├── log.md                 # Append-only history
│   ├── overview.md            # Living synthesis across all sources
│   ├── sources/
│   │   ├── papers/            # Ingested academic paper pages
│   │   └── notes/             # Ingested personal knowledge pages
│   ├── entities/              # People, projects, products
│   ├── concepts/              # Ideas, frameworks, theories
│   └── syntheses/             # Saved query answers
├── 2_graph/
│   ├── graph.json             # Auto-generated graph data
│   └── graph.html             # Visual interactive graph explorer
├── 1_tools/                   # Python pipeline scripts
├── 10_System/Templates/       # Note templates for Obsidian
├── main.py                    # Single entry point for all commands
├── GEMINI.md                  # Gemini CLI system prompt and schema
├── WIKI_STATUS.md             # Handoff state between Python and Gemini CLI
└── .env                       # API key and model configuration
```

---

## Setup

### 1. Install uv and create environment

```bash
uv venv
source .venv/bin/activate
uv sync
```

### 2. Configure `.env`

```
GEMINI_API_KEY="your-api-key-here"
LLM_MODEL="gemini-2.0-flash"
```

---

## Note Templates

Use the right template when writing your source notes in Obsidian or any markdown editor:

- **Academic paper notes** → `10_System/Templates/Paper Summary Template.md`
- **Personal knowledge notes** → `10_System/Templates/Default Property Template.md`

The ingest pipeline auto-detects which type of note it's reading and applies the appropriate processing.

---

## Commands

### Ingest

Processes source documents, extracts entities and concepts, and updates the wiki.

```bash
# Ingest a single note
uv run main.py ingest 20_raw/20.2_notes/my-note.md

# Ingest a PDF paper
uv run main.py ingest 20_raw/20.3_pdf/paper.pdf

# Ingest an entire folder
uv run main.py ingest 20_raw/20.2_notes/

# Validate wiki integrity only (no ingest)
uv run main.py ingest --validate-only
```

### Query

Ask questions about your knowledge base and get synthesized answers with citations.

```bash
# Print answer to terminal
uv run main.py query "what do I know about transformers?"

# Save answer to wiki/syntheses/
uv run main.py query "what connects my signal processing papers?" --save

# Save to a specific path
uv run main.py query "methodology gaps?" --save 30_wiki/syntheses/methodology-gaps.md
```

For interactive multi-turn querying, use Gemini CLI instead (see below).

### Graph

Builds a visual knowledge graph from all `[[wikilinks]]` in the wiki.

```bash
# Build graph.json and graph.html
uv run main.py graph

# Build and open in browser
uv run main.py graph --open

# Skip semantic inference (faster, wikilinks only)
uv run main.py graph --no-infer
```

Run this after every batch ingest to keep the graph current.

### Lint

Checks the wiki for structural and semantic issues.

```bash
# Print report to terminal
uv run main.py lint

# Save report to 30_wiki/lint-report.md
uv run main.py lint --save
```

Checks for: orphan pages, broken `[[wikilinks]]`, missing entity pages, referenced papers not yet ingested, contradictions between pages, data gaps, hub stubs, and fragile bridges between knowledge clusters.

### Refresh

Re-ingests source files that have changed since the last run.

```bash
# Re-ingest only changed sources
uv run main.py refresh

# Force re-ingest everything
uv run main.py refresh --force

# Refresh a specific page
uv run main.py refresh --page sources/papers/my-paper

# Preview what would be refreshed
uv run main.py refresh --dry-run
```

### Heal

Auto-generates missing entity pages for terms mentioned 3+ times across the wiki but with no dedicated page.

```bash
uv run main.py heal
```

---

## Gemini CLI (Interactive Exploration)

```bash
cd /path/to/wiki-llm-knowledge
gemini
```

Inside Gemini CLI you can use plain English or shorthand triggers:

```
# Query the wiki
query: what do I know about biosignal processing?
query: what connects my latest papers?

# Check wiki health
lint

# Build the knowledge graph
build graph

# Ingest a new source
ingest 20_raw/20.2_notes/new-note.md

# Check what the Python pipeline last did
read WIKI_STATUS.md and tell me what was last done
```

---

## Recommended Daily Flow

```bash
# 1. Ingest new notes
uv run main.py ingest 20_raw/20.2_notes/
uv run main.py ingest 20_raw/20.3_pdf/

# 2. Rebuild graph
uv run main.py graph

# 3. Check health
uv run main.py lint

# 4. Explore interactively
gemini
```

---

## License

MIT — see [LICENSE](./LICENSE.md) for details.