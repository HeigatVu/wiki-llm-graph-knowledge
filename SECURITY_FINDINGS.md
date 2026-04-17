# Security Scan — wiki-llm-knowledge

Scope scanned: repo contents on `main` (commit `275ab90`). The project is a
local Python CLI (no web server, no database, no HTTP endpoints), so CORS,
debug routes, and auth-on-HTTP-endpoints checks are N/A.

## Summary

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| 1 | **Critical** | `.env` committed to git history | **Fixed** — untracked, added to `.gitignore`, `.env.example` added |
| 2 | **High** | Path traversal via LLM-controlled paths in `ingest.py` (`slug`, `entity_pages[*].path`, `concept_pages[*].path`) | **Fixed** — added `safe_wiki_path` / `safe_slug` guards |
| 3 | **Medium** | Path traversal via user-supplied `--save` path in `query.py` | **Fixed** — sanitized |
| 4 | **Medium** | Path traversal via user-supplied `--page` path in `refresh.py` | **Fixed** — sanitized |
| 5 | Low | `main.py` `.env` loader overrides already-exported env vars | Documented (not fixed — behavior change) |
| 6 | Low | `query.py:160` passes extra positional args to `call_llm(...)` that it doesn't accept — will crash at runtime | Documented (out of scope of a pure security fix; left for the repo owner) |
| 7 | Info | `pypdf` is imported by `ingest.py` but not declared in `pyproject.toml` | Documented (functional, not security) |
| 8 | Info | No hardcoded **real** secrets found in source. Only placeholder `"API-key-here"` in `.env` and `"your-api-key-here"` in `README.md` | — |
| 9 | Info | No SQL use; no `shell=True`; no `eval`/`exec`/`pickle`/`yaml.load`; no HTTP server → CORS/auth/debug endpoints N/A | — |
| 10 | Info | Dependencies (`google-generativeai>=0.8.6`, `networkx>=3.4.2`) use lower-bound pins. No known CVEs flagged at these floors, but a `requirements.lock` / upper bound would make supply-chain review easier. | — |

---

## Details

### 1. `.env` committed to git — **Critical** (pattern), placeholder only

- `git ls-files` showed `.env` tracked. `.gitignore` only ignored `.env.bk`.
- Current value was the placeholder `GEMINI_API_KEY="API-key-here"`, so no
  real key leaked in this commit. However the **pattern** is dangerous — any
  future `git add .env` would commit a real key, and the file in history
  encourages contributors to edit-in-place and accidentally commit.

**Fix (this PR):**
- `git rm --cached .env` and delete the file.
- `.gitignore` now excludes `.env` and any `.env.*` except `.env.example`.
- New `.env.example` documents the expected keys (`LLM_MODEL`, `GEMINI_API_KEY`).

**Action for the repo owner:**
- If any real key was ever pushed to a private branch or an earlier commit,
  rotate `GEMINI_API_KEY` in Google AI Studio. History rewriting
  (`git filter-repo` / BFG) is only worthwhile if a real key was leaked.

---

### 2. Path traversal via LLM-controlled output — **High**

`1_tools/ingest.py` (before this PR):

```python
write_file(WIKI_DIR / "sources" / subdir / f"{data['slug']}.md", data["source_page"])
for page in data.get("entity_pages", []):
    write_file(WIKI_DIR / page["path"], page["content"])
for page in data.get("concept_pages", []):
    write_file(WIKI_DIR / page["path"], page["content"])
```

`data` is parsed from the LLM's JSON response. Because the tool feeds
arbitrary user markdown/PDF content into the prompt, a **prompt-injection
attack from a malicious source document** could cause the model to return
e.g.:

```json
{ "slug": "../../../../tmp/pwned",
  "entity_pages": [{"path": "../../../etc/cron.d/pwn", "content": "..."}] }
```

…which would then write **outside** `30_wiki/`. On a dev machine, any file
writeable by the process could be clobbered.

**Fix (this PR):**
- Added `safe_wiki_path(rel)` that `.resolve()`s the candidate and rejects
  anything whose real path isn't under `WIKI_DIR`.
- Added `safe_slug(s)` that strips everything outside `[A-Za-z0-9_-]`, so a
  malicious `slug` can't inject path separators.
- `entity_pages` must resolve under `entities/`, `concept_pages` under
  `concepts/`, and both must end in `.md`. Anything else is skipped with a
  warning instead of being written.

---

### 3 & 4. Path traversal via CLI flags — **Medium**

- `1_tools/query.py`: `--save <path>` was joined as `WIKI_DIR / save_path`
  with no validation. `--save ../../../../etc/evil.md` would escape the wiki.
- `1_tools/refresh.py`: `--page <path>` had the same shape.
- `query.py` also prompts the user for a slug via `input(...)` and
  concatenates it directly into a path.

**Fix (this PR):**
- Both files gained the same `safe_wiki_path` helper.
- `query.py` additionally sanitizes the interactive slug via
  `re.sub(r"[^A-Za-z0-9_\-]", "-", ...)`.
- Both reject paths that don't end in `.md`.

Severity is "medium" rather than "high" because these are CLI-local flags
the operator types themselves — but the guards are cheap and protect
against copy-pasted commands from untrusted sources.

---

### 5. `.env` loader in `main.py` overwrites existing env vars

```python
os.environ[key.strip()] = val.strip().strip("'\"")
```

If a user has already exported `GEMINI_API_KEY` in their shell, the stale
value in `.env` silently wins. Consider `os.environ.setdefault(...)`.
Left unchanged in this PR to avoid behavior surprises — flag only.

---

### 6. `query.py:160` — broken `call_llm` call

```python
answer = call_llm(prompt, "LLM_MODEL", "claude-3-5-sonnet-latest", max_tokens=4096)
```

`call_llm(prompt, max_tokens=...)` only takes two args; these extra
positionals will raise `TypeError` on the first non-trivial query. Not a
security bug but worth fixing; left in this PR as it's out of the
security-scan scope and changing the call surface should be a conscious
product decision.

---

### 7. Missing `pypdf` dependency

`1_tools/ingest.py` imports `pypdf` for PDF ingestion but only catches
`ImportError` with an install hint. `pyproject.toml` should declare it (or
mark it an optional extra). Functional issue, not security.

---

### 8–10. What the scan explicitly did **not** find

- **Hardcoded real API keys or tokens** — only placeholders.
- **SQL injection** — no database code.
- **`shell=True`, `os.system`, `eval`, `exec`, `pickle.loads`,
  `yaml.load` without `SafeLoader`, `__import__` of user input** — none.
- **CORS / auth / debug endpoints** — N/A, no HTTP server.
- **Subprocess invocation** — only `subprocess.run([sys.executable, ...])`
  and `subprocess.run(["gemini"], ...)` with argv lists (no shell), safe.

---

## Recommendations the repo owner should still action manually

1. **Rotate `GEMINI_API_KEY`** if a real key was ever committed (even in a
   branch that got force-pushed later). The current tracked value was a
   placeholder, but auditing this is cheap.
2. Consider replacing the hand-rolled `.env` parser in `main.py` with
   `python-dotenv` and `load_dotenv(override=False)` so shell env wins.
3. Pin dependencies more tightly (`uv.lock` is committed, which is good —
   but `pyproject.toml` uses floor-only ranges).
4. Add `pypdf` (or `pymupdf`) to `pyproject.toml`.
5. Fix the broken `call_llm` invocation in `query.py:160`.
