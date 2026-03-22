"""
Tests for health monitor and routing strategies.
These run without needing live Orthanc nodes by using mocks.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pydicom
import pytest

from diomede.endpoints import DicomEndpoint
from diomede.health import NodeHealth, select_best_node
from diomede.routing import LeastQueueStrategy, ModalityAwareStrategy, RoundRobinStrategy


def make_endpoint(name: str, port: int = 4242) -> DicomEndpoint:
    return DicomEndpoint(
        name=name,
        ae_title=name.upper(),
        host="localhost",
        dicom_port=port,
        rest_port=8042,
    )


def make_health(name: str, is_reachable: bool, queue: int, latency: float) -> NodeHealth:
    return NodeHealth(
        endpoint=make_endpoint(name),
        is_reachable=is_reachable,
        queue_depth=queue,
        echo_latency_ms=latency,
    )


def make_dataset(modality: str = "CT") -> pydicom.Dataset:
    ds = pydicom.Dataset()
    ds.Modality = modality
    return ds


# ── select_best_node ────────────────────────────────────────────────────────

def test_select_best_node_picks_lowest_queue():
    results = [
        make_health("Node1", is_reachable=True, queue=10, latency=5.0),
        make_health("Node2", is_reachable=True, queue=3,  latency=5.0),
        make_health("Node3", is_reachable=True, queue=7,  latency=5.0),
    ]
    best = select_best_node(results)
    assert best.endpoint.name == "Node2"


def test_select_best_node_ignores_unreachable_nodes():
    results = [
        make_health("Node1", is_reachable=False, queue=0,  latency=-1),
        make_health("Node2", is_reachable=True,  queue=10, latency=5.0),
    ]
    best = select_best_node(results)
    assert best.endpoint.name == "Node2"


def test_select_best_node_returns_none_when_all_down():
    results = [
        make_health("Node1", is_reachable=False, queue=0, latency=-1),
        make_health("Node2", is_reachable=False, queue=0, latency=-1),
    ]
    assert select_best_node(results) is None


def test_select_best_node_breaks_tie_with_latency():
    results = [
        make_health("Node1", is_reachable=True, queue=5, latency=20.0),
        make_health("Node2", is_reachable=True, queue=5, latency=8.0),
    ]
    best = select_best_node(results)
    assert best.endpoint.name == "Node2"


# ── LeastQueueStrategy ──────────────────────────────────────────────────────

def test_least_queue_strategy_selects_least_loaded_node():
    nodes = [make_endpoint("Node1"), make_endpoint("Node2"), make_endpoint("Node3")]
    dataset = make_dataset()

    mock_results = [
        make_health("Node1", is_reachable=True, queue=20, latency=5.0),
        make_health("Node2", is_reachable=True, queue=5,  latency=5.0),
        make_health("Node3", is_reachable=True, queue=12, latency=5.0),
    ]

    with patch("diomede.routing.check_all_nodes", return_value=mock_results):
        strategy = LeastQueueStrategy()
        chosen = strategy.select(dataset, nodes)

    assert chosen.name == "Node2"


# ── RoundRobinStrategy ──────────────────────────────────────────────────────

def test_round_robin_cycles_through_nodes():
    nodes = [make_endpoint("Node1"), make_endpoint("Node2"), make_endpoint("Node3")]
    dataset = make_dataset()

    mock_results = [
        make_health("Node1", is_reachable=True, queue=0, latency=5.0),
        make_health("Node2", is_reachable=True, queue=0, latency=5.0),
        make_health("Node3", is_reachable=True, queue=0, latency=5.0),
    ]

    strategy = RoundRobinStrategy()
    chosen_names = []
    for _ in range(6):
        with patch("diomede.routing.check_all_nodes", return_value=mock_results):
            chosen = strategy.select(dataset, nodes)
            chosen_names.append(chosen.name)

    assert chosen_names == ["Node1", "Node2", "Node3", "Node1", "Node2", "Node3"]


# ── ModalityAwareStrategy ───────────────────────────────────────────────────

def test_modality_aware_routes_ct_to_node1():
    nodes = [make_endpoint("Node1"), make_endpoint("Node2"), make_endpoint("Node3")]
    dataset = make_dataset(modality="CT")

    mock_results = [
        make_health("Node1", is_reachable=True, queue=0, latency=5.0),
        make_health("Node2", is_reachable=True, queue=0, latency=5.0),
        make_health("Node3", is_reachable=True, queue=0, latency=5.0),
    ]

    with patch("diomede.routing.check_all_nodes", return_value=mock_results):
        strategy = ModalityAwareStrategy()
        chosen = strategy.select(dataset, nodes)

    assert chosen.name == "Node1"


def test_modality_aware_falls_back_when_preferred_node_is_down():
    nodes = [make_endpoint("Node1"), make_endpoint("Node2"), make_endpoint("Node3")]
    dataset = make_dataset(modality="CT")  # CT prefers Node1, but Node1 is down

    mock_results = [
        make_health("Node1", is_reachable=False, queue=0,  latency=-1),
        make_health("Node2", is_reachable=True,  queue=3,  latency=5.0),
        make_health("Node3", is_reachable=True,  queue=10, latency=5.0),
    ]

    with patch("diomede.routing.check_all_nodes", return_value=mock_results):
        strategy = ModalityAwareStrategy()
        chosen = strategy.select(dataset, nodes)

    assert chosen.name == "Node2"


def test_modality_aware_uses_least_queue_for_unknown_modality():
    nodes = [make_endpoint("Node1"), make_endpoint("Node2")]
    dataset = make_dataset(modality="XA")  # no affinity defined

    mock_results = [
        make_health("Node1", is_reachable=True, queue=10, latency=5.0),
        make_health("Node2", is_reachable=True, queue=2,  latency=5.0),
    ]

    with patch("diomede.routing.check_all_nodes", return_value=mock_results):
        strategy = ModalityAwareStrategy()
        chosen = strategy.select(dataset, nodes)

    assert chosen.name == "Node2"
