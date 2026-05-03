"""Tests for M3 Local Replanner."""

import pytest

from apex.tactical.replanner import (
    Disruption,
    DisruptionType,
    EscalationSignal,
    LocalReplanner,
    Resolution,
)


class _StubCBSPlanner:
    def __init__(self, result: dict[str, list[tuple[int, int]]] | None) -> None:
        self.result = result
        self.called = False

    def plan_paths(
        self, starts: dict[str, tuple[int, int]], goals: dict[str, tuple[int, int]]
    ) -> dict[str, list[tuple[int, int]]] | None:
        self.called = True
        return self.result


def test_local_replanner_creation():
    """Test replanner initialization."""
    replanner = LocalReplanner()
    assert replanner.horizon == 50.0
    assert replanner.escalation_threshold == 3


def test_blocked_path_resolution():
    """Test local resolution of blocked path."""
    replanner = LocalReplanner()
    disruption = Disruption(
        type=DisruptionType.BLOCKED_PATH,
        agent_id="picker-1",
        context={"alternate_pos": (3, 4)},
    )
    
    result = replanner.handle(disruption, None)
    assert isinstance(result, Resolution)
    assert len(result.revised_instructions) > 0


def test_failed_pick_retry():
    """Test retry on pick failure."""
    replanner = LocalReplanner()
    disruption = Disruption(
        type=DisruptionType.FAILED_PICK,
        agent_id="picker-1",
        context={"shelf_id": "shelf_a"},
    )
    
    result = replanner.handle(disruption, None)
    assert isinstance(result, Resolution)
    assert any(i.action_type == "RETRY_PICK" for i in result.revised_instructions)


def test_agent_failure_escalation():
    """Test escalation on agent failure."""
    replanner = LocalReplanner()
    disruption = Disruption(
        type=DisruptionType.AGENT_FAILURE,
        agent_id="picker-2",
        context={"reason": "Battery depleted"},
    )
    
    result = replanner.handle(disruption, None)
    assert isinstance(result, EscalationSignal)
    assert "picker-2" in result.reason


def test_escalation_on_repeated_conflicts():
    """Test escalation after threshold is exceeded."""
    replanner = LocalReplanner(escalation_threshold=2)
    
    disruption = Disruption(
        type=DisruptionType.BLOCKED_PATH,
        agent_id="picker-1",
        context={"alternate_pos": (3, 4)},
    )
    
    # First two should resolve locally
    result1 = replanner.handle(disruption, None)
    assert isinstance(result1, Resolution)
    
    result2 = replanner.handle(disruption, None)
    assert isinstance(result2, Resolution)
    
    # Third should escalate
    result3 = replanner.handle(disruption, None)
    assert isinstance(result3, EscalationSignal)


def test_blocked_path_uses_cbs_reroute_first():
    stub = _StubCBSPlanner(result={"picker-1": [(1, 1), (1, 2), (1, 3)]})
    replanner = LocalReplanner(cbs_planner=stub)
    disruption = Disruption(
        type=DisruptionType.BLOCKED_PATH,
        agent_id="picker-1",
        context={
            "alternate_pos": (9, 9),
            "cbs_starts": {"picker-1": (1, 1)},
            "cbs_goals": {"picker-1": (1, 3)},
        },
    )

    result = replanner.handle(disruption, None)
    assert stub.called is True
    assert isinstance(result, Resolution)
    assert all(instr.action_type == "MOVE_TO" for instr in result.revised_instructions)
    assert result.revised_instructions[0].target_pos == (1, 2)


def test_blocked_path_escalates_after_threshold_when_cbs_unsat():
    stub = _StubCBSPlanner(result=None)
    replanner = LocalReplanner(escalation_threshold=0, cbs_planner=stub)
    disruption = Disruption(
        type=DisruptionType.BLOCKED_PATH,
        agent_id="picker-1",
        context={
            "cbs_starts": {"picker-1": (1, 1)},
            "cbs_goals": {"picker-1": (1, 3)},
        },
    )

    result = replanner.handle(disruption, None)
    assert stub.called is True
    assert isinstance(result, EscalationSignal)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])