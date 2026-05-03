"""End-to-end demo: planning → adaptation → execution → visualization."""

from collections.abc import Generator

import simpy

from apex.adapter.translator import DomainTranslator, AbstractTask
from apex.planner.htn.planner import HTNPlanner
from apex.simulation.grid import CellType, Grid
from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
from apex.simulation.warehouse import (
    ConveyorSegment,
    LoadingBay,
    ShelfZone,
    WarehouseState,
)
from apex.tactical.executor import TacticalExecutor
from apex.agents.registry import AgentRegistry
from apex.agents.base import Agent, AgentCapabilities, AgentStatus
from apex.agents.picker import PickerBot

try:
    from apex.visualization.viewer import WarehouseVisualizer
    VIZ_AVAILABLE = True
except ImportError:
    VIZ_AVAILABLE = False


def _simulate_work_step(
    env: simpy.Environment,
    agent: Agent,
    duration: float,
    *,
    increment_work: bool = False,
) -> Generator[simpy.Event, None, None]:
    """Set WORKING, wait, consume battery, optionally bump work, return IDLE."""
    agent.status = AgentStatus.WORKING
    yield env.timeout(duration)
    agent.consume_battery(duration * agent.capabilities.battery_consumption_rate)
    if increment_work:
        agent.total_work_done += 1
    agent.status = AgentStatus.IDLE


def _drive_executor_queue(
    env: simpy.Environment,
    executor: TacticalExecutor,
    warehouse: WarehouseState,
    agent: PickerBot,
) -> Generator[simpy.Event, None, None]:
    """Execute queued :class:`TaskInstruction` records and update agent pose for the viewer."""
    while True:
        instr = executor.get_next_instruction(agent.id)
        if instr is None:
            executor.set_agent_action(agent.id, "ALL TASKS COMPLETE")
            yield env.timeout(0.5)
            continue

        executor.set_agent_action(agent.id, f"EXECUTING: {instr.action_type}")

        if instr.action_type == "MOVE_TO" and instr.target_pos is not None:
            yield env.process(agent._move_to(instr.target_pos, env, warehouse))
        elif instr.action_type == "PICK":
            yield from _simulate_work_step(env, agent, 1.0, increment_work=True)
        elif instr.action_type == "PLACE_ON_CONVEYOR":
            yield from _simulate_work_step(env, agent, 0.8)
        elif instr.action_type == "DISPATCH":
            yield from _simulate_work_step(env, agent, 0.8, increment_work=True)
        else:
            yield env.timeout(0.3)

        executor.mark_completed(instr)


def main():
    # Create warehouse
    env = simpy.Environment()
    grid = Grid(20, 20, env)

    shelf_a = ShelfZone(id="shelf_a", positions=[(5, 5), (5, 6)], capacity=100)
    shelf_b = ShelfZone(id="shelf_b", positions=[(8, 8)], capacity=100)
    bay_out = LoadingBay(id="bay_out", position=(15, 15))
    conveyor = ConveyorSegment(
        id="conv_main",
        positions=[(10, 10), (10, 11), (10, 12)],
        direction="E",
        speed=2.0,
    )

    # Stamp logical warehouse entities into grid cells for visualization/rendering.
    for shelf in (shelf_a, shelf_b):
        for pos in shelf.positions:
            grid.set_cell(pos, CellType.SHELF)

    for pos in conveyor.positions:
        grid.set_cell(pos, CellType.CONVEYOR)

    grid.set_cell(bay_out.position, CellType.BAY)

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf_a, shelf_b],
        conveyors=[conveyor],
        bays=[bay_out],
        pending_orders=[],
        active_orders=[],
    )

    print("=" * 60)
    print("APEX End-to-End Demo: Planning → Adaptation → Execution")
    print("=" * 60)

    # Step 1: Strategic Planning (M5)
    print("\n[M5] STRATEGIC PLANNER")
    print("-" * 40)
    planner = HTNPlanner()

    orders = [
        Order(
            id="ord-1",
            items=[
                OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2),
                OrderItem(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1),
            ],
            priority=1,
            deadline=200.0,
            status=OrderStatus.PENDING,
        ),
        Order(
            id="ord-2",
            items=[OrderItem(sku="SKU-C", shelf_zone_id="shelf_a", quantity=3)],
            priority=2,
            deadline=300.0,
            status=OrderStatus.PENDING,
        ),
    ]

    batch = OrderBatch(orders=orders)
    task_graph = planner.plan_batch(batch, warehouse)

    print(f"Task Graph created with {len(task_graph.nodes)} nodes")
    for node in task_graph.nodes[:5]:  # Show first 5
        print(f"  - {node.task_type}: {node.id} (order: {node.order_id})")
    if len(task_graph.nodes) > 5:
        print(f"  ... and {len(task_graph.nodes) - 5} more")

    # Step 2: Domain Adaptation (M4)
    print("\n[M4] DOMAIN ADAPTER")
    print("-" * 40)
    translator = DomainTranslator()

    abstract_tasks = [
        AbstractTask(task_type="PICK", item_sku="SKU-A", priority=1, deadline=200.0),
        AbstractTask(task_type="TRANSPORT", priority=1, deadline=250.0),
        AbstractTask(task_type="DISPATCH", priority=1, deadline=300.0),
    ]

    concrete_instructions = []
    for task in abstract_tasks:
        instrs = translator.translate(task, warehouse, "picker-1")
        concrete_instructions.extend(instrs)
        print(f"Translated {task.task_type} → {len(instrs)} instructions")

    print(f"Total concrete instructions: {len(concrete_instructions)}")
    for instr in concrete_instructions[:3]:
        print(f"  - {instr.action_type} @ {instr.target_pos}")

    # Step 3: Tactical Execution (M3)
    print("\n[M3] TACTICAL EXECUTOR")
    print("-" * 40)
    executor = TacticalExecutor(env)

    for instr in concrete_instructions:
        executor.assign(instr)

    print(f"Assigned {len(concrete_instructions)} instructions to executor")
    print(f"Agent actions: {executor.get_agent_actions()}")

    # Step 4: Visualization (optional)
    if VIZ_AVAILABLE:
        print("\n[VIZ] VISUALIZATION")
        print("-" * 40)
        print("Initializing visualizer (close window to exit)...")

        viz = WarehouseVisualizer(
            warehouse,
            width=1000,
            height=800,
            cell_size=30,
            scenario_hint={
                "id": "end_to_end_demo",
                "seed": 0,
                "horizon": "ad-hoc",
                "grid_rows": grid.rows,
                "grid_cols": grid.cols,
                "orders": len(orders),
                "disruptions": 0,
            },
        )

        registry = AgentRegistry()

        picker_caps = AgentCapabilities(
            max_speed=2.0,
            max_payload=10,
            battery_capacity=100.0,
        )

        picker1 = PickerBot(id="picker-1", position=(0, 0), capabilities=picker_caps)
        picker2 = PickerBot(id="picker-2", position=(2, 2), capabilities=picker_caps)

        registry.register(picker1)
        registry.register(picker2)

        agents = registry.get_all_agents()
        executor.set_agent_action("picker-2", "IDLE (no assigned queue)")

        planned_waypoints: list[tuple[int, int]] = [picker1.position]
        for instr in concrete_instructions:
            if instr.agent_id == picker1.id and instr.target_pos is not None:
                planned_waypoints.append(instr.target_pos)
        paths = {picker1.id: planned_waypoints} if len(planned_waypoints) > 1 else {}

        env.process(_drive_executor_queue(env, executor, warehouse, picker1))

        sim_dt = 0.05
        max_frames = 800
        print(
            f"Created {len(agents)} agents; advancing SimPy by {sim_dt}s per frame "
            f"(up to {max_frames} frames).\n"
        )

        for frame in range(max_frames):
            if not viz.paused:
                env.run(until=env.now + sim_dt)
            actions = executor.get_agent_actions()
            if not viz.render(
                agents=agents,
                paths=paths or None,
                time=env.now,
                actions=actions,
            ):
                break

            if frame % 40 == 0:
                print(f"Frame {frame}: sim_t={env.now:.2f}s, agents={len(agents)}")

        viz.close()
        print("\nVisualization closed.")
    else:
        print("\n[VIZ] Pygame not installed. Skipping visualization.")
        print("Install with: pip install -e '.[viz]'")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()