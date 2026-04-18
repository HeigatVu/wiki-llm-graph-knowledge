# LLM Wiki — Personal Knowledge Base

# Background

This repo is a personal LLM-maintained wiki inspired by 
[Andrej Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 
and [SamurAIGPT](https://github.com/SamurAIGPT/llm-wiki-agent).

The core problem it solves: linking knowledge across research 
papers and personal notes, with an LLM handling all the 
bookkeeping — extracting concepts, building wikilinks, and 
detecting gaps automatically.

Each project or knowledge domain should have its own separate 
wiki instance. The pipeline processes markdown files only, 
keeping token usage low and making all content readable in 
Obsidian.

> **Note**: This repo processes markdown files only to save 
> tokens and keep content readable for Gemini CLI.

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

## Gap Analysis
```bash
# Run semantic gap analysis (terminal output)
uv run main.py gap

# Run and save report to 2_graph/gap-report.md
uv run main.py gap --save

# Rebuild from wiki pages instead of graph.json
uv run main.py gap --rebuild
```
Finds underconnected topic clusters in your research using 
local graph algorithms — no external API required. Run after 
`graph` for best results.

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
- `/wiki-ingest <file>` → run Ingest Workflow
- `/wiki-query <question>` → run Query Workflow  
- `/wiki-lint` → run Lint Workflow
- `/wiki-graph` → run Graph Workflow
- `/wiki-gap` → run Gap Analysis
- `/wiki-heal` → run Heal Workflow
- `/wiki-refresh` → run Refresh Workflow


---

# Recommended Workflow

## After every batch of new papers
```bash
# 1. Ingest new notes
uv run main.py ingest 20_raw/papers/my_notes/
uv run main.py ingest 20_raw/my_knowledge_notes/

# 2. Rebuild knowledge graph
uv run main.py graph

# 3. Check wiki health
uv run main.py lint

# 4. Fix missing entity pages (run after lint reports 5+ missing)
uv run main.py heal
```

## Every 10 papers ingested
```bash
# Detect research gaps
uv run main.py gap

# Save all reports for Obsidian review
uv run main.py graph --report --save
uv run main.py lint --save
uv run main.py gap --save
```

## When you edit an existing raw file
```bash
# Re-ingest only changed files
uv run main.py refresh

# Preview what would change without re-ingesting
uv run main.py refresh --dry-run
```

## Interactive exploration (Gemini CLI)
```bash
cd /path/to/wiki-llm-knowledge
gemini
```

## Paper Ingestion with NotebookLM

For extracting paper summaries, use NotebookLM with the 
provided prompt to generate markdown following 
`10_System/Templates/Paper_Summary_Template.md`.

1. Upload your PDF to NotebookLM
2. Run the extraction prompt (see `10_System/Templates/NotebookLM_Prompt.md`) or use my suggert prompt:
### Paper prompt
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
  - Reported pros: (from the review's own assessment)
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
(Skip this section for review/survey papers unless you have a specific view to add)
- Write your own critical observations here after reading

## Related Notes
- Use [[filename-without-extension]] to link to similar papers already in your notes
- Only include links you are confident about — do not hallucinate filenames
```
### Book_prompt
```
Can you list out all important contents in this book in order to create
checkpoints for me to find later — like an index of the book but with
a little bit extra information.

Format your response EXACTLY like this (I will copy it into my wiki system):

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
- **Key concepts**: <comma-separated list of important terms/ideas>
- **Key claims**:
  - <claim 1>
  - <claim 2>
- **Notable quotes**: "> quote here" (include page/location if available)

### Chapter 2: <Chapter Title>
(repeat same structure)

(continue for all chapters)

## Cross-Cutting Themes
- <Theme 1>: appears in chapters X, Y, Z
- <Theme 2>: appears in chapters X, Y, Z

## Key Entities
- <Person/Organization/Product>: <why they matter in this book>

## Related Topics (for linking to other knowledge)
- <Topic 1>
- <Topic 2>
```

3. Save the output to `20_raw/papers/my_notes/<slug>.md`
4. Run `uv run main.py ingest 20_raw/papers/my_notes/<slug>.md`

> **Note**: Fill in `## Personal Critique` and `## Related Notes` 
> yourself before ingesting — these sections reflect your own 
> thinking and are not extracted automatically.

---

## License

MIT — see [LICENSE](./LICENSE.md) for details.