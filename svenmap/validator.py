"""Минимальная проверка проходимости по сетке.

Это не замена игровому тесту: здесь проверяется только то, что между
стартом и целью есть геометрический коридор, достаточный для hull игрока.
Пока используется на этапе 1, чтобы подтвердить «по карте можно пройти».
"""

from collections import deque

PLAYER_RADIUS = 16.0   # половина ширины hull игрока GoldSrc
PLAYER_HEIGHT = 72.0   # высота hull игрока
CELL = 16.0
Z_FEET = 24.0          # высота точек ног над полом (пол заканчивается на z=16)


def parse_origin(text):
    return tuple(float(v) for v in text.split())


def unreachable_areas(solids, spec, z=24):
    """Список id площадей, центры которых недостижимы из старта."""
    grid = build_grid(solids, z=z)
    start = spec.area_center(spec.start)
    bad = []
    for area in spec.areas:
        ok, _steps, _path, _reason = find_path(
            grid, start, spec.area_center(area.id)
        )
        if not ok:
            bad.append(area.id)
    return bad


def reachable_areas_ids(solids, spec, z=24):
    """Множество id площадей, центры которых достижимы из старта."""
    grid = build_grid(solids, z=z)
    start = spec.area_center(spec.start)
    result = set()
    for area in spec.areas:
        ok, _steps, _path, _reason = find_path(
            grid, start, spec.area_center(area.id)
        )
        if ok:
            result.add(area.id)
    return result


def spawn_is_clear(solids, origin, z=28, radius=16, height=72):
    """Проверить, что hull игрока в точке спавна не пересекает стену/пол."""
    x, y = origin[0], origin[1]
    for s in solids:
        if not (s.z0 < z + height and s.z1 > z):
            continue
        if (s.x0 - radius < x < s.x1 + radius
                and s.y0 - radius < y < s.y1 + radius):
            return False
    return True


def build_grid(solids, z=Z_FEET, radius=PLAYER_RADIUS,
               height=PLAYER_HEIGHT, cell=CELL, margin=64.0):
    xs = [v for s in solids for v in (s.x0, s.x1)]
    ys = [v for s in solids for v in (s.y0, s.y1)]
    min_x, min_y = min(xs) - margin, min(ys) - margin
    max_x, max_y = max(xs) + margin, max(ys) + margin
    nx = int((max_x - min_x) // cell) + 1
    ny = int((max_y - min_y) // cell) + 1

    blocked = set()
    for i in range(nx):
        for j in range(ny):
            x = min_x + i * cell + cell / 2
            y = min_y + j * cell + cell / 2
            for s in solids:
                # Пересечение по высоте: solid должен попадать в hull игрока.
                if not (s.z0 < z + height and s.z1 > z):
                    continue
                if (s.x0 - radius <= x <= s.x1 + radius
                        and s.y0 - radius <= y <= s.y1 + radius):
                    blocked.add((i, j))
                    break

    return {
        "min_x": min_x, "min_y": min_y,
        "nx": nx, "ny": ny,
        "cell": cell, "blocked": blocked,
    }


def to_cell(grid, point):
    return (
        int((point[0] - grid["min_x"]) // grid["cell"]),
        int((point[1] - grid["min_y"]) // grid["cell"]),
    )


def find_path(grid, start_xy, goal_xy):
    """BFS по 4 соседям. Возвращает (найден, число шагов, путь)."""
    start = to_cell(grid, start_xy)
    goal = to_cell(grid, goal_xy)
    blocked = grid["blocked"]

    if start in blocked:
        return False, 0, [], "стартовая точка заблокирована"
    if goal in blocked:
        return False, 0, [], "целевая точка заблокирована"

    queue = deque([start])
    came_from = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return True, len(path) - 1, path, ""

        i, j = current
        for neighbour in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            ni, nj = neighbour
            if not (0 <= ni < grid["nx"] and 0 <= nj < grid["ny"]):
                continue
            if neighbour in blocked or neighbour in came_from:
                continue
            came_from[neighbour] = current
            queue.append(neighbour)

    return False, 0, [], "путь не найден"


def ascii_map(grid, path=(), start=None, goal=None, max_x=100, max_y=40):
    """Компактный вид сетки для проверки глазами."""
    step_x = max(1, grid["nx"] // max_x)
    step_y = max(1, grid["ny"] // max_y)
    path_set = set(path)
    lines = []
    for j in range(0, grid["ny"], step_y):
        row = []
        for i in range(0, grid["nx"], step_x):
            cell = (i, j)
            if cell == start:
                row.append("S")
            elif cell == goal:
                row.append("G")
            elif cell in path_set:
                row.append("*")
            elif cell in grid["blocked"]:
                row.append("#")
            else:
                row.append(".")
        lines.append("".join(row))
    return "\n".join(lines)
