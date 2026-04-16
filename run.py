#!/usr/bin/env python3
"""
Single entry point for the wiki pipeline.

Usage:
    python run.py ingest raw/papers/my_notes/paper_note.md
    python run.py ingest raw/my_knowledge_notes/
    python run.py query "what do I know about transformers?"
    python run.py lint
    python run.py lint --save
    python run.py graph
    python run.py refresh
    python run.py heal
"""

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent

TOOL_MAP = {
    "ingest":  "1_tools/ingest.py",
    "query":   "1_tools/query.py",
    "lint":    "1_tools/lint.py",
    "graph":   "1_tools/build_graph.py",
    "refresh": "1_tools/refresh.py",
    "heal":    "1_tools/heal.py",
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <command> [args]")
        print("Commands:", ", ".join(TOOL_MAP.keys()))
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command not in TOOL_MAP:
        print(f"Unknown command: {command}")
        print("Commands:", ", ".join(TOOL_MAP.keys()))
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, TOOL_MAP[command]] + rest,
        cwd=REPO_ROOT
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()