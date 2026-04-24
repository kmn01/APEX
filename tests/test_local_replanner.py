"""Tests for M3 Local Replanner."""

import pytest

from apex.tactical.replanner import (
    Disruption,
    DisruptionType,
    EscalationSignal,
    LocalReplanner,
    Resolution,
)


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])