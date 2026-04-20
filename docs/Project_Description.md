# APEX: Adaptive Planning and Execution System for Multi-Agent Strategic Orchestration 

## Overview
APEX (Adaptive Planning and Execution System) is a software system that demonstrates hierarchical, adaptive multi-agent planning through a realistic warehouse and logistics simulation. The system coordinates a fleet of heterogeneous agents — picker bots, carrier bots, sorter bots, and optionally human workers — across two distinct planning layers: a strategic planner that reasons over batches of orders and long-horizon objectives, and a tactical executor that translates those plans into real-time agent actions within a dynamic grid environment. A domain adapter bridges the two layers, converting abstract task specifications into warehouse-specific instructions (shelf IDs, conveyor zones, loading bays).
The system is designed as a research vehicle for studying how symbolic planning, multi-agent reinforcement learning, and game-theoretic coordination can be combined to produce robust, scalable behavior in partially observable, dynamically changing environments.

## Core Architecture
The architecture is composed of five interacting components, as shown in the diagram above.
* Strategic Planner (Layer 1) — The planner receives an incoming batch of customer orders and is responsible for goal decomposition, task assignment, and resource allocation. It uses Hierarchical Task Networks (HTN) to break orders into sub-tasks (pick, transport, stage, store, dispatch), then scores candidate assignments using MCTS over a multi-agent utility function that accounts for agent proximity, current load, battery state, and zone congestion. It produces a structured task plan: a directed acyclic graph of sub-tasks with agent assignments, deadlines, and dependencies.
* Domain Adapter (Layer 2) — The adapter translates the planner's abstract output into concrete warehouse-executable instructions. It resolves logical references (e.g., "pick item from zone C") into physical warehouse coordinates: specific shelf IDs, conveyor segments, staging lanes, and loading bay slots. It also manages constraint propagation — if a shelf is blocked, the adapter proactively re-queries the planner for an alternative sub-task assignment before the agent reaches the location.
* Tactical Executor (Layer 3) — Each agent runs a local executor that converts its assigned instructions into a sequence of low-level actions. A conflict-based search (CBS) algorithm handles multi-agent pathfinding on the grid, computing collision-free paths and maintaining a reservation table of occupied cells at each timestep. When local replanning is triggered (e.g., a dynamic obstacle, a failed pick, a new priority order), the executor resolves the disruption without invoking the full strategic planner — only escalating if the disruption invalidates the global task graph.
* Agent Pool — The agent fleet is heterogeneous by design, with each agent type having distinct capability profiles: speed, payload capacity, sensor range, battery constraints, and available action primitives. This heterogeneity forces the planner to reason about agent-task compatibility, not just proximity.
* Warehouse Simulation Environment — A grid-based simulation that models shelves, conveyors, loading bays, and open transit corridors. The environment is partially observable (agents have limited sensor range), stochastic (new orders arrive mid-session, agents can fail), and dynamic (shelves may be temporarily blocked, conveyor speeds vary). This is implemented in Python using a custom grid engine, with a real-time visualization layer for monitoring agent behavior.

## Key Technical Contributions
* Hierarchical Planning with Adaptive Re-planning — The system's primary research contribution is a clean separation between strategic and tactical planning, with a well-defined escalation protocol between them. Most disruptions are handled at the tactical layer; only genuine goal-level conflicts escalate to the strategic planner, minimizing expensive global re-computation.
* Multi-Agent Pathfinding under Uncertainty — The CBS-based path planner is extended with probabilistic reservation tables that account for uncertain agent positions arising from sensor noise. This moves beyond standard deterministic MAPF (multi-agent pathfinding) formulations toward something applicable in real-world settings.
* Communication and Theory of Mind — Agents share intention vectors via a Graph Neural Network (GNN) over a dynamic agent-interaction graph. This allows agents to anticipate teammates' future positions and task states without full communication, enabling decentralized coordination that degrades gracefully when communication is limited or delayed.
* Learning-Augmented Planning — The system integrates a MAPPO (multi-agent proximal policy optimization) policy for low-level agent behavior, pre-trained via self-play in the simulation. The learned policy is used as a warm-start for the CBS path planner, reducing the search space significantly in densely populated warehouse configurations.

## Simulation Scenario Design
The primary test scenario is a mid-scale warehouse fulfillment session: 3–6 agents operating in a 30×30 grid with 12 shelf zones, 4 conveyor segments, and 2 loading bays. A batch of 20–40 orders arrives at session start, with 5–10 additional orders injected mid-session. Agent failures are randomly triggered at a configurable rate to test robustness.
Evaluation is structured around four dimensions:
Task completion rate and order throughput measure planning effectiveness. Time-to-completion and inter-agent idle time measure execution efficiency. Performance under mid-session disruptions (new orders, agent failures, blocked shelves) measures adaptability. The rate of path conflicts, redundant coverage, and successful task handoffs measures coordination quality. Scalability experiments increase agent count and warehouse size to characterize how performance degrades.

## Implementation Plan
The system is built in Python, with the following module structure:
The simulation engine implements the grid world, agent kinematics, shelf state, conveyor dynamics, and a discrete-event clock. It exposes a step-based API that both the strategic planner and tactical executor query.
The strategic planner module wraps an HTN planner (using the pyhop or pytask library) and a MCTS solver for task assignment optimization.
The domain adapter module maintains a live warehouse state map and provides resolution services for the planner's abstract task references.
The tactical executor module implements CBS-based multi-agent pathfinding with the MAPPO warm-start integration, plus the GNN for agent intention modeling.
The visualization layer provides a real-time overhead grid view of agent positions, task assignments, and plan status, plus a dashboard of the evaluation metrics.

## Keywords
long-horizon goal decomposition, real-time adaptation, coordination under partial observability, learning from experience
hierarchical planning, adaptive re-planning, Multi-Agent Reinforcement Learning (MARL - MAPPO), symbolic planning (HTN), stochastic search (MCTS), graph communication (GNN)
