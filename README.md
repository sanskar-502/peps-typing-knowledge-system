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
                     needs GEMINI_API_KEY               |  query time
                                                       v
                                                Reasoning engine
                                                (local graph traversal
                                                 + scoring)
                                                       |
                                                       v
                                                CLI: new input -->
                                                structured report
```

The LLM (Gemini 3.6 Flash, free tier) is used once, offline, during knowledge base construction -- and only as a constrained classifier that slots text into categories we defined. It never decides what entities or relationships exist. Query-time reasoning is fully local graph traversal. No API key needed to run the CLI.

## Quick Start

### 1. Set up the environment

```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Query the knowledge system (no API key needed)

The knowledge state ships pre-built. Just run:

```bash
python query.py "Should Python support a shorthand for defining a Protocol inline, without writing a full class definition?"
```

For JSON output:

```bash
python query.py --format json "What about lazy evaluation of type annotations?"
```

### 4. Regenerate the knowledge state (optional)

Only needed if you want to re-run the extraction pipeline from scratch:

```bash
# set your API key for the constrained-classification step
# Windows (PowerShell):
$env:GEMINI_API_KEY="your-key-here"
# macOS/Linux:
export GEMINI_API_KEY=your-key-here

# run the full pipeline
python -m src.build_kb --peps-dir data/peps
```

Without an API key, the pipeline still works -- it uses cached results for all sections that were previously classified, and skips the LLM step for any uncached sections. The pre-committed cache covers all 29 PEPs.

### 5. Run tests

```bash
python -m pytest tests/test_reasoning.py -v
```

### 6. Run gold-set evaluation

```bash
python -m gold_set.evaluate
```

## How the Extraction Pipeline Works

The pipeline runs in three phases, each building on the previous one:

### Phase 1: Deterministic Extraction

Parses PEP `.rst` files using regex and keyword matching. Extracts:
- **Header fields** (PEP number, title, author, status, type, requires, superseded-by)
- **Cross-references** (every `PEP NNN` and `:pep:\`NNN\`` mention, tagged by which section it appears in)
- **Section segmentation** (splits the body into top-level RST sections)
- **Concept matching** (maps each PEP to a taxonomy of 17 typing concepts via keyword rules)

This phase produces ~87% of all edges in the final graph and requires zero external dependencies.

### Phase 2: Constrained Classification

For sections that are too unstructured for regex (mainly "Rejected Ideas" and "Backwards Compatibility"), we use the Gemini API as a constrained classifier:
- The LLM receives a fixed Pydantic schema with an enum we defined (`ObjectionCategory`)
- It classifies text into pre-defined categories: `performance`, `backward_compat`, `complexity`, `ambiguity`, `precedent_conflict`, `out_of_scope`
- Two worked examples in the prompt anchor the expected output format
- Results are cached to disk so the API is called at most once per section

### Phase 3: Graph Assembly

Merges deterministic and classified extractions into a single `networkx.MultiDiGraph`:
- Guards against edges pointing to PEPs outside our 29-PEP scope
- Adds hand-tagged `resembles` edges linking rejected alternatives to PEPs that later shipped similar ideas
- Validates graph integrity (orphan nodes, dangling edges, type distribution)
- Exports to `knowledge_state.json` and `knowledge_state.graphml`

## Knowledge Graph Statistics

| Metric | Count |
|---|---|
| Total nodes | 144 |
| Total edges | 545 |
| Proposals (PEPs) | 29 |
| Authors | 30 |
| Concepts | 17 |
| Rejected alternatives | 46 |
| Objections | 22 |

**Edge types:** `authored_by` (51), `relates_to_concept` (306), `references` (115), `considers_and_rejects` (46), `raises` (22), `supersedes` (2), `resembles` (3)

## How the Reasoning Engine Works

When a new input arrives (a developer describing a feature idea), the engine:

1. **Maps the input to concepts** using the same keyword matcher from Phase 1
2. **Retrieves candidates** from the graph: all Proposal and Alternative nodes linked to matched concepts
3. **Ranks candidates** by a weighted score combining concept overlap (strongest signal), evidence richness (how many objections/alternatives that PEP has), and graph degree (how connected the PEP is)
4. **Pulls evidence** for top-ranked candidates: their Objection and Alternative nodes with rejection reasons and categories
5. **Aggregates friction points** across the evidence set to predict where resistance is likely
6. **Formats** a structured report (text or JSON) with precedents, evidence, and friction predictions

The engine runs entirely on local graph traversal. No network calls, no API keys, no token costs.

## Evaluation

We built a hand-labeled gold set covering 8 PEPs (stratified across statuses) and measure precision, recall, and F1 against the extraction pipeline output:

| Metric | Alternatives | Objections |
|---|---|---|
| Precision | 0.957 | 0.765 |
| Recall | 0.957 | 0.765 |
| F1 | 0.957 | 0.765 |

Failure cases and their root causes are documented in `approach.md`. The remaining mismatches are substring-matching artifacts, not extraction errors -- a human reviewer would rate the pipeline's actual quality higher than these numbers suggest.

Run the evaluation yourself:

```bash
python -m gold_set.evaluate
```

## Repo Structure

```
peps-typing-knowledge-system/
├── README.md                       # this file
├── approach.md                     # design reasoning and evaluation (read this)
├── requirements.txt                # python dependencies
├── query.py                        # CLI entry point
├── knowledge_state.json            # the knowledge graph (mandatory deliverable)
├── knowledge_state.graphml         # graph visualization export
├── data/
│   └── peps/                       # 29 filtered PEP .rst source files
├── src/
│   ├── __init__.py
│   ├── ontology.py                 # entity/relationship definitions (the core)
│   ├── extract_deterministic.py    # header parsing, regex, concept matching
│   ├── extract_classified.py       # constrained-LLM classification + caching
│   ├── build_kb.py                 # orchestrates extraction --> graph
│   └── reasoning.py                # query-time reasoning engine (no API key)
├── extraction_cache/               # cached LLM classification outputs (committed)
├── gold_set/
│   ├── gold_set.json               # hand-labeled evaluation data (8 PEPs)
│   └── evaluate.py                 # precision/recall evaluation harness
├── scripts/
│   └── generate_cache.py           # utility for writing extraction cache files
└── tests/
    └── test_reasoning.py           # unit tests for the reasoning engine
```

## Scope

This system covers 29 PEPs spanning the evolution of Python's type system, from the foundational PEP 483 (Theory of Type Hints, 2014) through PEP 742 (TypeIs, 2024). The subset was chosen because these PEPs form a genuine evolving system with rich internal cross-referencing:

- PEP 563 was accepted, had its Python 3.10 default walked back, and was later superseded by PEP 649
- PEP 647 (TypeGuard) had limitations that PEP 742 (TypeIs) later addressed
- Rejected alternatives in early PEPs (like PEP 484's angle brackets) foreshadowed design choices in later PEPs (like PEP 695's type parameter syntax)

These are not isolated proposals -- they are a connected design conversation, and the `resembles` edges in the graph make that conversation explicit. See `approach.md` for the full reasoning behind scope selection and every other design decision.

## Design Decisions

Key choices explained (details in `approach.md`):

- **Why MultiDiGraph:** PEPs can have multiple relationships to the same target (e.g., both `references` and `supersedes`). A regular DiGraph would silently overwrite edges.
- **Why keyword matching over NLP:** Keeps the system fully deterministic, explainable, and dependency-light. The PEP corpus uses consistent terminology that keyword rules handle well.
- **Why cache extraction results:** Ensures reproducibility. The same build command produces the same graph regardless of API availability.
- **Why hand-tag resembles edges:** These are the highest-value edges in the graph (linking a rejected idea to a PEP that later shipped it). Automating this reliably would require semantic understanding we can't guarantee.
