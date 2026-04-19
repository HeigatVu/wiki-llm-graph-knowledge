import os
import sys
import argparse
import subprocess
from pathlib import Path
import re
import datetime

from utils import _call_gemini, REPO_ROOT, WIKI_DIR, ENTITIES_DIR, CONCEPTS_DIR, INDEX_FILE, OVERVIEW_FILE, SCHEMA_FILE
import lint
find_missing_entities = lint.find_missing_entities
all_wiki_pages = lint.all_wiki_pages

def search_sources(entity: str, pages: list[Path]) -> list[Path]:
    """Find up to 15 pages where this entity is mentioned natively."""
    sources = []
    for p in pages:
        if "entities" not in str(p.parent) and "concepts" not in str(p.parent):
            content = p.read_text(encoding="utf-8")
            if entity.lower() in content.lower():
                sources.append(p)
    return sources[:15]

def heal_missing_entities(auto: bool = False):
    pages = all_wiki_pages()
    missing_entities = find_missing_entities(pages)
    
    if not missing_entities:
        print("Graph is fully connected. No missing entities found!")
        return

    ENTITIES_DIR.mkdir(exist_ok=True, parents=True)
    print(f"Found {len(missing_entities)} missing entity nodes.")
    if not auto:
        print("Interactive mode: You will be prompted before creating each page. (Use --auto to skip this)")
    
    for entity in missing_entities:
        if not auto:
            ans = input(f"\nHeal entity page for '{entity}'? [y/N]: ").strip().lower()
            if ans != 'y':
                print(f"  Skipping {entity}.")
                continue

        print(f"Healing entity page for: {entity}")
        sources = search_sources(entity, pages)
        
        context = ""
        for s in sources:
            context += f"\n\n### {s.name}\n{s.read_text(encoding='utf-8')[:800]}"
        
        prompt = f"""You are filling a data gap in the Personal LLM Wiki. 
Create an Entity definition page for "{entity}".

Here is how the entity appears in the current sources:
{context}

Format:
---
title: "{entity}"
type: entity
tags: []
sources: {[s.name for s in sources]}
---

# {entity}

Write a concise, 1-2 sentence definition explaining what `{entity}` means in the context of this wiki. Do not write a long paragraph.
"""
        try:
            result = _call_gemini(prompt, max_tokens=1024)
            
            # Strip Gemini's conversational wrapping — keep only the wiki page
            code_match = re.search(r'```(?:markdown|yaml|md)?\n(---.*?)```', result, re.DOTALL)
            if code_match:
                page_content = code_match.group(1).strip()
            elif "---" in result:
                start = result.find("---")
                page_content = result[start:].strip()
            else:
                today = datetime.date.today().isoformat()
                page_content = (
                    f"---\ntitle: \"{entity}\"\ntype: entity\ntags: []\n"
                    f"sources: {[s.name for s in sources]}\nlast_updated: {today}\n---\n\n"
                    f"# {entity}\n\n{result.strip()}"
                )
            
            out_path = ENTITIES_DIR / f"{entity}.md"
            out_path.write_text(page_content, encoding="utf-8")
            print(f" -> Saved to {out_path.relative_to(REPO_ROOT)}")
        except Exception as e:
            print(f" [!] Failed to generate {entity}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", action="store_true", 
                        help="Open Gemini CLI after completing")
    parser.add_argument("--auto", action="store_true",
                        help="Automatically heal all missing entities without asking")
    args = parser.parse_args()

    heal_missing_entities(auto=args.auto)

    if args.handoff:
        import subprocess
        print("\nHanding off to Gemini CLI...")
        subprocess.run(["gemini"], cwd=REPO_ROOT)