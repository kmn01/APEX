"""Unit tests for assignment-domain MCTS."""

import random

import pytest

from apex.planner.htn.planner import TaskNode
from apex.planner.htn.operators import TaskType
from apex.planner.mcts.domain import (
    AssignmentDomain,
    assignment_state_from_graph,
    default_assignment_cost,
)
from apex.planner.mcts.node import AssignmentState
from apex.planner.mcts.search import MCTSSearch


def test_legal_moves_respects_can_assign() -> None:
    domain = AssignmentDomain(
        tasks_by_id={
            "t_pick": TaskNode(id="t_pick", task_type=TaskType.PICK),
            "t_tr": TaskNode(id="t_tr", task_type=TaskType.TRANSPORT),
        },
        agent_ids=["picker", "carrier"],
        can_assign=lambda aid, tt: (aid == "picker" and tt == "PICK")
        or (aid == "carrier" and tt == "TRANSPORT"),
    )
    state = AssignmentState(unassigned_tasks=["t_pick", "t_tr"], task_to_agent={})
    moves = domain.legal_moves(state)
    assert ("t_pick", "picker") in moves
    assert ("t_tr", "carrier") in moves
    assert ("t_pick", "carrier") not in moves


def test_search_assigns_single_feasible_task() -> None:
    domain = AssignmentDomain(
        tasks_by_id={"only": TaskNode(id="only", task_type=TaskType.STAGE)},
        agent_ids=["bot"],
        can_assign=lambda _a, _t: True,
    )
    mcts = MCTSSearch(domain, n_iterations=10, rng=random.Random(0))
    out = mcts.search(AssignmentState(unassigned_tasks=["only"], task_to_agent={}))
    assert out.unassigned_tasks == []
    assert out.task_to_agent["only"] == "bot"


def test_assignment_state_from_graph_presets() -> None:
    nodes = [
        TaskNode(id="fixed", task_type=TaskType.PICK, agent_id="p1"),
        TaskNode(id="open", task_type=TaskType.TRANSPORT),
    ]
    st = assignment_state_from_graph(nodes)
    assert st.task_to_agent == {"fixed": "p1"}
    assert st.unassigned_tasks == ["open"]


def test_default_assignment_cost_additive() -> None:
    tasks = {
        "a": TaskNode(id="a", task_type=TaskType.PICK),
        "b": TaskNode(id="b", task_type=TaskType.TRANSPORT),
    }
    st = AssignmentState(
        task_to_agent={"a": "x", "b": "y"},
        unassigned_tasks=[],
    )
    c = default_assignment_cost(tasks, st)
    assert c == pytest.approx(6.0)


def test_infeasible_partial_returns_root_cost_safe() -> None:
    """No legal moves: search must return the initial snapshot unchanged."""
    domain = AssignmentDomain(
        tasks_by_id={"orphan": TaskNode(id="orphan", task_type=TaskType.PICK)},
        agent_ids=["wrong_bot"],
        can_assign=lambda _a, _t: False,
    )
    root = AssignmentState(unassigned_tasks=["orphan"], task_to_agent={})
    mcts = MCTSSearch(domain, n_iterations=20, rng=random.Random(1))
    out = mcts.search(root)
    assert out == root
