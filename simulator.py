"""Симулятор Forge & Die v2.0 (каркас).

Шаг 1: инициализация, ходьба по тайлам, кузница, переход на этаж.
Без боя, событий, сокровищ, найма, снаряжения.

Последовательность хода:
1. Начало хода (бот стоит на клетке, куда пришёл в прошлом ходу).
2. Свободная фаза (пока заглушка).
3. Перемещение (step_forward).
4. resolve_tile — список доступных Action.
5. bot_decide — выбор одного Action.
6. Обработка Action (переход на этаж / пропуск).
7. Запись шага в лог.
"""

import argparse
import json
import os
import random
import time
from datetime import datetime

import config
import data


# ============================================================
# Утилиты
# ============================================================

def roll_d6() -> int:
    """Бросок d6."""
    return random.randint(1, 6)


def snapshot_boiets(boiets: dict) -> dict:
    """Снимок бойца для лога (то, что покажет player.py)."""
    return {
        "class": boiets["class"],
        "level": boiets["level"],
        "hp": boiets["hp"],
        "max_hp": boiets["max_hp"],
        "xp": boiets["xp"],
        "gold": boiets["gold"],
    }


# ============================================================
# Инициализация
# ============================================================

def create_boiets(class_name: str) -> dict:
    """Создаёт бойца 1-го уровня."""
    level_data = data.CLASSES[class_name][0]  # индекс 0 — уровень 1
    return {
        "class": class_name,
        "level": 1,
        "hp": level_data["hp"],
        "max_hp": level_data["hp"],
        "xp": 0,
        "gold": 10,
        "inventory": [],
        "effects": [],
        "ability_uses": {},
    }


def create_party(class_name: str) -> list:
    """Создаёт команду из одного бойца."""
    return [create_boiets(class_name)]


def create_floor_state(floor_index: int) -> dict:
    """Создаёт состояние этажа: линия тайлов, колода, позиция."""
    tiles_deck = []
    for t in data.TILES:
        if t["in_deck"]:
            tile_copy = t.copy()
            tile_copy["visited"] = False
            tiles_deck.append(tile_copy)
    random.shuffle(tiles_deck)

    start_tile = data.TILES[0].copy()
    start_tile["visited"] = True  # старт уже посещён

    return {
        "floor_index": floor_index,
        "tiles": [start_tile],
        "position": 0,
        "floor_steps": 0,
        "forge_found": False,
        "tiles_deck": tiles_deck,
    }


# ============================================================
# Свободная фаза (заглушка)
# ============================================================

def free_phase(party: list, floor_state: dict) -> None:
    """Свободная фаза в начале хода: эликсиры, аура, чутьё, болезнь.

    На каркасе — пусто. Позже сюда войдут эффекты.
    """
    pass


# ============================================================
# Ходьба
# ============================================================

def step_forward(floor_state: dict) -> dict:
    """Шаг вперёд: тянет новый тайл или двигается по линии.

    Возвращает тайл, на который встал бот, или None, если колода пуста.
    """
    if floor_state["position"] == len(floor_state["tiles"]) - 1:
        # на последнем тайле — тянем новый
        if not floor_state["tiles_deck"]:
            return None
        tile = floor_state["tiles_deck"].pop(0)
        floor_state["tiles"].append(tile)
        if tile["type"] == data.TileType.FORGE:
            floor_state["forge_found"] = True

    floor_state["position"] += 1
    floor_state["floor_steps"] += 1
    tile = floor_state["tiles"][floor_state["position"]]
    tile["visited"] = True  # отмечаем посещение
    return tile


def step_back(floor_state: dict) -> dict:
    """Шаг назад по линии (не используется в каркасе, но нужен позже)."""
    if floor_state["position"] > 0:
        floor_state["position"] -= 1
        floor_state["floor_steps"] += 1
    return floor_state["tiles"][floor_state["position"]]


# ============================================================
# Разрешение тайла (варианты действий)
# ============================================================

def resolve_tile(floor_state: dict, party: list) -> list:
    """Возвращает список доступных Action на текущем тайле.

    Не принимает решение — только предлагает варианты.
    """
    tile = floor_state["tiles"][floor_state["position"]]

    if tile["type"] == data.TileType.FORGE:
        return [data.Action.FORGE, data.Action.SKIP]

    # монстр, сокровищница, событие, лагерь, торговец, старт — пока только пропуск
    return [data.Action.SKIP]


# ============================================================
# Выбор бота
# ============================================================

def bot_decide(available: list, party: list, floor_state: dict, profile: str) -> int:
    """Выбирает одно Action из списка доступных по профилю.

    Rusher: если есть FORGE — берёт FORGE, иначе SKIP.
    """
    if profile == "rusher":
        if data.Action.FORGE in available:
            return data.Action.FORGE
        return data.Action.SKIP

    # по умолчанию — первый вариант
    return available[0]


# ============================================================
# Главный цикл партии
# ============================================================

def play_one_game(class_name: str, profile: str, seed: int) -> dict:
    """Одна партия. Возвращает журнал."""
    random.seed(seed)
    party = create_party(class_name)
    floor_index = 0
    floor_state = create_floor_state(floor_index)
    log = {
        "seed": seed,
        "profile": profile,
        "class": class_name,
        "steps": [],
    }

    step_num = 0
    while floor_index < 4:
        # 1. свободная фаза
        free_phase(party, floor_state)

        # 2. перемещение
        tile = step_forward(floor_state)
        if tile is None:
            break  # колода пуста

        # 3. варианты действий на тайле
        available = resolve_tile(floor_state, party)

        # 4. выбор бота
        action = bot_decide(available, party, floor_state, profile)

        # 5. запись шага в лог
        log["steps"].append({
            "step": step_num,
            "floor": floor_index,
            "tile_index": floor_state["position"],
            "tile_type": int(tile["type"]),
            "available": [int(a) for a in available],
            "action": int(action),
            "party": [snapshot_boiets(b) for b in party],
        })
        step_num += 1

        # 6. обработка действия
        if action == data.Action.FORGE:
            floor_index += 1
            if floor_index >= 4:
                break
            floor_state = create_floor_state(floor_index)

        # защита от бесконечного цикла
        if floor_state["floor_steps"] > config.MAX_FLOOR_STEPS:
            break

    log["final_floor"] = floor_index
    log["result"] = "reached_floor_4" if floor_index >= 4 else "stuck"
    return log


# ============================================================
# Прогон N партий
# ============================================================
def make_run_id() -> str:
    """Генерирует run_id вида YYYY-MM-DD-NNN."""
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    existing = [d for d in os.listdir(config.LOGS_DIR) if d.startswith(today)]
    nnn = len(existing) + 1
    return f"{today}-{nnn:03d}"


def print_progress(current: int, total: int, stats: dict, elapsed: float) -> None:
    """Одна строка прогресса (перерисовка через \\r)."""
    pct = current / total * 100
    line = (
        f"[{current}/{total}] {pct:5.1f}% | "
        f"reach4: {stats['reached_floor_4']} | "
        f"stuck: {stats['stuck']} | "
        f"{elapsed:.1f}s"
    )
    print(f"\r{line}", end="", flush=True)


def run_simulation(n_games: int, class_name: str, profile: str,
                   seed_base: int = None, no_progress: bool = False) -> None:
    """Прогоняет N партий, пишет логи, выводит статистику."""
    run_id = make_run_id()
    run_dir = os.path.join(config.LOGS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    started_at = datetime.now().isoformat()
    stats = {"reached_floor_4": 0, "stuck": 0}
    start_time = time.time()

    for i in range(n_games):
        seed = (seed_base + i) if seed_base is not None else None
        game_log = play_one_game(class_name, profile, seed)
        stats[game_log["result"]] += 1

        game_path = os.path.join(run_dir, f"game_{i+1:04d}.json")
        with open(game_path, "w", encoding="utf-8") as f:
            json.dump(game_log, f, ensure_ascii=False, indent=2)

        if not no_progress:
            print_progress(i + 1, n_games, stats, time.time() - start_time)

    if not no_progress:
        print()

    finished_at = datetime.now().isoformat()

    meta = {
        "run_id": run_id,
        "class": class_name,
        "profile": profile,
        "n_games": n_games,
        "project_version": config.PROJECT_VERSION,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(os.path.join(run_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"Готово. Логи: {run_dir}")
    print(f"Дошли до 4-го этажа: {stats['reached_floor_4']} / {n_games}")
    print(f"Застряли: {stats['stuck']}")


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forge & Die Simulator")
    parser.add_argument("--games", type=int, default=config.DEFAULT_GAMES,
                        help="число партий")
    parser.add_argument("--class", dest="class_name", default=config.DEFAULT_CLASS,
                        help="класс бойца (warrior)")
    parser.add_argument("--profile", default="rusher",
                        help="профиль бота (rusher)")
    parser.add_argument("--seed", type=int, default=None,
                        help="базовый сид (для воспроизводимости)")
    parser.add_argument("--no-progress", action="store_true",
                        help="не выводить прогресс")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_simulation(
        n_games=args.games,
        class_name=args.class_name,
        profile=args.profile,
        seed_base=args.seed,
        no_progress=args.no_progress,
    )


if __name__ == "__main__":
    main()