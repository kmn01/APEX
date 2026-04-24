"""Pygame visualization UI for warehouse simulation and planning."""

from __future__ import annotations

import math
import sys
from typing import Any

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class WarehouseVisualizer:
    """Real-time visualization of warehouse simulation using pygame."""

    def __init__(
        self,
        warehouse_state: Any,
        width: int = 1200,
        height: int = 900,
        cell_size: int = 30,
    ):
        if not PYGAME_AVAILABLE:
            raise ImportError("pygame-ce is required for visualization")

        self.warehouse_state = warehouse_state
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.running = True
        self.paused = False

        self.panel_width = 278
        self._grid_origin = (14, 56)

        pygame.init()
        pygame.display.set_caption("APEX — warehouse simulation")
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()

        ui = "segoeui" if sys.platform == "win32" else None
        try:
            self.font_small = pygame.font.SysFont(ui, 15) if ui else pygame.font.Font(None, 17)
            self.font_medium = pygame.font.SysFont(ui, 18, bold=True) if ui else pygame.font.Font(None, 21)
            self.font_large = pygame.font.SysFont(ui, 22, bold=True) if ui else pygame.font.Font(None, 26)
            self.font_tiny = pygame.font.SysFont(ui, 12) if ui else pygame.font.Font(None, 14)
        except (OSError, pygame.error):
            self.font_small = pygame.font.Font(None, 17)
            self.font_medium = pygame.font.Font(None, 21)
            self.font_large = pygame.font.Font(None, 26)
            self.font_tiny = pygame.font.Font(None, 14)

        self.colors = {
            "screen_bg": (22, 24, 32),
            "world_bg": (28, 32, 44),
            "floor_a": (40, 46, 62),
            "floor_b": (36, 41, 56),
            "grid_line": (52, 58, 74),
            "shelf_base": (68, 108, 142),
            "shelf_hi": (110, 150, 188),
            "shelf_lo": (48, 78, 102),
            "conveyor_base": (140, 82, 42),
            "conveyor_hi": (190, 128, 72),
            "bay_base": (52, 130, 88),
            "bay_hi": (92, 190, 128),
            "obstacle": (24, 26, 32),
            "path_glow": (60, 52, 28),
            "path_core": (255, 214, 102),
            "path_vertex": (255, 250, 220),
            "agent_shadow": (8, 8, 12),
            "agent_picker": (232, 72, 72),
            "agent_picker_hi": (255, 140, 140),
            "agent_carrier": (72, 128, 255),
            "agent_sorter": (72, 220, 120),
            "text_dark": (228, 230, 238),
            "text_muted": (160, 165, 180),
            "panel_bg": (30, 34, 48),
            "panel_border": (70, 76, 98),
            "panel_accent": (90, 140, 255),
            "overlay_paused": (0, 0, 0, 140),
        }

    def _cell_rect(self, row: int, col: int) -> pygame.Rect:
        ox, oy = self._grid_origin
        return pygame.Rect(
            ox + col * self.cell_size,
            oy + row * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    def _cell_center(self, row: int, col: int) -> tuple[float, float]:
        ox, oy = self._grid_origin
        x = ox + col * self.cell_size + self.cell_size // 2
        y = oy + row * self.cell_size + self.cell_size // 2
        return x, y

    def _blit_text_outlined(
        self,
        surf: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        pos: tuple[int, int],
        outline_color: tuple[int, int, int] = (18, 20, 30),
    ) -> None:
        x, y = pos
        base = font.render(text, True, color)
        edge = font.render(text, True, outline_color)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            surf.blit(edge, (x + dx, y + dy))
        surf.blit(base, (x, y))

    def draw_header(self, time: float, fps: float) -> None:
        title = self.font_large.render("APEX warehouse", True, self.colors["text_dark"])
        sub = self.font_small.render(
            f"Sim time {time:6.1f}s   ·   {fps:4.0f} FPS   ·   Space pause",
            True,
            self.colors["text_muted"],
        )
        self.screen.blit(title, (self._grid_origin[0], 10))
        self.screen.blit(sub, (self._grid_origin[0], 34))

    def draw_grid(self, sim_time: float) -> None:
        grid = self.warehouse_state.grid
        stripe_phase = (sim_time * 3.5 * self.cell_size) % (self.cell_size * 2)

        for row in range(grid.rows):
            for col in range(grid.cols):
                rect = self._cell_rect(row, col)
                cell_type = grid.get_cell_type((row, col))
                name = cell_type.name

                if name == "OBSTACLE":
                    pygame.draw.rect(self.screen, self.colors["obstacle"], rect)
                elif name == "SHELF":
                    pygame.draw.rect(self.screen, self.colors["shelf_lo"], rect)
                    inset = rect.inflate(-4, -4)
                    pygame.draw.rect(self.screen, self.colors["shelf_base"], inset)
                    pygame.draw.line(
                        self.screen,
                        self.colors["shelf_hi"],
                        inset.topleft,
                        (inset.right - 1, inset.top),
                        2,
                    )
                    pygame.draw.line(
                        self.screen,
                        self.colors["shelf_hi"],
                        inset.topleft,
                        (inset.left, inset.bottom - 1),
                        2,
                    )
                elif name == "CONVEYOR":
                    pygame.draw.rect(self.screen, self.colors["conveyor_base"], rect)
                    inner = rect.inflate(-6, -6)
                    for k in range(-2, 4):
                        x0 = inner.left + int(stripe_phase + k * (self.cell_size // 2)) % (inner.width + self.cell_size)
                        pygame.draw.line(
                            self.screen,
                            self.colors["conveyor_hi"],
                            (x0, inner.top),
                            (x0 - self.cell_size // 3, inner.bottom),
                            2,
                        )
                elif name == "BAY":
                    pygame.draw.rect(self.screen, self.colors["bay_base"], rect)
                    pygame.draw.rect(self.screen, self.colors["bay_hi"], rect.inflate(-6, -6), 2)
                else:
                    alt = (row + col) % 2
                    c = self.colors["floor_a"] if alt else self.colors["floor_b"]
                    pygame.draw.rect(self.screen, c, rect)

                pygame.draw.rect(self.screen, self.colors["grid_line"], rect, 1)

    def draw_zone_hints(self) -> None:
        wh = self.warehouse_state
        for zone in getattr(wh, "shelf_zones", []) or []:
            if not zone.positions:
                continue
            row, col = zone.positions[0]
            rect = self._cell_rect(row, col)
            label = self.font_tiny.render(zone.id[:10], True, (230, 240, 255))
            self.screen.blit(label, (rect.x + 3, rect.y + 2))

        for bay in getattr(wh, "bays", []) or []:
            row, col = bay.position
            rect = self._cell_rect(row, col)
            label = self.font_tiny.render(bay.id[:10], True, (200, 255, 220))
            self.screen.blit(label, (rect.x + 3, rect.y + rect.height - 14))

        for conv in getattr(wh, "conveyors", []) or []:
            if not conv.positions:
                continue
            mid = conv.positions[len(conv.positions) // 2]
            r, c = mid
            cx, cy = self._cell_center(r, c)
            vec = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}.get(
                getattr(conv, "direction", "E") or "E", (1, 0)
            )
            ax = cx + vec[0] * (self.cell_size * 0.22)
            ay = cy + vec[1] * (self.cell_size * 0.22)
            pygame.draw.polygon(
                self.screen,
                (255, 220, 160),
                [
                    (ax + vec[0] * 8, ay + vec[1] * 8),
                    (ax - vec[1] * 5 - vec[0] * 4, ay + vec[0] * 5 - vec[1] * 4),
                    (ax + vec[1] * 5 - vec[0] * 4, ay - vec[0] * 5 - vec[1] * 4),
                ],
            )

    def draw_paths(self, paths: dict[str, list[tuple[int, int]]]) -> None:
        for _agent_id, path in paths.items():
            if not path or len(path) < 2:
                continue

            points = [
                (int(self._cell_center(pos[0], pos[1])[0]), int(self._cell_center(pos[0], pos[1])[1]))
                for pos in path
            ]

            if len(points) > 1:
                pygame.draw.lines(self.screen, self.colors["path_glow"], False, points, width=6)
                pygame.draw.lines(self.screen, self.colors["path_core"], False, points, width=3)
                for px, py in points[1:-1]:
                    pygame.draw.circle(self.screen, self.colors["path_vertex"], (px, py), 4)
                    pygame.draw.circle(self.screen, self.colors["path_core"], (px, py), 2)

    def draw_agents(
        self,
        agents: list[Any],
        paths: dict[str, list[tuple[int, int]]] | None,
    ) -> None:
        for agent in agents:
            row, col = agent.position
            x, y = self._cell_center(row, col)
            radius = self.cell_size // 3

            nxt: tuple[int, int] | None = None
            if paths and agent.id in paths:
                plist = paths[agent.id]
                if plist:
                    for i, p in enumerate(plist):
                        if p == (row, col) and i + 1 < len(plist):
                            nxt = plist[i + 1]
                            break
                    if nxt is None and plist and (row, col) not in plist:
                        nxt = plist[0]

            if nxt is not None:
                nr, nc = nxt
                dx = nc - col
                dy = nr - row
                length = math.hypot(dx, dy) or 1.0
                fx = x + (dx / length) * (radius + 4)
                fy = y + (dy / length) * (radius + 4)
                pygame.draw.line(
                    self.screen,
                    (255, 255, 255),
                    (int(x), int(y)),
                    (int(fx), int(fy)),
                    3,
                )
                pygame.draw.circle(self.screen, (255, 255, 255), (int(fx), int(fy)), 4)

            pygame.draw.circle(
                self.screen, self.colors["agent_shadow"], (int(x) + 3, int(y) + 4), int(radius) + 2
            )

            agent_type_lower = agent.type.value.lower()
            base = self.colors.get(f"agent_{agent_type_lower}", (200, 200, 210))
            pygame.draw.circle(self.screen, base, (int(x), int(y)), int(radius))

            hi = self.colors.get(f"agent_{agent_type_lower}_hi")
            if hi:
                pygame.draw.circle(self.screen, hi, (int(x) - 2, int(y) - 2), max(2, int(radius) // 3))

            status_colors = {
                "IDLE": (110, 220, 140),
                "MOVING": (255, 220, 80),
                "WORKING": (255, 150, 70),
                "BLOCKED": (255, 60, 60),
                "FAILED": (140, 40, 40),
            }
            status_color = status_colors.get(agent.status.value, (140, 140, 150))
            pygame.draw.circle(self.screen, status_color, (int(x), int(y)), int(radius) + 3, 3)

            short_id = agent.id[-8:] if len(agent.id) > 8 else agent.id
            tw = self.font_small.size(short_id)[0]
            self._blit_text_outlined(
                self.screen,
                self.font_small,
                short_id,
                (255, 255, 255),
                (int(x) - tw // 2, int(y) - 8),
            )

            cap = max(agent.capabilities.battery_capacity, 1e-6)
            battery_pct = max(0.0, min(1.0, agent.battery_level / cap))
            battery_color = (
                (60, 200, 110) if battery_pct > 0.5 else (220, 160, 60) if battery_pct > 0.2 else (220, 70, 70)
            )
            bw = int((radius * 1.6) * battery_pct)
            bx = int(x - radius * 0.8)
            by = int(y + radius + 4)
            pygame.draw.rect(self.screen, (20, 22, 28), (bx, by, int(radius * 1.6), 5), border_radius=2)
            if bw > 0:
                pygame.draw.rect(self.screen, battery_color, (bx, by, bw, 5), border_radius=2)

    def draw_info_panel(
        self,
        agents: list[Any],
        time: float,
        actions: dict[str, str],
        fps: float,
    ) -> None:
        panel_x = self.width - self.panel_width - 10
        panel_y = 10
        panel_h = min(self.height - 20, 420)

        panel_rect = pygame.Rect(panel_x, panel_y, self.panel_width, panel_h)
        pygame.draw.rect(self.screen, self.colors["panel_bg"], panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.colors["panel_border"], panel_rect, 2, border_radius=8)

        accent = pygame.Rect(panel_x, panel_y, 4, panel_h)
        pygame.draw.rect(self.screen, self.colors["panel_accent"], accent, border_radius=2)

        x0 = panel_x + 14
        y = panel_y + 12

        title = self.font_large.render("Fleet status", True, self.colors["text_dark"])
        self.screen.blit(title, (x0, y))
        y += 30

        time_text = self.font_small.render(f"Simulation clock: {time:.2f} s", True, self.colors["text_muted"])
        self.screen.blit(time_text, (x0, y))
        y += 22

        fps_t = self.font_small.render(f"Render: {fps:.0f} FPS", True, self.colors["text_muted"])
        self.screen.blit(fps_t, (x0, y))
        y += 26

        if self.paused:
            banner = self.font_medium.render("PAUSED", True, (255, 200, 90))
            self.screen.blit(banner, (x0, y))
            y += 26

        if agents:
            idle_count = sum(1 for a in agents if a.status.value == "IDLE")
            moving_count = sum(1 for a in agents if a.status.value == "MOVING")
            working_count = sum(1 for a in agents if a.status.value == "WORKING")
            failed_count = sum(1 for a in agents if a.status.value == "FAILED")

            self.screen.blit(
                self.font_small.render(f"Agents: {len(agents)}", True, self.colors["text_dark"]),
                (x0, y),
            )
            y += 20
            for label, count, color in (
                ("Idle", idle_count, (120, 210, 150)),
                ("Moving", moving_count, (240, 210, 120)),
                ("Working", working_count, (240, 160, 110)),
                ("Failed", failed_count, (240, 100, 100)),
            ):
                self.screen.blit(
                    self.font_tiny.render(f"  {label}: {count}", True, color),
                    (x0, y),
                )
                y += 18

            y += 6
            avg_b = sum(a.battery_level for a in agents) / len(agents)
            self.screen.blit(
                self.font_small.render(f"Avg battery: {avg_b:.0f}", True, self.colors["text_muted"]),
                (x0, y),
            )
            y += 22
            total_work = sum(a.total_work_done for a in agents)
            self.screen.blit(
                self.font_small.render(f"Work units done: {total_work}", True, self.colors["text_muted"]),
                (x0, y),
            )
            y += 28

        self.screen.blit(self.font_small.render("Telemetry", True, self.colors["text_dark"]), (x0, y))
        y += 22
        for agent_id, action in list(actions.items())[:8]:
            line = f"{agent_id}: {action}"
            if len(line) > 36:
                line = line[:33] + "..."
            self.screen.blit(
                self.font_tiny.render(line, True, (180, 190, 230)),
                (x0, y),
            )
            y += 17

        y = panel_rect.bottom - 52
        self.screen.blit(
            self.font_tiny.render("Status ring = agent state", True, self.colors["text_muted"]),
            (x0, y),
        )
        y += 16
        self.screen.blit(
            self.font_tiny.render("Arrow = next route waypoint", True, self.colors["text_muted"]),
            (x0, y),
        )

    def draw_pause_overlay(self) -> None:
        grid = self.warehouse_state.grid
        ox, oy = self._grid_origin
        gw = grid.cols * self.cell_size
        gh = grid.rows * self.cell_size
        overlay = pygame.Surface((gw, gh), pygame.SRCALPHA)
        overlay.fill((12, 14, 22, 130))
        self.screen.blit(overlay, (ox, oy))
        tw = self.font_large.size("PAUSED")[0]
        mx = ox + gw // 2 - tw // 2
        my = oy + gh // 2 - self.font_large.get_height() // 2
        self._blit_text_outlined(
            self.screen, self.font_large, "PAUSED", (255, 240, 200), (mx, my)
        )

    def render(
        self,
        agents: list[Any] | None = None,
        paths: dict[str, list[tuple[int, int]]] | None = None,
        time: float = 0.0,
        actions: dict[str, str] | None = None,
    ) -> bool:
        """Render one frame. Return False if should exit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.paused = not self.paused

        self.screen.fill(self.colors["screen_bg"])

        ox, oy = self._grid_origin
        grid = self.warehouse_state.grid
        world_rect = pygame.Rect(
            0,
            0,
            ox + grid.cols * self.cell_size + 12,
            self.height,
        )
        pygame.draw.rect(self.screen, self.colors["world_bg"], world_rect)

        fps = self.clock.get_fps()

        self.draw_header(time, fps)
        self.draw_grid(time)
        self.draw_zone_hints()

        if paths:
            self.draw_paths(paths)

        if agents:
            self.draw_agents(agents, paths)

        if self.paused:
            self.draw_pause_overlay()

        self.draw_info_panel(agents or [], time, actions or {}, fps)

        pygame.display.flip()
        self.clock.tick(60 if not self.paused else 15)
        return self.running

    def close(self) -> None:
        """Clean up pygame."""
        pygame.quit()


if __name__ == "__main__":
    print("Visualization module loaded successfully")
    print(f"Pygame available: {PYGAME_AVAILABLE}")
