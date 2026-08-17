"""
Deterministic extraction -- the backbone of the pipeline.

This module handles everything that can be extracted from PEP source files
without any inference: header fields, cross-references, section segmentation,
and concept matching via keywords.

A measurable majority of edges in the final graph come from this module,
not from the LLM classifier. That's intentional.
"""

import re
import os
from pathlib import Path
from typing import Optional

from .ontology import (
    Proposal, Person, PEPStatus, PEPType, ReferenceContext,
    CONCEPTS, PEPS_IN_SCOPE,
)


# maps section titles (lowercased) to our ReferenceContext enum
SECTION_CONTEXT_MAP = {
    "abstract": ReferenceContext.ABSTRACT,
    "motivation": ReferenceContext.MOTIVATION,
    "specification": ReferenceContext.SPECIFICATION,
    "rationale": ReferenceContext.RATIONALE,
    "rejected ideas": ReferenceContext.REJECTED_IDEAS,
    "rejected alternatives": ReferenceContext.REJECTED_IDEAS,
    "backwards compatibility": ReferenceContext.BACKWARDS_COMPAT,
    "backward compatibility": ReferenceContext.BACKWARDS_COMPAT,
}

# regex for PEP cross-references in body text
PEP_REF_PATTERN = re.compile(r'\bPEP\s+(\d+)\b', re.IGNORECASE)

# status string normalization
STATUS_MAP = {
    "accepted": PEPStatus.ACCEPTED,
    "active": PEPStatus.ACTIVE,
    "deferred": PEPStatus.DEFERRED,
    "draft": PEPStatus.DRAFT,
    "final": PEPStatus.FINAL,
    "provisional": PEPStatus.PROVISIONAL,
    "rejected": PEPStatus.REJECTED,
    "superseded": PEPStatus.SUPERSEDED,
    "withdrawn": PEPStatus.WITHDRAWN,
}

TYPE_MAP = {
    "standards track": PEPType.STANDARDS_TRACK,
    "informational": PEPType.INFORMATIONAL,
    "process": PEPType.PROCESS,
}


def find_pep_files(peps_dir: str) -> dict[int, Path]:
    """Locate PEP files on disk for our in-scope PEP numbers.
    PEP files are named like pep-0484.rst or pep-0484.txt."""
    found = {}
    peps_path = Path(peps_dir)

    if not peps_path.exists():
        return found

    for pep_num in PEPS_IN_SCOPE:
        # try both .rst and .txt, newer peps might be .rst
        for ext in [".rst", ".txt"]:
            filename = f"pep-{pep_num:04d}{ext}"
            filepath = peps_path / filename
            if filepath.exists():
                found[pep_num] = filepath
                break

    return found


def parse_pep_header(raw_text: str) -> dict[str, str]:
    """Parse the RFC-822-style header block at the top of a PEP file.
    Returns a dict of field name -> value. Multi-line values are joined."""
    headers = {}
    current_key = None
    lines = raw_text.split("\n")

    for line in lines:
        # blank line or a reST section marker ends the header
        if line.strip() == "" or line.startswith("===") or line.startswith("---"):
            if current_key is not None:
                break
            continue

        # continuation line (starts with whitespace)
        if line.startswith((" ", "\t")) and current_key:
            headers[current_key] += " " + line.strip()
            continue

        # new field
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # skip lines that look like reST directives, not headers
            if key.startswith(".."):
                continue
            current_key = key.lower()
            headers[current_key] = value
        else:
            # probably hit body text
            if current_key is not None:
                break

    return headers


def parse_header_to_proposal(headers: dict[str, str]) -> Optional[Proposal]:
    """Build a Proposal entity from parsed header fields."""
    pep_str = headers.get("pep", "").strip()
    if not pep_str or not pep_str.isdigit():
        return None

    pep_number = int(pep_str)
    title = headers.get("title", "Untitled")

    # status
    raw_status = headers.get("status", "draft").lower().strip()
    status = STATUS_MAP.get(raw_status, PEPStatus.DRAFT)

    # type
    raw_type = headers.get("type", "standards track").lower().strip()
    pep_type = TYPE_MAP.get(raw_type, PEPType.STANDARDS_TRACK)

    # authors -- comma-separated, sometimes with email in angle brackets
    raw_authors = headers.get("author", "")
    authors = _parse_authors(raw_authors)

    # dates and versions
    created = headers.get("created", None)
    python_version = headers.get("python-version", None)

    # cross-pep links from headers
    superseded_by = _parse_single_pep_ref(headers.get("superseded-by", ""))
    replaces = _parse_single_pep_ref(headers.get("replaces", ""))
    requires_raw = headers.get("requires", "")
    requires = _parse_pep_list(requires_raw)

    return Proposal(
        pep_number=pep_number,
        title=title,
        status=status,
        pep_type=pep_type,
        authors=authors,
        created_date=created,
        python_version=python_version,
        superseded_by=superseded_by,
        requires=requires,
        replaces=replaces,
    )


def _parse_authors(raw: str) -> list[str]:
    """Extract author names, stripping emails and BDFL-Delegate noise."""
    authors = []
    # split on comma, handle "Name <email>" format
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        # strip email
        name = re.sub(r'<[^>]+>', '', chunk).strip()
        # strip any trailing whitespace or weird chars
        name = re.sub(r'\s+', ' ', name).strip()
        if name:
            authors.append(name)
    return authors


def _parse_single_pep_ref(raw: str) -> Optional[int]:
    """Parse a header value that should contain a single PEP number."""
    raw = raw.strip()
    if not raw:
        return None
    match = re.search(r'(\d+)', raw)
    return int(match.group(1)) if match else None


def _parse_pep_list(raw: str) -> list[int]:
    """Parse a comma-separated list of PEP numbers."""
    nums = []
    for match in re.finditer(r'(\d+)', raw):
        nums.append(int(match.group(1)))
    return nums


def segment_pep_body(raw_text: str) -> dict[str, str]:
    """Split a PEP's body text into named sections.
    Returns {section_name_lower: section_text}."""
    sections = {}
    current_section = "preamble"
    current_lines = []

    # skip past the header block first
    in_header = True
    lines = raw_text.split("\n")

    for i, line in enumerate(lines):
        # detect end of header: first blank line after seeing header fields
        if in_header:
            if line.strip() == "" and i > 2:
                in_header = False
            continue

        # reST section headers: a line followed by === or --- or ~~~
        if i + 1 < len(lines) and lines[i + 1].strip():
            underline = lines[i + 1].strip()
            if len(underline) >= 3 and all(c == underline[0] for c in underline) \
                    and underline[0] in "=-~^`:.'\"":
                # this line is a section title
                if current_lines:
                    sections[current_section] = "\n".join(current_lines)
                current_section = line.strip().lower()
                current_lines = []
                continue

        current_lines.append(line)

    # don't forget the last section
    if current_lines:
        sections[current_section] = "\n".join(current_lines)

    return sections


def extract_pep_references(sections: dict[str, str]) -> list[dict]:
    """Find all PEP cross-references in the body text.
    Returns list of {target_pep: int, context: ReferenceContext}."""
    refs = []
    seen = set()  # dedupe within same section

    for section_name, text in sections.items():
        context = SECTION_CONTEXT_MAP.get(section_name, ReferenceContext.OTHER)

        for match in PEP_REF_PATTERN.finditer(text):
            target = int(match.group(1))
            key = (target, context)
            if key not in seen:
                seen.add(key)
                refs.append({"target_pep": target, "context": context.value})

    return refs


def match_concepts(sections: dict[str, str]) -> list[str]:
    """Match the PEP's body text against our hand-curated concept list.
    Returns list of matched concept names."""
    # combine all section text for matching
    full_text = " ".join(sections.values()).lower()
    matched = []

    for concept in CONCEPTS:
        for keyword in concept.keywords:
            if keyword.lower() in full_text:
                matched.append(concept.name)
                break  # one keyword match is enough per concept

    return matched


def extract_all(peps_dir: str) -> dict:
    """Run the full deterministic extraction pipeline.
    Returns a dict with proposals, persons, references, concept_links."""
    pep_files = find_pep_files(peps_dir)
    results = {
        "proposals": {},
        "persons": set(),
        "references": {},  # pep_number -> [ref_dicts]
        "concept_links": {},  # pep_number -> [concept_names]
        "sections": {},  # pep_number -> {section_name: text} -- for later phases
    }

    for pep_num, filepath in sorted(pep_files.items()):
        raw = filepath.read_text(encoding="utf-8", errors="replace")

        # parse header
        headers = parse_pep_header(raw)
        proposal = parse_header_to_proposal(headers)
        if proposal is None:
            print(f"  warning: couldn't parse PEP {pep_num} header, skipping")
            continue

        results["proposals"][pep_num] = proposal

        # collect authors
        for author in proposal.authors:
            results["persons"].add(author)

        # segment body
        sections = segment_pep_body(raw)
        results["sections"][pep_num] = sections

        # cross-references
        refs = extract_pep_references(sections)
        results["references"][pep_num] = refs

        # concept matching
        concepts = match_concepts(sections)
        results["concept_links"][pep_num] = concepts

    # convert persons set to list for serialization later
    results["persons"] = sorted(results["persons"])

    print(f"extracted {len(results['proposals'])} proposals, "
          f"{len(results['persons'])} unique authors")

    return results
