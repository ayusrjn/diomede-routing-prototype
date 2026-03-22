#!/usr/bin/env python3
"""
Diomede — Dynamic DICOM Router
Usage:
    python cli.py --file scan.dcm --strategy modality_aware
    python cli.py --dir ./dicoms  --strategy least_queue
    python cli.py --status
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from diomede.endpoints import DEFAULT_NODES
from diomede.health import check_all_nodes
from diomede.router import DynamicRouter
from diomede.sender import SendError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("diomede.cli")


def print_node_status() -> None:
    print("\n── Node Health Check ──────────────────────────────")
    health_results = check_all_nodes(DEFAULT_NODES)
    for h in health_results:
        status = "✓ UP" if h.is_reachable else "✗ DOWN"
        print(
            f"  {h.endpoint.name:8s}  {status:7s}  "
            f"queue={h.queue_depth:4d}  latency={h.echo_latency_ms:6.1f}ms  "
            f"AET={h.endpoint.ae_title}  port={h.endpoint.dicom_port}"
        )
    print("───────────────────────────────────────────────────\n")


def route_file(path: Path, strategy: str) -> None:
    router = DynamicRouter(strategy=strategy)
    try:
        destination = router.route(path)
        print(f"✓ Sent {path.name} → {destination.name}")
    except SendError as exc:
        print(f"✗ Failed: {exc}", file=sys.stderr)
        sys.exit(1)


def route_directory(path: Path, strategy: str) -> None:
    router = DynamicRouter(strategy=strategy)
    results = router.route_directory(path)
    print("\n── Routing Results ─────────────────────────────────")
    for filename, destination in results.items():
        icon = "✗" if destination.startswith("ERROR") else "✓"
        print(f"  {icon} {filename:40s} → {destination}")
    print("───────────────────────────────────────────────────\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diomede Dynamic DICOM Router")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Path to a single .dcm file")
    group.add_argument("--dir", type=Path, help="Directory of .dcm files to route")
    group.add_argument("--status", action="store_true", help="Show health of all nodes")
    parser.add_argument(
        "--strategy",
        choices=["least_queue", "round_robin", "modality_aware"],
        default="least_queue",
        help="Routing strategy (default: least_queue)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.status:
        print_node_status()
        return

    if args.file:
        route_file(args.file, args.strategy)
    elif args.dir:
        route_directory(args.dir, args.strategy)


if __name__ == "__main__":
    main()
