import os
import requests
import sys

from dotenv import load_dotenv
load_dotenv()

import time

def _call_ollama(prompt: str, max_tokens: int) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)

def call_gemini_cli(prompt: str, max_tokens: int = 0) -> str:
    """Call the local gemini CLI binary in headless mode."""
    import subprocess
    import re
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt, "--include-directories", "30_wiki,20_raw"],
            capture_output=True,
            text=True,
            check=True
        )
        stdout = result.stdout.strip()
        
        # Filter out agent status/thought lines
        lines = stdout.splitlines()
        clean_lines = []
        for line in lines:
            # Skip lines that look like agent "thoughts", status messages, or interactive prompts
            l = line.strip()
            if not l:
                clean_lines.append(line)
                continue
            if re.match(r"^(I will|I'll|Error executing tool|YOLO mode is enabled|Processing|Reading|Checking|Searching|Would you like me to|Please let me know|Let me know if|Exit code)", l, re.IGNORECASE):
                continue
            clean_lines.append(line)
        
        return "\n".join(clean_lines).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running gemini CLI: {e.stderr}")
        return f"Error: {e.stderr}"
    except FileNotFoundError:
        print("Error: gemini CLI not found in PATH")
        sys.exit(1)

def _call_gemini(prompt: str, max_tokens: int, model_override: str | None = None) -> str:
    """Call Gemini API with prompt. Retries on rate limit or server busy.
    
    Args:
        model_override: If set, uses this model instead of LLM_MODEL env var.
                        Use os.getenv('INGEST_MODEL') to pick the ingest model.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Error: google-genai not installed. Run: uv add google-genai")
        sys.exit(1)
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in .env file")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model_name = model_override or os.getenv("LLM_MODEL")

    for attempt in range(3):
        try:
            # Gentle pacing to stay within rate limits
            time.sleep(4 if attempt == 0 else 65)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except Exception as e:
            err = str(e)
            if ("429" in err or "503" in err) and attempt < 2:
                wait = 65 if "429" in err else 30
                print(f"  [{'Rate limit' if '429' in err else 'Server busy'}] Waiting {wait}s before retry {attempt+1}/2...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API: max retries exceeded")

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "30_wiki"
LOG_FILE = WIKI_DIR / "log.md"
INDEX_FILE = WIKI_DIR / "index.md"
OVERVIEW_FILE = WIKI_DIR / "overview.md"
SCHEMA_FILE = WIKI_DIR / "GEMINI.md"
GRAPH_DIR = REPO_ROOT / "2_graph"
GRAPH_JSON = GRAPH_DIR / "graph.json"
GRAPH_HTML = GRAPH_DIR / "graph.html"
CACHE_FILE = GRAPH_DIR / ".cache.json"
INFERRED_EDGES_FILE = GRAPH_DIR / ".inferred_edges.jsonl"
MANIFEST_FILE = REPO_ROOT / "2_graph" / ".ingest_manifest.json"
SOURCES_DIR = WIKI_DIR / "sources"
ENTITIES_DIR = WIKI_DIR / "entities"
CONCEPTS_DIR = WIKI_DIR / "concepts"

def load_manifest() -> dict:
    """Load the ingest manifest mapping source files to created wiki pages."""
    import json
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def sha256(text: str) -> str:
    """Compute SHA256 hash of text."""
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]

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

def read_file(path: Path) -> str:
    """Read file content safely."""
    return path.read_text(encoding="utf-8") if path.exists() else ""

def write_file(path: Path, content: str) -> None:
    """Write file content safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def all_wiki_pages() -> list[Path]:
    """Return list of all wiki page paths."""
    if not WIKI_DIR.exists():
        return []
    return [p for p in WIKI_DIR.rglob("*.md")
            if p.name not in ("index.md", "overview.md", "log.md", "lint-report.md")]

def extract_wikilinks(content: str) -> list[str]:
    """Extract wikilinks from content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)

def append_log(entry: str) -> None:
    """Append entry to log.md."""
    existing = read_file(LOG_FILE)
    write_file(LOG_FILE, entry.strip() + "\n\n" + existing)