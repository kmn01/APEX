"""Tests for M3 Tactical Executor."""

import pytest
import simpy

from apex.tactical.executor import TaskInstruction, TacticalExecutor


def test_tactical_executor_creation():
    """Test executor initialization."""
    env = simpy.Environment()
    executor = TacticalExecutor(env)
    assert executor is not None
    assert len(executor.get_agent_actions()) == 0


def test_assign_single_instruction():
    """Test assigning a single instruction."""
    env = simpy.Environment()
    executor = TacticalExecutor(env)
    
    instr = TaskInstruction(
        agent_id="picker-1",
        action_type="MOVE_TO",
        target_pos=(5, 5),
    )
    
    executor.assign(instr)
    actions = executor.get_agent_actions()
    assert "picker-1" in actions
    assert "QUEUED" in actions["picker-1"]


def test_get_next_instruction():
    """Test retrieving instructions from queue."""
    env = simpy.Environment()
    executor = TacticalExecutor(env)
    
    instr1 = TaskInstruction(
        agent_id="picker-1",
        action_type="MOVE_TO",
        target_pos=(5, 5),
    )
    instr2 = TaskInstruction(
        agent_id="picker-1",
        action_type="PICK",
        shelf_id="shelf_a",
    )
    
    executor.assign(instr1)
    executor.assign(instr2)
    
    next_instr = executor.get_next_instruction("picker-1")
    assert next_instr.action_type == "MOVE_TO"
    
    next_instr = executor.get_next_instruction("picker-1")
    assert next_instr.action_type == "PICK"
    
    next_instr = executor.get_next_instruction("picker-1")
    assert next_instr is None


def test_set_agent_action():
    env = simpy.Environment()
    executor = TacticalExecutor(env)
    executor.set_agent_action("picker-1", "CUSTOM")
    assert executor.get_agent_actions()["picker-1"] == "CUSTOM"


def test_completed_tracking():
    """Test instruction completion tracking."""
    env = simpy.Environment()
    executor = TacticalExecutor(env)
    
    instr = TaskInstruction(agent_id="picker-1", action_type="PICK")
    executor.assign(instr)
    executor.mark_completed(instr)
    
    assert executor.get_completed_count() == 1


def test_task_instruction_supports_conveyor_id():
    instr = TaskInstruction(
        agent_id="carrier-1",
        action_type="PLACE_ON_CONVEYOR",
        conveyor_id="conv_main",
    )
    assert instr.conveyor_id == "conv_main"


def test_repr_reports_active_agent_queues():
    """repr should describe live per-agent queue state."""
    env = simpy.Environment()
    executor = TacticalExecutor(env)

    empty_repr = repr(executor)
    assert "queued=0" in empty_repr
    assert "active_agents=0" in empty_repr

    executor.assign(TaskInstruction(agent_id="picker-1", action_type="MOVE_TO"))
    queued_repr = repr(executor)
    assert "queued=1" in queued_repr
    assert "active_agents=1" in queued_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])