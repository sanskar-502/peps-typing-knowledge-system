"""
Knowledge base builder -- orchestrates the extraction pipeline and assembles
the final knowledge graph.

Usage:
    python -m src.build_kb [--peps-dir data/peps] [--skip-llm]

The --skip-llm flag builds the graph from deterministic extraction only,
useful for development or when you don't have an API key handy.
"""

import argparse
import json
import sys
from pathlib import Path

import networkx as nx

from .ontology import PEPS_IN_SCOPE, CONCEPTS, EDGE_TYPES
from .extract_deterministic import extract_all
from .extract_classified import extract_classified


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph(deterministic_results: dict, classified_results: dict = None) -> nx.MultiDiGraph:
    """Assemble the knowledge graph from extraction results."""
    G = nx.MultiDiGraph()

    proposals = deterministic_results["proposals"]
    persons = deterministic_results["persons"]
    references = deterministic_results["references"]
    concept_links = deterministic_results["concept_links"]

    # --- add proposal nodes ---
    for pep_num, proposal in proposals.items():
        G.add_node(
            f"pep_{pep_num}",
            type="proposal",
            pep_number=pep_num,
            title=proposal.title,
            status=proposal.status.value,
            pep_type=proposal.pep_type.value,
            authors=proposal.authors,
            created_date=proposal.created_date or "",
            python_version=proposal.python_version or "",
        )

    # --- add person nodes + authored_by edges ---
    for person in persons:
        node_id = f"person_{person.lower().replace(' ', '_')}"
        G.add_node(node_id, type="person", name=person)

    for pep_num, proposal in proposals.items():
        for author in proposal.authors:
            person_id = f"person_{author.lower().replace(' ', '_')}"
            G.add_edge(f"pep_{pep_num}", person_id, type="authored_by")

    # --- add concept nodes + relates_to_concept edges ---
    for concept in CONCEPTS:
        concept_id = f"concept_{concept.name.lower().replace(' ', '_')}"
        G.add_node(
            concept_id,
            type="concept",
            name=concept.name,
            description=concept.description,
            keywords=concept.keywords,
        )

    for pep_num, matched_concepts in concept_links.items():
        for concept_name in matched_concepts:
            concept_id = f"concept_{concept_name.lower().replace(' ', '_')}"
            G.add_edge(f"pep_{pep_num}", concept_id, type="relates_to_concept")

    # --- supersedes / requires / replaces edges ---
    for pep_num, proposal in proposals.items():
        if proposal.superseded_by is not None:
            target_id = f"pep_{proposal.superseded_by}"
            if target_id in G:
                G.add_edge(target_id, f"pep_{pep_num}", type="supersedes")
        if proposal.replaces is not None:
            target_id = f"pep_{proposal.replaces}"
            if target_id in G:
                G.add_edge(f"pep_{pep_num}", target_id, type="supersedes")
        for req in proposal.requires:
            target_id = f"pep_{req}"
            if target_id in G:
                G.add_edge(f"pep_{pep_num}", target_id, type="requires")

    # --- cross-reference edges ---
    for pep_num, refs in references.items():
        for ref in refs:
            target = ref["target_pep"]
            target_id = f"pep_{target}"
            if target_id in G:
                G.add_edge(f"pep_{pep_num}", target_id,
                           type="references", context=ref["context"])

    # --- classified extraction (objections + alternatives) ---
    if classified_results:
        alt_counter = 0
        obj_counter = 0

        for pep_num, result in classified_results.items():
            for alt in result.alternatives:
                alt_id = f"alt_{pep_num}_{alt_counter}"
                alt_counter += 1
                G.add_node(
                    alt_id,
                    type="alternative",
                    name=alt.name,
                    description=alt.description,
                    reason_rejected=alt.reason_rejected,
                    reason_category=alt.reason_category.value,
                    source_pep=pep_num,
                )
                G.add_edge(f"pep_{pep_num}", alt_id, type="considers_and_rejects")

            for obj in result.objections:
                obj_id = f"obj_{pep_num}_{obj_counter}"
                obj_counter += 1
                G.add_node(
                    obj_id,
                    type="objection",
                    text=obj.text,
                    category=obj.category.value,
                    source_pep=pep_num,
                    source_section=obj.source_section,
                )
                G.add_edge(f"pep_{pep_num}", obj_id, type="raises")

    # --- manual "resembles" edges ---
    # these are hand-tagged: a rejected alternative in an older PEP that
    # closely resembles what a later PEP actually shipped.
    _add_manual_resembles_edges(G)

    return G


def _add_manual_resembles_edges(G: nx.MultiDiGraph):
    """Add hand-identified 'resembles' edges.

    These are the most valuable edges in the graph -- they capture the insight
    that a rejected idea in one PEP was essentially what a later PEP shipped.
    Can't automate this reliably, so we tag them manually after reviewing
    the extraction output.
    """
    # Find alternative nodes by matching on source_pep and name substring
    def find_alt(source_pep: int, name_fragment: str):
        for node_id, data in G.nodes(data=True):
            if (data.get("type") == "alternative"
                    and data.get("source_pep") == source_pep
                    and name_fragment.lower() in data.get("name", "").lower()):
                return node_id
        return None

    # Hand-justified resembles pairs:
    resembles = [
        # PEP 563 rejected "lazy evaluation via descriptors" -- PEP 649 later
        # shipped exactly this approach (deferred evaluation using descriptors).
        # This is the flagship example of the system's value.
        (563, "lazy evaluation", 649,
         "PEP 563 rejected lazy/deferred evaluation as too complex; PEP 649 "
         "later shipped this exact approach with a different mechanism."),

        # PEP 647 rejected "narrows in both branches" for TypeGuard --
        # PEP 742 later shipped TypeIs which does exactly that.
        (647, "narrows in both branches", 742,
         "PEP 647 rejected bidirectional narrowing for TypeGuard; PEP 742 "
         "introduced TypeIs which provides this with stricter guarantees."),

        # PEP 484 considered angle brackets -- PEP 695 revisited the syntax
        # question entirely with its new type parameter syntax.
        (484, "angle brackets", 695,
         "PEP 484 rejected angle brackets for generics; PEP 695 revisited "
         "type parameter syntax and chose a different approach entirely."),
    ]

    for source_pep, name_frag, target_pep, justification in resembles:
        alt_id = find_alt(source_pep, name_frag)
        if alt_id:
            G.add_edge(alt_id, f"pep_{target_pep}",
                       type="resembles", justification=justification)
        else:
            print(f"  warning: couldn't find alternative '{name_frag}' "
                  f"in PEP {source_pep} for resembles edge")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_graph(G: nx.MultiDiGraph) -> dict:
    """Run integrity checks on the assembled graph."""
    stats = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": {},
        "edge_types": {},
        "orphan_nodes": [],
        "dangling_refs": [],
    }

    # count by type
    for node, data in G.nodes(data=True):
        ntype = data.get("type", "unknown")
        stats["node_types"][ntype] = stats["node_types"].get(ntype, 0) + 1

    for u, v, key, data in G.edges(data=True, keys=True):
        etype = data.get("type", "unknown")
        stats["edge_types"][etype] = stats["edge_types"].get(etype, 0) + 1

    # orphan nodes -- nodes with no edges at all
    for node in G.nodes():
        if G.degree(node) == 0:
            stats["orphan_nodes"].append(node)

    # dangling references -- edges pointing to nodes outside our scope
    for pep_num in PEPS_IN_SCOPE:
        node_id = f"pep_{pep_num}"
        if node_id not in G:
            stats["dangling_refs"].append(pep_num)

    return stats


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def graph_to_knowledge_state(G: nx.MultiDiGraph) -> dict:
    """Serialize the graph to our knowledge_state.json format.
    This is the mandatory deliverable -- must be human-readable."""
    state = {
        "metadata": {
            "description": "Knowledge graph of Python typing PEPs (484-742)",
            "scope": "29 PEPs covering the evolution of Python's type system",
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
        "nodes": [],
        "edges": [],
    }

    for node_id, data in G.nodes(data=True):
        entry = {"id": node_id}
        entry.update(data)
        state["nodes"].append(entry)

    for u, v, key, data in G.edges(data=True, keys=True):
        entry = {"source": u, "target": v}
        entry.update(data)
        state["edges"].append(entry)

    return state


def export_graphml(G: nx.MultiDiGraph, path: str):
    """Export graph in GraphML format for visualization in Gephi/Cytoscape."""
    # graphml doesn't handle lists well, convert to strings
    H = G.copy()
    for node, data in H.nodes(data=True):
        for key, val in list(data.items()):
            if isinstance(val, list):
                data[key] = ", ".join(str(v) for v in val)
    nx.write_graphml(H, path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build the typing PEP knowledge base")
    parser.add_argument("--peps-dir", default="data/peps",
                        help="directory containing PEP .rst files")
    parser.add_argument("--skip-llm", action="store_true",
                        help="skip LLM classification, use only deterministic extraction")
    parser.add_argument("--output", default="knowledge_state.json",
                        help="output path for knowledge state JSON")
    args = parser.parse_args()

    print("=== Phase 1: Deterministic extraction ===")
    det_results = extract_all(args.peps_dir)

    classified = None
    if not args.skip_llm:
        print("\n=== Phase 2: Constrained classification ===")
        classified = extract_classified(det_results["sections"])
    else:
        print("\n(skipping LLM classification)")

    print("\n=== Phase 3: Graph assembly ===")
    G = build_graph(det_results, classified)

    print("\n=== Validation ===")
    stats = validate_graph(G)
    print(f"  nodes: {stats['total_nodes']}")
    print(f"  edges: {stats['total_edges']}")
    print(f"  node types: {stats['node_types']}")
    print(f"  edge types: {stats['edge_types']}")
    if stats["orphan_nodes"]:
        print(f"  orphan nodes: {stats['orphan_nodes']}")
    if stats["dangling_refs"]:
        print(f"  dangling refs (PEPs not found on disk): {stats['dangling_refs']}")

    print(f"\n=== Exporting ===")
    knowledge_state = graph_to_knowledge_state(G)
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(knowledge_state, f, indent=2)
    print(f"  wrote {output_path}")

    # optional graphml
    graphml_path = output_path.with_suffix(".graphml")
    try:
        export_graphml(G, str(graphml_path))
        print(f"  wrote {graphml_path}")
    except Exception as e:
        print(f"  graphml export failed (non-critical): {e}")

    print("\ndone.")


if __name__ == "__main__":
    main()
