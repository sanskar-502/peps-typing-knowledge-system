"""
Gold-set evaluation -- compares pipeline extraction against hand-labeled ground truth.

This is the part that proves we understand our own pipeline's limits rather than
trusting it blindly. Run after extraction to get precision/recall numbers.

Usage:
    python -m gold_set.evaluate
"""

import json
from pathlib import Path
from collections import defaultdict


GOLD_SET_PATH = Path(__file__).parent / "gold_set.json"
EXTRACTION_CACHE_DIR = Path(__file__).parent.parent / "extraction_cache"


def load_gold_set() -> dict:
    """Load the hand-labeled gold set."""
    with open(GOLD_SET_PATH, "r") as f:
        return json.load(f)


def load_extracted(pep_number: int) -> dict:
    """Load the extraction cache for a PEP.
    Merges all cached sections for that PEP."""
    merged = {"alternatives": [], "objections": []}
    cache_dir = EXTRACTION_CACHE_DIR

    if not cache_dir.exists():
        return merged

    for cache_file in cache_dir.glob(f"pep_{pep_number}_*.json"):
        with open(cache_file, "r") as f:
            data = json.load(f)
            merged["alternatives"].extend(data.get("alternatives", []))
            merged["objections"].extend(data.get("objections", []))

    return merged


def compute_metrics(gold_items: list, extracted_items: list,
                    match_key: str = "name") -> dict:
    """Compute precision, recall, F1 for a set of items.

    Matching is done on the match_key field, case-insensitive substring match.
    This is intentionally lenient -- we care more about whether the pipeline
    found the right things than whether it phrased them identically.
    """
    if not gold_items and not extracted_items:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0,
                "true_pos": 0, "false_pos": 0, "false_neg": 0}

    gold_names = [item[match_key].lower().strip() for item in gold_items]
    extracted_names = [item.get(match_key, "").lower().strip() for item in extracted_items]

    true_pos = 0
    matched_gold = set()

    for ext_name in extracted_names:
        for i, gold_name in enumerate(gold_names):
            if i in matched_gold:
                continue
            # substring match in either direction
            if gold_name in ext_name or ext_name in gold_name:
                true_pos += 1
                matched_gold.add(i)
                break

    false_pos = len(extracted_names) - true_pos
    false_neg = len(gold_names) - true_pos

    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_pos": true_pos,
        "false_pos": false_pos,
        "false_neg": false_neg,
    }


def evaluate():
    """Run evaluation and print results."""
    gold = load_gold_set()

    print("Gold-set Evaluation")
    print("=" * 60)

    overall_alt_metrics = defaultdict(int)
    overall_obj_metrics = defaultdict(int)

    for pep_entry in gold.get("peps", []):
        pep_num = pep_entry["pep_number"]
        extracted = load_extracted(pep_num)

        alt_metrics = compute_metrics(
            pep_entry.get("alternatives", []),
            extracted.get("alternatives", []),
            match_key="name"
        )
        obj_metrics = compute_metrics(
            pep_entry.get("objections", []),
            extracted.get("objections", []),
            match_key="text"
        )

        print(f"\nPEP {pep_num}:")
        print(f"  Alternatives -- P: {alt_metrics['precision']:.3f}  "
              f"R: {alt_metrics['recall']:.3f}  F1: {alt_metrics['f1']:.3f}  "
              f"(TP={alt_metrics['true_pos']} FP={alt_metrics['false_pos']} "
              f"FN={alt_metrics['false_neg']})")
        print(f"  Objections   -- P: {obj_metrics['precision']:.3f}  "
              f"R: {obj_metrics['recall']:.3f}  F1: {obj_metrics['f1']:.3f}  "
              f"(TP={obj_metrics['true_pos']} FP={obj_metrics['false_pos']} "
              f"FN={obj_metrics['false_neg']})")

        for key in ["true_pos", "false_pos", "false_neg"]:
            overall_alt_metrics[key] += alt_metrics[key]
            overall_obj_metrics[key] += obj_metrics[key]

    # overall
    print("\n" + "=" * 60)
    print("Overall:")
    for label, metrics in [("Alternatives", overall_alt_metrics),
                           ("Objections", overall_obj_metrics)]:
        tp = metrics["true_pos"]
        fp = metrics["false_pos"]
        fn = metrics["false_neg"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        print(f"  {label:15s} -- P: {p:.3f}  R: {r:.3f}  F1: {f1:.3f}")


if __name__ == "__main__":
    evaluate()
