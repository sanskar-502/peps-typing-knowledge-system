"""
Constrained LLM classification for extracting objections and alternatives
from PEP sections that are too unstructured for pure regex.

Key design constraint: the LLM never decides what an entity or relationship
type is. We define the schema (ObjectionCategory enum, ExtractedAlternative
model), and the LLM slots text into those pre-defined categories. It's a
fuzzy classifier, not a knowledge extractor.

Requires GEMINI_API_KEY env var. Results are cached to disk so the
pipeline only calls the API once per PEP section.
"""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .ontology import ObjectionCategory


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------

class ExtractedAlternative(BaseModel):
    """A design alternative considered and rejected in the PEP."""
    name: str
    description: str  # paraphrased, 2 sentences max
    reason_rejected: str  # paraphrased, 2 sentences max
    reason_category: ObjectionCategory


class ExtractedObjection(BaseModel):
    """An objection or concern raised against the PEP's main proposal."""
    text: str  # paraphrased, 2 sentences max
    category: ObjectionCategory
    source_section: str


class ExtractionResult(BaseModel):
    """Full extraction result for one PEP's unstructured sections."""
    pep_number: int
    alternatives: list[ExtractedAlternative] = []
    objections: list[ExtractedObjection] = []


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """You are analyzing a section from a Python Enhancement Proposal (PEP).
Your job is to identify:
1. Design alternatives that were considered and rejected
2. Objections or concerns raised against the main proposal

For each alternative, classify the rejection reason into exactly one category:
- performance: rejected due to runtime or memory overhead
- backward_compat: rejected because it would break existing code
- complexity: rejected because it adds too much conceptual or implementation complexity
- ambiguity: rejected because it creates ambiguous or confusing semantics
- precedent_conflict: rejected because it contradicts established patterns or prior decisions
- out_of_scope: rejected because it goes beyond what this PEP aims to address

For each objection, use the same categories.

Here are worked examples:

Example 1 (from PEP 604, Union syntax):
Text: "One alternative was to use a new keyword 'or' for union types. This was rejected because it would conflict with the existing boolean 'or' operator and create parsing ambiguity."
Alternative: {{"name": "Keyword 'or' for unions", "description": "Use 'or' keyword instead of '|' for union type syntax.", "reason_rejected": "Conflicts with existing boolean 'or' operator and creates parsing ambiguity.", "reason_category": "ambiguity"}}

Example 2 (from PEP 544, Protocols):
Text: "Making protocols check structural compatibility at runtime was considered but rejected due to the significant performance cost of deep structural comparison on every isinstance check."
Objection: {{"text": "Runtime structural compatibility checking was rejected due to significant performance cost of deep comparison on every isinstance call.", "category": "performance", "source_section": "rejected_ideas"}}

Now analyze the following PEP section. Return ONLY valid JSON matching this schema:
{{
  "alternatives": [list of alternatives found],
  "objections": [list of objections found]
}}

If none are found, return empty lists. Be conservative -- only extract items that are clearly stated, don't infer or speculate.

PEP {pep_number}, Section: {section_name}
---
{text}
"""


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent.parent / "extraction_cache"


def _cache_path(pep_number: int, section: str) -> Path:
    """Get the cache file path for a given PEP + section."""
    safe_section = section.replace(" ", "_").replace("/", "_")
    return CACHE_DIR / f"pep_{pep_number}_{safe_section}.json"


def _load_cached(pep_number: int, section: str) -> Optional[dict]:
    """Load a cached extraction result if it exists."""
    path = _cache_path(pep_number, section)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return None


def _save_cache(pep_number: int, section: str, data: dict):
    """Save an extraction result to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(pep_number, section)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------

def classify_section(pep_number: int, section_name: str, text: str,
                     use_cache: bool = True) -> dict:
    """Run constrained classification on a PEP section.

    Checks cache first. If not cached, calls the Gemini API with
    our pre-defined schema and worked examples.
    """
    if use_cache:
        cached = _load_cached(pep_number, section_name)
        if cached is not None:
            return cached

    # check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"  skipping LLM classification for PEP {pep_number}/{section_name} "
              f"-- no GEMINI_API_KEY set")
        return {"alternatives": [], "objections": []}

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.6-flash")

    prompt = CLASSIFICATION_PROMPT.format(
        pep_number=pep_number,
        section_name=section_name,
        text=text[:6000],  # gemini handles longer context well
    )

    try:
        response = model.generate_content(prompt)
        raw_response = response.text.strip()

        # strip markdown code fences if the model wraps its output
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
            raw_response = raw_response.strip()

        result = json.loads(raw_response)

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"  warning: failed to parse LLM output for PEP {pep_number}/{section_name}: {e}")
        result = {"alternatives": [], "objections": []}
    except Exception as e:
        print(f"  error calling Gemini API for PEP {pep_number}/{section_name}: {e}")
        result = {"alternatives": [], "objections": []}

    # cache the result either way
    if use_cache:
        _save_cache(pep_number, section_name, result)

    return result



# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------

# keywords that indicate a section is worth classifying
TARGET_KEYWORDS = ["rejected", "backwards compat", "backward compat"]


def _is_target_section(section_name: str) -> bool:
    """Check if a section name is one we want to classify."""
    name = section_name.lower()
    return any(kw in name for kw in TARGET_KEYWORDS)


def extract_classified(sections_by_pep: dict[int, dict[str, str]]) -> dict[int, ExtractionResult]:
    """Run constrained classification on all relevant sections across all PEPs.
    Returns {pep_number: ExtractionResult}."""
    results = {}

    for pep_number, sections in sorted(sections_by_pep.items()):
        all_alternatives = []
        all_objections = []

        for section_name, text in sections.items():
            if not _is_target_section(section_name):
                continue
            if len(text.strip()) < 50:  # skip trivially short sections
                continue

            print(f"  classifying PEP {pep_number} / {section_name}")
            raw = classify_section(pep_number, section_name, text)

            for alt_data in raw.get("alternatives", []):
                try:
                    alt = ExtractedAlternative(**alt_data)
                    all_alternatives.append(alt)
                except Exception:
                    pass  # skip malformed entries

            for obj_data in raw.get("objections", []):
                try:
                    obj_data["source_section"] = section_name
                    obj = ExtractedObjection(**obj_data)
                    all_objections.append(obj)
                except Exception:
                    pass

        results[pep_number] = ExtractionResult(
            pep_number=pep_number,
            alternatives=all_alternatives,
            objections=all_objections,
        )

    total_alts = sum(len(r.alternatives) for r in results.values())
    total_objs = sum(len(r.objections) for r in results.values())
    print(f"classified extraction done: {total_alts} alternatives, {total_objs} objections")

    return results
