# First step to build wiki
```
Ingest a source document into the LLM Wiki.

Usage:
    python tools/ingest.py <path-to-source>
    python tools/ingest.py raw/articles/my-article.md
    python tools/ingest.py --validate-only   # run validation on existing wiki

The LLM reads the source, extracts knowledge, and updates the wiki:
  - Creates wiki/sources/<slug>.md
  - Updates wiki/index.md
  - Updates wiki/overview.md (if warranted)
  - Creates/updates entity and concept pages
  - Appends to wiki/log.md
  - Flags contradictions
  - Runs post-ingest validation (broken links, index coverage)
```

# Second step to build
```
Query the LLM Wiki.

Usage:
    python tools/query.py "What are the main themes across all sources?"
    python tools/query.py "How does ConceptA relate to ConceptB?" --save
    python tools/query.py "Summarize everything about EntityName" --save synthesis/my-analysis.md

Flags:
    --save              Save the answer back into the wiki (prompts for filename)
    --save <path>       Save to a specific wiki path
```

# Third step to build
```
Lint the LLM Wiki for health issues.

Usage:
    python tools/lint.py
    python tools/lint.py --save          # save lint report to wiki/lint-report.md

Checks:
  - Orphan pages (no inbound wikilinks from other pages)
  - Broken wikilinks (pointing to pages that don't exist)
  - Missing entity pages (entities mentioned in 3+ pages but no page)
  - Contradictions between pages
  - Data gaps and suggested new sources
```

# Fourth step to build
```
Build the knowledge graph from the wiki.

Usage:
    python tools/build_graph.py               # full rebuild
    python tools/build_graph.py --no-infer    # skip semantic inference (faster)
    python tools/build_graph.py --open        # open graph.html in browser after build

Outputs:
    graph/graph.json    — node/edge data (cached by SHA256)
    graph/graph.html    — interactive vis.js visualization

Edge types:
    EXTRACTED   — explicit [[wikilink]] in a page
    INFERRED    — Claude-detected implicit relationship
    AMBIGUOUS   — low-confidence inferred relationship
```

# Fifth step to build
```
Graph Self-Healing Tool

Automatically retrieves "Missing Entity Pages" from the wiki and generates 
comprehensive definition pages for them using the LLM. 
It resolves broken entity links by scanning existing contexts where the entity is referenced.

Usage:
    python tools/heal.**py**
```

# Finally step to build
```
Refresh stale source pages by re-ingesting from raw documents.

Usage:
    python tools/refresh.py                     # refresh only changed sources
    python tools/refresh.py --force             # force re-ingest all sources
    python tools/refresh.py --page sources/X    # refresh a specific page

Compares raw document hashes against stored hashes to detect changes.
Re-ingests changed documents to update wiki/sources/ pages with accurate facts.
```

# Overall run
```
Single entry point for the wiki pipeline.

Usage:
    python run.py ingest raw/papers/my-paper.md
    python run.py ingest raw/my_knowledge_notes/   # bulk ingest a folder
    python run.py query "what do I know about transformers?"
    python run.py lint
    python run.py graph
    python run.py refresh
    python run.py heal
    python run.py chat    # skip pipeline, open Gemini CLI directly
```