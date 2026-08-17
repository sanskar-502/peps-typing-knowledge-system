"""
Ontology for the Python typing PEP knowledge system.

This defines every entity and relationship type the system understands.
The schema was designed before any extraction code was written -- see approach.md
for the reasoning behind each choice.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PEPStatus(str, Enum):
    ACCEPTED = "accepted"
    FINAL = "final"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DRAFT = "draft"
    DEFERRED = "deferred"
    ACTIVE = "active"
    PROVISIONAL = "provisional"


class PEPType(str, Enum):
    STANDARDS_TRACK = "standards_track"
    INFORMATIONAL = "informational"
    PROCESS = "process"


class ObjectionCategory(str, Enum):
    """
    Categories for objections raised in PEP discussions.
    Decided on these six after reading through the rejected-ideas sections
    of ~10 typing PEPs -- they cover the recurring themes without being
    so granular that classification becomes ambiguous.
    """
    PERFORMANCE = "performance"
    BACKWARD_COMPAT = "backward_compat"
    COMPLEXITY = "complexity"
    AMBIGUITY = "ambiguity"
    PRECEDENT_CONFLICT = "precedent_conflict"
    OUT_OF_SCOPE = "out_of_scope"


class ReferenceContext(str, Enum):
    """Where in the PEP a cross-reference appeared. A mention in rejected-ideas
    is a stronger relatedness signal than one in the bibliography."""
    MOTIVATION = "motivation"
    SPECIFICATION = "specification"
    RATIONALE = "rationale"
    REJECTED_IDEAS = "rejected_ideas"
    BACKWARDS_COMPAT = "backwards_compat"
    ABSTRACT = "abstract"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    """A PEP document. Most attributes come straight from the RFC-822 header."""
    pep_number: int
    title: str
    status: PEPStatus
    pep_type: PEPType
    authors: list[str] = field(default_factory=list)
    created_date: Optional[str] = None
    python_version: Optional[str] = None
    # which PEP superseded this one, if any
    superseded_by: Optional[int] = None
    requires: list[int] = field(default_factory=list)
    replaces: Optional[int] = None


@dataclass
class Person:
    """An author or contributor. Kept minimal on purpose -- we care about
    authorship relationships, not biographical data."""
    name: str


@dataclass
class Concept:
    """
    A hand-curated abstraction that connects PEPs across time.

    This is the layer that makes the graph more than a citation list.
    PEP 604 doesn't cite PEP 484's Union discussion by number, but they
    share the 'Union Types' concept. That link only exists because we
    modeled it explicitly.
    """
    name: str
    description: str
    # keywords used for deterministic matching
    keywords: list[str] = field(default_factory=list)


@dataclass
class Objection:
    """An objection or concern raised in a PEP's discussion, typically found
    in the Rejected Ideas or Backwards Compatibility sections."""
    text: str
    category: ObjectionCategory
    source_pep: int
    source_section: str


@dataclass
class Alternative:
    """A design alternative that was considered and rejected."""
    name: str
    description: str
    reason_rejected: str
    reason_category: ObjectionCategory
    source_pep: int


# ---------------------------------------------------------------------------
# Relationships (stored as typed edges in the graph)
# ---------------------------------------------------------------------------

# These aren't classes -- they're edge types with known attribute schemas.
# Keeping them as a reference for the graph assembly code.

EDGE_TYPES = {
    "supersedes": {
        "from": "Proposal",
        "to": "Proposal",
        "source": "deterministic (header field)",
    },
    "requires": {
        "from": "Proposal",
        "to": "Proposal",
        "source": "deterministic (header field)",
    },
    "authored_by": {
        "from": "Proposal",
        "to": "Person",
        "source": "deterministic (header field)",
    },
    "references": {
        "from": "Proposal",
        "to": "Proposal",
        "source": "deterministic (regex scan)",
        "attrs": ["context"],  # ReferenceContext enum
    },
    "relates_to_concept": {
        "from": "Proposal",
        "to": "Concept",
        "source": "deterministic (keyword match)",
    },
    "raises": {
        "from": "Proposal",
        "to": "Objection",
        "source": "constrained LLM classification",
    },
    "considers_and_rejects": {
        "from": "Proposal",
        "to": "Alternative",
        "source": "constrained LLM classification",
    },
    "resembles": {
        "from": "Alternative",
        "to": "Proposal",
        "source": "manual (hand-tagged)",
        "note": "A rejected alternative in an older PEP that closely resembles "
                "what a later PEP actually shipped. The most valuable edge type.",
    },
}


# ---------------------------------------------------------------------------
# Hand-curated concept list
# ---------------------------------------------------------------------------
# These are the abstractions that tie PEPs together across time.
# Keywords are used for deterministic matching in extract_deterministic.py.

CONCEPTS = [
    Concept(
        name="Gradual Typing",
        description="The idea that type hints are optional and don't affect runtime behavior",
        keywords=["gradual typing", "optional type", "type hint"],
    ),
    Concept(
        name="Structural Subtyping",
        description="Type compatibility based on structure rather than inheritance (Protocols)",
        keywords=["structural subtyp", "protocol", "duck typing"],
    ),
    Concept(
        name="Union Types",
        description="Representing a value that could be one of several types",
        keywords=["union", "x | y", "optional"],
    ),
    Concept(
        name="Generic Types",
        description="Parameterized types that work across different contained types",
        keywords=["generic", "typevar", "paramspec", "type parameter", "typevartuple"],
    ),
    Concept(
        name="Type Narrowing",
        description="Refining a type within a conditional branch (type guards, TypeIs)",
        keywords=["type guard", "narrowing", "typeis", "isinstance"],
    ),
    Concept(
        name="Annotation Evaluation",
        description="When and how type annotations are evaluated at runtime",
        keywords=["postponed eval", "deferred eval", "annotation", "forward reference",
                   "stringified", "pep 563", "pep 649", "__annotations__"],
    ),
    Concept(
        name="Runtime Introspection",
        description="Accessing type information at runtime via get_type_hints etc.",
        keywords=["get_type_hints", "runtime", "introspect", "__annotations__"],
    ),
    Concept(
        name="Type Aliases",
        description="Named shortcuts for complex type expressions",
        keywords=["type alias", "typealias"],
    ),
    Concept(
        name="Literal Types",
        description="Types restricted to specific literal values",
        keywords=["literal"],
    ),
    Concept(
        name="TypedDict",
        description="Typed dictionaries with per-key types",
        keywords=["typeddict", "typed dict", "required", "notrequired", "readonly"],
    ),
    Concept(
        name="Final and Constants",
        description="Declaring that a name should not be reassigned or overridden",
        keywords=["final", "@final", "constant"],
    ),
    Concept(
        name="Variance",
        description="Covariance, contravariance, and invariance in generic types",
        keywords=["covariant", "contravariant", "invariant", "variance"],
    ),
    Concept(
        name="Alternative Syntax Forms",
        description="Debates around functional vs class-based vs inline syntax for type constructs",
        keywords=["functional syntax", "class syntax", "shorthand", "inline"],
    ),
    Concept(
        name="Static Checker Compatibility",
        description="Ensuring new features work with mypy, pyright, and other checkers",
        keywords=["mypy", "pyright", "static checker", "type checker", "static analysis"],
    ),
    Concept(
        name="Decorator-Based Typing",
        description="Using decorators to convey type information (@override, @dataclass_transform)",
        keywords=["@override", "decorator", "dataclass_transform", "@deprecated"],
    ),
    Concept(
        name="Self Type",
        description="Referring to the type of the current class in annotations",
        keywords=["self type", "self"],
    ),
    Concept(
        name="String Annotations",
        description="Using string literals for forward references and annotation forms",
        keywords=["string annotation", "forward ref", "stringified"],
    ),
]


# PEPs in scope -- the typing saga from 483 to 742
PEPS_IN_SCOPE = [
    483, 484, 526, 544, 560, 561, 563, 585, 586, 589, 591, 593,
    604, 612, 613, 646, 647, 655, 673, 675, 681, 692, 695, 696,
    698, 702, 705, 742, 649,
]
