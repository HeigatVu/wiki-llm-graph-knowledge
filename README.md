# Setup
## UV
```
uv add litellm networkx
```
## Set up API key and model in .env

# DIRECTORY STRUCTURE
```
llm-wiki-agent/
  raw/
    my_knowledge_notes/     ← personal knowledge notes (.md)
    papers/
      my_notes/             ← your paper notes (.md)
      pdf/                  ← original PDFs
  wiki/
    index.md                ← catalog of all pages
    log.md                  ← append-only history
    overview.md             ← living synthesis
    sources/
      papers/               ← ingested paper pages
      notes/                ← ingested knowledge pages
    entities/               ← people, projects, products
    concepts/               ← ideas, frameworks, theories
    syntheses/              ← saved query answers
  graph/
    graph.json              ← auto-generated graph data
    graph.html              ← visual graph explorer
  tools/                    ← Python pipeline scripts
  GEMINI.md                 ← Gemini CLI system prompt
  WIKI_STATUS.md            ← handoff file between Python and CLI
  run.py                    ← single entry point
  requirements.txt
```

# COMMANDS
```
# Ingest a single paper note
python run.py ingest raw/papers/my_notes/paper_note.md

# Ingest a single knowledge note
python run.py ingest raw/my_knowledge_notes/my_note.md

# Ingest a PDF paper
python run.py ingest raw/papers/pdf/paper.pdf

# Ingest an entire folder (bulk)
python run.py ingest raw/papers/my_notes/
python run.py ingest raw/my_knowledge_notes/

# Validate wiki integrity only, no ingest
python run.py ingest --validate-only
```
# Workflow
## Query (automated / scripted only)
```
# Ask a question, print answer to terminal
python run.py query "what do I know about transformers?"

# Ask and save answer to wiki/syntheses/
python run.py query "what connects my Alzheimer's papers?" --save

# Ask and save to a specific path
python run.py query "methodology gaps across all papers?" --save 40_output/syntheses/methodology-gaps.md
```
**For interactive querying, use Gemini CLI instead — it supports follow-up questions and multi-turn conversation.**

## Lint
```
# Run health checks, print report to terminal
python run.py lint

# Run health checks and save report to wiki/lint-report.md
python run.py lint --save
```
- Orphan pages with no connections
- Broken [[wikilinks]]
- Missing entity pages mentioned 3+ times
- Referenced papers not yet ingested
- Contradictions between pages
- Data gaps and suggested sources
- Graph-aware issues (hub stubs, fragile bridges, isolated communities)

## Graph
```
# Build graph.json and graph.html from all wikilinks
python run.py graph

# Build and open graph.html in browser
python run.py graph --open
```
**Run this after every batch ingest to keep the graph current. Graph data also unlocks deeper checks in lint.**

## Refresh
```
# Re-ingest only source files that have changed since last run
python run.py refresh

# Force re-ingest all sources regardless of changes
python run.py refresh --force

# Refresh a specific wiki source page
python run.py refresh --page sources/papers/my-paper

# Preview what would be refreshed without making changes
python run.py refresh --dry-run
```

## Heal
```
# Auto-generate missing entity pages for things mentioned 3+ times
python run.py heal
```

## Gemini CLI (interactive exploration)
```
# Open Gemini CLI in the repo directory
cd /path/to/llm-wiki-agent
gemini
```
**Inside Gemini CLI you can use plain English or shorthand triggers:**
```
# Query the wiki
query: what do I know about speech recognition?
query: what connects my Alzheimer's papers?

# Check wiki health
lint

# Build the knowledge graph
build graph

# Ingest a new source
ingest raw/papers/my_notes/new-paper.md

# Orient yourself after Python pipeline ran
read WIKI_STATUS.md and tell me what was last done
```

# Recommend daily flow
```
# 1. Ingest new notes
python run.py ingest raw/papers/my_notes/
python run.py ingest raw/my_knowledge_notes/

# 2. Rebuild graph
python run.py graph

# 3. Check health
python run.py lint

# 4. Explore interactively
cd /path/to/llm-wiki-agent
gemini
```