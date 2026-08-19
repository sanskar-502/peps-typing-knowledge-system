"""
Script to generate extraction cache files from manual reading of PEP sections.

This replaces the LLM classification step. Each PEP's rejected ideas and
backwards compatibility sections were read by hand, and the alternatives
and objections were identified and categorized manually.

Run this once to populate extraction_cache/ -- then build_kb.py will
pick them up automatically.
"""

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "extraction_cache"
CACHE_DIR.mkdir(exist_ok=True)


def save(pep_number: int, section: str, data: dict):
    safe_section = section.replace(" ", "_").replace("/", "_")
    path = CACHE_DIR / f"pep_{pep_number}_{safe_section}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  wrote {path.name}")


# ============================================================
# PEP 484 -- Type Hints (the origin)
# ============================================================

save(484, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use square brackets for generics",
            "description": "Use List[int] style square bracket syntax by overloading __getitem__ on classes in typing module.",
            "reason_rejected": "Actually adopted -- this was chosen over angle brackets (List<int>) because Python's parser cannot handle angle brackets without ambiguity with comparison operators.",
            "reason_category": "ambiguity"
        },
        {
            "name": "Angle brackets for generic types",
            "description": "Use C++/Java-style angle brackets like List<int> for generic type parameters.",
            "reason_rejected": "Python's parser treats < and > as comparison operators. Introducing them as brackets would require deep parser changes and create ambiguity.",
            "reason_category": "complexity"
        },
        {
            "name": "Decorator-based type hints",
            "description": "Use decorators instead of annotations to specify types, e.g. @types(int, returns=str).",
            "reason_rejected": "More verbose, less readable, and doesn't integrate with the existing PEP 3107 annotation syntax that was already in the language.",
            "reason_category": "precedent_conflict"
        },
        {
            "name": "Type hints as comments only",
            "description": "Put all type information in comments rather than annotations, relying entirely on # type: comments.",
            "reason_rejected": "Comments are not programmatically accessible at runtime. Annotations provide a structured, inspectable mechanism.",
            "reason_category": "complexity"
        },
        {
            "name": "Use existing annotation meaning from PEP 3107",
            "description": "Keep annotations free-form as in PEP 3107 rather than standardizing them for type hints.",
            "reason_rejected": "The community needed a shared vocabulary for static analysis. Free-form annotations had led to fragmented, incompatible uses.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": [
        {
            "text": "Type hints will make Python feel like a statically typed language and go against its dynamic nature.",
            "category": "precedent_conflict",
            "source_section": "rejected alternatives"
        },
        {
            "text": "Runtime performance concerns -- annotations are evaluated at function definition time, adding overhead.",
            "category": "performance",
            "source_section": "rejected alternatives"
        }
    ]
})

# ============================================================
# PEP 526 -- Syntax for Variable Annotations
# ============================================================

save(526, "rejected/postponed proposals", {
    "alternatives": [
        {
            "name": "Use type comments for all variable annotations",
            "description": "Continue using '# type: X' comments for variable annotations instead of introducing new syntax.",
            "reason_rejected": "Comments are invisible to the runtime and tooling. A proper syntax makes annotations part of the language semantics.",
            "reason_category": "complexity"
        },
        {
            "name": "Introduce a new keyword like 'var'",
            "description": "Use 'var x: int = 5' syntax with a new keyword for variable declarations.",
            "reason_rejected": "Adding a new keyword would break existing code that uses 'var' as a variable name. Too disruptive for the ecosystem.",
            "reason_category": "backward_compat"
        }
    ],
    "objections": []
})

save(526, "backwards compatibility", {
    "alternatives": [],
    "objections": [
        {
            "text": "The new annotation syntax x: int = 5 might be confused with assignment, especially by newcomers.",
            "category": "ambiguity",
            "source_section": "backwards compatibility"
        }
    ]
})

# ============================================================
# PEP 544 -- Protocols: Structural subtyping
# ============================================================

save(544, "rejected/postponed ideas", {
    "alternatives": [
        {
            "name": "Runtime structural compatibility checking",
            "description": "Make isinstance() checks perform full structural comparison for Protocol types at runtime.",
            "reason_rejected": "Deep structural comparison on every isinstance call would be extremely expensive. The cost is proportional to the complexity of the protocol.",
            "reason_category": "performance"
        },
        {
            "name": "Use ABCs instead of Protocols",
            "description": "Continue using Abstract Base Classes for structural subtyping via __subclasshook__.",
            "reason_rejected": "ABCs require explicit registration or inheritance. Protocols capture duck typing patterns that ABCs cannot express without modifying the checked class.",
            "reason_category": "complexity"
        },
        {
            "name": "Implicit protocol inference",
            "description": "Let type checkers automatically infer protocols from usage patterns without explicit Protocol definitions.",
            "reason_rejected": "Implicit protocols make it impossible to distinguish intentional structural contracts from coincidental method overlap. Explicit is better than implicit.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": [
        {
            "text": "Protocols add another way to define interfaces alongside ABCs, increasing the conceptual surface of the type system.",
            "category": "complexity",
            "source_section": "rejected/postponed ideas"
        }
    ]
})

# ============================================================
# PEP 563 -- Postponed Evaluation of Annotations
# ============================================================

save(563, "rejected ideas", {
    "alternatives": [
        {
            "name": "Lazy evaluation via descriptors or thunks",
            "description": "Instead of stringifying annotations, evaluate them lazily on first access using a descriptor protocol or thunk mechanism.",
            "reason_rejected": "Considered too complex for the initial implementation. The stringification approach was simpler and addressed the forward reference problem directly.",
            "reason_category": "complexity"
        },
        {
            "name": "Keep eager evaluation with improved forward references",
            "description": "Keep evaluating annotations at definition time but improve the string-based forward reference mechanism.",
            "reason_rejected": "The fundamental problem is that annotations are evaluated too early, before referenced names are available. String workarounds are fragile and inconsistent.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "Stringification breaks runtime uses of annotations that expect actual type objects, including dataclasses, attrs, and Pydantic.",
            "category": "backward_compat",
            "source_section": "rejected ideas"
        },
        {
            "text": "Libraries relying on get_type_hints() may behave differently because stringified annotations require the correct global/local scope to resolve.",
            "category": "backward_compat",
            "source_section": "backwards compatibility"
        }
    ]
})

save(563, "backwards compatibility", {
    "alternatives": [],
    "objections": [
        {
            "text": "Code that accesses __annotations__ directly will get strings instead of types, breaking introspection-based frameworks.",
            "category": "backward_compat",
            "source_section": "backwards compatibility"
        },
        {
            "text": "The from __future__ import annotations mechanism creates a per-module opt-in that can cause confusing behavior at module boundaries.",
            "category": "ambiguity",
            "source_section": "backwards compatibility"
        }
    ]
})

# ============================================================
# PEP 585 -- Type Hinting Generics In Standard Collections
# ============================================================

save(585, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Keep typing module wrappers indefinitely",
            "description": "Continue using typing.List, typing.Dict etc. rather than allowing list[int], dict[str, int] directly.",
            "reason_rejected": "The typing module duplicates built-in types unnecessarily. Direct subscription of built-in types is more natural and reduces import burden.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "Deprecating typing.List etc. creates a migration burden for existing codebases with extensive type annotations.",
            "category": "backward_compat",
            "source_section": "rejected alternatives"
        }
    ]
})

# ============================================================
# PEP 586 -- Literal Types
# ============================================================

save(586, "rejected or out-of-scope ideas", {
    "alternatives": [
        {
            "name": "Enum-based literal types",
            "description": "Use Python enums to represent literal types instead of introducing Literal[].",
            "reason_rejected": "Enums require defining a new class for every set of literal values. Literal[] is more lightweight for ad-hoc value constraints.",
            "reason_category": "complexity"
        },
        {
            "name": "Support mutable literal values",
            "description": "Allow Literal types to include mutable values like lists or dicts.",
            "reason_rejected": "Mutable values don't have a stable identity. Literal types must be restricted to immutable, hashable values to maintain type system soundness.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 589 -- TypedDict
# ============================================================

save(589, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Functional syntax as the primary form",
            "description": "Use Point2D = TypedDict('Point2D', x=int, y=int) as the only way to define TypedDicts, without the class-based syntax.",
            "reason_rejected": "The functional form is harder for static type checkers to analyze and doesn't support inheritance or method definitions.",
            "reason_category": "ambiguity"
        },
        {
            "name": "Use NamedTuple instead of TypedDict",
            "description": "Use NamedTuple for all cases where structured data with typed fields is needed.",
            "reason_rejected": "NamedTuples are immutable and create new objects. TypedDict describes plain dicts which are mutable and already widely used in Python codebases, especially for JSON data.",
            "reason_category": "precedent_conflict"
        },
        {
            "name": "Use regular classes with __init__ annotations",
            "description": "Define typed dictionary-like objects as regular classes with annotated __init__ parameters.",
            "reason_rejected": "This doesn't match the actual runtime type (dict). TypedDict specifically describes the structure of plain dict objects.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "TypedDict adds another way to define structured types alongside dataclasses, NamedTuple, and regular classes, increasing cognitive load.",
            "category": "complexity",
            "source_section": "rejected alternatives"
        }
    ]
})

# ============================================================
# PEP 591 -- Adding a final qualifier to typing
# ============================================================

save(591, "rejected/deferred ideas", {
    "alternatives": [
        {
            "name": "Use ALL_CAPS convention instead of Final",
            "description": "Rely on the PEP 8 convention of UPPER_CASE names for constants rather than adding a type-level qualifier.",
            "reason_rejected": "Naming conventions are not enforceable by type checkers. Final provides a machine-checkable guarantee that a name won't be reassigned.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 604 -- Allow writing union types as X | Y
# ============================================================

# PEP 604 doesn't have a 'rejected ideas' section with = underline,
# but the rationale discusses alternatives implicitly
save(604, "rejected_ideas", {
    "alternatives": [
        {
            "name": "Keep Union[X, Y] as the only syntax",
            "description": "Continue using Union[X, Y] from typing module for union types.",
            "reason_rejected": "Union[X, Y] is verbose and requires importing from typing. The | operator is more intuitive and consistent with set-theoretic type notation.",
            "reason_category": "complexity"
        },
        {
            "name": "Use 'or' keyword for unions",
            "description": "Use 'int or str' syntax for union types using the 'or' keyword.",
            "reason_rejected": "The 'or' keyword is already a boolean operator. Overloading it for type expressions would create parsing ambiguity and confusion.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 612 -- Parameter Specification Variables
# ============================================================

save(612, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use *args and **kwargs types separately",
            "description": "Instead of ParamSpec, type decorators by separately typing *args and **kwargs.",
            "reason_rejected": "Separating args and kwargs loses the relationship between a callable's full parameter signature. ParamSpec captures the entire signature as a unit.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "ParamSpec introduces significant conceptual complexity for a feature most developers won't directly use.",
            "category": "complexity",
            "source_section": "rejected alternatives"
        }
    ]
})

# ============================================================
# PEP 613 -- Explicit Type Aliases
# ============================================================

save(613, "rejected ideas", {
    "alternatives": [
        {
            "name": "Infer type aliases from assignment context",
            "description": "Let type checkers automatically determine whether an assignment is a type alias or a regular variable.",
            "reason_rejected": "Ambiguous in many cases. x = int could be a type alias or a variable holding the int class. Explicit TypeAlias annotation removes the ambiguity.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 646 -- Variadic Generics
# ============================================================

save(646, "rationale and rejected ideas", {
    "alternatives": [
        {
            "name": "Use overloads for each arity",
            "description": "Define separate overloads for each possible number of type parameters instead of variadic generics.",
            "reason_rejected": "This approach doesn't scale. A generic type with N parameters would need infinite overloads to cover all cases.",
            "reason_category": "complexity"
        },
        {
            "name": "Map/zip operations on TypeVarTuples",
            "description": "Support element-wise type operations on variadic generics, similar to mapped types in TypeScript.",
            "reason_rejected": "Deferred to a future PEP. The complexity of type-level map/zip operations is significant and the use cases need more exploration.",
            "reason_category": "out_of_scope"
        }
    ],
    "objections": [
        {
            "text": "Variadic generics add substantial complexity to the type system for a relatively niche use case (primarily tensor shapes in NumPy/ML).",
            "category": "complexity",
            "source_section": "rationale and rejected ideas"
        }
    ]
})

# ============================================================
# PEP 647 -- User-Defined Type Guards
# ============================================================

save(647, "rejected ideas", {
    "alternatives": [
        {
            "name": "Automatic type narrowing from isinstance patterns",
            "description": "Have type checkers infer type guards automatically from isinstance() and similar patterns without explicit annotations.",
            "reason_rejected": "Already done for isinstance/issubclass, but custom functions with complex logic can't be auto-inferred. TypeGuard fills the gap for user-defined narrowing.",
            "reason_category": "complexity"
        },
        {
            "name": "TypeGuard narrows in both branches",
            "description": "If TypeGuard returns True, narrow to the guarded type; if False, narrow to the complement.",
            "reason_rejected": "The negative case is not always safe. A function might return False for reasons unrelated to type. This was later revisited in PEP 742 (TypeIs) with stricter semantics.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 649 -- Deferred Evaluation Of Annotations
# ============================================================

save(649, "backwards compatibility with pep 563 semantics", {
    "alternatives": [
        {
            "name": "Make PEP 563 (stringified annotations) the default",
            "description": "Proceed with PEP 563's plan to make 'from __future__ import annotations' the default behavior, stringifying all annotations.",
            "reason_rejected": "PEP 563's stringification broke runtime introspection for many libraries (dataclasses, attrs, Pydantic, FastAPI). The backward compatibility cost was too high.",
            "reason_category": "backward_compat"
        },
        {
            "name": "Keep current eager evaluation",
            "description": "Don't change annotation evaluation semantics at all, keep evaluating at function definition time.",
            "reason_rejected": "Forward reference problems remain unsolved. Annotations that reference not-yet-defined names continue to require awkward string quoting.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "Deferred evaluation changes the semantics of __annotations__ from a simple dict of evaluated objects to a more complex lazy-evaluation mechanism.",
            "category": "complexity",
            "source_section": "backwards compatibility with pep 563 semantics"
        },
        {
            "text": "Libraries that access __annotations__ directly (rather than via get_type_hints) may need to update their code.",
            "category": "backward_compat",
            "source_section": "backwards compatibility with stock semantics"
        }
    ]
})

# ============================================================
# PEP 655 -- Marking individual TypedDict items as required or not-required
# ============================================================

save(655, "rejected ideas", {
    "alternatives": [
        {
            "name": "Use total=True/False with per-key overrides",
            "description": "Keep the existing total parameter but add per-key override markers inline.",
            "reason_rejected": "The total parameter already provides a default, but mixing it with per-key overrides in the same class creates confusing interactions.",
            "reason_category": "ambiguity"
        },
        {
            "name": "Use Optional[] for not-required keys",
            "description": "Reuse Optional[T] to mean 'this key may be absent' in TypedDict.",
            "reason_rejected": "Optional means 'T or None', not 'key may be absent'. Conflating the two loses the distinction between a key that's present with value None and a key that's missing.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 673 -- Self Type
# ============================================================

save(673, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use TypeVar bound to the class",
            "description": "Define T = TypeVar('T', bound='MyClass') and use it as the return type for methods that return self.",
            "reason_rejected": "Requires boilerplate TypeVar declaration for every class. Self is a common enough pattern to warrant dedicated syntax.",
            "reason_category": "complexity"
        },
        {
            "name": "Implicit Self inference",
            "description": "Let type checkers automatically infer Self return types for methods that return self.",
            "reason_rejected": "Not all methods returning self should be typed as Self (some might return a fixed base class). Explicit is better than implicit.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 675 -- Arbitrary Literal String Type
# ============================================================

save(675, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use Literal type with all possible values",
            "description": "Use Literal['value1', 'value2', ...] to enumerate all safe string values.",
            "reason_rejected": "Impractical for SQL queries, file paths, and other domains where the set of valid strings is unbounded. LiteralString captures the safety property (developer-written, not user-provided) without enumeration.",
            "reason_category": "complexity"
        },
        {
            "name": "Mark tainted strings instead of safe ones",
            "description": "Use a Tainted[str] type to mark user-provided strings rather than marking safe ones.",
            "reason_rejected": "Inverting the marking creates a larger annotation burden since most strings in a typical program are safe. Marking the safe case with LiteralString is more ergonomic.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "LiteralString's safety guarantees are limited -- string concatenation of two LiteralStrings is still LiteralString, but f-strings with non-literal parts are not.",
            "category": "ambiguity",
            "source_section": "rejected alternatives"
        }
    ]
})

# ============================================================
# PEP 681 -- Data Class Transforms
# ============================================================

save(681, "rejected ideas", {
    "alternatives": [
        {
            "name": "Require libraries to use dataclass directly",
            "description": "Instead of dataclass_transform, require all dataclass-like libraries (attrs, Pydantic) to use @dataclass internally.",
            "reason_rejected": "These libraries have different semantics and features that don't map cleanly to @dataclass. Forcing them into that mold would limit their functionality.",
            "reason_category": "precedent_conflict"
        },
        {
            "name": "Per-library type checker plugins",
            "description": "Let each library maintain its own type checker plugin (mypy plugin, pyright plugin) for special handling.",
            "reason_rejected": "Plugins are fragile, hard to maintain across type checker versions, and create an uneven experience. A standard decorator provides a stable interface.",
            "reason_category": "complexity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 692 -- Using TypedDict for **kwargs typing
# ============================================================

save(692, "rejected ideas", {
    "alternatives": [
        {
            "name": "Use individual keyword argument annotations",
            "description": "Type each **kwargs key individually using some inline syntax.",
            "reason_rejected": "No clean syntax exists for annotating individual keys in **kwargs. TypedDict already provides per-key typing and is well understood.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "Using TypedDict for **kwargs blurs the line between dictionary types and function signatures, which may confuse users.",
            "category": "ambiguity",
            "source_section": "rejected ideas"
        }
    ]
})

# ============================================================
# PEP 695 -- Type Parameter Syntax
# ============================================================

save(695, "rejected ideas", {
    "alternatives": [
        {
            "name": "Keep TypeVar/ParamSpec/TypeVarTuple as-is",
            "description": "Continue using the existing TypeVar('T'), ParamSpec('P') syntax without new language syntax.",
            "reason_rejected": "The existing syntax requires redundant name repetition (T = TypeVar('T')), is verbose for simple cases, and doesn't support scoping type variables to their usage site.",
            "reason_category": "complexity"
        },
        {
            "name": "Use angle brackets for type parameters",
            "description": "Use class Foo<T>: syntax similar to Java/C#/TypeScript.",
            "reason_rejected": "Angle brackets conflict with comparison operators in Python's grammar. The [T] syntax in class Foo[T]: is unambiguous and consistent with subscription syntax.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": [
        {
            "text": "New syntax for something already expressible adds learning cost and creates two ways to do the same thing during a long transition period.",
            "category": "complexity",
            "source_section": "rejected ideas"
        }
    ]
})

# ============================================================
# PEP 698 -- @override decorator
# ============================================================

save(698, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use comments or naming conventions",
            "description": "Mark overrides with comments like # override or naming conventions.",
            "reason_rejected": "Comments aren't checkable by type checkers. A decorator provides a machine-verifiable contract that the method actually overrides something in a parent class.",
            "reason_category": "ambiguity"
        },
        {
            "name": "Implicit override detection",
            "description": "Let type checkers automatically detect overrides by comparing method names with parent classes.",
            "reason_rejected": "Accidental overrides (naming collisions) would go undetected. Explicit @override makes the intent clear and catches cases where the parent method is removed or renamed.",
            "reason_category": "ambiguity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 702 -- Marking deprecations using the type system
# ============================================================

save(702, "rejected ideas", {
    "alternatives": [
        {
            "name": "Use runtime warnings.warn only",
            "description": "Continue using only runtime DeprecationWarning via warnings.warn() without type-level support.",
            "reason_rejected": "Runtime warnings are only triggered when deprecated code actually executes. Type-level deprecation catches usage at analysis time, before the code runs.",
            "reason_category": "out_of_scope"
        }
    ],
    "objections": [
        {
            "text": "Adding deprecation to the type system mixes runtime lifecycle concerns with static type information.",
            "category": "precedent_conflict",
            "source_section": "rejected ideas"
        }
    ]
})

# ============================================================
# PEP 705 -- TypedDict: Read-only Items
# ============================================================

save(705, "rejected alternatives", {
    "alternatives": [
        {
            "name": "Use Final for read-only TypedDict items",
            "description": "Reuse Final[] to mark TypedDict items as read-only.",
            "reason_rejected": "Final means 'cannot be reassigned' in variable context, but TypedDict items aren't variables. ReadOnly is a clearer semantic for dict items that shouldn't be modified.",
            "reason_category": "ambiguity"
        },
        {
            "name": "Immutable TypedDict variant",
            "description": "Create a FrozenTypedDict that makes all items read-only at once.",
            "reason_rejected": "Per-item control is more flexible. Some items may need to be mutable while others are read-only in the same dict type.",
            "reason_category": "complexity"
        }
    ],
    "objections": []
})

# ============================================================
# PEP 742 -- Narrowing types with TypeIs
# ============================================================

save(742, "rejected ideas", {
    "alternatives": [
        {
            "name": "Fix TypeGuard to narrow in both branches",
            "description": "Modify the existing TypeGuard (PEP 647) to also narrow the type in the else branch instead of introducing a new form.",
            "reason_rejected": "Changing TypeGuard's semantics would break existing code that relies on the current one-sided narrowing behavior. A new form (TypeIs) with stricter requirements is safer.",
            "reason_category": "backward_compat"
        },
        {
            "name": "Add a flag to TypeGuard",
            "description": "Add a parameter like TypeGuard[X, narrow_negative=True] to opt into both-branch narrowing.",
            "reason_rejected": "Parameterized behavior on a type form is unusual in Python's type system and harder for type checkers to implement consistently.",
            "reason_category": "complexity"
        }
    ],
    "objections": [
        {
            "text": "TypeIs and TypeGuard are easy to confuse. Having two similar but subtly different type narrowing mechanisms increases cognitive load.",
            "category": "complexity",
            "source_section": "rejected ideas"
        }
    ]
})

# ============================================================
# PEP 696 -- Type defaults for TypeVarLikes
# ============================================================

save(696, "rejected_alternatives", {
    "alternatives": [
        {
            "name": "Use overloads instead of defaults",
            "description": "Define overloads for each combination of provided and omitted type parameters.",
            "reason_rejected": "Combinatorial explosion -- a generic with 3 parameters each with a default would need 8 overloads. Defaults are a more scalable solution.",
            "reason_category": "complexity"
        }
    ],
    "objections": []
})


print("\nDone. Cache files written to extraction_cache/")
