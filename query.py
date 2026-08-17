"""
CLI entry point for querying the knowledge system.

Usage:
    python query.py "Should Python support inline Protocol definitions?"
    python query.py --format json "What about lazy type evaluation?"
    python query.py --kb path/to/knowledge_state.json "your question here"

No API key required. This loads the pre-built knowledge state and reasons
over the local graph.
"""

import argparse
import json
import sys

from src.reasoning import reason, reason_json


def main():
    parser = argparse.ArgumentParser(
        description="Query the Python typing PEP knowledge system",
        epilog="Example: python query.py \"Should Python add inline Protocol syntax?\""
    )
    parser.add_argument("input", help="free-text description of a feature idea or question")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="output format (default: text)")
    parser.add_argument("--kb", default="knowledge_state.json",
                        help="path to knowledge_state.json")
    parser.add_argument("--top", type=int, default=5,
                        help="number of top precedents to show")
    args = parser.parse_args()

    if args.format == "json":
        result = reason_json(args.input, knowledge_path=args.kb, top_n=args.top)
        print(json.dumps(result, indent=2))
    else:
        report = reason(args.input, knowledge_path=args.kb, top_n=args.top)
        print(report)


if __name__ == "__main__":
    main()
