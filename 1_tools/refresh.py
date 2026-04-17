import os
import sys
import json
import hashlib
import re
from typing import Optional
from pathlib import Path
from datetime import date

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "30_wiki"
RAW_DIR = REPO_ROOT / "raw"
SOURCES_DIR = WIKI_DIR / "sources"
REFRESH_CACHE = REPO_ROOT / "2_graph" / ".refresh_cache.json"
MANIFEST_FILE = REPO_ROOT / "2_graph" / ".ingest_manifest.json"

def safe_wiki_path(relative_path: str) -> Path:
    """Resolve a wiki-relative path and ensure it stays inside WIKI_DIR."""
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


def load_manifest() -> dict:
    """Load the ingest manifest."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def delete_stale_pages(raw_path: Path) -> int:
    """Delete wiki pages previously created by this source file.
    
    Returns the number of pages deleted.
    """
    manifest = load_manifest()
    key = str(raw_path.resolve())
    stale_pages = manifest.get(key, [])

    deleted = 0
    for page_path_str in stale_pages:
        page_path = Path(page_path_str)
        if page_path.exists():
            page_path.unlink()
            print(f"  deleted stale page: {page_path.name}")
            deleted += 1

    return deleted

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_refresh_cache() -> dict:
    if REFRESH_CACHE.exists():
        try:
            return json.loads(REFRESH_CACHE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_refresh_cache(cache: dict):
    REFRESH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    REFRESH_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def extract_source_file(content: str) -> Optional[str]:
    """Extract source_file from YAML frontmatter."""
    match = re.search(r'^source_file:\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    return None


def find_stale_sources(force: bool = False) -> list[tuple[Path, Path]]:
    """Return list of (wiki_source_page, raw_document) pairs that need refresh."""
    cache = load_refresh_cache()
    stale = []

    if not SOURCES_DIR.exists():
        return stale

    for wiki_page in sorted(SOURCES_DIR.rglob("*.md")):
        content = read_file(wiki_page)
        source_file = extract_source_file(content)
        if not source_file:
            continue                    # skip pages with no source_file
        if source_file.endswith(".pdf"):
            continue                    # skip PDF-sourced pages

        raw_path = REPO_ROOT / source_file
        if not raw_path.exists():
            # Try relative to raw/
            raw_path = RAW_DIR / source_file
            if not raw_path.exists():
                continue

        raw_content = read_file(raw_path)
        current_hash = sha256(raw_content)
        cached_hash = cache.get(str(raw_path))

        if force or cached_hash != current_hash:
            stale.append((wiki_page, raw_path))

    return stale


def refresh_page(wiki_page: Path, raw_path: Path) -> bool:
    """Delete stale pages then re-ingest a single source document."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from ingest import ingest
        print(f"\n{'='*60}")
        print(f"  Refreshing: {wiki_page.name}")
        print(f"  From:       {raw_path}")
        print(f"{'='*60}")

        # Delete pages created by the previous ingest of this source
        deleted = delete_stale_pages(raw_path)
        if deleted:
            print(f"  cleaned up {deleted} stale page(s) from previous ingest")
        else:
            print(f"  no stale pages found in manifest — skipping cleanup")

        ingest(str(raw_path))
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to refresh {wiki_page.name}: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Refresh stale wiki source pages")
    parser.add_argument("--force", action="store_true", help="Force re-ingest all sources")
    parser.add_argument("--page", type=str, help="Refresh a specific wiki source page (e.g., sources/my-page)")
    parser.add_argument("--dry-run", action="store_true", help="Only list stale pages, don't refresh")
    args = parser.parse_args()

    if args.page:
        # Refresh a single specific page — validate the path stays inside the wiki
        page_arg = args.page
        if not Path(page_arg).suffix:
            page_arg = page_arg + ".md"
        try:
            wiki_page = safe_wiki_path(page_arg)
        except ValueError as e:
            print(f"Error: unsafe --page path: {e}")
            sys.exit(1)
        if not wiki_page.exists():
            print(f"Page not found: {wiki_page}")
            sys.exit(1)
        content = read_file(wiki_page)
        source_file = extract_source_file(content)
        if not source_file:
            print(f"No source_file found in frontmatter of {wiki_page.name}")
            sys.exit(1)
        raw_path = REPO_ROOT / source_file
        if not raw_path.exists():
            raw_path = RAW_DIR / source_file
        if not raw_path.exists():
            print(f"Raw document not found: {source_file}")
            sys.exit(1)
        stale = [(wiki_page, raw_path)]
    else:
        stale = find_stale_sources(force=args.force)

    if not stale:
        print("All source pages are up to date. Nothing to refresh.")
        return

    print(f"Found {len(stale)} stale source page(s):")
    for wiki_page, raw_path in stale:
        print(f"  • {wiki_page.name} ← {raw_path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    # Refresh each stale page
    cache = load_refresh_cache()
    refreshed = 0
    failed = 0

    for wiki_page, raw_path in stale:
        if refresh_page(wiki_page, raw_path):
            raw_content = read_file(raw_path)
            cache[str(raw_path)] = sha256(raw_content)
            refreshed += 1
        else:
            failed += 1

    save_refresh_cache(cache)

    print(f"\n{'='*60}")
    print(f"  Refresh complete: {refreshed} updated, {failed} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
