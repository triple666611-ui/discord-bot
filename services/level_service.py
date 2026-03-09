def xp_for_next_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


def level_from_xp(total_xp: int) -> tuple[int, int]:
    level = 0
    remaining = max(0, total_xp)
    while True:
        need = xp_for_next_level(level)
        if remaining < need:
            return level, remaining
        remaining -= need
        level += 1


def xp_from_level(level: int) -> int:
    total = 0
    for current in range(max(0, level)):
        total += xp_for_next_level(current)
    return total
