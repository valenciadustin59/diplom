from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.final_hard_negatives import HARD_NEGATIVE_POLICY_VERSION, materialize_hard_negatives


def _write_seeds(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query": "кофемашина для офиса",
                "category": "coffee_machines",
                "intent": "commercial",
                "city": "Москва",
                "region_code": 213,
                "top_n": 10,
                "pages_to_scan": 1,
            }
        )
        writer.writerow(
            {
                "query": "лазерная резка металла",
                "category": "laser_cutting",
                "intent": "commercial",
                "city": "Казань",
                "region_code": 43,
                "top_n": 10,
                "pages_to_scan": 1,
            }
        )


def _write_artifact(path: Path, *, url: str, html: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "requested_url": url,
                "final_url": url,
                "status_code": 200,
                "html": html,
                "text": text,
                "fetch_method": "http",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _dataset_row(*, query: str, category: str, url: str, artifact_path: str) -> dict[str, object]:
    row: dict[str, object] = {column: "" for column in DATASET_COLUMNS}
    row.update(
        {
            "dataset_version": "dataset-v7-final",
            "feature_schema_version": "v3",
            "extraction_artifact_version": "extraction-v2",
            "query": query,
            "category": category,
            "intent": "commercial",
            "city": "Москва",
            "region_code": 213,
            "url": url,
            "domain": url.split("/")[2],
            "rank": 1,
            "serp_page": 0,
            "fetch_status": "ok",
            "artifact_path": artifact_path,
            "target_score": 75,
            "semantic_similarity": 0.8,
            "keyword_coverage_ratio": 1.0,
            "query_core_keyword_coverage_ratio": 1.0,
        }
    )
    return row


def test_materialize_hard_negatives_recomputes_features_for_target_query(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    seeds_path = tmp_path / "seeds.csv"
    output_path = tmp_path / "dataset.with-hard-negatives.csv"
    report_path = tmp_path / "report.json"
    artifacts_dir = tmp_path / "artifacts"

    _write_seeds(seeds_path)
    _write_artifact(
        artifacts_dir / "coffee.json",
        url="https://coffee.example/offices",
        html="<html><head><title>Кофемашина для офиса</title></head><body><h1>Кофемашина для офиса</h1></body></html>",
        text="Кофемашина для офиса аренда обслуживание кофе",
    )
    _write_artifact(
        artifacts_dir / "laser.json",
        url="https://laser.example/cut",
        html="<html><head><title>Лазерная резка металла</title></head><body><h1>Лазерная резка металла</h1></body></html>",
        text="Лазерная резка металла чпу производство деталей",
    )

    rows = [
        _dataset_row(
            query="кофемашина для офиса",
            category="coffee_machines",
            url="https://coffee.example/offices",
            artifact_path="artifacts/coffee.json",
        ),
        _dataset_row(
            query="лазерная резка металла",
            category="laser_cutting",
            url="https://laser.example/cut",
            artifact_path="artifacts/laser.json",
        ),
    ]
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        fieldnames = list(DATASET_COLUMNS)
        for row in rows:
            for column in row:
                if column not in fieldnames:
                    fieldnames.append(column)
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = materialize_hard_negatives(
        dataset_path=dataset_path,
        seeds_path=seeds_path,
        output_path=output_path,
        report_path=report_path,
        max_negatives_per_query=1,
    )

    with output_path.open("r", encoding="utf-8", newline="") as file:
        output_rows = list(csv.DictReader(file))
    negative_rows = [row for row in output_rows if row["hard_negative"] == "1"]

    assert report["hard_negative_rows_count"] == 2
    assert len(output_rows) == 4
    assert len(negative_rows) == 2
    assert {row["label_source"] for row in negative_rows} == {"hard_negative_v7"}
    assert {row["hard_negative_policy_version"] for row in negative_rows} == {HARD_NEGATIVE_POLICY_VERSION}
    assert {row["rank"] for row in negative_rows} == {"999"}
    assert any(
        row["query"] == "кофемашина для офиса"
        and row["hard_negative_source_category"] == "laser_cutting"
        and float(row["keyword_coverage_ratio"]) < 1.0
        for row in negative_rows
    )
    assert report_path.exists()
