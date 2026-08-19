# Approach

This document explains the design decisions behind the typing PEP knowledge system. It's structured as: what we chose, why we chose it, and what we deliberately left out.

## 1. Scope: Why These PEPs

We focus on 29 PEPs covering Python's type system evolution, from PEP 483 (Theory of Type Hints, 2014) through PEP 742 (TypeIs, 2024). This is not an arbitrary slice -- it's a self-contained design saga with a clear narrative arc.

The typing subset is ideal for this assignment because:

- **It's a genuine evolving system.** Protocols (PEP 544) build on structural subtyping absent from PEP 484. `X | Y` syntax (PEP 604) simplifies `Union` from 484. PEP 563 was accepted, had its 3.10 default walked back, and was effectively superseded by PEP 649 years later. These aren't isolated proposals -- they're a connected design conversation.

- **The source data contains explicit reasoning.** PEPs have Motivation, Rationale, Rejected Ideas, and Backwards Compatibility sections. The argumentative structure is already semi-present in the documents -- our job is to formalize it, not hallucinate it.

- **The scale is right.** 29 PEPs is deep enough to build real relationships and shallow enough to hand-verify everything. The assignment explicitly values depth over breadth.

The PEP 563/649 arc is particularly valuable: it's a built-in demonstration of a feature that was tried (postponed evaluation), found to have unexpected consequences, and then revisited with a fundamentally different approach (deferred evaluation). This maps directly to the assignment's example query -- "has this been proposed before, and what happened?"

## 2. Ontology: What We Model and Why

The ontology was designed before any extraction code was written. Every entity and relationship type exists for a specific reason.

### Entities

| Entity | Why it exists |
|---|---|
| **Proposal** | The core unit. A PEP document with its header metadata. Most attributes come directly from structured header fields. |
| **Person** | Authorship matters for tracking who's involved in which design decisions, but we keep it minimal -- name only, no biographical data. |
| **Concept** | The abstraction layer that makes the graph more than a citation list. PEP 604 doesn't cite PEP 484's Union discussion by number, but they share the "Union Types" concept. That connection only exists because we modeled it as a first-class entity with hand-curated keywords. |
| **Objection** | An objection or concern raised in a PEP's discussion, categorized into one of six types we defined. |
| **Alternative** | A design alternative that was considered and rejected, with a classified rejection reason. |

**Why is Concept a first-class entity instead of just a tag?** Because concepts connect proposals across time in ways the PEPs' own cross-references don't capture. A tag is a flat label; an entity with edges lets us traverse from one PEP to another through shared abstractions.

**Why separate Objection from Alternative?** An objection can be raised against the main proposal itself, not just against a rejected alternative. Collapsing them loses that distinction and flattens the reasoning structure.

**What we deliberately did not model:** Individual mailing-list posts. The PEPs reference discussion threads via Post-History links, but modeling each post as an entity would create a shallow web of low-value nodes. We treat those links as evidence pointers, not first-class entities.

### Relationships

| Relationship | From -> To | How it's found |
|---|---|---|
| `supersedes` | Proposal -> Proposal | `Superseded-By` / `Replaces` header (deterministic) |
| `requires` | Proposal -> Proposal | `Requires` header (deterministic) |
| `authored_by` | Proposal -> Person | `Author` header (deterministic) |
| `references` | Proposal -> Proposal | Regex `PEP \d+` in body, tagged with source section |
| `relates_to_concept` | Proposal -> Concept | Keyword match against hand-curated concept list |
| `raises` | Proposal -> Objection | Constrained-LLM classification |
| `considers_and_rejects` | Proposal -> Alternative | Constrained-LLM classification |
| `resembles` | Alternative -> Proposal | Manual (hand-tagged) |

The `resembles` relationship is the most valuable edge type in the schema: it captures when a rejected alternative in an older PEP closely resembles what a later PEP actually shipped. PEP 563's rejected ideas vs. PEP 649's design is the flagship example.

## 3. Extraction Pipeline

The pipeline has two distinct phases, and the split is deliberate.

### Phase 1: Deterministic Extraction

Everything that can be extracted without inference:
- RFC-822-style PEP headers -> `Proposal` nodes, `supersedes`/`requires`/`authored_by` edges
- `PEP \d+` regex over body text -> `references` edges, tagged with which section they appeared in (a mention in Rejected Ideas is a stronger signal than one in the bibliography)
- Keyword/synonym matching against our hand-curated concept list -> `relates_to_concept` edges

This phase alone produces the majority of edges in the final graph, with zero inference risk. That's a deliberate architectural choice: the more of the graph that comes from deterministic parsing, the more trustworthy and explainable the whole system is.

### Phase 2: Constrained Classification

For sections that are too unstructured for regex (mainly Rejected Ideas and Backwards Compatibility), we use the Gemini API (gemini-3.6-flash, free tier) as a classifier. Critically:

- The LLM receives a fixed Pydantic schema with an enum we defined (`ObjectionCategory`)
- It's never asked "what are the entities here" -- it's asked "does this text contain instances of `Alternative` as I've defined it, and which of these six categories does the rejection reason fall into"
- Worked examples are provided in the prompt
- Every response is cached to disk and manually reviewed

**This does not violate the "no auto-extraction tools" constraint.** The entity definitions, the relationship schema, the category taxonomy, and the concept list are all ours. The LLM is used the way a fuzzy regex would be used -- to slot known text into categories we already fixed. It never has authority to invent entities or relationships.

## 4. Gold-Set Evaluation

To prove we understand our pipeline's limits rather than trusting it blindly:

1. We selected 8-10 PEPs stratified across statuses (accepted, withdrawn, superseded)
2. Read their Rejected Ideas / Backwards Compatibility sections by hand
3. Wrote down what we believe the correct `Alternative` and `Objection` entities are
4. Ran the pipeline on those same PEPs
5. Computed precision/recall against our own gold set

Results and concrete failure cases are reported in the evaluation section below.

### Evaluation Results

We evaluated 8 PEPs stratified across statuses (4 Final, 1 Superseded, 3 others):

| Metric | Alternatives | Objections |
|---|---|---|
| Overall Precision | 0.957 | 0.765 |
| Overall Recall | 0.957 | 0.765 |
| Overall F1 | 0.957 | 0.765 |

Alternatives extraction is strong (F1 = 0.957) because rejected alternatives are typically well-delineated in PEP text with clear names and reasons. Objection extraction is solid (F1 = 0.765) after expanding coverage to backwards-compatibility sections via Gemini classification.

Individual PEP results show perfect scores (F1 = 1.0) for PEPs 544, 589, 647, 649, and 742. The weakest scores are on PEP 484 and PEP 563 (objection substring mismatches) and PEP 695 (objection phrasing gap).

### Failure Cases

**PEP 484, objection matching (P = 0.5):** The gold label "Runtime performance concerns from annotation evaluation" failed to match the extracted "Runtime performance concerns -- annotations are evaluated at function definition time, adding overhead." The substring match fails because the gold label uses "from" while the extraction uses a dash. Both describe the same concern.

**PEP 563, objection matching (P = 0.5):** Two of the four gold set objections fail to match because the extracted text uses longer, more specific phrasing. For example, the gold label "The from \_\_future\_\_ import annotations mechanism creates confusing behavior" partially matches, but two other gold-to-extraction pairs diverge too far for substring matching.

**PEP 695, objection matching (F1 = 0.0):** The gold label used "two ways to do the same thing" while the extracted objection used "learning cost" and "transition period." Both describe the same concern (duplicate syntax during migration), but the surface text overlap is too low for substring matching. A semantic similarity approach would handle this, but we deliberately avoided introducing one to keep the evaluation fully deterministic.

These failures are instructive: they tell us that an exact-match evaluation underestimates the pipeline's real performance on objection extraction, and that a human reviewer would likely rate the actual quality higher than the numbers suggest.

## 5. Reasoning Engine

When a new input arrives (a developer describing a feature idea), the system:

1. **Maps the input to concepts** using the same keyword matcher from Phase 1. This reuses code, keeps the system explainable, and means the demo doesn't depend on API availability.

2. **Retrieves candidates** from the graph: all `Proposal` and `Alternative` nodes linked to the matched concepts.

3. **Ranks candidates** by a weighted score combining concept overlap (strongest signal), evidence richness (how many objections/alternatives that PEP has), and graph degree (how connected/central the PEP is).

4. **Pulls evidence** for top-ranked candidates: their typed `Objection` and `Alternative` nodes.

5. **Aggregates friction points**: counts objection categories across the evidence set to predict where resistance is likely.

6. **Formats** a structured report -- not prose, not a summary, but a specific breakdown of precedents, evidence, and predicted friction.

### Worked Example

Input: *"Should Python support a shorthand for defining a Protocol inline, without writing a full class definition -- similar to how TypedDict has a functional syntax?"*

The system matches concepts "Structural Subtyping" and "Alternative Syntax Forms," retrieves PEP 544 (Protocols) and PEP 589 (TypedDict) as precedents, surfaces the rejected "functional syntax as primary form" alternative from PEP 589 with its ambiguity categorization, and notes that PEP 544 never evaluated a shorthand form. The friction prediction highlights ambiguity concerns based on precedent.

## 6. What We'd Build Next

Given more time, in priority order:

1. **Expand `resembles` edges** beyond the PEP 563/649 pair to 2-3 more cases, hand-justified. This is the highest-insight edge type and there are more instances in the data.

2. **Ingest CPython `python/typing` GitHub issues** as a `DiscussionThread` data source for the most-connected PEPs. This would demonstrate multi-source triangulation -- the same design question discussed in different venues with different participants.

3. **Richer scoring** in the reasoning engine. The current scoring is a simple weighted sum; with more data, we could weight by PEP status (an objection that led to a PEP being withdrawn is stronger evidence than one in an accepted PEP).

4. **Temporal reasoning** -- surfacing how opinions on a concept shifted over time across PEPs, not just what the final positions were.
