"""Tests for :mod:`apex.planner.graph_delta` validation and apply."""

import pytest

from apex.planner.graph_delta import (
    TaskGraphDelta,
    apply_task_graph_delta,
    graph_is_acyclic,
    validate_task_graph,
    validate_task_graph_delta,
)
from apex.planner.htn.operators import TaskType
from apex.planner.htn.planner import TaskGraph, TaskNode


def test_graph_is_acyclic_chain():
    ids = {"a", "b", "c"}
    edges = [("a", "b"), ("b", "c")]
    assert graph_is_acyclic(ids, edges) is True


def test_graph_is_acyclic_detects_cycle():
    ids = {"a", "b", "c"}
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    assert graph_is_acyclic(ids, edges) is False


def test_validate_task_graph_unknown_type():
    g = TaskGraph(
        nodes=[TaskNode(id="n1", task_type="NOT_A_TASK")],
        edges=[],
    )
    err = validate_task_graph(g)
    assert any("unknown task_type" in e for e in err)


def test_apply_task_graph_delta_remove_and_validate():
    n1 = TaskNode(id="n1", task_type=TaskType.PICK, order_id="o1")
    n2 = TaskNode(id="n2", task_type=TaskType.TRANSPORT, order_id="o1")
    base = TaskGraph(nodes=[n1, n2], edges=[("n1", "n2")])
    delta = TaskGraphDelta(removed=["n2"])
    merged = apply_task_graph_delta(base, delta)
    assert len(merged.nodes) == 1
    assert merged.get_node("n1") is not None


def test_validate_task_graph_delta_rejects_unknown_remove():
    n1 = TaskNode(id="n1", task_type=TaskType.PICK)
    base = TaskGraph(nodes=[n1], edges=[])
    delta = TaskGraphDelta(removed=["missing"])
    err = validate_task_graph_delta(base, delta)
    assert any("not in baseline" in e for e in err)


def test_apply_task_graph_delta_modified_deadline():
    n1 = TaskNode(id="n1", task_type=TaskType.PICK, deadline=10.0, order_id="o1")
    base = TaskGraph(nodes=[n1], edges=[])
    n1b = n1.model_copy(update={"deadline": 99.0})
    delta = TaskGraphDelta(modified=[n1b])
    merged = apply_task_graph_delta(base, delta)
    assert merged.get_node("n1") is not None
    assert merged.get_node("n1").deadline == 99.0


def test_apply_task_graph_delta_raises_on_invalid_merge():
    n1 = TaskNode(id="n1", task_type=TaskType.PICK)
    n2 = TaskNode(id="n2", task_type=TaskType.TRANSPORT)
    base = TaskGraph(nodes=[n1, n2], edges=[("n1", "n2"), ("n2", "n1")])
    delta = TaskGraphDelta()
    with pytest.raises(ValueError, match="invalid graph"):
        apply_task_graph_delta(base, delta)
