# LLM Wiki — Personal Knowledge Base

## Background

This repo is a personal LLM-maintained wiki inspired by
[Andrej Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
and [SamurAIGPT](https://github.com/SamurAIGPT/llm-wiki-agent).

The core problem it solves: linking knowledge across research papers and personal notes, with an LLM handling all the bookkeeping — extracting concepts, building wikilinks, and detecting gaps automatically.

Each project or knowledge domain should have its own separate wiki instance. The pipeline processes markdown files only, keeping token usage low and making all content readable in Obsidian.

---

## How It Works

There are two layers:

- **Python pipeline** (`main.py` + `1_tools/`) — handles batch operations: ingesting files, building the knowledge graph, linting for issues, querying for answers, and healing missing pages. All pipeline tasks use the **Gemini REST API** directly.
- **Gemini CLI** (`GEMINI.md`) — an interactive conversational layer. Open the repo with `gemini` for multi-turn exploration, `/wiki-lint`, `/wiki-heal`, and follow-up questions. `WIKI_STATUS.md` acts as the handoff state between the two layers.

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
│   ├── sources/               # One page per source document
│   ├── entities/              # People, projects, products
│   ├── concepts/              # Ideas, frameworks, theories
│   └── syntheses/             # Saved query answers
├── 2_graph/
│   ├── graph.json             # Auto-generated graph data
│   └── graph.html             # Interactive visual graph explorer
├── 1_tools/                   # Python pipeline scripts
│   ├── ingest.py              # Source document ingestion
│   ├── build_graph.py         # Knowledge graph construction (Louvain clustering)
│   ├── lint.py                # Wiki health checker
│   ├── heal.py                # Missing entity page generator
│   ├── query.py               # Question-answering over the wiki
│   ├── utils.py               # Shared API wrappers and helpers
│   └── assets/
│       ├── graph_template.html # Graph UI template
│       ├── graph.js           # Interactive graph logic
│       └── graph.css          # Interactive graph CSS
├── README.md                  # This file
├── main.py                    # Single entry point for all commands
├── GEMINI.md                  # Gemini CLI system prompt and wiki schema
├── WIKI_STATUS.md             # Handoff state between Python and Gemini CLI
└── .env                       # API keys and model configuration
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

```env
# Default model for heal, lint, query, gap (lighter, higher quota)
LLM_MODEL="gemini-3.1-flash-lite-preview"

# Higher-quality model used specifically for ingest
INGEST_MODEL="gemini-3-flash-preview"

GEMINI_API_KEY="your-api-key-here"

# Local model for Ollama (optional)
OLLAMA_MODEL="llama3.2"
```

> **Model split**: `INGEST_MODEL` is used by `ingest` for complex document parsing.
> `LLM_MODEL` is used by everything else (`heal`, `lint`, `query`, `gap`).
> Change either independently in `.env` without touching any code.

---

## Commands

### Ingest

Parses source documents and writes structured wiki pages.

```bash
# Ingest a single file
uv run main.py ingest 20_raw/20.2_notes/my-paper.md

# Batch ingest an entire folder
uv run main.py ingest 20_raw/20.2_notes/

# Force re-ingest (ignore content hash cache)
uv run main.py ingest 20_raw/my-paper.md --force
```

Uses `INGEST_MODEL` from `.env` (defaults to `LLM_MODEL` if not set).

### Graph

Builds a visual knowledge graph from all `[[wikilinks]]` using **Louvain community detection** (pure mathematical clustering — fast, no AI required).

```bash
# Build graph.json and graph.html
uv run main.py graph

# Build and open in browser immediately
uv run main.py graph --open
```

### Serve

Starts a local HTTP server for the interactive knowledge graph UI.

```bash
uv run main.py serve
# Opens at http://localhost:8080/graph.html
```

If port 8080 is already in use (common after a hard stop):

```bash
fuser -k 8080/tcp && uv run main.py serve
```

**Graph UI features:**
- **Cluster filtering**: Check/uncheck individual math clusters in the sidebar. Use **All / None** shortcuts to bulk toggle.
- **Click a cluster name** to select it for focused AI chat — the AI only considers nodes in that group.
- **Click any node** to open its detail drawer with full markdown content and related nodes.
- **AI chat panel**: Ask Gemini (API), Gemini CLI, or a local Ollama model about the selected node, cluster, or the whole graph. Context is injected automatically from your `GEMINI.md` wiki schema.
- **Rebuild button**: Rebuilds the graph in-place without leaving the browser.

### Lint

Checks the wiki for structural and semantic issues.

```bash
# Print report to terminal
uv run main.py lint

# Save report to 30_wiki/lint-report.md
uv run main.py lint --save
```

Checks for: orphan pages, broken `[[wikilinks]]`, missing entity pages, referenced papers not yet ingested, contradictions between pages, stale content, and fragile single-bridge connections between clusters.

### Heal

Auto-generates missing entity pages for terms mentioned 3+ times across the wiki but with no dedicated page. Uses `LLM_MODEL`.

```bash
# Interactive mode — prompts before each page
uv run main.py heal

# Auto mode — creates all pages without prompting
uv run main.py heal --auto
```

> **Tip**: Run `lint` first to see what's missing, then run `heal` to fix it.

### Gap

Detects underconnected topic clusters and suggests where to find new papers.

```bash
uv run main.py gap

# Save report to 2_graph/gap-report.md
uv run main.py gap --save
```

Run after `graph` for best results.

### Query

Ask questions about your knowledge base and get synthesized answers with `[[wikilink]]` citations.

```bash
# Print answer to terminal
uv run main.py query "what do I know about speech biomarkers?"

# Save answer to 30_wiki/syntheses/
uv run main.py query "what connects my signal processing papers?" --save
```

### Refresh

Re-ingests source files that have changed since the last run.

```bash
# Re-ingest only changed sources
uv run main.py refresh

# Force re-ingest everything
uv run main.py refresh --force

# Preview what would be refreshed without changing anything
uv run main.py refresh --dry-run
```

## Gemini CLI (Interactive Exploration)

```bash
cd /path/to/your-wiki
gemini
```

Inside Gemini CLI you can use slash commands or plain English:

| Command | Description |
|---------|-------------|
| `/wiki-ingest <file>` | Run Ingest Workflow |
| `/wiki-query <question>` | Run Query Workflow |
| `/wiki-lint` | Run Lint Workflow |
| `/wiki-graph` | Run Graph Workflow |
| `/wiki-gap` | Run Gap Analysis |
| `/wiki-heal` | Run Heal Workflow |
| `/wiki-refresh` | Run Refresh Workflow |

> **Note**: Gemini CLI uses your Google account quota (separate from the API key quota). If the API key hits its daily limit, Gemini CLI continues to work.

---

## Recommended Workflow

### After every batch of new papers

```bash
# 1. Ingest new notes
uv run main.py ingest 20_raw/20.2_notes/

# 2. Rebuild knowledge graph
uv run main.py graph

# 3. Check wiki health
uv run main.py lint

# 4. Fix missing entity pages
uv run main.py heal --auto
```

### Every 10 papers

```bash
# Detect research gaps
uv run main.py gap --save

# Save lint report for Obsidian review
uv run main.py lint --save
```

### When you edit an existing raw file

```bash
# Re-ingest only changed files
uv run main.py refresh

# Preview what would change first
uv run main.py refresh --dry-run
```


## Paper Ingestion with NotebookLM

For extracting paper summaries, use NotebookLM to generate structured markdown, then ingest it.

1. Upload your PDF to NotebookLM
2. Use the paper prompt below to extract a structured summary
3. Save to `20_raw/20.2_notes/<slug>.md`
4. Run `uv run main.py ingest 20_raw/20.2_notes/<slug>.md`

> **Tip**: Fill in `## Personal Critique` and `## Related Notes` yourself before ingesting — these reflect your own thinking and are not extracted automatically.

### Paper Extraction Prompt

```
You are a research assistant helping me summarize academic papers into structured markdown notes. I am a researcher in biosignal processing.

First, classify the paper type before filling any section:
- EMPIRICAL: presents new experiments, datasets, models, or systems
- REVIEW / SURVEY: synthesizes existing literature without new experiments
Write [PAPER TYPE: EMPIRICAL] or [PAPER TYPE: REVIEW] on the very first line of your output, then the frontmatter block.

Extract information from this paper and return ONLY a markdown note using EXACTLY this format — no extra text, no preamble:

---

Title: <paper title>

Authors: <lastname1, lastname2, ...>

Year: <year>

Source: <journal or conference name>

tags:

---

## Core Contribution
One sentence: what specific problem does this paper solve and what is the key novelty?

## Key Methodology (Important)

### If EMPIRICAL paper:
For each method or technique, include:
- **Method name**: what it is in one line
  - Input: signal/data type, sampling rate, channels if mentioned
  - Processing steps: exact sequence of operations
  - Key parameters: specific values, thresholds, window sizes, filter specs
  - Output: what comes out

Cover ALL of these if present:
- Signal acquisition setup (hardware, electrode placement, sampling rate)
- Preprocessing pipeline (filtering, artifact removal, segmentation)
- Feature extraction methods
- Classification or modeling approach
- Evaluation protocol (dataset, cross-validation strategy, metrics)

### If REVIEW / SURVEY paper:
For each technique or method category covered in the review:
- **Technique name**
  - How it works (1–2 sentences)
  - Reported pros:
  - Reported cons / limitations:
  - Performance on benchmark datasets: (exact numbers if given)
  - Datasets used in reviewed studies: (names, sizes)

Then add:
- **Gaps identified by the authors**: what the review says is missing or unsolved
- **Recommended directions**: what the authors suggest as future work

## Results & Conclusions

### If EMPIRICAL:
- 3–5 bullet points of key quantitative results (include exact numbers)
- Main conclusion (one sentence)
- Stated limitations (one sentence)

### If REVIEW / SURVEY:
- Summary of the field's overall performance landscape (one paragraph)
- Which technique category performs best and under what conditions
- Consensus limitations across the reviewed studies

## Personal Critique & Ideas for Future Improvement
(Skip for review/survey papers unless you have a specific view)
- Write your own critical observations here after reading

## Related Notes
- Use [[filename-without-extension]] to link to similar papers already in your notes
- Only include links you are confident about — do not hallucinate filenames
```

### Book Extraction Prompt

```
Can you list out all important contents in this book in order to create
checkpoints for me to find later — like an index of the book but with
a little bit extra information.

Format your response EXACTLY like this:

---

Title: "<Book Title>"

Authors: "<Author Names>"

Year: <YYYY>

Source: "NotebookLM grounded extraction"

tags: [book]

---

## Core Contribution
One sentence: what is this book's main thesis or contribution?

## Chapter Checkpoints

### Chapter 1: <Chapter Title>
- **Core idea**: <1 sentence>
- **Key concepts**: <comma-separated list>
- **Key claims**:
  - <claim 1>
  - <claim 2>
- **Notable quotes**: "> quote here" (include page if available)

(repeat for all chapters)

## Cross-Cutting Themes
- <Theme 1>: appears in chapters X, Y, Z

## Key Entities
- <Person/Organization/Product>: <why they matter>

## Related Topics
- <Topic 1>
- <Topic 2>
```

---

## License

MIT — see [LICENSE](./LICENSE.md) for details.