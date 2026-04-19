import re
import json
import hashlib
import argparse
import statistics
import webbrowser
from pathlib import Path
from datetime import date

from utils import (
    REPO_ROOT, WIKI_DIR, GRAPH_DIR, GRAPH_JSON, GRAPH_HTML, 
    CACHE_FILE, INFERRED_EDGES_FILE, LOG_FILE, SCHEMA_FILE,
    read_file, sha256, all_wiki_pages, extract_wikilinks
)

try:
    import networkx as nx
    from networkx.algorithms import community as nx_community
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Community detection disabled. Run: pip install networkx")

# Node type → color mapping
TYPE_COLORS = {
    "source": "#4CAF50",
    "entity": "#2196F3",
    "concept": "#FF9800",
    "synthesis": "#9C27B0",
    "unknown": "#9E9E9E",
}

EDGE_COLORS = {
    "EXTRACTED": "#555555",
    "INFERRED": "#FF5722",
    "AMBIGUOUS": "#BDBDBD",
}




def extract_frontmatter_type(content: str) -> str:
    match = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    return match.group(1).strip('"\'') if match else "unknown"


def page_id(path: Path) -> str:
    return path.relative_to(WIKI_DIR).as_posix().replace(".md", "")


def edge_id(src: str, target: str, edge_type: str) -> str:
    return f"{src}->{target}:{edge_type}"


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache: dict):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def build_nodes(pages: list[Path]) -> list[dict]:
    nodes = []
    for p in pages:
        content = read_file(p)
        node_type = extract_frontmatter_type(content)
        title_match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        label = title_match.group(1).strip() if title_match else p.stem
        body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
        preview_lines = []
        for line in body.splitlines():
            line = line.strip()
            if not line: continue
            
            # If line is a header, strip the '#' and append a ':' for cleaner reading
            if line.startswith('#'):
                line = re.sub(r'^#+\s+', '', line)
                if line and not line.endswith(('.', ':', '?', '!')):
                    line += ':'
            
            preview_lines.append(line)
        preview = " ".join(preview_lines[:3])[:220]
        node_date = None
        date_match = re.search(r'^(?:date|last_updated):\s*"?(\d{4}-\d{2}-\d{2})"?', content, re.MULTILINE)
        if date_match:
            node_date = date_match.group(1).strip()
        else:
            year_match = re.search(r'^year:\s*"?(\d{4})"?', content, re.MULTILINE)
            if year_match:
                node_date = f"{year_match.group(1).strip()}-01-01"
        
        nodes.append({
            "id": page_id(p),
            "label": label,
            "type": node_type,
            "date": node_date,
            "color": TYPE_COLORS.get(node_type, TYPE_COLORS["unknown"]),
            "path": str(p.relative_to(REPO_ROOT)),
            "markdown": content,
            "preview": preview,
        })
    return nodes


def build_extracted_edges(pages: list[Path]) -> list[dict]:
    """Pass 1: deterministic wikilink edges."""
    # Build a map from stem (lower) -> page_id for resolution
    stem_map = {p.stem.lower(): page_id(p) for p in pages}
    edges = []
    seen = set()
    for p in pages:
        content = read_file(p)
        src = page_id(p)
        for link in extract_wikilinks(content):
            target = stem_map.get(link.lower())
            if target and target != src:
                key = (src, target)
                if key not in seen:
                    seen.add(key)
                    edges.append({
                        "id": edge_id(src, target, "EXTRACTED"),
                        "from": src,
                        "to": target,
                        "type": "EXTRACTED",
                        "color": EDGE_COLORS["EXTRACTED"],
                        "confidence": 1.0,
                    })
    return edges


def load_checkpoint() -> tuple[list[dict], set[str]]:
    """Load previously inferred edges from JSONL checkpoint file."""
    edges = []
    completed = set()
    if INFERRED_EDGES_FILE.exists():
        for line in INFERRED_EDGES_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                completed.add(record["page_id"])
                for edge in record.get("edges", []):
                    if not isinstance(edge, dict) or "from" not in edge or "to" not in edge:
                        continue
                    rel_type = edge.get("type", "INFERRED")
                    edges.append({
                        "id": edge.get("id", edge_id(edge["from"], edge["to"], rel_type)),
                        "from": edge["from"],
                        "to": edge["to"],
                        "type": rel_type,
                        "title": edge.get("title", edge.get("relationship", "")),
                        "label": edge.get("label", ""),
                        "color": edge.get("color", EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"])),
                        "confidence": float(edge.get("confidence", 0.7)),
                    })
            except (json.JSONDecodeError, KeyError):
                continue
    return edges, completed


def append_checkpoint(page_id_str: str, edges: list[dict]):
    """Append one page's inferred edges to the JSONL checkpoint."""
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    record = {"page_id": page_id_str, "edges": edges, "ts": date.today().isoformat()}
    with open(INFERRED_EDGES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_inferred_edges(pages: list[Path], existing_edges: list[dict], cache: dict, resume: bool = True) -> list[dict]:
    """Pass 2: API-inferred semantic relationships with checkpoint/resume."""
    checkpoint_edges, completed_ids = ([], set())
    if resume:
        checkpoint_edges, completed_ids = load_checkpoint()
        if completed_ids:
            print(f"  checkpoint: {len(completed_ids)} pages already done, {len(checkpoint_edges)} edges loaded")

    new_edges = list(checkpoint_edges)

    changed_pages = []
    for p in pages:
        content = read_file(p)
        h = sha256(content)
        pid = page_id(p)
        entry = cache.get(str(p))

        if pid in completed_ids:
            continue

        if isinstance(entry, dict) and entry.get("hash") == h:
            for rel in entry.get("edges", []):
                rel_type = rel.get("type", "INFERRED")
                confidence = float(rel.get("confidence", 0.7))
                new_edges.append({
                    "id": edge_id(pid, rel["to"], rel_type),
                    "from": pid,
                    "to": rel["to"],
                    "type": rel_type,
                    "title": rel.get("relationship", ""),
                    "label": "",
                    "color": EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]),
                    "confidence": confidence,
                })
        else:
            changed_pages.append(p)

    if not changed_pages:
        print("  no changed pages — skipping semantic inference")
        return new_edges

    total_pages = len(changed_pages)
    already_done = len(completed_ids)
    grand_total = total_pages + already_done
    print(f"  inferring relationships for {total_pages} remaining pages (of {grand_total} total)...")

    # Build a summary of existing nodes for context
    node_list = "\n".join(f"- {page_id(p)} ({extract_frontmatter_type(read_file(p))})" for p in pages)
    existing_edge_summary = "\n".join(
        f"- {e['from']} → {e['to']} (EXTRACTED)" for e in existing_edges[:30]
    )

    for i, p in enumerate(changed_pages, 1):
        full_content = read_file(p)
        content = full_content[:2000]
        src = page_id(p)
        global_idx = already_done + i
        print(f"    [{global_idx}/{grand_total}] Inferring for '{src}'... ", end="", flush=True)

        prompt = f"""Analyze this wiki page and identify implicit semantic relationships to other pages in the wiki.

Source page: {src}
Content:
{content}

All available pages:
{node_list}

Already-extracted edges from this page:
{existing_edge_summary}

Return ONLY a JSON object containing an "edges" array of NEW relationships not already captured by explicit wikilinks. The response must be STRICTLY valid JSON formatted exactly like this:
{{
  "edges": [
    {{"to": "page-id", "relationship": "one-line description", "confidence": 0.0-1.0, "type": "INFERRED or AMBIGUOUS"}}
  ]
}}

CRITICAL INSTRUCTION:
YOU MUST RETURN ONLY A RAW JSON STRING BEGINNING WITH {{ AND ENDING WITH }}.
DO NOT OUTPUT BULLET POINTS. DO NOT OUTPUT MARKDOWN LISTS.
ANY CONVERSATIONAL PREAMBLE WILL CAUSE A SYSTEM CRASH.

Rules:
- Only include pages from the available list above
- Confidence >= 0.7 → INFERRED, < 0.7 → AMBIGUOUS
- Do not repeat edges already in the extracted list
- Return {{"edges": []}} if no new relationships found
"""
        page_edges = []
        valid_rels = []
        try:
            raw = _call_gemini(prompt, max_tokens=1024)
            raw = raw.strip()

            match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
            if match:
                raw = match.group(0)
            else:
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            inferred = json.loads(raw)
            if isinstance(inferred, dict):
                edges_list = inferred.get("edges", [])
            elif isinstance(inferred, list):
                edges_list = inferred
            else:
                edges_list = []

            for rel in edges_list:
                if isinstance(rel, dict) and "to" in rel:
                    confidence = float(rel.get("confidence", 0.7))
                    rel_type = rel.get("type") or ("INFERRED" if confidence >= 0.7 else "AMBIGUOUS")
                    edge = {
                        "id": edge_id(src, rel["to"], rel_type),
                        "from": src,
                        "to": rel["to"],
                        "type": rel_type,
                        "title": rel.get("relationship", ""),
                        "label": "",
                        "color": EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]),
                        "confidence": confidence,
                    }
                    page_edges.append(edge)
                    new_edges.append(edge)
                    valid_rels.append({
                        "to": rel["to"],
                        "relationship": rel.get("relationship", ""),
                        "confidence": confidence,
                        "type": rel_type,
                    })

            cache[str(p)] = {
                "hash": sha256(full_content),
                "edges": valid_rels,
            }
            append_checkpoint(src, page_edges)
            print(f"-> Found {len(page_edges)} edges.")
        except (json.JSONDecodeError, TypeError, ValueError) as jde:
            print(f"-> [WARN] Invalid JSON: {str(jde)[:60]}")
        except Exception as e:
            err_msg = str(e).replace('\n', ' ')[:80]
            print(f"-> [ERROR] {err_msg}")

    return new_edges


def deduplicate_edges(edges: list[dict]) -> list[dict]:
    """Merge duplicate and bidirectional edges, keeping highest confidence."""
    best = {}  # (min(a,b), max(a,b)) -> edge
    for e in edges:
        a, b = e["from"], e["to"]
        key = (min(a, b), max(a, b))
        existing = best.get(key)
        if not existing or e.get("confidence", 0) > existing.get("confidence", 0):
            best[key] = e
    deduped = []
    for edge in best.values():
        rel_type = edge.get("type", "INFERRED")
        edge["id"] = edge.get("id", edge_id(edge["from"], edge["to"], rel_type))
        edge["color"] = edge.get("color", EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]))
        edge["confidence"] = float(edge.get("confidence", 0.7 if rel_type != "EXTRACTED" else 1.0))
        edge.setdefault("title", "")
        edge.setdefault("label", "")
        deduped.append(edge)
    return deduped


def detect_communities(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
    """Assign community IDs to nodes using Louvain algorithm."""
    if not HAS_NETWORKX:
        return {}

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"])
    for e in edges:
        G.add_edge(e["from"], e["to"])

    if G.number_of_edges() == 0:
        return {}

    try:
        communities = nx_community.louvain_communities(G, seed=42)
        node_to_community = {}
        for i, comm in enumerate(communities):
            for node in comm:
                node_to_community[node] = i
        return node_to_community
    except Exception:
        return {}



def generate_report(nodes: list[dict], edges: list[dict], communities: dict[str, int]) -> str:
    """Generate a structured graph health report.

    Analyzes the graph for orphan nodes, hub pages (god nodes),
    fragile inter-community bridges, and overall connectivity health.
    """
    today = date.today().isoformat()
    n_nodes = len(nodes)
    n_edges = len(edges)

    if n_nodes == 0:
        return f"# Graph Insights Report — {today}\n\nWiki is empty — nothing to report.\n"

    # Build NetworkX graph for analysis
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"])
    for e in edges:
        G.add_edge(e["from"], e["to"])

    # --- Metrics ---
    degrees = dict(G.degree())
    edges_per_node = n_edges / n_nodes if n_nodes else 0
    density = nx.density(G)

    # Health rating
    if edges_per_node >= 2.0:
        health = "✅ healthy"
    elif edges_per_node >= 1.0:
        health = "⚠️ warning"
    else:
        health = "🔴 critical"

    # Orphans: degree == 0
    orphans = sorted([n for n, d in degrees.items() if d == 0])
    orphan_count = len(orphans)
    orphan_pct = (orphan_count / n_nodes * 100) if n_nodes else 0

    # God nodes: degree > mean + 2*std
    deg_values = list(degrees.values())
    mean_deg = statistics.mean(deg_values) if deg_values else 0
    std_deg = statistics.stdev(deg_values) if len(deg_values) > 1 else 0
    god_threshold = mean_deg + 2 * std_deg
    god_nodes = sorted(
        [(n, d) for n, d in degrees.items() if d > god_threshold],
        key=lambda x: x[1],
        reverse=True,
    )

    # Community stats
    community_count = len(set(communities.values())) if communities else 0
    comm_members: dict[int, list[str]] = {}
    for node_id, comm_id in communities.items():
        comm_members.setdefault(comm_id, []).append(node_id)

    # Fragile bridges: community pairs connected by exactly 1 edge
    cross_comm_edges: dict[tuple[int, int], list[dict]] = {}
    for e in edges:
        ca = communities.get(e["from"], -1)
        cb = communities.get(e["to"], -1)
        if ca >= 0 and cb >= 0 and ca != cb:
            key = (min(ca, cb), max(ca, cb))
            cross_comm_edges.setdefault(key, []).append(e)
    fragile_bridges = [
        (pair, edge_list[0])
        for pair, edge_list in sorted(cross_comm_edges.items())
        if len(edge_list) == 1
    ]

    # --- Build report ---
    lines = [
        f"# Graph Insights Report — {today}",
        "",
        "## Health Summary",
        f"- **{n_nodes}** nodes, **{n_edges}** edges ({edges_per_node:.2f} edges/node — {health})",
        f"- **{orphan_count}** orphan nodes ({orphan_pct:.1f}%) — target: <10%",
        f"- **{community_count}** communities",
        f"- Link density: {density:.4f}",
        "",
    ]

    # Orphan section
    lines.append(f"## 🔴 Orphan Nodes ({orphan_count} pages, {orphan_pct:.1f}%)")
    if orphans:
        lines.append("These pages have zero graph connections. Consider adding [[wikilinks]]:")
        for o in orphans:
            lines.append(f"- `{o}`")
    else:
        lines.append("No orphan nodes — excellent!")
    lines.append("")

    # God nodes section
    lines.append("## 🟡 God Nodes (Hub Pages)")
    if god_nodes:
        lines.append("These nodes carry disproportionate connectivity (degree > μ+2σ). Verify they are comprehensive:")
        lines.append("")
        lines.append("| Node | Degree | % of Edges | Community |")
        lines.append("|---|---|---|---|")
        for node_id, deg in god_nodes:
            edge_pct = (deg / (2 * n_edges) * 100) if n_edges else 0
            comm = communities.get(node_id, -1)
            lines.append(f"| `{node_id}` | {deg} | {edge_pct:.1f}% | {comm} |")
    else:
        lines.append("No god nodes detected — degree distribution is balanced.")
    lines.append("")

    # Fragile bridges section
    lines.append("## 🟡 Fragile Bridges")
    if fragile_bridges:
        lines.append("Community pairs connected by only 1 edge — one deleted link breaks them:")
        for (ca, cb), edge in fragile_bridges:
            lines.append(f"- Community {ca} ↔ Community {cb} via `{edge['from']}` → `{edge['to']}`")
    else:
        lines.append("No fragile bridges — all community connections are redundant.")
    lines.append("")

    # Community overview
    lines.append("## 🟢 Community Overview")
    if comm_members:
        lines.append("")
        lines.append("| Community | Nodes | Key Members |")
        lines.append("|---|---|---|")
        for comm_id in sorted(comm_members.keys()):
            members = comm_members[comm_id]
            # Sort by degree descending to show key members first
            members_sorted = sorted(members, key=lambda m: degrees.get(m, 0), reverse=True)
            key_members = ", ".join(members_sorted[:5])
            if len(members_sorted) > 5:
                key_members += ", …"
            lines.append(f"| {comm_id} | {len(members)} | {key_members} |")
    else:
        lines.append("No communities detected.")
    lines.append("")

    # Suggested actions
    lines.append("## Suggested Actions")
    actions = []
    if orphans:
        actions.append(f"1. Add wikilinks to top orphan pages (highest potential impact: {orphans[0]})")
    if god_nodes:
        actions.append(f"{len(actions)+1}. Review god nodes for stub content vs. genuine hubs")
    if fragile_bridges:
        actions.append(f"{len(actions)+1}. Strengthen fragile bridges with cross-references")
    if not actions:
        actions.append("1. Graph is in good shape — maintain current linking practices")
    lines.extend(actions)
    lines.append("")

    return "\n".join(lines)


COMMUNITY_COLORS = [
    "#E91E63", "#00BCD4", "#8BC34A", "#FF5722", "#673AB7",
    "#FFC107", "#009688", "#F44336", "#3F51B5", "#CDDC39",
]


def render_html(nodes: list[dict], edges: list[dict], communities: dict, community_names: dict, theme_to_math: dict) -> str:
    """Generate vis.js HTML using external template and assets."""
    nodes_json = json.dumps(nodes, indent=2, ensure_ascii=False)
    edges_json = json.dumps(edges, indent=2, ensure_ascii=False)
    communities_json = json.dumps(communities, indent=2, ensure_ascii=False)
    community_names_json = json.dumps(community_names, indent=2, ensure_ascii=False)
    theme_to_math_json = json.dumps(theme_to_math, indent=2, ensure_ascii=False)

    TYPE_TOOLTIPS = {
        "source": "Raw documents, papers, notes, or articles.",
        "entity": "People, organizations, projects, or products.",
        "concept": "Abstract ideas, frameworks, methods, or theories.",
        "synthesis": "Saved analyses synthesizing multiple sources."
    }

    legend_items = "".join(
        f'<button class="type-filter active" title="{t.capitalize()}: {TYPE_TOOLTIPS.get(t, t)} (Click to toggle)" data-type="{t}" style="background:{color};padding:4px 10px;margin:3px 2px;border-radius:4px;font-size:13px;border:none;color:white;cursor:pointer;opacity:1.0;font-family:inherit;">{t}</button>'
        for t, color in TYPE_COLORS.items() if t != "unknown"
    )

    n_extracted = len([e for e in edges if e.get('type') == 'EXTRACTED'])

    assets_dir = REPO_ROOT / "1_tools" / "assets"
    template = read_file(assets_dir / "graph_template.html")
    css = read_file(assets_dir / "graph.css")
    js = read_file(assets_dir / "graph.js")

    return template.replace("/* {{graph_css}} */", css)\
                   .replace("/* {{graph_js}} */", js)\
                   .replace("{{nodes_json}}", nodes_json)\
                   .replace("{{edges_json}}", edges_json)\
                   .replace("{{communities_json}}", communities_json)\
                   .replace("{{community_names_json}}", community_names_json)\
                   .replace("{{theme_to_math_json}}", theme_to_math_json)\
                   .replace("{{legend_items}}", legend_items)\
                   .replace("{{n_extracted}}", str(n_extracted))


def append_log(entry: str):
    log_path = WIKI_DIR / "log.md"
    entry_text = entry.strip()
    if not log_path.exists():
        log_path.write_text(
            "# Wiki Log\n\n"
            "> Records important additions, revisions, and clarifications in the project knowledge layer. Maintained in append-only mode for agent and human traceability.\n\n"
            f"{entry_text}\n",
            encoding="utf-8",
        )
        return

    existing = read_file(log_path).rstrip()
    if not existing:
        existing = (
            "# Wiki Log\n\n"
            "> Records important additions, revisions, and clarifications in the project knowledge layer. Maintained in append-only mode for agent and human traceability."
        )
    log_path.write_text(existing + "\n\n" + entry_text + "\n", encoding="utf-8")


def build_graph(infer: bool = True, open_browser: bool = False, clean: bool = False,
                report: bool = False, save: bool = False):
    pages = all_wiki_pages()
    today = date.today().isoformat()

    if not pages:
        print("Wiki is empty. Ingest some sources first.")
        return

    print(f"Building graph from {len(pages)} wiki pages...")
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    # Clean checkpoint if requested
    if clean and INFERRED_EDGES_FILE.exists():
        INFERRED_EDGES_FILE.unlink()
        print("  cleaned: removed inference checkpoint")

    cache = load_cache()

    # Pass 1: extracted edges
    print("  Pass 1: extracting wikilinks...")
    nodes = build_nodes(pages)
    edges = build_extracted_edges(pages)
    print(f"  → {len(edges)} extracted edges")

    # Pass 2: inferred edges
    if infer:
        print("  Pass 2: inferring semantic relationships...")
        inferred = build_inferred_edges(pages, edges, cache, resume=not clean)
        edges.extend(inferred)
        print(f"  → {len(inferred)} inferred edges")
        save_cache(cache)

    # Deduplicate edges
    before_dedup = len(edges)
    edges = deduplicate_edges(edges)
    if before_dedup != len(edges):
        print(f"  dedup: {before_dedup} → {len(edges)} edges")

    # Community detection
    print("  Running traditional Louvain community detection...")
    communities = detect_communities(nodes, edges)
    # Generic names for clusters
    community_names = {cid: f"Cluster {cid}" for cid in set(communities.values())}
    # No theme-to-math mapping needed for pure math mode
    theme_to_math = {f"Cluster {cid}": [str(cid)] for cid in community_names.keys()}
    
    for node in nodes:
        math_id = communities.get(node["id"], -1)
        node["color"] = COMMUNITY_COLORS[math_id % len(COMMUNITY_COLORS)] if math_id >= 0 else "#888"
        node["group"] = math_id
        node["math_id"] = math_id
        node["group_name"] = f"Cluster {math_id}" if math_id >= 0 else "Unassigned"
        node["theme_name"] = node["group_name"]

    degree_map: dict[str, int] = {}
    for e in edges:
        degree_map[e["from"]] = degree_map.get(e["from"], 0) + 1
        degree_map[e["to"]] = degree_map.get(e["to"], 0) + 1
        
        # Set spring length based on community to visually separate clusters
        from_comm = communities.get(e["from"], -1)
        to_comm = communities.get(e["to"], -1)
        if from_comm >= 0 and from_comm == to_comm:
            e["length"] = 80  # tighter inner-cluster springs
        else:
            e["length"] = 700  # much longer cross-cluster springs to push them apart
            
    for node in nodes:
        node["value"] = degree_map.get(node["id"], 0) + 1  # +1 so isolated nodes are still visible

    # Save graph.json
    graph_data = {"nodes": nodes, "edges": edges, "built": today}
    GRAPH_JSON.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False))
    print(f"  saved: graph/graph.json  ({len(nodes)} nodes, {len(edges)} edges)")

    # Save graph.html
    html = render_html(nodes, edges, communities, community_names, theme_to_math)
    GRAPH_HTML.write_text(html, encoding="utf-8")
    print(f"  saved: graph/graph.html")

    n_ext = len([e for e in edges if e['type']=='EXTRACTED'])
    n_inf = len([e for e in edges if e['type'] in ('INFERRED', 'AMBIGUOUS')])
    append_log(f"## [{today}] graph | Knowledge graph rebuilt\n\n{len(nodes)} nodes, {len(edges)} edges ({n_ext} extracted, {n_inf} inferred).")

    # Generate health report
    if report:
        if not HAS_NETWORKX:
            print("Warning: networkx not installed. Cannot generate report.")
        else:
            report_text = generate_report(nodes, edges, communities)
            print("\n" + report_text)
            if save:
                report_path = GRAPH_DIR / "graph-report.md"
                report_path.write_text(report_text, encoding="utf-8")
                print(f"  saved: {report_path.relative_to(REPO_ROOT)}")
            append_log(f"## [{today}] report | Graph health report generated\n\n{len(nodes)} nodes analyzed.")

    if report:
      from gap_analysis import SemanticGapAnalyzer
      gap_analyzer = SemanticGapAnalyzer(use_graph_json=True)
      gap_report = gap_analyzer.run()
      print(gap_report)
      if save:
          (GRAPH_DIR / "gap-report.md").write_text(gap_report, encoding="utf-8")

    if open_browser:
        webbrowser.open(f"file://{GRAPH_HTML.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build LLM Wiki knowledge graph")
    parser.add_argument("--infer", action="store_true", help="Run semantic inference (slow)")
    parser.add_argument("--open", action="store_true", help="Open graph.html in browser")
    parser.add_argument("--clean", action="store_true", help="Delete checkpoint and force full re-inference")
    parser.add_argument("--report", action="store_true", help="Generate graph health report")
    parser.add_argument("--save", action="store_true", help="Save report to graph/graph-report.md")
    args = parser.parse_args()
    build_graph(infer=args.infer, open_browser=args.open, clean=args.clean,
                report=args.report, save=args.save)