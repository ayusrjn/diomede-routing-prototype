from __future__ import annotations

import itertools
import logging
from typing import Protocol

import pydicom

from diomede.endpoints import DicomEndpoint
from diomede.health import NodeHealth, check_all_nodes, select_best_node

logger = logging.getLogger(__name__)

# Maps DICOM modality codes to preferred node names.
# Extend this dict to add modality-specific affinity rules.
MODALITY_NODE_AFFINITY: dict[str, str] = {
    "CT": "Node1",
    "MR": "Node2",
    "PT": "Node3",   # PET
    "CR": "Node1",   # Computed Radiography
    "DX": "Node1",   # Digital X-ray
}


class RoutingStrategy(Protocol):
    def select(
        self,
        dataset: pydicom.Dataset,
        nodes: list[DicomEndpoint],
    ) -> DicomEndpoint | None:
        ...


class LeastQueueStrategy:
    """Route to the node with the fewest stored instances."""

    def select(
        self,
        dataset: pydicom.Dataset,
        nodes: list[DicomEndpoint],
    ) -> DicomEndpoint | None:
        health_results = check_all_nodes(nodes)
        best = select_best_node(health_results)
        if best:
            logger.info(
                "LeastQueue selected %s (queue=%d, latency=%.1fms)",
                best.endpoint.name,
                best.queue_depth,
                best.echo_latency_ms,
            )
        return best.endpoint if best else None


class RoundRobinStrategy:
    """Cycle through available nodes regardless of load."""

    def __init__(self) -> None:
        self._counter = itertools.count()

    def select(
        self,
        dataset: pydicom.Dataset,
        nodes: list[DicomEndpoint],
    ) -> DicomEndpoint | None:
        health_results = check_all_nodes(nodes)
        reachable = [h.endpoint for h in health_results if h.is_reachable]
        if not reachable:
            return None
        chosen = reachable[next(self._counter) % len(reachable)]
        logger.info("RoundRobin selected %s", chosen.name)
        return chosen


class ModalityAwareStrategy:
    """
    Route based on DICOM modality affinity first, then fall back to
    least-queue for unrecognised modalities or unavailable preferred nodes.
    """

    def __init__(self) -> None:
        self._fallback = LeastQueueStrategy()

    def select(
        self,
        dataset: pydicom.Dataset,
        nodes: list[DicomEndpoint],
    ) -> DicomEndpoint | None:
        modality = getattr(dataset, "Modality", None)
        preferred_name = MODALITY_NODE_AFFINITY.get(modality or "")

        if preferred_name:
            health_results = check_all_nodes(nodes)
            preferred = next(
                (
                    h for h in health_results
                    if h.endpoint.name == preferred_name and h.is_reachable
                ),
                None,
            )
            if preferred:
                logger.info(
                    "ModalityAware: routed %s to preferred node %s",
                    modality,
                    preferred.endpoint.name,
                )
                return preferred.endpoint

        logger.info(
            "ModalityAware: no affinity match for modality=%s, falling back to LeastQueue",
            modality,
        )
        return self._fallback.select(dataset, nodes)


STRATEGIES: dict[str, RoutingStrategy] = {
    "least_queue": LeastQueueStrategy(),
    "round_robin": RoundRobinStrategy(),
    "modality_aware": ModalityAwareStrategy(),
}


def get_strategy(name: str) -> RoutingStrategy:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{name}'. Choose from: {list(STRATEGIES)}")
    return STRATEGIES[name]
