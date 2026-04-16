import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <command> [args]")
        print("Commands: ingest, query, lint, graph, refresh, heal, chat")
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    tool_map = {
        "ingest":  "1_tools/ingest.py",
        "query":   "1_tools/query.py",
        "lint":    "1_tools/lint.py",
        "graph":   "1_tools/build_graph.py",
        "refresh": "1_tools/refresh.py",
        "heal":    "1_tools/heal.py",
    }

    if command == "chat":
        # Go straight to Gemini CLI
        subprocess.run(["gemini"], cwd=REPO_ROOT)
        return

    if command not in tool_map:
        print(f"Unknown command: {command}")
        sys.exit(1)

    # Run the Python tool
    result = subprocess.run(
        [sys.executable, tool_map[command]] + rest,
        cwd=REPO_ROOT
    )

    # After ingest, lint, heal — offer to open Gemini CLI
    if result.returncode == 0 and command in ("ingest", "lint", "heal"):
        answer = input("\nOpen Gemini CLI to explore? [y/N] ").strip().lower()
        if answer == "y":
            subprocess.run(["gemini"], cwd=REPO_ROOT)


if __name__ == "__main__":
    main()