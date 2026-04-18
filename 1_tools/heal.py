import os
import sys
from pathlib import Path

from utils import _call_gemini

# Ensure the tools directory is in the path to allow imports
sys.path.insert(0, str(Path(__file__).parent))
import lint
find_missing_entities = lint.find_missing_entities
all_wiki_pages = lint.all_wiki_pages

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "30_wiki"
ENTITIES_DIR = WIKI_DIR / "entities"

def search_sources(entity: str, pages: list[Path]) -> list[Path]:
    """Find up to 15 pages where this entity is mentioned natively."""
    sources = []
    for p in pages:
        if "entities" not in str(p.parent) and "concepts" not in str(p.parent):
            content = p.read_text(encoding="utf-8")
            if entity.lower() in content.lower():
                sources.append(p)
    return sources[:15]

def heal_missing_entities():
    pages = all_wiki_pages()
    missing_entities = find_missing_entities(pages)
    
    if not missing_entities:
        print("Graph is fully connected. No missing entities found!")
        return

    ENTITIES_DIR.mkdir(exist_ok=True, parents=True)
    print(f"Found {len(missing_entities)} missing entity nodes. Commencing auto-heal...")
    
    for entity in missing_entities:
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

Write a comprehensive paragraph defining what `{entity}` means in the context of this wiki, its main significance, and any actions or associations related to it.
"""
        try:
            result = _call_gemini(prompt)
            out_path = ENTITIES_DIR / f"{entity}.md"
            out_path.write_text(result, encoding="utf-8")
            print(f" -> Saved to {out_path.relative_to(REPO_ROOT)}")
        except Exception as e:
            print(f" [!] Failed to generate {entity}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", action="store_true", 
                        help="Open Gemini CLI after completing")
    args = parser.parse_args()

    heal_missing_entities()

    if args.handoff:
        import subprocess
        print("\nHanding off to Gemini CLI...")
        subprocess.run(["gemini"], cwd=REPO_ROOT)