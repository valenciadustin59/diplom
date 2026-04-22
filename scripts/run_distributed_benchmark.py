from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import httpx
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from app.distributed_benchmark import (  # noqa: E402
    DistributedBenchmarkConfig,
    build_default_benchmark_output_dir,
    load_benchmark_workload,
    render_benchmark_report_markdown,
    run_distributed_benchmark,
    write_distributed_benchmark_report,
)
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--workload-file",
        default=str(PROJECT_ROOT / "scripts" / "distributed_benchmark.workload.example.json"),
    )
    parser.add_argument("--benchmark-name", default="distributed-runtime-benchmark")
    parser.add_argument("--max-inflight", type=int, default=3)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--metrics-interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--print-markdown", action="store_true")
    args = parser.parse_args()
    workload = load_benchmark_workload(args.workload_file)
    config = DistributedBenchmarkConfig(
        benchmark_name=args.benchmark_name,
        max_inflight=args.max_inflight,
        poll_interval_seconds=args.poll_interval,
        metrics_interval_seconds=args.metrics_interval,
        timeout_seconds=args.timeout,
        request_timeout_seconds=args.request_timeout,
    )
    output_dir = Path(args.output_dir) if args.output_dir else build_default_benchmark_output_dir(args.benchmark_name)
    base_url = args.base_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=args.request_timeout, follow_redirects=True) as client:
        report = run_distributed_benchmark(
            client,
            workload,
            config,
            base_url=base_url,
        )
    output_paths = write_distributed_benchmark_report(report, output_dir)
    summary = {
        "benchmark_name": report["benchmark_name"],
        "base_url": report["base_url"],
        "requested_audits": report["admission"]["requested"],
        "accepted_audits": report["admission"]["accepted"],
        "rejected_audits": report["admission"]["rejected"],
        "terminal_status_counts": report["audits"]["terminal_status_counts"],
        "runtime_sample_count": report["runtime"]["sample_count"],
        **output_paths,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.print_markdown:
        print()
        print(render_benchmark_report_markdown(report))
if __name__ == "__main__":
    main()
