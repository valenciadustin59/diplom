from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.competitors import build_comparison_summary, select_competitor_context_candidates
from app.query_relevance import (
    QUERY_RELEVANCE_GUARDRAIL_VERSION,
    build_query_relevance_guardrail,
    build_query_relevance_preflight_decision,
    has_strong_query_topic_fit,
)
from app.semantic_providers import (
    DEFAULT_ROSBERTA_MODEL,
    ROSBERTA_PROVIDER,
    build_semantic_numeric_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "D95"
D95_REPORT_VERSION = "d95-rosberta-competitor-replacement-focused-v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "artifacts" / "ranking-benchmarks" / "d95-rosberta-competitor-replacement"
DEFAULT_CATALOG_PATH = DEFAULT_OUTPUT_DIR / "d95-focused-catalog.json"
DEFAULT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d95-focused-product-benchmark-report.json"
DEFAULT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d95-focused-product-benchmark-report.md"
STORED_SMOKE_PATH = PROJECT_ROOT / "output" / "runtime-smoke" / "d84-d87-final-smoke-summary.json"
ROSBERTA_SAMPLE_REPORT_PATH = (
    PROJECT_ROOT
    / "backend"
    / "artifacts"
    / "embedding-benchmarks"
    / "dataset-v7-rosberta-vs-minilm-sample"
    / "sample-comparison-report.json"
)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": _display_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def _rosberta_metadata(*, fallback_used: bool = False, failure: bool = False) -> dict[str, float | int]:
    return build_semantic_numeric_metadata(
        provider=ROSBERTA_PROVIDER,
        model_name=DEFAULT_ROSBERTA_MODEL,
        fallback_used=fallback_used,
        failure=failure,
    )


def _base_relevance_features(**overrides: float | int) -> dict[str, float | int]:
    features: dict[str, float | int] = {
        "http_status_code": 200,
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 1100,
        "text_length_chars": 6800,
        "semantic_similarity": 0.32,
        "semantic_similarity_raw": 0.27,
        "keyword_coverage_ratio": 0.75,
        "query_core_keyword_coverage_ratio": 1.0,
        "query_intent_modifier_count": 0,
        "query_intent_modifier_matches": 0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.006,
        "query_core_term_count": 8,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 1,
        "title_semantic_alignment": 0.55,
        "heading_semantic_alignment": 0.62,
        "query_prominence_score": 0.58,
        **_rosberta_metadata(),
    }
    features.update(overrides)
    return features


def _relevance_case(
    *,
    case_id: str,
    group: str,
    source_kind: str,
    query: str,
    page_hint: str,
    base_score: float,
    features: dict[str, float | int],
    expectation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "group": group,
        "source_kind": source_kind,
        "query": query,
        "page_hint": page_hint,
        "base_score": base_score,
        "features": features,
        "expectation": expectation,
    }


def _competitor(
    score: float,
    *,
    rank: int,
    word_count: int = 700,
    text_length_chars: int = 4200,
) -> dict[str, object]:
    return {
        "url": f"https://d95-competitor-{rank}.example/",
        "domain": f"d95-competitor-{rank}.example",
        "serp_rank": rank,
        "serp_page": 0,
        "fetch_status": "success",
        "score": score,
        "features": {
            "semantic_similarity": 0.78,
            "query_core_keyword_coverage_ratio": 1.0,
            "technical_seo_score": 0.72,
            "word_count": word_count,
            "text_length_chars": text_length_chars,
        },
    }


def _failed_competitor(code: str, *, rank: int) -> dict[str, object]:
    return {
        "url": f"https://d95-failed-{rank}.example/",
        "domain": f"d95-failed-{rank}.example",
        "serp_rank": rank,
        "serp_page": 0,
        "fetch_status": "failed",
        "fetch_error_code": code,
        "fetch_error_message": code,
        "score": None,
        "features": None,
    }


def _competitor_case(
    *,
    case_id: str,
    source_kind: str,
    query: str,
    requested_top_n: int,
    user_score: float,
    competitor_results: list[dict[str, object]],
    expectation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "source_kind": source_kind,
        "query": query,
        "requested_top_n": requested_top_n,
        "user_score": user_score,
        "competitor_results": competitor_results,
        "expectation": expectation,
    }


def build_d95_relevance_cases() -> list[dict[str, Any]]:
    return [
        _relevance_case(
            case_id="d95-rosberta-full-mismatch-near-zero",
            group="full_mismatch",
            source_kind="d88_regression",
            query="kupit kozlovoy kran",
            page_hint="wine shop page with no crane terms",
            base_score=94.0,
            features=_base_relevance_features(
                semantic_similarity=0.06,
                semantic_similarity_raw=0.04,
                keyword_coverage_ratio=0.0,
                query_core_keyword_coverage_ratio=0.0,
                query_intent_modifier_coverage_ratio=0.0,
                query_density=0.0,
                query_core_term_count=0,
                exact_query_count=0,
                query_in_title=0,
                query_in_text=0,
                title_semantic_alignment=0.0,
                heading_semantic_alignment=0.0,
                query_prominence_score=0.0,
            ),
            expectation={
                "early_stop": True,
                "bands": ["full_mismatch"],
                "score_min": 0.0,
                "score_max": 5.0,
                "provider": ROSBERTA_PROVIDER,
            },
        ),
        _relevance_case(
            case_id="d95-rosberta-approximate-relevant-not-crushed",
            group="approximate_relevant",
            source_kind="d89_regression",
            query="diagnostika nasosa vodosnabzheniya",
            page_hint="service page described semantically but without exact query tokens",
            base_score=86.0,
            features=_base_relevance_features(
                semantic_similarity=0.34,
                semantic_similarity_raw=0.29,
                keyword_coverage_ratio=0.0,
                query_core_keyword_coverage_ratio=0.0,
                query_intent_modifier_coverage_ratio=0.0,
                query_density=0.0,
                query_core_term_count=0,
                exact_query_count=0,
                query_in_title=0,
                query_in_text=0,
                title_semantic_alignment=0.0,
                heading_semantic_alignment=0.0,
                query_prominence_score=0.0,
            ),
            expectation={
                "early_stop": False,
                "bands": ["weak_match"],
                "score_min": 25.0,
                "score_max": 55.0,
                "provider": ROSBERTA_PROVIDER,
            },
        ),
        _relevance_case(
            case_id="d95-relevant-no-buy-price-modifier-keeps-score",
            group="no_commercial_modifier_required",
            source_kind="d89_regression",
            query="chekap organizma",
            page_hint="medical checkup page; query has no buy or price modifier",
            base_score=82.0,
            features=_base_relevance_features(
                semantic_similarity=0.31,
                semantic_similarity_raw=0.26,
                keyword_coverage_ratio=0.666667,
                query_core_keyword_coverage_ratio=1.0,
                query_intent_modifier_count=0,
                query_intent_modifier_matches=0,
                query_intent_modifier_coverage_ratio=0.0,
                query_density=0.006,
                query_core_term_count=8,
                query_in_text=1,
                title_semantic_alignment=0.55,
                heading_semantic_alignment=0.62,
                query_prominence_score=0.58,
            ),
            expectation={
                "early_stop": False,
                "bands": [None],
                "score_min": 82.0,
                "score_max": 82.0,
                "strong_topic_fit": True,
                "provider": ROSBERTA_PROVIDER,
            },
        ),
        _relevance_case(
            case_id="d95-commercial-modifier-only-does-not-hide-core-mismatch",
            group="modifier_only_core_mismatch",
            source_kind="d89_regression",
            query="kupit analizy krovi",
            page_hint="laptop catalog with buy/delivery terms but no medical core topic",
            base_score=88.0,
            features=_base_relevance_features(
                semantic_similarity=0.29,
                semantic_similarity_raw=0.24,
                keyword_coverage_ratio=0.2,
                query_core_keyword_coverage_ratio=0.0,
                query_intent_modifier_count=1,
                query_intent_modifier_matches=1,
                query_intent_modifier_coverage_ratio=1.0,
                query_density=0.0007,
                query_core_term_count=0,
                exact_query_count=0,
                query_in_title=0,
                query_in_text=1,
                title_semantic_alignment=0.0,
                heading_semantic_alignment=0.0,
                query_prominence_score=0.05,
            ),
            expectation={
                "early_stop": False,
                "bands": ["probable_mismatch"],
                "score_min": 6.0,
                "score_max": 25.0,
                "provider": ROSBERTA_PROVIDER,
            },
        ),
    ]


def build_d95_competitor_cases() -> list[dict[str, Any]]:
    return [
        _competitor_case(
            case_id="d95-replacement-pool-excludes-bad-and-fills-context",
            source_kind="d90_d94_regression",
            query="remont kvartir moscow",
            requested_top_n=3,
            user_score=72.0,
            competitor_results=[
                _failed_competitor("http_403", rank=1),
                _competitor(2.5, rank=2, word_count=24, text_length_chars=260),
                _competitor(86.0, rank=3),
                _competitor(66.0, rank=4, word_count=8, text_length_chars=80),
                _competitor(89.0, rank=5),
                _competitor(78.0, rank=6),
                _competitor(92.0, rank=7),
            ],
            expectation={
                "competitor_context_status": "ready",
                "score_basis": "competitiveness_score",
                "competitors_average_score": 84.3333,
                "accepted_competitors": 3,
                "discarded_competitors": 3,
                "replacement_attempts": 3,
                "replacements_used": 2,
                "unused_candidates": 1,
                "discard_reasons": {
                    "bot_block_suspected": 1,
                    "score_below_minimum": 1,
                    "thin_content": 1,
                },
            },
        ),
        _competitor_case(
            case_id="d95-insufficient-after-bad-competitor-exclusion",
            source_kind="d85_d90_regression",
            query="kozlovoy kran kupit",
            requested_top_n=2,
            user_score=70.0,
            competitor_results=[
                _failed_competitor("browser_blocked", rank=1),
                _competitor(3.5, rank=2, word_count=22, text_length_chars=240),
                _competitor(81.0, rank=3),
            ],
            expectation={
                "competitor_context_status": "insufficient_processed_competitors",
                "score_basis": "primary_page_score",
                "competitors_average_score": None,
                "accepted_competitors": 1,
                "discarded_competitors": 2,
                "replacement_attempts": 2,
                "replacements_used": 1,
                "unused_candidates": 0,
                "discard_reasons": {
                    "bot_block_suspected": 1,
                    "score_below_minimum": 1,
                },
            },
        ),
    ]


def build_d95_catalog() -> dict[str, Any]:
    return {
        "task": TASK_ID,
        "version": D95_REPORT_VERSION,
        "scope": "focused_product_benchmark_no_full_dataset",
        "relevance_cases": build_d95_relevance_cases(),
        "competitor_cases": build_d95_competitor_cases(),
        "stored_evidence_sources": {
            "stored_smoke": _display_path(STORED_SMOKE_PATH),
            "rosberta_sample_report": _display_path(ROSBERTA_SAMPLE_REPORT_PATH),
        },
    }


def _evaluate_relevance_case(case: dict[str, Any]) -> dict[str, Any]:
    features = dict(case["features"])
    expectation = case["expectation"]
    base_score = float(case["base_score"])
    preflight = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, base_score)
    adjusted_score = float(guardrail["adjusted_score"])
    semantic_layer = guardrail.get("semantic_layer") if isinstance(guardrail.get("semantic_layer"), dict) else {}
    failures: list[str] = []

    if bool(guardrail["early_stop"]) != bool(expectation["early_stop"]):
        failures.append("early_stop_state")
    if adjusted_score < float(expectation["score_min"]) or adjusted_score > float(expectation["score_max"]):
        failures.append("score_band")
    if guardrail.get("band") not in expectation["bands"]:
        failures.append("relevance_band")
    if semantic_layer.get("provider") != expectation["provider"]:
        failures.append("semantic_provider")
    if "strong_topic_fit" in expectation and has_strong_query_topic_fit(features) != expectation["strong_topic_fit"]:
        failures.append("strong_topic_fit")

    return {
        "id": case["id"],
        "group": case["group"],
        "source_kind": case["source_kind"],
        "query": case["query"],
        "page_hint": case["page_hint"],
        "status": "pass" if not failures else "fail",
        "failed_checks": failures,
        "base_score": base_score,
        "adjusted_score": adjusted_score,
        "score_delta": guardrail.get("score_delta"),
        "guardrail_active": guardrail.get("active"),
        "guardrail_band": guardrail.get("band"),
        "guardrail_reason": guardrail.get("reason"),
        "early_stop": guardrail.get("early_stop"),
        "preflight_decision": preflight.get("decision"),
        "preflight_reason": preflight.get("reason"),
        "strong_topic_fit": has_strong_query_topic_fit(features),
        "semantic_layer": semantic_layer,
        "metrics": guardrail.get("metrics"),
    }


def _evaluate_competitor_case(case: dict[str, Any]) -> dict[str, Any]:
    expectation = case["expectation"]
    competitor_results = list(case["competitor_results"])
    selection = select_competitor_context_candidates(
        competitor_results,
        requested_top_n=int(case["requested_top_n"]),
    )
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.72, "technical_seo_score": 0.7},
        user_score=float(case["user_score"]),
        competitor_results=competitor_results,
        requested_top_n=int(case["requested_top_n"]),
    )
    quality = summary["competitor_context_quality"]
    failures: list[str] = []
    for key in (
        "competitor_context_status",
        "score_basis",
        "competitors_average_score",
        "accepted_competitors",
        "discarded_competitors",
        "replacement_attempts",
        "replacements_used",
        "unused_candidates",
        "discard_reasons",
    ):
        actual = summary.get(key) if key in summary else quality.get(key)
        if actual != expectation[key]:
            failures.append(key)

    accepted_results = list(selection["accepted_results"])
    bad_accepted = [
        {
            "domain": item.get("domain"),
            "fetch_status": item.get("fetch_status"),
            "score": item.get("score"),
        }
        for item in accepted_results
        if item.get("fetch_status") != "success"
        or not isinstance(item.get("score"), (int, float))
        or float(item["score"]) < 10.0
    ]
    if bad_accepted:
        failures.append("bad_competitor_accepted")

    return {
        "id": case["id"],
        "source_kind": case["source_kind"],
        "query": case["query"],
        "status": "pass" if not failures else "fail",
        "failed_checks": failures,
        "requested_top_n": case["requested_top_n"],
        "user_score": case["user_score"],
        "competitor_context_status": summary["competitor_context_status"],
        "score_basis": summary["score_basis"],
        "competitors_average_score": summary["competitors_average_score"],
        "score_difference": summary["score_difference"],
        "primary_score_difference": summary["primary_score_difference"],
        "accepted_competitors": summary["accepted_competitors"],
        "discarded_competitors": summary["discarded_competitors"],
        "replacement_attempts": summary["replacement_attempts"],
        "replacements_used": quality["replacements_used"],
        "unused_candidates": quality["unused_candidates"],
        "discard_reasons": summary["discard_reasons"],
        "bad_accepted": bad_accepted,
        "competitor_context_quality": quality,
        "candidate_statuses": [
            {
                "domain": item.get("domain"),
                "candidate_index": item.get("candidate_index"),
                "context_status": item.get("competitor_context_status"),
                "discard_reason": item.get("discard_reason"),
                "replacement_candidate": bool(item.get("replacement_candidate")),
                "score": item.get("score"),
            }
            for item in selection["annotated_results"]
        ],
    }


def _summarize_stored_evidence() -> dict[str, Any]:
    smoke = _read_json(STORED_SMOKE_PATH)
    rosberta_sample = _read_json(ROSBERTA_SAMPLE_REPORT_PATH)
    smoke_cases = smoke.get("cases") if isinstance(smoke.get("cases"), list) else []
    rosberta_models = rosberta_sample.get("models") if isinstance(rosberta_sample.get("models"), list) else []
    rosberta_model = next((model for model in rosberta_models if model.get("key") == "ru_en_rosberta"), None)
    return {
        "stored_smoke": {
            "path": _display_path(STORED_SMOKE_PATH),
            "status": smoke.get("decision") or smoke.get("status"),
            "cases_count": len(smoke_cases),
            "failed_cases_count": len(smoke.get("failures") or []),
            "case_labels": [case.get("label") for case in smoke_cases],
            "competitor_context_statuses": [
                (case.get("comparison") or {}).get("competitor_context_status")
                for case in smoke_cases
                if isinstance(case, dict)
            ],
        },
        "rosberta_sample_report": {
            "path": _display_path(ROSBERTA_SAMPLE_REPORT_PATH),
            "status": rosberta_sample.get("decision") if "decision" in rosberta_sample else rosberta_sample.get("status"),
            "sample_rows": (rosberta_sample.get("sample") or {}).get("rows"),
            "sample_queries": (rosberta_sample.get("sample") or {}).get("queries"),
            "rosberta_auc": ((rosberta_model or {}).get("binary") or {}).get("auc") if isinstance(rosberta_model, dict) else None,
            "rosberta_positive_top1_rate": ((rosberta_model or {}).get("query_level") or {}).get("positive_top1_rate")
            if isinstance(rosberta_model, dict)
            else None,
        },
    }


def _build_criteria(results: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    relevance = results["relevance"]
    competitors = results["competitors"]
    full_mismatch = [item for item in relevance if item["group"] == "full_mismatch"]
    approximate = [item for item in relevance if item["group"] == "approximate_relevant"]
    no_modifier = [item for item in relevance if item["group"] == "no_commercial_modifier_required"]
    return {
        "full_mismatch_near_zero": {
            "passed": all(item["status"] == "pass" and item["adjusted_score"] <= 5.0 for item in full_mismatch),
            "cases": [item["id"] for item in full_mismatch],
        },
        "approximate_relevant_not_crushed_to_zero": {
            "passed": all(item["status"] == "pass" and item["adjusted_score"] > 25.0 for item in approximate),
            "cases": [item["id"] for item in approximate],
        },
        "relevant_without_buy_price_not_penalized_when_query_lacks_modifiers": {
            "passed": all(
                item["status"] == "pass" and item["guardrail_active"] is False and item["adjusted_score"] == item["base_score"]
                for item in no_modifier
            ),
            "cases": [item["id"] for item in no_modifier],
        },
        "bad_competitors_score_below_10_or_failed_excluded": {
            "passed": all(item["status"] == "pass" and not item["bad_accepted"] for item in competitors),
            "cases": [item["id"] for item in competitors],
        },
        "accepted_competitor_count_and_context_quality_visible": {
            "passed": all(
                item["status"] == "pass"
                and isinstance(item["accepted_competitors"], int)
                and isinstance(item["competitor_context_quality"], dict)
                and item["competitor_context_quality"].get("schema_version") == "competitor-context-quality-v2"
                for item in competitors
            ),
            "cases": [item["id"] for item in competitors],
        },
    }


def run_d95_focused_product_benchmark(
    *,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    report_path: Path = DEFAULT_REPORT_JSON_PATH,
    markdown_path: Path = DEFAULT_REPORT_MD_PATH,
) -> dict[str, Any]:
    catalog = build_d95_catalog()
    relevance_results = [_evaluate_relevance_case(case) for case in catalog["relevance_cases"]]
    competitor_results = [_evaluate_competitor_case(case) for case in catalog["competitor_cases"]]
    results = {"relevance": relevance_results, "competitors": competitor_results}
    failed_cases = [
        {"suite": "query_relevance", **result}
        for result in relevance_results
        if result["status"] != "pass"
    ] + [
        {"suite": "competitor_replacement", **result}
        for result in competitor_results
        if result["status"] != "pass"
    ]
    criteria = _build_criteria(results)
    failed_criteria = [name for name, item in criteria.items() if not item["passed"]]
    status = "passed" if not failed_cases and not failed_criteria else "failed"
    report: dict[str, Any] = {
        "task": TASK_ID,
        "version": D95_REPORT_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "focused_product_benchmark_no_full_dataset_no_runtime_mutation",
        "status": status,
        "decision": (
            "focused_product_guardrails_passed_for_rosberta_and_competitor_replacement"
            if status == "passed"
            else "review_focused_product_guardrail_failures"
        ),
        "query_relevance_guardrail_version": QUERY_RELEVANCE_GUARDRAIL_VERSION,
        "semantic_provider": {
            "provider": ROSBERTA_PROVIDER,
            "model_name": DEFAULT_ROSBERTA_MODEL,
            "fallback_used_in_focused_cases": False,
        },
        "cases_count": len(relevance_results) + len(competitor_results),
        "relevance_cases_count": len(relevance_results),
        "competitor_cases_count": len(competitor_results),
        "failed_cases_count": len(failed_cases),
        "failed_cases": failed_cases,
        "failed_criteria": failed_criteria,
        "criteria": criteria,
        "results": results,
        "stored_evidence": _summarize_stored_evidence(),
        "catalog_path": _display_path(catalog_path),
        "verification_commands": [
            ".venv\\Scripts\\python.exe -m app.ml.d95_focused_product_benchmark",
            ".venv\\Scripts\\python.exe -m pytest tests\\test_query_relevance_runtime.py tests\\test_competitiveness_score.py -q -p no:cacheprovider",
        ],
        "notes": [
            "Focused benchmark only; it does not run dataset-v7 or network competitor fetching.",
            "Runtime modules are imported read-only to evaluate the current product contract.",
        ],
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_report(report), encoding="utf-8")
    return report


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# D95 Focused Product Benchmark",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['decision']}`",
        f"- Scope: `{report['scope']}`",
        f"- Cases: `{report['cases_count']}` (`{report['relevance_cases_count']}` relevance, `{report['competitor_cases_count']}` competitor replacement)",
        f"- Failed cases: `{report['failed_cases_count']}`",
        f"- Semantic provider: `{report['semantic_provider']['provider']}` / `{report['semantic_provider']['model_name']}`",
        f"- Catalog: `{report['catalog_path']}`",
        "",
        "## Criteria",
        "",
    ]
    for name, payload in report["criteria"].items():
        lines.append(f"- `{name}`: `{'pass' if payload['passed'] else 'fail'}` ({', '.join(payload['cases'])})")

    lines.extend(["", "## Query Relevance", ""])
    for item in report["results"]["relevance"]:
        lines.append(
            f"- `{item['id']}`: `{item['status']}`, band `{item['guardrail_band']}`, "
            f"score `{item['base_score']}` -> `{item['adjusted_score']}`, early stop `{item['early_stop']}`"
        )

    lines.extend(["", "## Competitor Replacement", ""])
    for item in report["results"]["competitors"]:
        lines.append(
            f"- `{item['id']}`: `{item['status']}`, context `{item['competitor_context_status']}`, "
            f"accepted `{item['accepted_competitors']}`, discarded `{item['discarded_competitors']}`, "
            f"replacements `{item['replacements_used']}/{item['replacement_attempts']}`"
        )

    stored = report["stored_evidence"]
    lines.extend(
        [
            "",
            "## Stored Evidence Sources",
            "",
            (
                f"- Smoke: `{stored['stored_smoke']['path']}`, status `{stored['stored_smoke']['status']}`, "
                f"cases `{stored['stored_smoke']['cases_count']}`"
            ),
            (
                f"- RoSBERTa sample: `{stored['rosberta_sample_report']['path']}`, "
                f"rows `{stored['rosberta_sample_report']['sample_rows']}`, "
                f"queries `{stored['rosberta_sample_report']['sample_queries']}`"
            ),
            "",
            "## Notes",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in report["notes"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D95 focused product benchmark.")
    parser.add_argument("--catalog-path", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_JSON_PATH)
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_REPORT_MD_PATH)
    args = parser.parse_args()
    report = run_d95_focused_product_benchmark(
        catalog_path=args.catalog_path,
        report_path=args.report_path,
        markdown_path=args.markdown_path,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "cases_count": report["cases_count"],
                "failed_cases_count": report["failed_cases_count"],
                "failed_criteria": report["failed_criteria"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
