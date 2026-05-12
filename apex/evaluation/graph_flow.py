"""Task graph ordering for instruction materialization."""

from __future__ import annotations

from collections import defaultdict, deque

from apex.adapter.translator import AbstractTask, DomainTranslator
from apex.planner.htn.operators import TaskType
from apex.planner.htn.planner import TaskGraph, TaskNode
from apex.simulation.order import Order
from apex.simulation.warehouse import WarehouseState
from apex.tactical.executor import TaskInstruction


def topological_nodes(graph: TaskGraph) -> list[TaskNode]:
    """Kahn topological sort; falls back to declaration order on cycles."""
    nodes = {n.id: n for n in graph.nodes}
    indegree: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)
    for nid in nodes:
        indegree[nid] = 0
    for u, v in graph.edges:
        adj[u].append(v)
        indegree[v] += 1

    dq = deque([nid for nid in nodes if indegree[nid] == 0])
    out: list[TaskNode] = []
    while dq:
        u = dq.popleft()
        out.append(nodes[u])
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                dq.append(v)

    if len(out) != len(nodes):
        return list(graph.nodes)
    return out


def order_first_keys(graph: TaskGraph) -> list[str]:
    """Stable order ids following first appearance in topological walk."""
    seen: list[str] = []
    for n in topological_nodes(graph):
        if n.order_id and n.order_id not in seen:
            seen.append(n.order_id)
    return seen


def assign_orders_to_agents(graph: TaskGraph, agent_ids: list[str]) -> dict[str, str]:
    """Map order_id -> agent_id (round-robin)."""
    keys = order_first_keys(graph)
    if not agent_ids:
        return {}
    return {oid: agent_ids[i % len(agent_ids)] for i, oid in enumerate(keys)}


def node_to_abstract(node: TaskNode, orders_by_id: dict[str, Order]) -> AbstractTask:
    if isinstance(node.task_type, TaskType):
        tt = node.task_type.value
    else:
        tt = str(node.task_type)
    oid = node.order_id
    sku: str | None = None
    if oid and oid in orders_by_id and orders_by_id[oid].items:
        sku = orders_by_id[oid].items[0].sku
    return AbstractTask(
        task_type=tt,
        item_sku=sku,
        order_id=oid,
        priority=0,
        deadline=float(node.deadline or 0.0),
        task_node_id=node.id,
    )


def graph_to_instructions(
    graph: TaskGraph,
    warehouse: WarehouseState,
    orders_by_id: dict[str, Order],
    agent_ids: list[str],
    translator: DomainTranslator,
    *,
    use_mcts_agent_ids: bool = False,
    plan_run_id: str | None = None,
    graph_version_id: str | None = None,
) -> list[TaskInstruction]:
    """Flatten HTN graph to executable instructions in cross-order parallel-friendly order."""
    ordered = topological_nodes(graph)
    order_to_agent = assign_orders_to_agents(graph, agent_ids)
    by_order: dict[str, list[TaskNode]] = defaultdict(list)
    for n in ordered:
        if n.order_id:
            by_order[n.order_id].append(n)

    sequence_order = order_first_keys(graph)
    flat_nodes: list[TaskNode] = []
    for oid in sequence_order:
        flat_nodes.extend(by_order[oid])

    instrs: list[TaskInstruction] = []
    for node in flat_nodes:
        agent_id = node.agent_id if use_mcts_agent_ids and node.agent_id else order_to_agent.get(
            node.order_id or "", agent_ids[0] if agent_ids else "picker-0"
        )
        abstract = node_to_abstract(node, orders_by_id)
        abstract.plan_run_id = plan_run_id
        abstract.graph_version_id = graph_version_id
        instrs.extend(translator.translate(abstract, warehouse, agent_id))
    return instrs
