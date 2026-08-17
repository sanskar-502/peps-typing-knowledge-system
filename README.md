# Python Typing PEP Knowledge System

A knowledge system that models the design history of Python's type system across 29 PEPs (484-742). Rather than just storing PEP text, it builds a structured graph of proposals, concepts, objections, and rejected alternatives -- then reasons over that graph when you describe a new feature idea.

Give it a feature proposal in plain English, and it returns a structured report: what's been tried before, what objections were raised, and where friction is likely to come from.

## Architecture

```
Raw PEP corpus  -->  Extraction pipeline  -->  Knowledge State (JSON)
(.rst files,         (deterministic +           (committed to repo,
 cloned repo)         constrained-LLM)           inspectable)
                                                       |
                     OFFLINE, ONE-TIME                 |  loaded at
                     needs ANTHROPIC_API_KEY            |  query time
                                                       v
                                                Reasoning engine
                                                (local graph traversal
                                                 + scoring)
                                                       |
                                                       v
                                                CLI: new input -->
                                                structured report
```

The LLM is used once, offline, during knowledge base construction -- and only as a classifier into categories we defined. Query-time reasoning is fully local. No API key needed to run the CLI.

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Query the knowledge system (no API key needed)

The knowledge state ships pre-built. Just run:

```bash
python query.py "Should Python support a shorthand for defining a Protocol inline, without writing a full class definition?"
```

For JSON output:

```bash
python query.py --format json "What about lazy evaluation of type annotations?"
```

### Regenerate the knowledge state (optional)

Only needed if you want to re-run the extraction pipeline:

```bash
# set your API key for the constrained-classification step
export ANTHROPIC_API_KEY=your-key-here

# run the full pipeline
python -m src.build_kb --peps-dir data/peps

# or skip the LLM step and build from deterministic extraction only
python -m src.build_kb --peps-dir data/peps --skip-llm
```

### Run tests

```bash
pytest tests/ -v
```

## Repo Structure

```
peps-typing-knowledge-system/
├── README.md                       # you're here
├── approach.md                     # design reasoning (read this first)
├── requirements.txt
├── query.py                        # CLI entry point
├── knowledge_state.json            # the knowledge graph (mandatory deliverable)
├── data/
│   └── peps/                       # filtered PEP .rst files
├── src/
│   ├── ontology.py                 # entity/relationship definitions -- the core
│   ├── extract_deterministic.py    # header parsing, regex, concept matching
│   ├── extract_classified.py       # constrained-LLM classification + caching
│   ├── build_kb.py                 # orchestrates extraction --> graph
│   └── reasoning.py                # query-time reasoning (no API key)
├── extraction_cache/               # cached LLM outputs (committed)
├── gold_set/
│   ├── gold_set.json               # hand-labeled evaluation data
│   └── evaluate.py                 # precision/recall harness
└── tests/
    └── test_reasoning.py
```

## Scope

This system covers 29 PEPs spanning the evolution of Python's type system, from the foundational PEP 483 (Theory of Type Hints) through PEP 742 (TypeIs). The subset was chosen because these PEPs form a genuine evolving system with rich internal cross-referencing, not a pile of unrelated proposals. See `approach.md` for the full reasoning.
