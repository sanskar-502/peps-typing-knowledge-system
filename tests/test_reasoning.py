"""
Tests for the reasoning engine.

These test that the reasoning pipeline produces sensible output
for known inputs, using the actual knowledge state.
"""

import json
import os
import pytest
from pathlib import Path

# adjust path if running from repo root
KB_PATH = Path(__file__).parent.parent / "knowledge_state.json"


def kb_exists():
    return KB_PATH.exists()


@pytest.mark.skipif(not kb_exists(), reason="knowledge_state.json not built yet")
class TestReasoning:

    def test_concept_matching_finds_something(self):
        """A query about protocols should match the structural subtyping concept."""
        from src.reasoning import match_input_to_concepts
        concepts = match_input_to_concepts("I want to define a Protocol inline")
        assert "Structural Subtyping" in concepts

    def test_concept_matching_union_types(self):
        """A query about union syntax should match union types."""
        from src.reasoning import match_input_to_concepts
        concepts = match_input_to_concepts("Can we use X | Y instead of Union[X, Y]?")
        assert "Union Types" in concepts

    def test_concept_matching_annotation_eval(self):
        """A query about deferred evaluation should match annotation concepts."""
        from src.reasoning import match_input_to_concepts
        concepts = match_input_to_concepts(
            "What if we postponed annotation evaluation to avoid forward reference issues?"
        )
        assert "Annotation Evaluation" in concepts

    def test_full_reasoning_returns_report(self):
        """End-to-end: a query should produce a non-empty report."""
        from src.reasoning import reason
        report = reason(
            "Should Python support a shorthand for defining a Protocol inline?",
            knowledge_path=str(KB_PATH),
        )
        assert "PRECEDENT" in report
        assert len(report) > 100

    def test_json_output_has_structure(self):
        """The JSON output should have the expected top-level keys."""
        from src.reasoning import reason_json
        result = reason_json(
            "What about making type aliases first-class?",
            knowledge_path=str(KB_PATH),
        )
        assert "matched_concepts" in result
        assert "precedents" in result
        assert "friction_points" in result

    def test_no_concepts_matched_gracefully(self):
        """A totally unrelated query should not crash, just return low-info report."""
        from src.reasoning import reason
        report = reason(
            "How do I make a sandwich?",
            knowledge_path=str(KB_PATH),
        )
        assert "No matching concepts" in report
