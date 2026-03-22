from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
from pynetdicom import AE
from pynetdicom.sop_class import Verification

from diomede.endpoints import DicomEndpoint

logger = logging.getLogger(__name__)

ECHO_TIMEOUT_SECONDS = 3
REST_TIMEOUT_SECONDS = 3


@dataclass
class NodeHealth:
    endpoint: DicomEndpoint
    is_reachable: bool
    queue_depth: int
    echo_latency_ms: float


def check_node_health(endpoint: DicomEndpoint) -> NodeHealth:
    """Query a node's availability and queue depth via C-ECHO and REST."""
    echo_latency_ms = _measure_echo_latency(endpoint)
    is_reachable = echo_latency_ms >= 0

    queue_depth = _fetch_queue_depth(endpoint) if is_reachable else -1

    return NodeHealth(
        endpoint=endpoint,
        is_reachable=is_reachable,
        queue_depth=queue_depth,
        echo_latency_ms=echo_latency_ms,
    )


def check_all_nodes(nodes: list[DicomEndpoint]) -> list[NodeHealth]:
    """Return health status for every node in the list."""
    return [check_node_health(node) for node in nodes]


def select_best_node(health_results: list[NodeHealth]) -> NodeHealth | None:
    """
    Pick the destination with the lowest queue depth among reachable nodes.
    Falls back to lowest echo latency when queue depths are equal.
    """
    reachable = [h for h in health_results if h.is_reachable]
    if not reachable:
        return None
    return min(reachable, key=lambda h: (h.queue_depth, h.echo_latency_ms))


def _measure_echo_latency(endpoint: DicomEndpoint) -> float:
    """Send a DICOM C-ECHO and return round-trip time in ms, or -1 on failure."""
    ae = AE(ae_title="ROUTER")
    ae.add_requested_context(Verification)

    start = time.monotonic()
    try:
        assoc = ae.associate(
            endpoint.host,
            endpoint.dicom_port,
            ae_title=endpoint.ae_title,
        )
        if not assoc.is_established:
            return -1
        status = assoc.send_c_echo()
        assoc.release()
        if status and status.Status == 0x0000:
            return (time.monotonic() - start) * 1000
        return -1
    except Exception as exc:
        logger.debug("C-ECHO failed for %s: %s", endpoint.name, exc)
        return -1


def _fetch_queue_depth(endpoint: DicomEndpoint) -> int:
    """
    Use Orthanc's REST API to get the number of stored instances.
    This approximates queue load — more instances means more work done/pending.
    """
    try:
        response = requests.get(
            f"{endpoint.rest_base_url}/statistics",
            timeout=REST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        stats = response.json()
        return int(stats.get("CountInstances", 0))
    except Exception as exc:
        logger.debug("REST health check failed for %s: %s", endpoint.name, exc)
        return 0
