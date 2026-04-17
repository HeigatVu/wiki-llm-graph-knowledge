# LLM Wiki Agent — Schema & Workflow Instructions

This wiki is maintained entirely by Gemini CLI. No API key or Python scripts needed — just open this repo with `gemini` and talk to it.

## Startup Behavior

When the user opens this repo, ALWAYS read these files first before doing anything:
1. `WIKI_STATUS.md` — shows what the Python pipeline last did
2. `30_wiki/index.md` — current wiki contents
3. `30_wiki/overview.md` — living synthesis

Then greet the user with a one-line summary of the current wiki state.
Example: "Wiki has 12 papers, 8 notes, 34 concepts. Last action: ingest | Attention Is All You Need."

## How to Use

Describe what you want in plain English:
- *"Ingest this file: 20_raw/papers/my-paper.md"*
- *"What does the wiki say about transformer models?"*
- *"Check the wiki for orphan pages and contradictions"*
- *"Build the knowledge graph"*

Or use shorthand triggers:
- `ingest <file>` → runs the Ingest Workflow
- `query: <question>` → runs the Query Workflow
- `lint` → runs the Lint Workflow
- `build graph` → runs the Graph Workflow

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

## Slash Command Shortcuts
- `/wiki-ingest <file>` → run Ingest Workflow
- `/wiki-query <question>` → run Query Workflow  
- `/wiki-lint` → run Lint Workflow
- `/wiki-graph` → run Graph Workflow
- `/wiki-gap` → run Gap Analysis
- `/wiki-heal` → run Heal Workflow
- `/wiki-refresh` → run Refresh Workflow


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

---

## Query Workflow

Triggered by: *"query: <question>"*

1. Read `30_wiki/index.md` — identify relevant pages
2. Read those pages
3. Synthesize answer with `[[PageName]]` citations
4. Offer to save as `30_wiki/syntheses/<slug>.md`

---

## Lint Workflow

Triggered by: *"lint"*

Check for: orphan pages, broken links, contradictions, stale content, missing entity pages, data gaps.

---

## Graph Workflow

Triggered by: *"build graph"*

Try `python run.py graph --open` first. If unavailable, build graph.json and graph.html manually from wikilinks.

---

## Naming Conventions

- Source slugs: `kebab-case`
- Entity/Concept pages: `TitleCase.md`

## Log Format

`## [YYYY-MM-DD] <operation> | <title>`