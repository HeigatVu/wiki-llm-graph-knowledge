import os
import sys
import json
import hashlib
import re
from pathlib import Path 
from datetime import date

from utils import _call_gemini

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "30_wiki"
LOG_FILE = WIKI_DIR / "log.md"
INDEX_FILE = WIKI_DIR / "index.md"
OVERVIEW_FILE = WIKI_DIR / "overview.md"
SCHEMA_FILE = WIKI_DIR / "GEMINI.md"
MANIFEST_FILE = REPO_ROOT / "2_graph" / ".ingest_manifest.json"

def load_manifest() -> dict:
    """Load the ingest manifest mapping source files to created wiki pages."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_manifest(manifest: dict) -> None:
    """Save the ingest manifest."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

def sha256(text:str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def read_file(path:Path) -> str:
    """Read file content safely."""
    return path.read_text(encoding="utf-8") if path.exists() else ""

def safe_wiki_path(relative_path: str) -> Path:
    """Resolve a wiki-relative path and ensure it stays inside WIKI_DIR.

    Rejects absolute paths and any traversal (e.g. '../etc/passwd') that
    would escape the wiki directory. This is important because some paths
    come from LLM output (e.g. entity/concept page paths, source slugs) and
    could otherwise be abused via prompt injection in source documents to
    write arbitrary files.
    """
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ValueError(f"Refusing absolute path inside wiki: {relative_path!r}")
    candidate = (WIKI_DIR / rel).resolve()
    wiki_root = WIKI_DIR.resolve()
    if candidate != wiki_root and wiki_root not in candidate.parents:
        raise ValueError(
            f"Refusing path that escapes wiki directory: {relative_path!r}"
        )
    return candidate


def safe_slug(slug: str) -> str:
    """Sanitize an LLM-provided slug to a safe single-segment filename stem."""
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("Empty or non-string slug")
    # Keep only lowercase letters, digits, dashes and underscores
    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "-", slug.strip()).strip("-._")
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"Unsafe slug: {slug!r}")
    # Cap length to avoid pathological filenames
    return cleaned[:100]


def write_file(path:Path, content:str) -> None:
    """Write file content safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote: {path.relative_to(REPO_ROOT)}")
    
def build_wiki_context(source_content: str) -> str:
    """Build wiki context from index, overview, and topically relevant sources.
    
    Instead of pulling the 5 most recently modified pages (which are often
    unrelated to the new source), we extract wikilinks already present in the
    source content and pull those pages specifically. This keeps the context
    window focused and avoids feeding the LLM irrelevant pages.
    """
    parts = []

    # Always include index and overview
    if INDEX_FILE.exists():
        parts.append(f"## 30_wiki/index.md\n{read_file(INDEX_FILE)}")
    if OVERVIEW_FILE.exists():
        parts.append(f"## 30_wiki/overview.md\n{read_file(OVERVIEW_FILE)}")

    # Find pages explicitly linked in the source content
    linked_names = re.findall(r'\[\[([^\]]+)\]\]', source_content)

    # Also extract candidate names from the source frontmatter and headings
    # so even un-wikilinked references get matched
    heading_words = re.findall(r'^#{1,3}\s+(.+)$', source_content, re.MULTILINE)
    frontmatter_match = re.match(r'^---\n(.*?)\n---', source_content, re.DOTALL)
    frontmatter_text = frontmatter_match.group(1) if frontmatter_match else ""

    # Build a lookup of all existing wiki pages by stem
    sources_dir = WIKI_DIR / "sources"
    entities_dir = WIKI_DIR / "entities"
    concepts_dir = WIKI_DIR / "concepts"

    all_pages: dict[str, Path] = {}
    for d in [sources_dir, entities_dir, concepts_dir]:
        if d.exists():
            for p in d.rglob("*.md"):
                all_pages[p.stem.lower()] = p

    # Pull pages that are explicitly wikilinked
    relevant: list[Path] = []
    seen: set[str] = set()
    for name in linked_names:
        key = name.lower()
        if key in all_pages and key not in seen:
            seen.add(key)
            relevant.append(all_pages[key])

    # If we found fewer than 3 linked pages, fall back to heading-word matching
    # so we still get some context for sources with no wikilinks yet
    if len(relevant) < 3:
        for heading in heading_words:
            for word in heading.split():
                key = word.strip(":.,-").lower()
                if len(key) > 4 and key in all_pages and key not in seen:
                    seen.add(key)
                    relevant.append(all_pages[key])
                if len(relevant) >= 5:
                    break
            if len(relevant) >= 5:
                break

    # Cap at 5 pages to avoid blowing the context window
    for p in relevant[:5]:
        parts.append(f"## {p.relative_to(REPO_ROOT)}\n{read_file(p)}")

    return "\n\n---\n\n".join(parts)

def parse_json_from_response(text:str) -> dict:
    """Parse JSON from LLM response."""
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    # Find the outermost JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object founmd in response")
    return json.loads(match.group())

def update_index(new_entry: str, section: str = "Sources"):
    content = read_file(INDEX_FILE)
    if not content:
        content = "# Wiki Index\n\n## Overview\n- [Overview](overview.md) — living synthesis\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n"
    section_header = f"## {section}"
    if section_header in content:
        content = content.replace(section_header + "\n", section_header + "\n" + new_entry + "\n")
    else:
        content += f"\n{section_header}\n{new_entry}\n"
    write_file(INDEX_FILE, content)
    
def append_log(entry:str) -> None:
    """Append entry to log.md."""
    existing = read_file(LOG_FILE)
    write_file(LOG_FILE, entry.strip() + "\n\n" + existing)
    
def extract_wikilinks(content:str) -> list[str]:
    """Extract wikilinks from content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)

def all_wiki_pages() -> set[str]:
    """Return set of all wiki page titles."""
    pages = set()
    for p in WIKI_DIR.rglob("*.md"):
        if p.name not in ("index.md", "overview.md", "log.md"):
            pages.add(p.stem.lower())
    return pages

def validate_ingest(changed_pages: list[str] | None = None) -> dict:
    """Validate wiki integrity after an ingest.

    Checks:
      1. Broken wikilinks in changed pages (or all pages if none specified)
      2. Pages not registered in index.md

    Returns dict with 'broken_links' and 'unindexed' lists.
    """
    existing_pages = all_wiki_pages()
    index_content = read_file(INDEX_FILE).lower()

    # Determine which pages to scan for broken links
    if changed_pages:
        scan_paths = [WIKI_DIR / p for p in changed_pages if (WIKI_DIR / p).exists()]
    else:
        scan_paths = [p for p in WIKI_DIR.rglob("*.md")
                      if p.name not in ("index.md", "log.md", "lint-report.md")]

    # Check 1: Broken wikilinks
    broken_links = []
    for page_path in scan_paths:
        content = read_file(page_path)
        rel = str(page_path.relative_to(WIKI_DIR))
        for link in extract_wikilinks(content):
            # Normalize: strip paths, check stem only
            link_stem = Path(link).stem.lower() if '/' in link else link.lower()
            if link_stem not in existing_pages:
                broken_links.append((rel, link))

    # Check 2: Unindexed pages (only check changed pages)
    unindexed = []
    for p in (changed_pages or []):
        page_path = WIKI_DIR / p
        if page_path.exists():
            # Check if the page filename appears in index.md
            stem = page_path.stem.lower()
            if stem not in index_content and p not in ("log.md", "overview.md"):
                unindexed.append(p)

    return {"broken_links": broken_links, "unindexed": unindexed}

def build_ingest_prompt(source_content, source, wiki_context, schema, today, note_type):
    if note_type == "paper":
        type_instructions = """
            Note type: ACADEMIC PAPER
            - Separate objective claims (Key Methodology / Results) from subjective opinions (Personal Critique).
            - Prefix critique content with "User notes:" in the source page — do not treat as factual claims.
            - Extract authors as entity pages if they appear significantly.
            - Map Key Methodology items to concept pages aggressively.
            - Include Year and Source in the source page frontmatter.
            """
    elif note_type == "book":
        type_instructions = """
            Note type: BOOK (extracted via NotebookLM — grounded, low hallucination)
            - This is a structured extraction from a full book. The content is grounded on
              the actual source text, so treat claims as reliable.
            - PRESERVE the Chapter Checkpoints structure — do NOT flatten it.
            - Extract the author as an entity page.
            - Be VERY aggressive about creating concept pages from Key Concepts in each chapter.
            - Create entity pages for all people, organizations, and products mentioned.
            - Cross-Cutting Themes should become concept pages that link to multiple chapters.
            - The source page should keep the chapter-by-chapter structure for easy lookup.
            - Add [[wikilinks]] to EVERY concept, entity, and cross-reference inline.
            - If "Related Topics" or "Cross-Cutting Themes" are listed, check if they match
              existing wiki concepts and link them. If not, create new concept pages.
            """
    else:
        type_instructions = """
            Note type: PERSONAL KNOWLEDGE NOTE
            - Treat all content as the user's own synthesized understanding, not a citation.
            - Do NOT create author entity pages.
            - Be aggressive about creating concept pages — this note IS the primary source.
            - No external citation to attribute claims to.
            """
 
    prompt = f"""You are maintaining an LLM Wiki. Process this source document and integrate its knowledge into the wiki.
 
        {type_instructions}
        Schema and conventions:
        {schema}
 
        Current wiki state (index + recent pages):
        {wiki_context if wiki_context else "(wiki is empty — this is the first source)"}
 
        New source to ingest (file: {source.relative_to(REPO_ROOT) if source.is_relative_to(REPO_ROOT) else source.name}):
        === SOURCE START ===
        {source_content}
        === SOURCE END ===
 
        Today's date: {today}
 
        Return ONLY a valid JSON object with these fields (no markdown fences, no prose outside the JSON):
        {{
        "title": "Human-readable title for this source",
        "slug": "kebab-case-slug-for-filename",
        "source_page": "full markdown content for wiki/sources/<slug>.md — use the source page format from the schema. CRITICAL: Aggressively convert key people, products, concepts and projects into [[Wikilinks]] inline in the text. Omitting [[ ]] for known terms is a failure.",
        "index_entry": "- [Title](sources/slug.md) — one-line summary",
        "overview_update": "full updated content for wiki/overview.md, or null if no update needed",
        "entity_pages": [
            {{"path": "entities/EntityName.md", "content": "full markdown content"}}
        ],
        "concept_pages": [
            {{"path": "concepts/ConceptName.md", "content": "full markdown content"}}
        ],
        "contradictions": ["describe any contradiction with existing wiki content, or empty list"],
        "log_entry": "## [{today}] ingest | <title>\\n\\nAdded source. Key claims: ..."
        }}
        """
    return prompt

def detect_note_type(source_path: Path, content: str) -> str:
    path_str = str(source_path)
 
    # Path-based detection first — most reliable
    if "papers/my_notes" in path_str or "papers/pdf" in path_str:
        return "paper"
    if "my_knowledge_notes" in path_str:
        return "knowledge"
    # NEW: detect book type
    if "/books/" in path_str:
        return "book"
 
    # Fallback: inspect frontmatter fields
    frontmatter = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if frontmatter:
        fields = frontmatter.group(1)
 
        # NEW: check for book tag in frontmatter
        if re.search(r'tags:\s*\[.*book.*\]', fields):
            return "book"
 
        has_paper_fields = any(
            re.search(rf'^{field}:', fields, re.MULTILINE)
            for field in ["Title", "Authors", "Year", "Source"]
        )
        if has_paper_fields:
            return "paper"
 
    return "knowledge"

def read_source(source: Path) -> str:
    if source.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("Error: pypdf not installed. Run: pip install pypdf")
            sys.exit(1)
        reader = PdfReader(str(source))
        return "\n\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
    return source.read_text(encoding="utf-8")

def ingest(source_path:str) -> None:
    """Ingest a source file into the wiki."""
    source = Path(source_path)
    if not source.exists():
        print(f"Error: Source file not found: {source}")
        sys.exit(1)
        
    source_content = read_source(source)
    source_hash = sha256(source_content)
    today = date.today().isoformat()
    print(f"\nIngesting: {source.name}  (hash: {source_hash})")
    
    wiki_context = build_wiki_context(source_content)
    schema = read_file(SCHEMA_FILE)
    
    note_type = detect_note_type(source, source_content)
    prompt = build_ingest_prompt(source_content, source, wiki_context, schema, today, note_type)
    
    print(f"Calling API (model: ...)")
    raw = _call_gemini(prompt, max_tokens=8192)
    try:
        data = parse_json_from_response(raw)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error: Failed to parse JSON from LLM response: {e}")
        print("Raw response saved to /tmp/ingest_debug.txt:\n")
        Path("/tmp/ingest_debug.txt").write_text(raw)
        sys.exit(1)
        
    # Write source page
    if note_type == "paper":
        subdir = "papers"
    elif note_type == "book":
        subdir = "books"
    else:
        subdir = "notes"
    write_file(WIKI_DIR / "sources" / subdir / f"{data['slug']}.md", data["source_page"])


    # Write entity pages — validate LLM-provided paths to block traversal.
    # Only allow paths under entities/ or concepts/ to avoid overwriting
    # index.md, log.md, or arbitrary files elsewhere in the repo.
    def _safe_sub_path(raw_path: str, allowed_prefix: str) -> Path | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        try:
            resolved = safe_wiki_path(raw_path)
        except ValueError as exc:
            print(f"  [warn] skipping unsafe page path {raw_path!r}: {exc}")
            return None
        allowed_root = (WIKI_DIR / allowed_prefix).resolve()
        if allowed_root not in resolved.parents:
            print(
                f"  [warn] skipping page path outside {allowed_prefix}/: {raw_path!r}"
            )
            return None
        if resolved.suffix != ".md":
            print(f"  [warn] skipping non-markdown page path: {raw_path!r}")
            return None
        return resolved

    for page in data.get("entity_pages", []):
        target = _safe_sub_path(page.get("path", ""), "entities")
        if target is not None:
            write_file(target, page.get("content", ""))

    # Write concept pages
    for page in data.get("concept_pages", []):
        target = _safe_sub_path(page.get("path", ""), "concepts")
        if target is not None:
            write_file(target, page.get("content", ""))
        
    # Update overview
    if data.get("overview_update"):
        write_file(OVERVIEW_FILE, data["overview_update"])
        
    # Update index
    if note_type == "paper":
        section = "Papers"
    elif note_type == "book":
        section = "Books"
    else:
        section = "Notes"
    update_index(data["index_entry"], section=section)
    
    # Log
    append_log(data["log_entry"])

    # Report contradictions
    contradictions = data.get("contradictions", [])
    if contradictions:
        print("\n  ⚠️  Contradictions detected:")
        for c in contradictions:
            print(f"     - {c}")

    # --- Post-ingest validation ---
    created_pages = [f"sources/{data['slug']}.md"]
    for page in data.get("entity_pages", []):
        created_pages.append(page["path"])
    for page in data.get("concept_pages", []):
        created_pages.append(page["path"])
    updated_pages = ["index.md", "log.md"]
    if data.get("overview_update"):
        updated_pages.append("overview.md")
        
    # Validate created/updated files
    validation = validate_ingest(created_pages)

    print(f"\n{'='*50}")
    print(f"  ✅ Ingested: {data['title']}")
    print(f"{'='*50}")
    print(f"  Created : {len(created_pages)} pages")
    for p in created_pages:
        print(f"           + 30_wiki/{p}")
    print(f"  Updated : {len(updated_pages)} pages")
    for p in updated_pages:
        print(f"           ~ 30_wiki/{p}")
    if contradictions:
        print(f"  Warnings: {len(contradictions)} contradiction(s)")
    if validation["broken_links"]:
        print(f"  ⚠️  Broken links: {len(validation['broken_links'])}")
        for page, link in validation["broken_links"][:10]:
            print(f"           30_wiki/{page} → [[{link}]]")
        if len(validation["broken_links"]) > 10:
            print(f"           ... and {len(validation['broken_links']) - 10} more")
    if validation["unindexed"]:
        print(f"  ⚠️  Not in index.md: {len(validation['unindexed'])}")
        for p in validation["unindexed"][:10]:
            print(f"           30_wiki/{p}")
        if len(validation["unindexed"]) > 10:
            print(f"           ... and {len(validation['unindexed']) - 10} more")
    if not validation["broken_links"] and not validation["unindexed"]:
        print("  ✓ Validation passed — no broken links, all pages indexed")
    print()

    update_status(
        action=f"ingest | {data['title']}",
        details=f"Created {len(created_pages)} pages. Contradictions: {len(contradictions)}"
    )
    
    # Record which pages this source created so refresh.py can clean them up later
    manifest = load_manifest()
    manifest[str(source.resolve())] = [
        str((WIKI_DIR / p).resolve()) for p in created_pages
    ]
    save_manifest(manifest)
    
def update_status(action: str, details: str):
    """Write a status file so Gemini CLI knows the current wiki state."""
    status_path = REPO_ROOT / "WIKI_STATUS.md"
    today = date.today().isoformat()
    
    index_content = read_file(INDEX_FILE)
    
    # Count pages by type
    papers = list((WIKI_DIR / "sources" / "papers").glob("*.md")) if (WIKI_DIR / "sources" / "papers").exists() else []
    notes = list((WIKI_DIR / "sources" / "notes").glob("*.md")) if (WIKI_DIR / "sources" / "notes").exists() else []
    books = list((WIKI_DIR / "sources" / "books").glob("*.md")) if (WIKI_DIR / "sources" / "books").exists() else []
    entities = list((WIKI_DIR / "entities").glob("*.md")) if (WIKI_DIR / "entities").exists() else []
    concepts = list((WIKI_DIR / "concepts").glob("*.md")) if (WIKI_DIR / "concepts").exists() else []

    content = f"""# Wiki Status
Last updated: {today}
Last action: {action}

## Stats
- Papers: {len(papers)}
- Knowledge notes: {len(notes)}
- Books: {len(books)}
- Entities: {len(entities)}
- Concepts: {len(concepts)}

## Last Action Details
{details}

## Suggested Next Steps
- Run `/wiki-query` to explore what was just added
- Run `/wiki-lint` to check for gaps or contradictions
- Run `/wiki-graph` to rebuild the knowledge graph
"""
    status_path.write_text(content, encoding="utf-8")    


if __name__ == "__main__":
    # Handle --validate-only flag
    if len(sys.argv) == 2 and sys.argv[1] == "--validate-only":
        print("Running wiki validation (no ingest)...\n")
        result = validate_ingest()
        if result["broken_links"]:
            print(f"Broken wikilinks: {len(result['broken_links'])}")
            for page, link in result["broken_links"][:20]:
                print(f"  30_wiki/{page} → [[{link}]]")
            if len(result["broken_links"]) > 20:
                print(f"  ... and {len(result['broken_links']) - 20} more")
        else:
            print("No broken wikilinks found.")
        print()
        pages = all_wiki_pages()
        index_content = read_file(INDEX_FILE).lower()
        unindexed_all = []
        for p in WIKI_DIR.rglob("*.md"):
            if p.name in ("index.md", "log.md", "lint-report.md", "overview.md"):
                continue
            if p.stem.lower() not in index_content:
                unindexed_all.append(str(p.relative_to(WIKI_DIR)))
        if unindexed_all:
            print(f"Pages not in index.md: {len(unindexed_all)}")
            for up in unindexed_all[:20]:
                print(f"  30_wiki/{up}")
            if len(unindexed_all) > 20:
                print(f"  ... and {len(unindexed_all) - 20} more")
        else:
            print("All pages are indexed.")
        sys.exit(0)

    if len(sys.argv) < 2:
        print("Usage: python tools/ingest.py <path-to-source> [path2 ...] [dir1 ...]")
        print("       python tools/ingest.py --validate-only")
        sys.exit(1)
        
    paths_to_process = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_file() and p.suffix == ".md":
            paths_to_process.append(p)
        elif p.is_dir():
            for f in p.rglob("*.md"):
                if f.is_file():
                    paths_to_process.append(f)
        else:
            import glob
            for f in glob.glob(arg, recursive=True):
                g_p = Path(f)
                if g_p.is_file() and g_p.suffix == ".md":
                    paths_to_process.append(g_p)
                    
    # Deduplicate while preserving order
    unique_paths = []
    seen = set()
    for p in paths_to_process:
        abs_p = p.resolve()
        if abs_p not in seen:
            seen.add(abs_p)
            unique_paths.append(p)

    if not unique_paths:
        print("Error: no markdown files found to ingest.")
        sys.exit(1)
        
    if len(unique_paths) > 1:
        print(f"Batch mode: found {len(unique_paths)} files to ingest.")
        
    for p in unique_paths:
        ingest(str(p))
        
    # Run gemini
    if "--handoff" in sys.argv:
        import subprocess
        print("\nHanding off to Gemini CLI...")
        subprocess.run(["gemini"], cwd=REPO_ROOT)
