import csv
import json
from pathlib import Path

from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.model_schema import get_model_feature_schema
from app.ml.v3_dataset import build_v3_dataset


V2_COLUMNS = get_model_feature_schema("v2").feature_columns
V3_COLUMNS = get_model_feature_schema("v3").feature_columns


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _artifact(url: str) -> dict[str, object]:
    return {
        "requested_url": url,
        "final_url": url,
        "status_code": 200,
        "response_headers": {"content-type": "text/html; charset=utf-8"},
        "response_time_ms": 120.0,
        "fetch_method": "browser",
        "html": """
            <html lang="ru">
              <head>
                <title>Buy repair service</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <script type="application/ld+json">
                  {"@context":"https://schema.org","@type":"LocalBusiness","name":"Example","telephone":"+7 900 000"}
                </script>
              </head>
              <body>
                <h1>Buy repair service in Moscow</h1>
                <p>Commercial service page with price, contacts, warranty and order form.</p>
                <img src="/a.png" alt="">
                <form><input name="phone"></form>
                <script>window.app = true;</script>
              </body>
            </html>
        """,
        "text": "Buy repair service in Moscow with price contacts warranty and order form",
        "json_ld": [
            '{"@context":"https://schema.org","@type":"LocalBusiness","name":"Example","telephone":"+7 900 000"}'
        ],
    }


def _source_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    queries = ["buy repair service moscow", "order windows kazan"]
    for query_index, query in enumerate(queries, start=1):
        for rank in (1, 2):
            url = f"https://example{query_index}.com/page-{rank}"
            row = {column: "" for column in DATASET_COLUMNS}
            row.update(
                {
                    "dataset_version": "dataset-v2-test",
                    "feature_schema_version": "v2",
                    "extraction_artifact_version": "extraction-v2",
                    "label_schema_version": "hybrid-v1",
                    "label_source": "weak_serp",
                    "weak_target_score": 100.0 if rank == 1 else 50.0,
                    "query": query,
                    "category": "services",
                    "intent": "commercial",
                    "city": "moscow",
                    "region_code": 213,
                    "url": url,
                    "domain": f"example{query_index}.com",
                    "rank": rank,
                    "serp_page": 0,
                    "title": f"Title {rank}",
                    "snippet": f"Snippet {rank}",
                    "page_type": "content",
                    "fetch_status": "ok",
                    "fetch_error": "",
                    "artifact_path": f"artifacts/row-{query_index}-{rank}.json",
                    "target_score": 100.0 if rank == 1 else 50.0,
                    "phone_present": 1,
                    "address_present": 1,
                    "price_present": 1,
                    "commercial_signals_score": 0.8,
                    "trust_signals_score": 0.7,
                    "commercial_trust_score": 0.75,
                    "page_indexable": 1,
                    "technical_seo_score": 0.85,
                    "semantic_similarity": 0.8,
                    "query_semantic_alignment": 0.72,
                    "query_prominence_score": 0.7,
                    "keyword_coverage_ratio": 0.8,
                    "conversion_signal_score": 0.6,
                    "cta_semantic_score": 0.5,
                }
            )
            for feature_index, feature_name in enumerate(V2_COLUMNS, start=1):
                row.setdefault(feature_name, float(feature_index))
                if row[feature_name] == "":
                    row[feature_name] = float(feature_index)
            rows.append(row)
    return rows


def test_build_v3_dataset_adds_heavy_and_intent_columns_without_serp_relative(tmp_path):
    source_dir = tmp_path / "dataset-v2"
    output_dir = tmp_path / "dataset-v3-d37"
    source_dataset = source_dir / "dataset.csv"
    source_seeds = source_dir / "seeds.csv"
    artifacts_dir = source_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    source_rows = _source_rows()
    _write_csv(source_dataset, DATASET_COLUMNS, source_rows)
    _write_csv(
        source_seeds,
        ["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        [
            {
                "query": "buy repair service moscow",
                "category": "services",
                "intent": "commercial",
                "city": "moscow",
                "region_code": 213,
                "top_n": 2,
                "pages_to_scan": 1,
            },
            {
                "query": "order windows kazan",
                "category": "services",
                "intent": "commercial",
                "city": "kazan",
                "region_code": 43,
                "top_n": 2,
                "pages_to_scan": 1,
            },
        ],
    )
    for row in source_rows:
        artifact_path = source_dir / str(row["artifact_path"])
        artifact_path.write_text(json.dumps(_artifact(str(row["url"])), ensure_ascii=False), encoding="utf-8")

    report = build_v3_dataset(
        source_dataset_path=source_dataset,
        source_failures_path=source_dir / "missing-failures.csv",
        source_seeds_path=source_seeds,
        source_artifacts_dir=artifacts_dir,
        output_dataset_path=output_dir / "dataset.csv",
        output_failures_path=output_dir / "failures.csv",
        output_seeds_path=output_dir / "seeds.csv",
        output_split_path=output_dir / "split.json",
        output_manifest_path=output_dir / "manifest.json",
        output_report_path=output_dir / "d37-v3-dataset-report.json",
        dataset_version="dataset-v3-test",
    )

    assert report["model_schema_version"] == "v3"
    assert report["feature_count"] == len(V3_COLUMNS)
    assert report["source_artifacts_missing"] == 0
    assert report["rows_with_heavy_features"] == 4
    assert report["rows_with_intent_alignment"] == 4

    with (output_dir / "dataset.csv").open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["dataset_version"] == "dataset-v3-test"
    assert rows[0]["feature_schema_version"] == "v3"
    assert set(V3_COLUMNS).issubset(rows[0].keys())
    assert "serp_relative_context_available" not in rows[0]
    assert float(rows[0]["heavy_analysis_available"]) == 1.0
    assert float(rows[0]["structured_data_score"]) > 0.0
    assert float(rows[0]["intent_alignment_score"]) > 0.0
    assert (output_dir / rows[0]["artifact_path"]).exists()

    split = json.loads((output_dir / "split.json").read_text(encoding="utf-8"))
    assert split["split_mode"] == "group_by_query"
    assert not (set(split["train_queries"]) & set(split["validation_queries"]))
