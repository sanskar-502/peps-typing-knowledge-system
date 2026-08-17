"""
Reasoning engine -- the part that makes this a knowledge system, not a database.

Takes a free-text input (e.g. a developer describing a feature idea) and reasons
over the knowledge graph to produce a structured precedent & risk report.

This runs entirely locally. No API key needed. The graph does the work.

Pipeline:
  1. Map input text to concepts (reuses the same keyword matcher from extraction)
  2. Retrieve candidate proposals + alternatives linked to matched concepts
  3. Rank by concept overlap + graph proximity
  4. Pull evidence (objections, alternatives) for top candidates
  5. Aggregate friction points
  6. Format structured output
"""

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import networkx as nx

from .ontology import CONCEPTS


def load_knowledge_graph(path: str = "knowledge_state.json") -> nx.MultiDiGraph:
    """Load the knowledge state JSON back into a networkx graph."""
    with open(path, "r") as f:
        state = json.load(f)

    G = nx.MultiDiGraph()

    for node in state["nodes"]:
        node_id = node.pop("id")
        G.add_node(node_id, **node)

    for edge in state["edges"]:
        src = edge.pop("source")
        tgt = edge.pop("target")
        G.add_edge(src, tgt, **edge)

    return G


def match_input_to_concepts(text: str) -> list[str]:
    """Match free-text input against our concept list using the same
    keyword logic as the extraction phase. Consistency matters."""
    text_lower = text.lower()
    matched = []

    for concept in CONCEPTS:
        for keyword in concept.keywords:
            if keyword.lower() in text_lower:
                matched.append(concept.name)
                break

    return matched


def retrieve_candidates(G: nx.DiGraph, concepts: list[str]) -> list[dict]:
    """Find all proposals and alternatives linked to the matched concepts."""
    candidates = []
    seen_peps = set()

    for concept_name in concepts:
        concept_id = f"concept_{concept_name.lower().replace(' ', '_')}"
        if concept_id not in G:
            continue

        # find all proposals that relate to this concept
        for predecessor in G.predecessors(concept_id):
            node_data = G.nodes[predecessor]
            if node_data.get("type") == "proposal" and predecessor not in seen_peps:
                seen_peps.add(predecessor)
                candidates.append({
                    "node_id": predecessor,
                    "type": "proposal",
                    "data": dict(node_data),
                    "matched_via": [concept_name],
                })

    # second pass: if a candidate was matched via multiple concepts, merge
    by_id = {}
    for c in candidates:
        if c["node_id"] in by_id:
            by_id[c["node_id"]]["matched_via"].extend(c["matched_via"])
        else:
            by_id[c["node_id"]] = c

    return list(by_id.values())


def score_candidates(candidates: list[dict], concepts: list[str],
                     G: nx.DiGraph) -> list[dict]:
    """Score and rank candidates by relevance.

    Scoring factors:
      - concept overlap: how many of the input's concepts does this PEP share
      - objection richness: PEPs with more extracted objections/alternatives
        are more informative as precedents
      - graph centrality: PEPs that are heavily cross-referenced are more
        likely to be foundational
    """
    for candidate in candidates:
        node_id = candidate["node_id"]
        overlap = len(set(candidate["matched_via"]) & set(concepts))

        # count connected objections and alternatives
        evidence_count = 0
        for successor in G.successors(node_id):
            stype = G.nodes[successor].get("type", "")
            if stype in ("objection", "alternative"):
                evidence_count += 1

        # simple degree as a proxy for "how central is this PEP"
        degree = G.degree(node_id)

        # weighted score -- concept overlap matters most
        candidate["score"] = (overlap * 3) + (evidence_count * 2) + (degree * 0.5)
        candidate["concept_overlap"] = overlap
        candidate["evidence_count"] = evidence_count

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def pull_evidence(G: nx.DiGraph, node_id: str) -> dict:
    """For a given proposal node, pull all connected objections and alternatives."""
    alternatives = []
    objections = []

    for successor in G.successors(node_id):
        node_data = G.nodes[successor]
        ntype = node_data.get("type", "")

        if ntype == "alternative":
            alternatives.append(dict(node_data))
        elif ntype == "objection":
            objections.append(dict(node_data))

    return {"alternatives": alternatives, "objections": objections}


def aggregate_friction_points(evidence_sets: list[dict]) -> dict:
    """Count objection categories across all evidence to predict friction."""
    category_counts = Counter()
    total_precedents = len(evidence_sets)

    for ev in evidence_sets:
        categories_in_this = set()
        for obj in ev.get("objections", []):
            cat = obj.get("category", "unknown")
            categories_in_this.add(cat)
        for alt in ev.get("alternatives", []):
            cat = alt.get("reason_category", "unknown")
            categories_in_this.add(cat)
        for cat in categories_in_this:
            category_counts[cat] += 1

    return {
        "total_precedents": total_precedents,
        "friction_by_category": dict(category_counts),
    }


def format_report(input_text: str, concepts: list[str],
                  ranked_candidates: list[dict], evidence_sets: list[dict],
                  friction: dict, top_n: int = 5) -> str:
    """Format the final structured report for human consumption."""
    lines = []
    lines.append("PRECEDENT & RISK REPORT")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Input: \"{input_text[:200]}\"")
    lines.append("")

    if not concepts:
        lines.append("No matching concepts found in the knowledge base.")
        lines.append("Try rephrasing your input with terms related to Python's type system.")
        return "\n".join(lines)

    lines.append(f"Matched concepts: {', '.join(concepts)}")
    lines.append("")

    lines.append("Top related precedents:")
    lines.append("-" * 40)

    shown = min(top_n, len(ranked_candidates))
    for i in range(shown):
        c = ranked_candidates[i]
        data = c["data"]
        pep_num = data.get("pep_number", "?")
        title = data.get("title", "Untitled")
        status = data.get("status", "unknown")
        lines.append(f"  {i+1}. PEP {pep_num} -- {title} ({status})")
        lines.append(f"     Shared concepts: {', '.join(c['matched_via'])}")

        # show most relevant alternative if any
        if i < len(evidence_sets):
            ev = evidence_sets[i]
            for alt in ev.get("alternatives", [])[:2]:
                lines.append(f"     Alternative considered: \"{alt.get('name', '')}\"")
                lines.append(f"       Rejected because: {alt.get('reason_rejected', 'N/A')}")
                lines.append(f"       Category: {alt.get('reason_category', 'N/A')}")
            if not ev.get("alternatives") and not ev.get("objections"):
                lines.append("     (no extracted objections/alternatives for this PEP)")

        lines.append("")

    # friction summary
    lines.append("Predicted friction points:")
    lines.append("-" * 40)
    total = friction["total_precedents"]
    if friction["friction_by_category"]:
        for cat, count in sorted(friction["friction_by_category"].items(),
                                 key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat}: raised in {count}/{total} precedents")
    else:
        lines.append("  No objection patterns found in precedents.")
    lines.append("")

    lines.append(f"Coverage: {shown} precedents found in 29-PEP scoped dataset")
    if shown <= 2:
        lines.append("(low coverage -- interpret with caution)")
    elif shown <= 4:
        lines.append("(moderate coverage)")
    else:
        lines.append("(good coverage)")

    return "\n".join(lines)


def reason(input_text: str, knowledge_path: str = "knowledge_state.json",
           top_n: int = 5) -> str:
    """Main entry point: take a free-text input, reason over the graph,
    return a structured report."""

    G = load_knowledge_graph(knowledge_path)

    # step 1: map to concepts
    concepts = match_input_to_concepts(input_text)

    # step 2: retrieve candidates
    candidates = retrieve_candidates(G, concepts)

    # step 3: rank
    ranked = score_candidates(candidates, concepts, G)

    # step 4: pull evidence for top candidates
    evidence = []
    for c in ranked[:top_n]:
        ev = pull_evidence(G, c["node_id"])
        evidence.append(ev)

    # step 5: aggregate friction
    friction = aggregate_friction_points(evidence)

    # step 6: format
    report = format_report(input_text, concepts, ranked, evidence, friction, top_n)
    return report


def reason_json(input_text: str, knowledge_path: str = "knowledge_state.json",
                top_n: int = 5) -> dict:
    """Same as reason(), but returns structured data instead of formatted text."""
    G = load_knowledge_graph(knowledge_path)
    concepts = match_input_to_concepts(input_text)
    candidates = retrieve_candidates(G, concepts)
    ranked = score_candidates(candidates, concepts, G)

    evidence = []
    for c in ranked[:top_n]:
        ev = pull_evidence(G, c["node_id"])
        evidence.append(ev)

    friction = aggregate_friction_points(evidence)

    return {
        "input": input_text,
        "matched_concepts": concepts,
        "precedents": [
            {
                "pep_number": c["data"].get("pep_number"),
                "title": c["data"].get("title"),
                "status": c["data"].get("status"),
                "shared_concepts": c["matched_via"],
                "score": c["score"],
                "evidence": evidence[i] if i < len(evidence) else {},
            }
            for i, c in enumerate(ranked[:top_n])
        ],
        "friction_points": friction,
    }
