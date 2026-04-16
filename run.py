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

# Manually load .env since some environments don't auto-load it
env_path = REPO_ROOT / ".env"
if env_path.exists():
    import os
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip("'\"")

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