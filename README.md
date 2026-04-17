# Background
- I based on description of Andrew Karpathy about [llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Besides, I also refer the idea of [SamurAIGPT](https://github.com/SamurAIGPT/llm-wiki-agent). I appreciate their suggestion because these idea inspire and guide me a lot to finish my workflow and code.
- The reason I build this repo to solve one problem about linking between papers and suggest about my knowledge notes. So I leverage the power of LLM to suggest me fixing and writing in obsidian.
- I also add WIKI_STATUS.md to track the status of my wiki when I use gemini.
- In my opinion, each project or our knowledge should be seperated wiki. So I build this repo to manage **my knowledge and my project paper notes**.
- When we use for project research with reading a lot of paper, we should use template in 10_System/Templates/Paper_Summary_Template.md. By constrast, for taking notes knowledge, we should use Default_Proterty_Template.md

***NOTE: This repo is just process markdown file to save token and easy for gemini to read.***
# Setup
## UV
```
# After install uv and setup anaconda
uv venv
source .venv/bin/activate
uv sync
```
## Set up API key and model in .env

# DIRECTORY STRUCTURE
```
wiki-llm-knowledge/
  20_raw/
	|-my_knowledge_notes/     ← personal knowledge notes (.md)
	|-papers/
	  |--my_notes/             ← your paper notes (.md)
	  |--pdf/                  ← original PDFs
  30_wiki/
	|-index.md                ← catalog of all pages
	|-log.md                  ← append-only history
	|-overview.md             ← living synthesis
	|-sources/
	  |-papers/               ← ingested paper pages
	  |-notes/                ← ingested knowledge pages
	|-entities/               ← people, projects, products
	|-concepts/               ← ideas, frameworks, theories
	|-syntheses/              ← saved query answers
  2_graph/
	|-graph.json              ← auto-generated graph data
	|-graph.html              ← visual graph explorer
  1_tools/                    ← Python pipeline scripts
  GEMINI.md                 ← Gemini CLI system prompt
  WIKI_STATUS.md            ← handoff file between Python and CLI
  main.py                    ← single entry point
  .env                        ← API key and model container
```
# Workflow
## Ingest
```
# Ingest a single paper note
uv run main.py ingest 20_raw/papers/my_notes/paper_note.md

# Ingest a single knowledge note
uv run main.py ingest 20_raw/my_knowledge_notes/my_note.md

# Ingest a PDF paper
uv run main.py ingest 20_raw/papers/pdf/paper.pdf

# Ingest an entire folder (bulk)
uv run main.py ingest 20_raw/papers/my_notes/
uv run main.py ingest 20_raw/my_knowledge_notes/

# Validate wiki integrity only, no ingest
uv run main.py ingest --validate-only
```

## Query (automated / scripted only)
```
# Ask a question, print answer to terminal
uv run main.py query "what do I know about transformers?"

# Ask and save answer to wiki/syntheses/
uv run main.py query "what connects my Alzheimer's papers?" --save

# Ask and save to a specific path
uv run main.py query "methodology gaps across all papers?" --save 40_output/syntheses/methodology-gaps.md
```
**For interactive querying, use Gemini CLI instead — it supports follow-up questions and multi-turn conversation.**

## Lint
```
# Run health checks, print report to terminal
uv run main.py lint

# Run health checks and save report to wiki/lint-report.md
uv run main.py lint --save
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
Build the knowledge graph from the wiki.

uv run main.py graph               # full rebuild with inference
uv run main.py graph --no-infer    # skip semantic inference (faster)
uv run main.py graph --open        # open graph.html after build
uv run main.py graph --clean       # wipe checkpoint, re-infer everything
uv run main.py graph --report      # also generate health report
uv run main.py graph --save        # save report to 2_graph/graph-report.md
uv run main.py graph --open
```
**Run this after every batch ingest to keep the graph current. Graph data also unlocks deeper checks in lint.**

## Refresh
```
# Re-ingest only source files that have changed since last run
uv run main.py refresh

# Force re-ingest all sources regardless of changes
uv run main.py refresh --force

# Refresh a specific wiki source page
uv run main.py refresh --page sources/papers/my-paper

# Preview what would be refreshed without making changes
uv run main.py refresh --dry-run
```

## Heal
```
# Auto-generate missing entity pages for things mentioned 3+ times
uv run main.py heal
```

## Gemini CLI (interactive exploration)
```
# Open Gemini CLI in the repo directory
cd /path/to/wiki-llm-knowledge
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
ingest 20_raw/papers/my_notes/new-paper.md

# Orient yourself after Python pipeline ran
read WIKI_STATUS.md and tell me what was last done
```

# Recommend daily flow
```
# 1. Ingest new notes
uv run main.py ingest 20_aw/papers/my_notes/
uv run main.py ingest 20_raw/my_knowledge_notes/

# 2. Rebuild graph
uv run main.py graph

# 3. Check health
uv run main.py lint

# 4. Explore interactively
cd /path/to/wiki-llm-knowledge
gemini
```

# License
MIT License - see [LICENSE](./LICENSE.md) for details.