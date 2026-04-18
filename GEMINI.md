# LLM Wiki Agent — Schema & Workflow Instructions

This wiki is maintained entirely by Gemini CLI. No API key or Python scripts needed — just open this repo with `gemini` and talk to it.

## Startup Behavior

When the user opens this repo, ALWAYS read these files first before doing anything:
1. `WIKI_STATUS.md` — shows what the Python pipeline last did
2. `30_wiki/index.md` — current wiki contents
3. `30_wiki/overview.md` — living synthesis

Then greet the user with a one-line summary of the current wiki state.
Example: "Wiki has 12 papers, 8 notes, 34 concepts. Last action: ingest | Attention Is All You Need."

## Slash Commands (Gemini CLI)

| Command | What to say / Example |
|---|---|
| `/wiki-ingest` | `ingest 20_raw/my-article.md` |
| `/wiki-query` | `query: what are the main themes?` |
| `/wiki-lint` | `lint the wiki` |
| `/wiki-graph` | `build the knowledge graph` |
| `/wiki-gap` | `find research gaps` |
| `/wiki-heal` | `heal missing pages` |
| `/wiki-refresh` | `refresh indices` |

Or just describe what you want in plain English:
- *"Ingest this file: 20_raw/papers/attention-is-all-you-need.md"*
- *"What does the wiki say about transformer models?"*
- *"Check the wiki for orphan pages and contradictions"*
- *"Build the graph and show me what's connected to Alzheimer's"*

---

## Directory Layout

```
20_raw/       # Immutable source documents — never modify these
30_wiki/      # Agent owns this layer entirely
  index.md    # Catalog of all pages — update on every ingest
  log.md      # Append-only chronological record
  overview.md # Living synthesis across all sources
  sources/    # One summary page per source document
  entities/   # People, companies, projects, products
  concepts/   # Ideas, frameworks, methods, theories
  syntheses/  # Saved query answers
2_graph/      # Auto-generated graph data
1_tools/      # Optional standalone Python scripts
```

---

## Page Format

Every wiki page uses this frontmatter:

```yaml
---
title: "Page Title"
type: source | entity | concept | synthesis
tags: []
sources: []
last_updated: YYYY-MM-DD
---
```

Use `[[PageName]]` wikilinks to link to other wiki pages.

---

## Ingest Workflow

Triggered by: *"ingest <file>"*

1. Read the source document fully
2. Read `30_wiki/index.md` and `30_wiki/overview.md` for current wiki context
3. Write `30_wiki/sources/<slug>.md` (source page format below)
4. Update `30_wiki/index.md` — add entry under Sources
5. Update `30_wiki/overview.md` — revise synthesis if warranted
6. Update/create entity and concept pages
7. Flag contradictions with existing wiki content
8. Append to `30_wiki/log.md`: `## [YYYY-MM-DD] ingest | <Title>`
9. **Post-ingest validation** — check for broken `[[wikilinks]]`, verify all new pages are in `index.md`, print a change summary


### Source Page Format

```markdown
---
title: "Source Title"
type: source
tags: []
date: YYYY-MM-DD
source_file: 20_raw/...
---

## Summary
2–4 sentence summary.

## Key Claims
- Claim 1

## Key Quotes
> "Quote here"

## Connections
- [[EntityName]] — how they relate

## Contradictions
- Contradicts [[OtherPage]] on: ...
```

### Domain-Specific Templates

If the source falls into a specific domain (e.g., personal diary, meeting notes), the agent should use a specialized template instead of the default generic one above:

#### Personal Knowledge Note Template
```markdown
---
title: "Concept or Topic Title"
type: source
tags: [personal-note]
date: YYYY-MM-DD
source_file: 20_raw/...
---

## Summary
User's own understanding in 2–4 sentences.

## Key Ideas
- Idea 1

## Connections
- [[ConceptName]] — how they relate

## Open Questions
- Question the user hasn't resolved yet
```

#### Diary / Journal Template
```markdown
---
title: "YYYY-MM-DD Diary"
type: source
tags: [diary]
date: YYYY-MM-DD
---
## Event Summary
...
## Key Decisions
...
## Energy & Mood
...
## Connections
...
## Shifts & Contradictions
...
```

#### Meeting Notes Template
```markdown
---
title: "Meeting Title"
type: source
tags: [meeting]
date: YYYY-MM-DD
---
## Goal
...
## Key Discussions
...
## Decisions Made
...
## Action Items
...
```

#### Book Template
---
title: "Book Title"
type: source
tags: [book]
author: 
year: 
source_file: 20_raw/books/...
---

## Summary
What is this book's main thesis or contribution in 2–4 sentences.

## Chapter Checkpoints

### Chapter 1: <Title>
- **Core idea**: ...
- **Key concepts**: [[Concept1]], [[Concept2]]
- **Key claims**:
  - Claim 1
  - Claim 2

(repeat for all chapters)

## Cross-Cutting Themes
- Theme 1: appears in chapters X, Y, Z
- Theme 2: appears in chapters X, Y, Z

## Key Entities
- [[EntityName]] — role in this book

## Connections
- [[ConceptName]] — how they relate

## Personal Notes
- User's own critique or reflection (added after ingestion)
---

## Query Workflow

Triggered by: *"query: <question>"*

1. Read `30_wiki/index.md` — identify relevant pages
2. Read those pages
3. Synthesize answer with `[[PageName]]` citations
4. Offer to save as `30_wiki/syntheses/<slug>.md`

---

## Lint Workflow

Triggered by: *"/wiki-lint"*

Use tools (like grep_search and view_file) to check for:
- **Orphan pages** — wiki pages with no inbound `[[links]]` from other pages
- **Broken links** — `[[WikiLinks]]` pointing to pages that don't exist
- **Contradictions** — claims that conflict across pages
- **Stale summaries** — pages not updated after newer sources
- **Missing entity pages** — entities mentioned in 3+ pages but lacking their own page
- **Data gaps** — questions the wiki can't answer; suggest new sources

Output a lint report and ask if the user wants it saved to `30_wiki/lint-report.md`.

---

## Graph Workflow

Triggered by: *"build graph"*

Try `uv run main.py graph --open --no-infer` first. If unavailable, build graph.json and graph.html manually from wikilinks.

---

## Gap Analysis Workflow

Triggered by: *"/wiki-gap"*

1. Read `30_wiki/overview.md` to understand the current "center of gravity" of the research.
2. Read `30_wiki/index.md` to see the breadth of Entities and Concepts.
3. Compare current state against the **Research Pillars** (e.g., Data Types, Processing, Models, Clinical context).
4. Identify "Islands": Topics mentioned with no supporting source papers.
5. Identify "Dead Ends": Claims that lack citations or follow-up.
6. Propose 3-5 specific questions or topics the user should research next.

---

## Heal Workflow

Triggered by: *"/wiki-heal"*

1. Identify concepts/entities in `index.md` mentioned 3+ times without a dedicated page.
2. For each, search the wiki for all mentions to gather context.
3. Create a new `entities/` or `concepts/` page using the standard template.
4. Update `30_wiki/index.md` and `30_wiki/overview.md`.

---

## Resource & Rate Limit Management

- **Rate Limits:** If the user asks to ingest more than 3 files at once, recommend they use the Python script (`for f in ...; do python 1_tools/ingest.py "$f"; done`) to respect the 10-second `time.sleep` delays and avoid API limits.
- **Context Limits:** Avoid reading more than 10 large files in a single turn to prevent context overflow.

---

## Naming Conventions

- Source slugs: `kebab-case`
- Entity/Concept pages: `TitleCase.md`

## Index Format

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources
- [Source Title](sources/slug.md) — one-line summary

## Entities
- [Entity Name](entities/EntityName.md) — one-line description

## Concepts
- [Concept Name](concepts/ConceptName.md) — one-line description

## Syntheses
- [Analysis Title](syntheses/slug.md) — what question it answers
```

## Log Format

Each entry starts with `## [YYYY-MM-DD] <operation> | <title>` so it's grep-parseable:

```
grep "^## \[" 30_wiki/log.md | tail -10
```

Operations: `ingest`, `query`, `lint`, `graph`, `gap`, `heal`, `refresh`