from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

try:
    import networkx as nx
    from networkx.algorithms import community as nx_community
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

# ── Paths ──────────────────────────────────────────────────────────────────────

from utils import REPO_ROOT, WIKI_DIR, GRAPH_DIR, GRAPH_JSON, read_file, extract_wikilinks, all_wiki_pages

GAP_REPORT = GRAPH_DIR / "gap-report.md"


# ── Helpers ────────────────────────────────────────────────────────────────────



def page_id(path: Path) -> str:
    return path.relative_to(WIKI_DIR).as_posix().replace(".md", "")


def extract_frontmatter_type(content: str) -> str:
    match = re.search(r"^type:\s*(\S+)", content, re.MULTILINE)
    return match.group(1).strip("\"'") if match else "unknown"


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


# ── Graph builder (reuses wikilinks, same as build_graph.py) ──────────────────

def build_nx_graph(pages: list[Path]) -> tuple[nx.Graph, dict[str, dict]]:
    """
    Build a NetworkX graph from wikilinks between wiki pages.
    Returns (G, node_metadata) where node_metadata maps page_id -> dict.
    """
    stem_map = {p.stem.lower(): page_id(p) for p in pages}
    node_meta: dict[str, dict] = {}

    G = nx.Graph()

    for p in pages:
        content = read_file(p)
        pid = page_id(p)
        node_meta[pid] = {
            "id": pid,
            "label": extract_title(content, p.stem),
            "type": extract_frontmatter_type(content),
            "path": str(p.relative_to(REPO_ROOT)),
        }
        G.add_node(pid, **node_meta[pid])

    seen_edges: set[tuple[str, str]] = set()
    for p in pages:
        content = read_file(p)
        src = page_id(p)
        for link in extract_wikilinks(content):
            target = stem_map.get(link.lower())
            if target and target != src:
                key = (min(src, target), max(src, target))
                if key not in seen_edges:
                    seen_edges.add(key)
                    G.add_edge(src, target)

    return G, node_meta


def load_graph_from_json() -> Optional[tuple[nx.Graph, dict[str, dict]]]:
    """
    Load graph from existing graph.json if available (faster than rebuilding).
    Falls back to None if file is missing or malformed.
    """
    if not GRAPH_JSON.exists():
        return None
    try:
        data = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
        G = nx.Graph()
        node_meta: dict[str, dict] = {}

        for node in data.get("nodes", []):
            G.add_node(node["id"], **node)
            node_meta[node["id"]] = node

        for edge in data.get("edges", []):
            if edge.get("type") == "EXTRACTED":  # wikilinks only
                G.add_edge(edge["from"], edge["to"])

        return G, node_meta
    except (json.JSONDecodeError, KeyError):
        return None


# ── Core gap analysis algorithms ───────────────────────────────────────────────

class SemanticGapAnalyzer:
    """
    Detects research gaps in your wiki knowledge graph using local graph algorithms.

    Usage:
        analyzer = SemanticGapAnalyzer()
        report = analyzer.run()
        print(report)
    """

    # Thresholds — tune these if you have very sparse or very dense graphs
    MIN_COMMUNITY_SIZE = 3        # ignore tiny communities (noise)
    GAP_DENSITY_THRESHOLD = 0.05  # pairs below this are "gaps"
    MIN_GAP_SCORE = 3.0           # only report meaningful gaps
    TOP_N_GAPS = 15               # max gaps to report
    TOP_N_BROKERS = 10            # max broker suggestions to report

    def __init__(self, use_graph_json: bool = True):
        if not HAS_NETWORKX:
            raise ImportError(
                "networkx is not installed. Run: pip install networkx"
            )

        self.G: nx.Graph
        self.node_meta: dict[str, dict]
        self.communities: list[frozenset[str]] = []
        self.node_to_comm: dict[str, int] = {}
        self._loaded = False
        self._use_graph_json = use_graph_json

    # ── Setup ──────────────────────────────────────────────────────────────────

    def _load(self):
        if self._loaded:
            return

        # Try loading from graph.json first (preserves EXTRACTED-only edges)
        if self._use_graph_json:
            result = load_graph_from_json()
            if result:
                self.G, self.node_meta = result
                print(f"  [gap] loaded graph from graph.json "
                      f"({self.G.number_of_nodes()} nodes, "
                      f"{self.G.number_of_edges()} edges)")
                self._detect_communities()
                self._loaded = True
                return

        # Fall back to rebuilding from wiki pages
        print("  [gap] graph.json not found — rebuilding from wiki pages...")
        pages = all_wiki_pages()
        if not pages:
            raise RuntimeError("Wiki is empty. Ingest sources first.")
        self.G, self.node_meta = build_nx_graph(pages)
        print(f"  [gap] built graph: {self.G.number_of_nodes()} nodes, "
              f"{self.G.number_of_edges()} edges")
        self._detect_communities()
        self._loaded = True

    def _detect_communities(self):
        """Run Louvain community detection, filter small communities."""
        if self.G.number_of_edges() == 0:
            self.communities = []
            self.node_to_comm = {}
            return

        raw = nx_community.louvain_communities(self.G, seed=42)

        # Filter: only communities with enough nodes to be meaningful
        self.communities = [
            c for c in raw if len(c) >= self.MIN_COMMUNITY_SIZE
        ]

        self.node_to_comm = {}
        for i, comm in enumerate(self.communities):
            for node in comm:
                self.node_to_comm[node] = i

    # ── Algorithm 1: Cross-community edge density ──────────────────────────────

    def _cross_community_density(self) -> list[dict]:
        """
        For every pair of communities, calculate:
          actual_edges / possible_edges

        Pairs below GAP_DENSITY_THRESHOLD with large communities = gaps.
        """
        n = len(self.communities)
        if n < 2:
            return []

        gaps = []
        for i in range(n):
            for j in range(i + 1, n):
                comm_a = self.communities[i]
                comm_b = self.communities[j]

                # Count actual edges between the two communities
                actual = sum(
                    1 for u in comm_a for v in self.G.neighbors(u)
                    if v in comm_b
                )

                # Maximum possible edges
                possible = len(comm_a) * len(comm_b)
                density = actual / possible if possible > 0 else 0.0

                if density < self.GAP_DENSITY_THRESHOLD:
                    # Score: larger communities + lower density = more important gap
                    size_weight = (len(comm_a) + len(comm_b)) / 2
                    gap_score = size_weight * (1.0 - density * 20)

                    gaps.append({
                        "comm_a": i,
                        "comm_b": j,
                        "size_a": len(comm_a),
                        "size_b": len(comm_b),
                        "actual_edges": actual,
                        "possible_edges": possible,
                        "density": density,
                        "gap_score": round(gap_score, 2),
                        "nodes_a": list(comm_a),
                        "nodes_b": list(comm_b),
                    })

        return sorted(gaps, key=lambda x: x["gap_score"], reverse=True)

    # ── Algorithm 2: Betweenness centrality — missing brokers ─────────────────

    def _find_missing_brokers(self) -> list[dict]:
        """
        Nodes with HIGH betweenness = current brokers between clusters.
        Community PAIRS with LOW total bridging betweenness = missing a broker.

        Returns suggested "missing concept" slots between cluster pairs.
        """
        if self.G.number_of_edges() == 0:
            return []

        betweenness = nx.betweenness_centrality(self.G, normalized=True)

        # For each community, find its top broker nodes
        comm_brokers: dict[int, list[tuple[str, float]]] = defaultdict(list)
        for node, score in betweenness.items():
            comm_id = self.node_to_comm.get(node, -1)
            if comm_id >= 0:
                comm_brokers[comm_id].append((node, score))

        # Sort each community's brokers by score
        for cid in comm_brokers:
            comm_brokers[cid].sort(key=lambda x: x[1], reverse=True)

        # Find community pairs where the bridge betweenness is very low
        n = len(self.communities)
        missing = []
        for i in range(n):
            for j in range(i + 1, n):
                # Nodes that connect i↔j
                bridge_nodes = [
                    (node, betweenness[node])
                    for node in self.G.nodes()
                    if self.node_to_comm.get(node) == i
                    for neighbor in self.G.neighbors(node)
                    if self.node_to_comm.get(neighbor) == j
                ]

                if not bridge_nodes:
                    # No bridge at all — this is a structural hole
                    top_a = comm_brokers[i][:3] if i in comm_brokers else []
                    top_b = comm_brokers[j][:3] if j in comm_brokers else []
                    missing.append({
                        "comm_a": i,
                        "comm_b": j,
                        "bridge_nodes": [],
                        "top_concepts_a": [n for n, _ in top_a],
                        "top_concepts_b": [n for n, _ in top_b],
                        "severity": "critical",  # zero connection
                    })
                elif len(bridge_nodes) == 1:
                    # Single bridge — fragile
                    missing.append({
                        "comm_a": i,
                        "comm_b": j,
                        "bridge_nodes": [bridge_nodes[0][0]],
                        "top_concepts_a": [],
                        "top_concepts_b": [],
                        "severity": "fragile",
                    })

        return missing

    # ── Algorithm 3: Structural holes (Burt's constraint) ─────────────────────

    def _structural_holes(self) -> list[dict]:
        """
        Nodes with LOW constraint = structural hole brokers = already bridging gaps.
        Nodes with HIGH constraint inside a community = deeply embedded, not bridging.

        We use this to find COMMUNITIES that lack any low-constraint node,
        meaning the community is an isolated silo.
        """
        if self.G.number_of_edges() == 0:
            return []

        try:
            constraint = nx.constraint(self.G)
        except Exception:
            return []

        # Average constraint per community
        comm_constraints: dict[int, list[float]] = defaultdict(list)
        for node, c in constraint.items():
            cid = self.node_to_comm.get(node, -1)
            if cid >= 0 and c is not None:
                comm_constraints[cid].append(c)

        silos = []
        for cid, values in comm_constraints.items():
            if not values:
                continue
            avg_constraint = statistics.mean(values)
            min_constraint = min(values)

            # High average constraint + high minimum = community is a silo
            if avg_constraint > 0.7 and min_constraint > 0.5:
                # Find the most connected node in this community as label
                comm_nodes = list(self.communities[cid])
                degrees = [(n, self.G.degree(n)) for n in comm_nodes]
                top_node = max(degrees, key=lambda x: x[1])[0]

                silos.append({
                    "community_id": cid,
                    "size": len(comm_nodes),
                    "avg_constraint": round(avg_constraint, 3),
                    "min_constraint": round(min_constraint, 3),
                    "representative_node": top_node,
                    "top_nodes": [n for n, _ in
                                  sorted(degrees, key=lambda x: x[1], reverse=True)[:5]],
                })

        return sorted(silos, key=lambda x: x["avg_constraint"], reverse=True)

    # ── Community labeling ─────────────────────────────────────────────────────

    def _label_community(self, comm_id: int, top_n: int = 5) -> str:
        """
        Generate a human-readable label for a community by picking
        the highest-degree nodes as representative concepts.
        """
        if comm_id >= len(self.communities):
            return f"Community {comm_id}"

        nodes = list(self.communities[comm_id])
        by_degree = sorted(nodes, key=lambda n: self.G.degree(n), reverse=True)
        top = by_degree[:top_n]

        labels = []
        for n in top:
            meta = self.node_meta.get(n, {})
            label = meta.get("label", n.split("/")[-1])
            labels.append(label)

        return " / ".join(labels)

    def _node_label(self, node_id: str) -> str:
        meta = self.node_meta.get(node_id, {})
        return meta.get("label", node_id.split("/")[-1])

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(self) -> str:
        """
        Run all gap analyses and return a formatted markdown report string.
        """
        self._load()

        n_nodes = self.G.number_of_nodes()
        n_edges = self.G.number_of_edges()
        n_comms = len(self.communities)

        if n_nodes == 0:
            return "# Semantic Gap Report\n\nWiki is empty.\n"

        if n_comms < 2:
            return (
                "# Semantic Gap Report\n\n"
                f"Only {n_comms} community detected ({n_nodes} nodes, {n_edges} edges). "
                "Gap analysis requires at least 2 communities. "
                "Ingest more papers and run `uv run main.py graph` first.\n"
            )

        print(f"  [gap] analyzing {n_comms} communities across "
              f"{n_nodes} nodes, {n_edges} edges...")

        density_gaps = self._cross_community_density()
        broker_gaps = self._find_missing_brokers()
        silo_gaps = self._structural_holes()

        return self._format_report(
            density_gaps, broker_gaps, silo_gaps, n_nodes, n_edges, n_comms
        )

    # ── Report formatting ──────────────────────────────────────────────────────

    def _format_report(
        self,
        density_gaps: list[dict],
        broker_gaps: list[dict],
        silo_gaps: list[dict],
        n_nodes: int,
        n_edges: int,
        n_comms: int,
    ) -> str:
        lines = [
            "# Semantic Gap Analysis",
            "",
            f"**{n_nodes}** nodes · **{n_edges}** edges · "
            f"**{n_comms}** communities detected",
            "",
            "> Gaps are ranked by severity. A gap means two thematic clusters "
            "> in your research have weak or no conceptual bridges — "
            "> indicating missing literature, under-explored connections, "
            "> or papers you haven't ingested yet.",
            "",
        ]

        # ── Section 1: Cross-community density gaps ────────────────────────────
        lines.append("## 🔴 Underconnected Topic Pairs")
        lines.append("")
        lines.append(
            "These research topic clusters exist in your wiki but are "
            "poorly connected. Each pair is a potential research gap."
        )
        lines.append("")

        top_density = [
            g for g in density_gaps
            if g["gap_score"] >= self.MIN_GAP_SCORE
        ][:self.TOP_N_GAPS]

        if not top_density:
            lines.append("No significant density gaps found. Your clusters are well-connected.")
        else:
            lines.append("| # | Cluster A | Cluster B | Bridges | Density | Gap Score |")
            lines.append("|---|-----------|-----------|---------|---------|-----------|")
            for rank, gap in enumerate(top_density, 1):
                label_a = self._label_community(gap["comm_a"])
                label_b = self._label_community(gap["comm_b"])
                lines.append(
                    f"| {rank} | {label_a} ({gap['size_a']} nodes) | "
                    f"{label_b} ({gap['size_b']} nodes) | "
                    f"{gap['actual_edges']} | "
                    f"{gap['density']:.3f} | "
                    f"**{gap['gap_score']}** |"
                )

        lines.append("")

        # ── Section 2: Missing brokers ─────────────────────────────────────────
        critical = [g for g in broker_gaps if g["severity"] == "critical"]
        fragile = [g for g in broker_gaps if g["severity"] == "fragile"]

        lines.append("## 🟠 Missing Conceptual Bridges")
        lines.append("")

        if critical:
            lines.append(
                f"**{len(critical)} cluster pair(s) have ZERO bridging concepts.** "
                "These are the most important gaps in your research — "
                "no paper in your wiki connects these topics at all."
            )
            lines.append("")
            for gap in critical[:self.TOP_N_BROKERS]:
                label_a = self._label_community(gap["comm_a"])
                label_b = self._label_community(gap["comm_b"])
                lines.append(f"### Gap: {label_a} ↔ {label_b}")
                lines.append("")
                lines.append("**Status**: No bridge exists")
                lines.append("")

                if gap["top_concepts_a"]:
                    concept_labels_a = [self._node_label(n) for n in gap["top_concepts_a"]]
                    lines.append(f"**Key concepts in Cluster A**: {', '.join(concept_labels_a)}")

                if gap["top_concepts_b"]:
                    concept_labels_b = [self._node_label(n) for n in gap["top_concepts_b"]]
                    lines.append(f"**Key concepts in Cluster B**: {', '.join(concept_labels_b)}")

                lines.append("")
                lines.append(
                    "> **Suggested action**: Search for papers that cite concepts "
                    "from both clusters. This bridge is your most valuable research gap."
                )
                lines.append("")
        else:
            lines.append("No completely disconnected cluster pairs.")
            lines.append("")

        if fragile:
            lines.append(
                f"**{len(fragile)} cluster pair(s) rely on a SINGLE bridge concept** — "
                "fragile connections that one missing paper could sever."
            )
            lines.append("")
            for gap in fragile[:5]:
                label_a = self._label_community(gap["comm_a"])
                label_b = self._label_community(gap["comm_b"])
                bridge = self._node_label(gap["bridge_nodes"][0])
                lines.append(
                    f"- **{label_a}** ↔ **{label_b}** — "
                    f"single bridge: `{bridge}`"
                )
            lines.append("")

        # ── Section 3: Isolated silos ──────────────────────────────────────────
        lines.append("## 🟡 Isolated Research Silos")
        lines.append("")

        if silo_gaps:
            lines.append(
                "These communities have high internal constraint — "
                "they are self-contained topic clusters with no meaningful "
                "outward connections. Could indicate missing cross-disciplinary papers."
            )
            lines.append("")
            lines.append("| Community | Size | Top Concepts | Constraint Score |")
            lines.append("|-----------|------|--------------|-----------------|")
            for silo in silo_gaps:
                top_labels = [self._node_label(n) for n in silo["top_nodes"]]
                lines.append(
                    f"| Community {silo['community_id']} | "
                    f"{silo['size']} nodes | "
                    f"{', '.join(top_labels[:3])} | "
                    f"{silo['avg_constraint']} |"
                )
        else:
            lines.append("No isolated silos detected.")

        lines.append("")

        # ── Section 4: Summary + actionable suggestions ────────────────────────
        lines.append("## Suggested Research Actions")
        lines.append("")

        total_critical = len(critical)
        total_density = len(top_density)
        total_silos = len(silo_gaps)

        if total_critical > 0:
            # Pick the most important gap
            top_gap = critical[0]
            label_a = self._label_community(top_gap["comm_a"])
            label_b = self._label_community(top_gap["comm_b"])
            lines.append(
                f"1. **Highest priority**: Find papers bridging "
                f"**{label_a}** and **{label_b}** — "
                f"this is a zero-bridge gap in your research."
            )
        elif total_density > 0:
            top_gap = top_density[0]
            label_a = self._label_community(top_gap["comm_a"])
            label_b = self._label_community(top_gap["comm_b"])
            lines.append(
                f"1. **Highest priority**: Strengthen the connection between "
                f"**{label_a}** and **{label_b}** "
                f"(gap score: {top_gap['gap_score']})."
            )

        if total_silos > 0:
            silo = silo_gaps[0]
            rep = self._node_label(silo["representative_node"])
            lines.append(
                f"2. **Break silo**: Community around `{rep}` "
                f"({silo['size']} nodes) has no external connections — "
                f"look for cross-disciplinary papers."
            )

        if total_density > 3:
            lines.append(
                f"3. **Batch action**: {total_density} underconnected pairs found — "
                f"consider a targeted literature search across these topic boundaries."
            )

        lines.append("")
        lines.append(
            "_Run `uv run main.py gap` after ingesting new papers "
            "to see if gaps are closing._"
        )
        lines.append("")

        return "\n".join(lines)


# ── Standalone runner ──────────────────────────────────────────────────────────

def run_gap_analysis(save: bool = False) -> str:
    """
    Entry point called by main.py and importable by lint.py / build_graph.py.

    Args:
        save: if True, write report to 2_graph/gap-report.md

    Returns:
        report string
    """
    if not HAS_NETWORKX:
        msg = (
            "ERROR: networkx is not installed.\n"
            "Run: pip install networkx"
        )
        print(msg)
        return msg

    analyzer = SemanticGapAnalyzer()
    report = analyzer.run()

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    if save:
        GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        GAP_REPORT.write_text(report, encoding="utf-8")
        print(f"\nSaved: {GAP_REPORT.relative_to(REPO_ROOT)}")

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Semantic gap analysis for LLM Wiki"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to 2_graph/gap-report.md",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild graph from wiki pages instead of using graph.json",
    )
    args = parser.parse_args()

    analyzer = SemanticGapAnalyzer(use_graph_json=not args.rebuild)
    report = analyzer.run()

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    if args.save:
        GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        GAP_REPORT.write_text(report, encoding="utf-8")
        print(f"\nSaved: {GAP_REPORT.relative_to(REPO_ROOT)}")