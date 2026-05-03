"""Headless episodic simulation: orders, planning, CBS/greedy tactics, disruptions."""

from __future__ import annotations

import contextlib
import io
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np
import simpy

from apex.adapter.translator import DomainTranslator
from apex.agents.base import AgentStatus
from apex.config.settings import get_settings
from apex.evaluation.graph_flow import graph_to_instructions
from apex.evaluation.metrics import MetricsCollector, count_pairwise_spacetime_conflicts, manhattan_path_cells
from apex.evaluation.run_config import RunConfig, StrategicReplanMode, TacticalCoordination
from apex.planner.coordinator import PlanningMode, StrategicCoordinator
from apex.planner.graph_delta import apply_task_graph_delta, validate_task_graph_delta
from apex.planner.htn.planner import TaskGraph
from apex.simulation.events import StochasticEventGenerator
from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
from apex.scenarios.builder import build_warehouse_and_registry
from apex.scenarios.models import OrderSpec, ScenarioSpec
from apex.tactical.cbs import CBSPlanner
from apex.tactical.executor import TacticalExecutor
from apex.tactical.replanner import Disruption, DisruptionType, EscalationSignal, LocalReplanner

if TYPE_CHECKING:
    pass


def materialize_order(spec: OrderSpec) -> Order:
    return Order(
        id=spec.id,
        items=[
            OrderItem(sku=i.sku, shelf_zone_id=i.shelf_zone_id, quantity=i.quantity)
            for i in spec.items
        ],
        priority=spec.priority,
        deadline=spec.deadline,
        status=OrderStatus.PENDING,
    )


def _greedy_paths_for_moves(
    instructions: list[tuple[int, tuple[int, int] | None]],
    start_positions: dict[str, tuple[int, int]],
) -> dict[str, list[tuple[int, int]]]:
    """Concatenate greedy Manhattan MOVE segments per agent."""
    chains: dict[str, list[tuple[int, int]]] = defaultdict(list)
    pos = dict(start_positions)
    for agent_id, target in instructions:
        if target is None:
            continue
        start = pos[agent_id]
        seg = manhattan_path_cells(start, target)
        if chains[agent_id]:
            seg = seg[1:]
        chains[agent_id].extend(seg)
        pos[agent_id] = target
    return dict(chains)


def _extract_move_sequence(
    instrs: list,
) -> list[tuple[str, tuple[int, int] | None]]:
    out: list[tuple[str, tuple[int, int] | None]] = []
    for ins in instrs:
        if ins.action_type == "MOVE_TO" and ins.target_pos is not None:
            out.append((ins.agent_id, ins.target_pos))
    return out


def assign_instruction_stream(
    executor: TacticalExecutor,
    instructions: list,
    positions: dict[str, tuple[int, int]],
    coordination: TacticalCoordination,
    collector: MetricsCollector,
) -> None:
    """Queue instructions, batching adjacent parallel MOVE_TO for CBS when enabled."""
    i = 0
    while i < len(instructions):
        ins = instructions[i]
        if (
            ins.action_type == "MOVE_TO"
            and ins.target_pos is not None
            and coordination == TacticalCoordination.CBS
        ):
            batch = []
            seen: set[str] = set()
            j = i
            while j < len(instructions):
                cur = instructions[j]
                if cur.action_type != "MOVE_TO" or cur.target_pos is None:
                    break
                if cur.agent_id in seen:
                    break
                seen.add(cur.agent_id)
                batch.append(cur)
                j += 1
            if len(batch) >= 2:
                executor.assign_batch(batch, agent_positions=positions)
                for _ in batch:
                    collector.record_event(
                        "task_instruction_scheduled",
                        {
                            "agent_id": _.agent_id,
                            "action_type": "MOVE_TO",
                            "order_id": _.order_id,
                            "time": executor.env.now,
                        },
                    )
                i = j
                continue
            if len(batch) == 1:
                b0 = batch[0]
                executor.assign(b0)
                collector.record_event(
                    "task_instruction_scheduled",
                    {
                        "agent_id": b0.agent_id,
                        "action_type": b0.action_type,
                        "order_id": b0.order_id,
                        "time": executor.env.now,
                    },
                )
                i = j
                continue

        if ins.action_type == "MOVE_TO" and coordination == TacticalCoordination.GREEDY_UNCOORDINATED:
            executor.assign(ins)
        else:
            executor.assign(ins)
        collector.record_event(
            "task_instruction_scheduled",
            {
                "agent_id": ins.agent_id,
                "action_type": ins.action_type,
                "order_id": ins.order_id,
                "time": executor.env.now,
            },
        )
        i += 1


class EpisodeDriver:
    """Run one scenario to completion (or horizon) with telemetry."""

    def __init__(self, scenario: ScenarioSpec, collector: MetricsCollector | None = None) -> None:
        self.scenario = scenario
        #: Use explicit ``None`` default — collectors start with len()==0 which is falsy.
        self.collector = MetricsCollector() if collector is None else collector
        self.env: simpy.Environment
        self.warehouse: WarehouseState
        self.coordinator: StrategicCoordinator
        self.executor: TacticalExecutor
        self.translator = DomainTranslator()
        self.replanner = LocalReplanner()
        self.orders_by_id: dict[str, Order] = {}
        self._current_graph: TaskGraph | None = None
        self._positions: dict[str, tuple[int, int]] = {}
        self._run_config: RunConfig = scenario.run
        self._agent_loops_started = False
        self._plan_dirty = False

    def run(self) -> "EpisodeMetrics":
        from apex.evaluation.metrics import EpisodeMetrics

        buf = io.StringIO()
        ctx = contextlib.redirect_stdout(buf) if self._run_config.quiet else contextlib.nullcontext()
        with ctx:
            self._setup_world()
            self.collector.record_event(
                "episode_started",
                {
                    "horizon": self.scenario.horizon,
                    "scenario_id": self.scenario.id,
                    "seed": self.scenario.seed,
                },
            )
            np.random.seed(self.scenario.seed)
            self.env.process(self._orchestrator())
            for spec in self.scenario.orders:
                self.env.process(self._release_order(spec))
            if self.scenario.stochastic_disruption is not None and self._run_config.disruption_stochastic_enabled:
                cfg = dict(self.scenario.stochastic_disruption)
                cfg.setdefault("rng_seed", self.scenario.seed)
                gen = StochasticEventGenerator(self.env, self.warehouse, cfg)
                self.env.process(gen.run())
            for d in self.scenario.disruptions:
                self.env.process(self._scripted_disruption(d.time, d.kind, d.payload))
            self.env.run(until=self.scenario.horizon)
        return self.collector.compute_episode_metrics()

    def _setup_world(self) -> None:
        env, wh, registry = build_warehouse_and_registry(self.scenario)
        self.env = env
        self.warehouse = wh
        cbs = (
            CBSPlanner(wh.grid)
            if self._run_config.coordination == TacticalCoordination.CBS
            else None
        )
        self.executor = TacticalExecutor(env, cbs_planner=cbs)
        self.coordinator = StrategicCoordinator(
            mode=self._run_config.planning_mode,
            warehouse_state=wh,
            agent_registry=registry,
            settings=get_settings(),
        )
        for a in registry.get_all_agents():
            self._positions[a.id] = a.position

    def _release_order(self, spec: OrderSpec):
        yield self.env.timeout(max(0.0, spec.arrival_time))
        order = materialize_order(spec)
        self.warehouse.pending_orders.append(order)
        self.orders_by_id[order.id] = order
        self.collector.record_event(
            "order_released",
            {"order_id": order.id, "time": self.env.now},
        )

    def _scripted_disruption(self, t: float, kind: str, payload: dict):
        yield self.env.timeout(max(0.0, t))
        self.collector.record_event(
            "disruption",
            {"kind": kind, "time": self.env.now, **payload},
        )
        if kind == "shelf_block":
            sid = payload.get("shelf_id", "shelf_a")
            try:
                sh = self.warehouse.get_shelf(sid)
                orig = sh.capacity
                sh.capacity = max(1, int(payload.get("reduced_capacity", orig // 2)))
                dur = float(payload.get("duration", 10.0))
                yield self.env.timeout(dur)
                sh.capacity = orig
            except KeyError:
                pass
        elif kind == "inject_order":
            items = payload.get("items", [])
            if not items:
                items = [{"sku": "SKU-X", "shelf_zone_id": "shelf_a", "quantity": 1}]
            o = Order(
                id=str(payload.get("id", f"inj-{int(self.env.now)}")),
                items=[
                    OrderItem(
                        sku=str(it.get("sku", "SKU-X")),
                        shelf_zone_id=str(it.get("shelf_zone_id", "shelf_a")),
                        quantity=int(it.get("quantity", 1)),
                    )
                    for it in items
                ],
                priority=int(payload.get("priority", 5)),
                deadline=float(payload.get("deadline", self.env.now + 500)),
                status=OrderStatus.PENDING,
            )
            self.warehouse.pending_orders.append(o)
            self.orders_by_id[o.id] = o
        elif kind == "agent_fail":
            aid = payload.get("agent_id", "")
            reg = self.coordinator.agent_registry
            try:
                ag = reg.get_agent(aid)
                ag.should_stop = True
                ag.status = AgentStatus.FAILED
            except KeyError:
                pass
            res = self.replanner.handle(
                Disruption(
                    type=DisruptionType.AGENT_FAILURE,
                    agent_id=aid,
                    context={"reason": payload.get("reason", "scripted")},
                ),
                self.warehouse,
            )
            if isinstance(res, EscalationSignal):
                yield from self._handle_escalation(res)

    def _orchestrator(self):
        """Activate orders, plan when queues drain, and keep workers alive until horizon."""
        yield self.env.timeout(0.001)
        if not self._agent_loops_started:
            self._agent_loops_started = True
            for a in self.coordinator.agent_registry.get_all_agents():
                if not a.should_stop:
                    self.env.process(self._agent_loop(a.id))

        while self.env.now < self.scenario.horizon:
            agents = self.coordinator.agent_registry.get_all_agents()
            queues_empty = all(
                len(self.executor._agent_queues.get(a.id, [])) == 0  # noqa: SLF001
                for a in agents
                if not a.should_stop
            ) or not agents

            pending = [o for o in self.warehouse.pending_orders if o.status == OrderStatus.PENDING]

            if pending and queues_empty:
                for o in list(pending):
                    self.warehouse.pending_orders.remove(o)
                    o.status = OrderStatus.IN_PROGRESS
                    self.warehouse.active_orders.append(o)
                    self.collector.record_event(
                        "order_activated",
                        {"order_id": o.id, "time": self.env.now},
                    )
                self._plan_dirty = True

            active_inc = [
                o
                for o in self.warehouse.active_orders
                if o.status not in (OrderStatus.COMPLETE, OrderStatus.FAILED)
            ]

            if active_inc and queues_empty and self._plan_dirty:
                self._dispatch_plan(active_inc)
                self._plan_dirty = False

            yield self.env.timeout(0.12)

    def _dispatch_plan(self, orders: list[Order]) -> None:
        self._plan_dirty = False
        batch = OrderBatch(orders=list(orders))
        graph = self.coordinator.plan(batch)
        self._current_graph = graph
        use_mcts = self._run_config.planning_mode == PlanningMode.MCTS_AUGMENTED
        agent_ids = [a.id for a in self.coordinator.agent_registry.get_all_agents() if not a.should_stop]
        instrs = graph_to_instructions(
            graph,
            self.warehouse,
            self.orders_by_id,
            agent_ids,
            self.translator,
            use_mcts_agent_ids=use_mcts,
        )
        moves = _extract_move_sequence(instrs)
        gpaths = _greedy_paths_for_moves(moves, self._positions)
        conflicts = count_pairwise_spacetime_conflicts(gpaths)
        self.collector.record_event(
            "planned_spacetime_conflict_total",
            {"count": conflicts, "time": self.env.now},
        )
        self.executor.clear_all_queues()
        assign_instruction_stream(
            self.executor,
            instrs,
            self._positions,
            self._run_config.coordination,
            self.collector,
        )

    def _handle_escalation(self, esc: EscalationSignal):
        self.collector.record_event(
            "escalation",
            {"time": self.env.now, "reason": esc.reason},
        )
        if self._run_config.strategic_replan == StrategicReplanMode.DISABLED:
            return
        if self._run_config.strategic_replan == StrategicReplanMode.LOCAL_ONLY:
            return
        baseline = self._current_graph or self.coordinator._last_task_graph  # noqa: SLF001
        delta = self.coordinator.replan(esc, current_graph=baseline)
        self.collector.record_event("strategic_replan", {"time": self.env.now, "reason": esc.reason})
        nonempty = bool(delta.added or delta.removed or delta.modified)
        if baseline is not None and nonempty:
            try:
                err = validate_task_graph_delta(baseline, delta)
                if not err:
                    merged = apply_task_graph_delta(baseline, delta)
                    self._current_graph = merged
                    orders = [
                        self.orders_by_id[n.order_id]
                        for n in merged.nodes
                        if n.order_id and n.order_id in self.orders_by_id
                    ]
                    uniq = list({o.id: o for o in orders}.values())
                    if uniq:
                        self._dispatch_plan(uniq)
                        return
            except ValueError:
                pass
        # HTN fallback full replan (MAP off or empty delta)
        inc = [
            o
            for o in self.warehouse.active_orders
            if o.status not in (OrderStatus.COMPLETE, OrderStatus.FAILED)
        ]
        if inc:
            self._dispatch_plan(inc)

    def _agent_loop(self, agent_id: str):
        reg = self.coordinator.agent_registry
        try:
            agent = reg.get_agent(agent_id)
        except KeyError:
            return
        while self.env.now < self.scenario.horizon and not agent.should_stop:
            instr = self.executor.get_next_instruction(agent_id)
            if instr is None:
                dt = 0.2
                self.collector.record_event(
                    "agent_idle_tick",
                    {"agent_id": agent_id, "duration": dt},
                )
                yield self.env.timeout(dt)
                continue

            if instr.action_type == "MOVE_TO" and instr.target_pos is not None:
                yield from self._move_stepped(agent, instr.target_pos)
            elif instr.action_type in ("PICK", "PLACE_ON_CONVEYOR", "DISPATCH", "STAGE_HOLD"):
                dt = {"PICK": 1.0, "PLACE_ON_CONVEYOR": 0.8, "DISPATCH": 0.8, "STAGE_HOLD": 0.5}[
                    instr.action_type
                ]
                agent.status = AgentStatus.WORKING
                self.collector.record_event(
                    "agent_busy_tick",
                    {"agent_id": agent_id, "duration": dt, "kind": "WORK"},
                )
                yield self.env.timeout(dt)
                if instr.action_type == "PICK":
                    agent.total_work_done += 1
                agent.status = AgentStatus.IDLE
                if instr.action_type == "DISPATCH" and instr.order_id:
                    self._complete_order(instr.order_id)
            else:
                yield self.env.timeout(0.2)

            self.executor.mark_completed(instr)
            self.collector.record_event(
                "task_instruction_completed",
                {
                    "agent_id": agent_id,
                    "action_type": instr.action_type,
                    "order_id": instr.order_id,
                    "time": self.env.now,
                },
            )
            self._positions[agent_id] = agent.position

    def _complete_order(self, order_id: str) -> None:
        for o in self.warehouse.active_orders:
            if o.id == order_id:
                o.status = OrderStatus.COMPLETE
                self.collector.record_event(
                    "order_completed",
                    {"order_id": order_id, "time": self.env.now},
                )
                return

    def _move_stepped(self, agent, goal: tuple[int, int]):
        step_time = 1.0 / max(agent.capabilities.max_speed, 0.01)
        while agent.position != goal and not agent.should_stop:
            r, c = agent.position
            tr, tc = goal
            if r != tr:
                r += 1 if tr > r else -1
            elif c != tc:
                c += 1 if tc > c else -1
            else:
                break
            agent.status = AgentStatus.MOVING
            self.collector.record_event(
                "agent_busy_tick",
                {"agent_id": agent.id, "duration": step_time, "kind": "MOVE"},
            )
            yield self.env.timeout(step_time)
            agent.position = (r, c)
            agent.total_distance_traveled += 1.0
            self._check_cooccupation()
        agent.status = AgentStatus.IDLE

    def _check_cooccupation(self) -> None:
        pos_map: dict[tuple[int, int], list[str]] = defaultdict(list)
        for a in self.coordinator.agent_registry.get_all_agents():
            if not a.should_stop:
                pos_map[a.position].append(a.id)
        for cell, ids in pos_map.items():
            if len(ids) > 1:
                self.collector.record_event(
                    "executed_conflict",
                    {
                        "time": self.env.now,
                        "cell": cell,
                        "agent_a": ids[0],
                        "agent_b": ids[1],
                    },
                )

