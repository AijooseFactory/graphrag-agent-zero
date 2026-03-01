#!/usr/bin/env python3
"""
Baseline Benchmark Runner for GraphRAG Agent Zero
Version: 1.0
Date: 2026-02-27

Runs benchmark questions against baseline (GraphRAG disabled) retrieval.
Collects latency, accuracy, and hallucination metrics.
"""

import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from statistics import mean, quantiles

# Configuration
BENCHMARK_DIR = Path(__file__).parent.parent / "benchmark"
CORPUS_DIR = BENCHMARK_DIR / "corpus"
QUESTIONS_FILE = BENCHMARK_DIR / "benchmark_questions.json"
RESULTS_DIR = Path(__file__).parent.parent / "results"

# Benchmark parameters
WARMUP_RUNS = 1  # Discard first N runs (cache cold start)
SAMPLE_RUNS = 10  # N runs per question for statistics
QUERY_TIMEOUT_MS = 30000  # 30 second timeout


@dataclass
class BenchmarkResult:
    """Single question benchmark result."""
    question_id: str
    category: str
    question: str
    expected_answer: str
    actual_answer: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    citations: list[str] = field(default_factory=list)
    certainty: str = "unknown"
    required_entities_found: list[str] = field(default_factory=list)
    required_sources_found: list[str] = field(default_factory=list)
    forbidden_claims_made: list[str] = field(default_factory=list)
    hallucination_detected: bool = False
    error: str = ""


@dataclass
class BenchmarkReport:
    """Full benchmark report."""
    timestamp: str
    graphrag_enabled: bool
    total_questions: int
    total_runs: int
    warmup_runs: int
    results: list[BenchmarkResult] = field(default_factory=list)
    
    # Aggregated metrics
    accuracy_score: float = 0.0
    provenance_score: float = 0.0
    hallucination_penalty: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_avg_ms: float = 0.0
    
    # Category breakdowns
    category_scores: dict[str, dict] = field(default_factory=dict)


def load_corpus() -> dict[str, str]:
    """Load all corpus documents into memory."""
    corpus = {}
    for doc_path in CORPUS_DIR.glob("*.md"):
        with open(doc_path, "r") as f:
            corpus[doc_path.stem] = f.read()
    print(f"Loaded {len(corpus)} corpus documents")
    return corpus


def load_questions() -> list[dict]:
    """Load benchmark questions."""
    with open(QUESTIONS_FILE, "r") as f:
        data = json.load(f)
    questions = data.get("questions", [])
    print(f"Loaded {len(questions)} benchmark questions")
    return questions


def simple_retrieve(question: str, corpus: dict[str, str], top_k: int = 3) -> list[tuple[str, str, float]]:
    """
    Simple keyword-based retrieval (baseline without embeddings).
    Returns list of (doc_id, content, score) tuples.
    """
    question_lower = question.lower()
    question_words = set(question_lower.split())
    
    # Remove common words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "which", 
                  "who", "when", "where", "how", "why", "does", "did", "do", "to",
                  "for", "of", "and", "or", "in", "on", "at", "by"}
    question_words -= stop_words
    
    scores = []
    for doc_id, content in corpus.items():
        content_lower = content.lower()
        score = sum(1 for word in question_words if word in content_lower)
        if score > 0:
            scores.append((doc_id, content, score))
    
    # Sort by score descending
    scores.sort(key=lambda x: x[2], reverse=True)
    return scores[:top_k]


def extract_citations(text: str) -> list[str]:
    """Extract [DOC-ID] citations from text."""
    import re
    pattern = r'\[([A-Z]+-[0-9]+|[A-Z_]+)\]'
    return re.findall(pattern, text)


def check_entity_found(answer: str, entity: str, corpus: dict[str, str]) -> bool:
    """Check if entity is mentioned in answer or retrieved context."""
    answer_lower = answer.lower()
    entity_lower = entity.lower()
    
    # Check direct mention
    if entity_lower in answer_lower:
        return True
    
    # Check aliases for common entities
    aliases = {
        "gateway": ["edgeproxy", "api gateway"],
        "edgeproxy": ["gateway", "api gateway"],
        "george freeney jr.": ["gfj", "g. freeney jr.", "george freeney", "george"],
        "gfj": ["george freeney jr.", "g. freeney jr.", "george freeney"],
        "alice chen": ["alice"],
    }
    
    for main, alts in aliases.items():
        if entity_lower == main or entity_lower in alts:
            for alt in [main] + alts:
                if alt in answer_lower:
                    return True
    
    return False


def check_source_found(citations: list[str], required_sources: list[str]) -> list[str]:
    """Check which required sources are cited."""
    found = []
    for src in required_sources:
        if src in citations:
            found.append(src)
    return found


def check_forbidden_claims(answer: str, forbidden: list[str]) -> list[str]:
    """Check if answer makes any forbidden claims."""
    answer_lower = answer.lower()
    made = []
    for claim in forbidden:
        if claim.lower() in answer_lower:
            made.append(claim)
    return made


def simulate_llm_response(question: str, context: list[tuple[str, str, float]], 
                          corpus: dict[str, str]) -> tuple[str, list[str], str]:
    """
    Simulate LLM response using retrieved context.
    In production, this would call actual LLM.
    Returns (answer, citations, certainty).
    """
    # For baseline, construct answer from context
    if not context:
        return "I don't have sufficient information to answer this question.", [], "unknown"
    
    # Build context string
    "\n\n".join([f"[{doc_id}] {content[:500]}..." 
                               for doc_id, content, score in context])
    
    # Extract citations
    citations = [doc_id for doc_id, _, _ in context]
    
    # Simple keyword matching for answer construction
    # In production, this would be LLM-generated
    answer_parts = []
    for doc_id, content, score in context:
        if score >= 2:  # High relevance
            answer_parts.append(f"Based on [{doc_id}]: {content[:200]}...")
    
    if answer_parts:
        answer = "\n\n".join(answer_parts)
        certainty = "supported" if len(context) >= 2 else "possible"
    else:
        answer = f"Limited information found. Refer to {', '.join(citations)}."
        certainty = "possible"
    
    return answer, citations, certainty


async def run_single_question(
    question_data: dict,
    corpus: dict[str, str],
    run_number: int
) -> BenchmarkResult:
    """Run a single benchmark question."""
    
    result = BenchmarkResult(
        question_id=question_data["id"],
        category=question_data["category"],
        question=question_data["question"],
        expected_answer=question_data["expected_answer"]
    )
    
    try:
        # Measure retrieval latency
        start_time = time.perf_counter()
        
        # Baseline retrieval (no GraphRAG)
        context = simple_retrieve(question_data["question"], corpus, top_k=3)
        
        retrieval_time = time.perf_counter() - start_time
        
        # Simulate LLM response
        answer, citations, certainty = simulate_llm_response(
            question_data["question"], context, corpus
        )
        
        # Total latency (retrieval + simulated generation)
        result.latency_ms = retrieval_time * 1000  # Just retrieval for baseline
        
        # Extract and validate citations
        result.citations = citations
        result.certainty = certainty
        
        # Check required entities
        for entity in question_data.get("required_entities", []):
            if check_entity_found(answer, entity, corpus):
                result.required_entities_found.append(entity)
        
        # Check required sources
        result.required_sources_found = check_source_found(
            citations, question_data.get("required_sources", [])
        )
        
        # Check forbidden claims
        result.forbidden_claims_made = check_forbidden_claims(
            answer, question_data.get("forbidden_claims", [])
        )
        
        # Detect hallucination
        result.hallucination_detected = len(result.forbidden_claims_made) > 0
        
        result.actual_answer = answer
        
    except Exception as e:
        result.error = str(e)
    
    return result


async def run_benchmark(graphrag_enabled: bool = False) -> BenchmarkReport:
    """Run full benchmark suite."""
    
    corpus = load_corpus()
    questions = load_questions()
    
    report = BenchmarkReport(
        timestamp=datetime.now().isoformat(),
        graphrag_enabled=graphrag_enabled,
        total_questions=len(questions),
        total_runs=SAMPLE_RUNS,
        warmup_runs=WARMUP_RUNS
    )
    
    all_latencies = []
    
    for q in questions:
        print(f"\nProcessing {q['id']} ({q['category']})...")
        
        # Warmup runs (discarded)
        for _ in range(WARMUP_RUNS):
            await run_single_question(q, corpus, 0)
        
        # Actual runs
        question_results = []
        for run in range(SAMPLE_RUNS):
            result = await run_single_question(q, corpus, run + 1)
            question_results.append(result)
            all_latencies.append(result.latency_ms)
        
        # Use first result as representative (could also aggregate)
        report.results.append(question_results[0])
    
    # Calculate aggregated metrics
    if all_latencies:
        report.latency_avg_ms = mean(all_latencies)
        if len(all_latencies) >= 5:
            q = quantiles(all_latencies, n=100)
            report.latency_p50_ms = q[49]  # 50th percentile
            report.latency_p95_ms = q[94]  # 95th percentile
    
    # Calculate accuracy scores
    total_entities = 0
    found_entities = 0
    total_sources = 0
    found_sources = 0
    hallucination_count = 0
    
    for result in report.results:
        total_entities += len([e for e in questions if e['id'] == result.question_id][0].get('required_entities', []))
        found_entities += len(result.required_entities_found)
        total_sources += len([s for s in questions if s['id'] == result.question_id][0].get('required_sources', []))
        found_sources += len(result.required_sources_found)
        if result.hallucination_detected:
            hallucination_count += 1
    
    report.accuracy_score = found_entities / total_entities if total_entities > 0 else 0
    report.provenance_score = found_sources / total_sources if total_sources > 0 else 0
    report.hallucination_penalty = hallucination_count / len(questions) if questions else 0
    
    return report


def save_report(report: BenchmarkReport, output_path: Path):
    """Save report to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict for JSON serialization
    report_dict = {
        "timestamp": report.timestamp,
        "graphrag_enabled": report.graphrag_enabled,
        "configuration": {
            "total_questions": report.total_questions,
            "total_runs": report.total_runs,
            "warmup_runs": report.warmup_runs,
            "sample_runs": SAMPLE_RUNS
        },
        "metrics": {
            "accuracy_score": report.accuracy_score,
            "provenance_score": report.provenance_score,
            "hallucination_penalty": report.hallucination_penalty,
            "latency_avg_ms": report.latency_avg_ms,
            "latency_p50_ms": report.latency_p50_ms,
            "latency_p95_ms": report.latency_p95_ms
        },
        "results": [
            {
                "question_id": r.question_id,
                "category": r.category,
                "latency_ms": r.latency_ms,
                "citations": r.citations,
                "certainty": r.certainty,
                "required_entities_found": r.required_entities_found,
                "required_sources_found": r.required_sources_found,
                "forbidden_claims_made": r.forbidden_claims_made,
                "hallucination_detected": r.hallucination_detected,
                "error": r.error
            }
            for r in report.results
        ]
    }
    
    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)
    
    print(f"\nReport saved to: {output_path}")


async def main():
    """Main entry point."""
    print("="*60)
    print("GraphRAG Agent Zero - Baseline Benchmark Runner")
    print("="*60)
    print("\nMode: BASELINE (GraphRAG DISABLED)")
    print(f"Questions: {QUESTIONS_FILE}")
    print(f"Corpus: {CORPUS_DIR}")
    print(f"Warmup runs: {WARMUP_RUNS}")
    print(f"Sample runs: {SAMPLE_RUNS}")
    print("="*60)
    
    report = await run_benchmark(graphrag_enabled=False)
    
    # Save report
    output_file = RESULTS_DIR / f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_report(report, output_file)
    
    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    print(f"Accuracy Score: {report.accuracy_score:.2%}")
    print(f"Provenance Score: {report.provenance_score:.2%}")
    print(f"Hallucination Penalty: {report.hallucination_penalty:.2%}")
    print(f"Avg Latency: {report.latency_avg_ms:.2f}ms")
    print(f"P50 Latency: {report.latency_p50_ms:.2f}ms")
    print(f"P95 Latency: {report.latency_p95_ms:.2f}ms")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
