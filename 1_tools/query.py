import sys
import re
import json
import argparse
from pathlib import Path
from datetime import date

from utils import _call_ollama, _call_gemini, call_gemini_cli, read_file, write_file, append_log, safe_wiki_path, REPO_ROOT, WIKI_DIR, LOG_FILE, INDEX_FILE, OVERVIEW_FILE, SCHEMA_FILE


def find_relevant_pages(question: str, index_content: str, model: str = "ollama") -> list[Path]:
    """Ask the LLM to identify relevant pages from the index."""
    prompt = f"""Given this wiki index:

            {index_content}

            Which pages are most relevant to answering: "{question}"

            Guidelines:
            - For questions about research, methodology, or what papers say → prefer pages under sources/papers/
            - For questions about personal understanding or concepts → prefer pages under sources/notes/
            - Always include overview.md if the question is broad or thematic

            Return ONLY a JSON array of relative file paths exactly as listed in the index.
            Examples: ["sources/papers/slug.md", "sources/notes/slug.md", "concepts/Bar.md"]
            Maximum 10 pages.
            """
    if model == "gemini-cli":
        raw = call_gemini_cli(prompt)
    elif model == "gemini":
        raw = _call_gemini(prompt, max_tokens=512)
    else:
        raw = _call_ollama(prompt, max_tokens=512)
    raw = raw.strip()
    # Try to find a JSON array in the output
    json_match = re.search(r"(\[[\s\S]*\])", raw)
    if json_match:
        raw = json_match.group(1)
    try:
        paths = json.loads(raw)
        relevant = [WIKI_DIR / p for p in paths if (WIKI_DIR / p).exists()]
    except (json.JSONDecodeError, TypeError):
        relevant = []

    # Always include overview
    overview = WIKI_DIR / "overview.md"
    if overview.exists() and overview not in relevant:
        relevant.insert(0, overview)

    return relevant[:15]


def query(question: str, save_path: str | None = None, model: str = "ollama"):
    today = date.today().isoformat()

    # Step 1: Read index
    index_content = read_file(INDEX_FILE)
    if not index_content:
        print("Wiki is empty. Ingest some sources first with: python tools/ingest.py <source>")
        sys.exit(1)

    # Step 2: Find relevant pages
    relevant_pages = find_relevant_pages(question, index_content, model=model)

    # If no keyword match, ask Claude to identify relevant pages from the index
    if not relevant_pages or len(relevant_pages) <= 1:
        print("  selecting relevant pages via API...")
        prompt = f"""Given this wiki index:

            {index_content}

            Which pages are most relevant to answering: "{question}"

            Guidelines:
            - For questions about research, methodology, or what papers say → prefer pages under sources/papers/
            - For questions about personal understanding or concepts → prefer pages under sources/notes/
            - Always include overview.md if the question is broad or thematic

            Return ONLY a JSON array of relative file paths exactly as listed in the index.
            Examples: ["sources/papers/slug.md", "sources/notes/slug.md", "concepts/Bar.md"]
            Maximum 10 pages.
            """
        if model == "gemini-cli":
            raw = call_gemini_cli(prompt)
        elif model == "gemini":
            raw = _call_gemini(prompt, max_tokens=512)
        else:
            raw = _call_ollama(prompt, max_tokens=512)
        raw = raw.strip()
        # Try to find a JSON array in the output
        json_match = re.search(r"(\[[\s\S]*\])", raw)
        if json_match:
            raw = json_match.group(1)
        try:
            paths = json.loads(raw)
            relevant_pages = [WIKI_DIR / p for p in paths if (WIKI_DIR / p).exists()]
        except (json.JSONDecodeError, TypeError):
            pass

    # Step 3: Read relevant pages
    pages_context = ""
    for p in relevant_pages:
        rel = p.relative_to(REPO_ROOT)
        pages_context += f"\n\n### {rel}\n{p.read_text(encoding='utf-8')}"

    if not pages_context:
        pages_context = f"\n\n### wiki/index.md\n{index_content}"

    schema = read_file(SCHEMA_FILE)

    # Step 4: Synthesize answer
    print(f"  synthesizing answer from {len(relevant_pages)} pages...")
    prompt = f"""You are querying an LLM Wiki to answer a question. Use the wiki pages below to synthesize a thorough answer. Cite sources using [[PageName]] wikilink syntax.

        When reading the wiki pages, follow these rules:
        - Pages under sources/papers/ are summaries of external academic papers — treat their content as citations from literature.
        - Pages under sources/notes/ are the user's own synthesized understanding — treat their content as the user's personal knowledge.
        - Any content prefixed with "User notes:" is personal opinion — present it clearly as the user's own view, not as an established fact.

        Schema:
        {schema}

        Wiki pages:
        {pages_context}

        Question: {question}

        Write a well-structured markdown answer with headers, bullets, and [[wikilink]] citations. At the end, add a ## Sources section listing the pages you drew from.
        """
    if model == "gemini-cli":
        answer = call_gemini_cli(prompt)
    elif model == "gemini":
        answer = _call_gemini(prompt, max_tokens=4096)
    else:
        answer = _call_ollama(prompt, max_tokens=4096)
    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60)

    # Step 5: Optionally save answer
    if save_path is not None:
        if save_path == "":
            # Prompt for filename
            slug_input = input("\nSave as (slug, e.g. 'my-analysis'): ").strip()
            if not slug_input:
                print("Skipping save.")
                return
            # Sanitize the slug to a single filename segment
            slug_clean = re.sub(r"[^A-Za-z0-9_\-]", "-", slug_input).strip("-._")[:100]
            if not slug_clean:
                print("Invalid slug — skipping save.")
                return
            save_path = f"syntheses/{slug_clean}.md"

        try:
            full_save_path = safe_wiki_path(save_path)
        except ValueError as e:
            print(f"Error: unsafe --save path: {e}")
            sys.exit(1)
        if full_save_path.suffix != ".md":
            print("Error: --save path must end with .md")
            sys.exit(1)
        frontmatter = f"""---
                        title: "{question[:80]}"
                        type: synthesis
                        tags: []
                        sources: []
                        last_updated: {today}
                        ---

                        """
        write_file(full_save_path, frontmatter + answer)

        # Update index
        index_content = read_file(INDEX_FILE)
        entry = f"- [{question[:60]}]({save_path}) — synthesis"
        if "## Syntheses" in index_content:
            index_content = index_content.replace("## Syntheses\n", f"## Syntheses\n{entry}\n")
            INDEX_FILE.write_text(index_content, encoding="utf-8")
        print(f"  indexed: {save_path}")

    # Append to log
    append_log(f"## [{today}] query | {question[:80]}\n\nSynthesized answer from {len(relevant_pages)} pages." +
               (f" Saved to {save_path}." if save_path else ""))
    
    return answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the LLM Wiki")
    parser.add_argument("question", help="Question to ask the wiki")
    parser.add_argument("--save", nargs="?", const="", default=None,
                        help="Save answer to wiki (optionally specify path)")
    parser.add_argument("--model", choices=["ollama", "gemini", "gemini-cli"], default="ollama",
                        help="Choose which LLM backend to use (default: ollama)")
    args = parser.parse_args()
    query(args.question, args.save, args.model)
