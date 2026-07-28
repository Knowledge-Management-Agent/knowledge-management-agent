"""Evaluation harness for the Knowledge Management Agent PoC.

Measures the three success metrics from the scope doc against the
curated corpus/question set in this directory:
  - Retrieval accuracy: expected source appears in top-3 retrieved chunks
  - Response grounding: LLM-as-judge check that the answer is supported
    by the retrieved context (an automated approximation, not a
    human-verified guarantee -- see plan.md §4)
  - Latency: end-to-end query time against the 8s target

Usage (from backend/.venv, with the backend package importable):
    cd backend
    .venv/Scripts/python -m eval.run_eval
Or, with the API server running:
    python eval/run_eval.py --via-api
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

RETRIEVAL_TARGET = 0.85
GROUNDING_TARGET = 0.90
LATENCY_TARGET_MS = 8000


def load_questions() -> list[dict]:
    questions = []
    with open(EVAL_DIR / "questions.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def ingest_corpus():
    from app.ingestion.loader import IngestionService

    service = IngestionService()
    corpus_dir = EVAL_DIR / "corpus"
    results = []
    for path in sorted(corpus_dir.glob("*")):
        if path.is_file():
            results.append(service.ingest_file(path, source_label=path.name))
    return results


def judge_grounding(llm, context: str, answer: str) -> bool:
    from app.rag.prompts import GROUNDING_JUDGE_SYSTEM, GROUNDING_JUDGE_TEMPLATE

    verdict = llm.generate(
        GROUNDING_JUDGE_TEMPLATE.format(context=context, answer=answer),
        system=GROUNDING_JUDGE_SYSTEM,
    )
    return "GROUNDED" in verdict.upper() and "UNGROUNDED" not in verdict.upper()


def run(reingest: bool) -> None:
    from app.llm.factory import get_llm_client
    from app.rag.prompts import format_context
    from app.rag.qa import answer_question
    from app.rag.retriever import Retriever
    from app.rag.store import get_store

    if reingest:
        print("Ingesting eval corpus...")
        for r in ingest_corpus():
            print(f"  {r['source']}: {r['chunks_ingested']} chunks")

    store = get_store()
    print(f"\nVector store now holds {store.count()} chunks.\n")

    retriever = Retriever()
    llm = get_llm_client()
    questions = load_questions()

    retrieval_hits = 0
    grounded_hits = 0
    latencies = []
    rows = []

    for q in questions:
        chunks = retriever.retrieve(q["query"], top_k=3)
        retrieved_sources = {c.source for c in chunks}
        hit = bool(retrieved_sources & set(q["expected_sources"]))
        retrieval_hits += int(hit)

        result = answer_question(q["query"], top_k=5)
        latencies.append(result["timings_ms"]["total"])

        context = format_context(retriever.retrieve(q["query"], top_k=5))
        grounded = judge_grounding(llm, context, result["answer"])
        grounded_hits += int(grounded)

        rows.append(
            {
                "query": q["query"],
                "expected_sources": q["expected_sources"],
                "retrieved_sources": sorted(retrieved_sources),
                "retrieval_hit": hit,
                "grounded": grounded,
                "latency_ms": result["timings_ms"]["total"],
            }
        )

    n = len(questions)
    retrieval_accuracy = retrieval_hits / n if n else 0
    grounding_rate = grounded_hits / n if n else 0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 1 else (latencies[0] if latencies else 0)

    print("Per-question results:")
    for r in rows:
        status = "OK" if r["retrieval_hit"] else "MISS"
        grounded_status = "grounded" if r["grounded"] else "UNGROUNDED"
        print(
            f"  [{status:4}] [{grounded_status:10}] {r['latency_ms']:7.1f}ms  {r['query']}"
        )

    print("\n=== Summary vs. scope doc targets ===")
    _print_metric(
        "Retrieval accuracy (top-3)", retrieval_accuracy, RETRIEVAL_TARGET, pct=True
    )
    _print_metric(
        "Response grounding (LLM-judge approx.)", grounding_rate, GROUNDING_TARGET, pct=True
    )
    _print_metric(
        "p95 end-to-end latency", p95_latency, LATENCY_TARGET_MS, pct=False, lower_is_better=True
    )


def _print_metric(name, value, target, pct, lower_is_better=False):
    if pct:
        passed = value >= target
        print(f"{name}: {value:.0%} (target >= {target:.0%}) -> {'PASS' if passed else 'FAIL'}")
    else:
        passed = value <= target if lower_is_better else value >= target
        cmp = "<=" if lower_is_better else ">="
        print(f"{name}: {value:.0f}ms (target {cmp} {target:.0f}ms) -> {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-reingest",
        action="store_true",
        help="Skip re-ingesting eval/corpus/ (use if already ingested into the store)",
    )
    args = parser.parse_args()
    run(reingest=not args.no_reingest)
