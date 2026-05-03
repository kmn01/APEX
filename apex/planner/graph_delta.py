"""``TaskGraphDelta`` contract plus validate/apply helpers for strategic edits.

Edges ``(u, v)`` mean *u precedes v* (same convention as HTN sequential wiring in
:class:`~apex.planner.htn.planner.HTNPlanner`).
"""

from __future__ import annotations

from collections import defaultdict, deque

from pydantic import BaseModel, Field

from apex.planner.htn.operators import TaskType
from apex.planner.htn.planner import TaskGraph, TaskNode


class TaskGraphDelta(BaseModel):
    """Incremental edits to an existing task graph."""

    added: list[TaskNode] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[TaskNode] = Field(default_factory=list)


def allowed_task_type_values() -> set[str]:
    """Primitive task labels allowed on :class:`TaskNode` for validation."""
    return {e.value for e in TaskType}


def _node_ids(graph: TaskGraph) -> set[str]:
    return {n.id for n in graph.nodes}


def graph_is_acyclic(node_ids: set[str], edges: list[tuple[str, str]]) -> bool:
    """Return True if precedence graph among ``node_ids`` is a DAG."""
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    succ: dict[str, list[str]] = defaultdict(list)
    for u, v in edges:
        if u not in node_ids or v not in node_ids:
            continue
        succ[u].append(v)
        indegree[v] += 1

    q: deque[str] = deque(n for n in node_ids if indegree[n] == 0)
    count = 0
    while q:
        n = q.popleft()
        count += 1
        for m in succ[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                q.append(m)
    return count == len(node_ids)


def validate_task_graph(graph: TaskGraph) -> list[str]:
    """Return human-readable errors; empty list means graph is valid."""
    errors: list[str] = []
    allowed = allowed_task_type_values()
    ids = _node_ids(graph)
    if len(ids) != len(graph.nodes):
        errors.append("duplicate task node ids in graph")

    for n in graph.nodes:
        tt = n.task_type.value if isinstance(n.task_type, TaskType) else str(n.task_type)
        if tt not in allowed:
            errors.append(f"unknown task_type on node {n.id!r}: {tt!r}")
        for dep in n.dependencies:
            if dep not in ids:
                errors.append(f"node {n.id!r} depends on unknown id {dep!r}")

    for a, b in graph.edges:
        if a not in ids or b not in ids:
            errors.append(f"edge references unknown node: {a!r} -> {b!r}")

    if not graph_is_acyclic(ids, list(graph.edges)):
        errors.append("task graph edges contain a cycle")

    return errors


def validate_task_graph_delta(baseline: TaskGraph, delta: TaskGraphDelta) -> list[str]:
    """Validate a delta against ``baseline`` before application."""
    errors: list[str] = []
    base_ids = _node_ids(baseline)
    allowed = allowed_task_type_values()

    for n in delta.added:
        tt = n.task_type.value if isinstance(n.task_type, TaskType) else str(n.task_type)
        if tt not in allowed:
            errors.append(f"delta.added unknown task_type on node {n.id!r}: {tt!r}")
        if n.id in base_ids:
            errors.append(f"delta.added node id collides with baseline: {n.id!r}")

    seen_add = [n.id for n in delta.added]
    if len(seen_add) != len(set(seen_add)):
        errors.append("duplicate ids in delta.added")

    for nid in delta.removed:
        if nid not in base_ids:
            errors.append(f"delta.removed id not in baseline: {nid!r}")

    for n in delta.modified:
        if n.id not in base_ids:
            errors.append(f"delta.modified id not in baseline: {n.id!r}")
        tt = n.task_type.value if isinstance(n.task_type, TaskType) else str(n.task_type)
        if tt not in allowed:
            errors.append(f"delta.modified unknown task_type on node {n.id!r}: {tt!r}")

    return errors


def apply_task_graph_delta(baseline: TaskGraph, delta: TaskGraphDelta) -> TaskGraph:
    """Return a new graph with ``delta`` applied (copy-on-write)."""
    removed = set(delta.removed)
    nodes_by_id: dict[str, TaskNode] = {}

    for n in baseline.nodes:
        if n.id in removed:
            continue
        nodes_by_id[n.id] = n

    for n in delta.modified:
        nodes_by_id[n.id] = n

    for n in delta.added:
        nodes_by_id[n.id] = n

    new_nodes = list(nodes_by_id.values())
    new_edges = [(a, b) for a, b in baseline.edges if a not in removed and b not in removed]

    merged = TaskGraph(nodes=new_nodes, edges=new_edges)
    v = validate_task_graph(merged)
    if v:
        raise ValueError("apply_task_graph_delta produced invalid graph: " + "; ".join(v))
    return merged
