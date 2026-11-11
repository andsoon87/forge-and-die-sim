"""Симулятор Forge & Die v2.0 (каркас).

Реализовано:
- ходьба по линии тайлов, кузница, переход на этаж;
- бой с монстрами (инициатива, атаки, смерть, XP, level-up);
- побег из боя (Action.FLEE);
- level-up в свободной фазе.

Последовательность хода:
1. Начало хода (бот стоит на клетке, куда пришёл в прошлом ходу).
2. Свободная фаза (level-up, позже -- эликсиры, аура, чутьё, болезнь).
3. bot_move -- Перемещение.
4. resolve_tile -- список доступных Action.
5. bot_decide -- выбор одного Action.
6. Обработка Action (переход на этаж / пропуск / бой / побег).
7. Запись шага в лог.

СОГЛАШЕНИЕ: структуры из data.py только читаются, не мутируются.
Изменяемое состояние живёт в копиях тайлов внутри floor_state.
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
    level_data = data.CLASSES[class_name][0]  # индекс 0 -- уровень 1
    return {
        "class": class_name,
        "level": 1,
        "hp": level_data["hp"],
        "max_hp": level_data["hp"],
        "at": level_data["at"],
        "df": level_data["df"],
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
    start_tile = data.TILES[0].copy()
    start_tile["id"] = 0
    start_tile["visited"] = True  # старт уже посещён
    
    tiles_deck = []
    for i, t in enumerate(data.TILES):
        if i == 0:
            continue  # старт уже добавлен на поле
        tile_copy = t.copy()
        tile_copy["id"] = i
        tile_copy["visited"] = False
        tiles_deck.append(tile_copy)
    
    random.shuffle(tiles_deck)

    return {
        "floor_index": floor_index,
        "tiles": [start_tile],
        "position": 0,
        "floor_steps": 0,
        "forge_found": False,
        "tiles_deck": tiles_deck,
    }

# ============================================================
# Свободная фаза
# ============================================================
def check_level_up(boiets: dict) -> list:
    """Проверяет и применяет level-up. Возвращает список событий для лога.

    XP тратится при получении уровня (списывается xp_cost следующего уровня).
    Уровень повышается, пока хватает XP и уровень < 7.
    """
    events = []
    table = data.CLASSES[boiets["class"]]
    while boiets["level"] < len(table):
        next_level_index = boiets["level"]  # 0-индекс: следующий уровень
        next_level_data = table[next_level_index]
        cost = next_level_data["xp_cost"]
        if boiets["xp"] < cost:
            break
        boiets["xp"] -= cost
        old_level = boiets["level"]
        boiets["level"] += 1
        # пересчёт характеристик
        delta_hp = next_level_data["hp"] - boiets["max_hp"]
        boiets["max_hp"] = next_level_data["hp"]
        boiets["hp"] = boiets["hp"] + delta_hp
        boiets["at"] = next_level_data["at"]
        boiets["df"] = next_level_data["df"]
        events.append({
            "event": "level_up",
            "class": boiets["class"],
            "from_level": old_level,
            "to_level": boiets["level"],
            "xp_spent": cost,
            "xp_left": boiets["xp"],
        })
    return events


def free_phase(party: list, floor_state: dict) -> list:
    """Свободная фаза в начале хода.
    Сейчас: level-up всем живым бойцам.
    Позже: эликсиры, «Святая аура», «Чутьё», болезнь.
    Возвращает список событий для лога.
    """
    events = []
    for b in party:
        events.extend(check_level_up(b))
    return events

# ============================================================
# Колода монстров и вытягивание
# ============================================================
def draw_monsters(floor_index: int, n_fighters: int, formula: dict) -> list:
    """Тянет монстров по формуле тайла.
    Монстры не кончаются: каждый бой -- свежий пул этажа.
    В одном бою монстры не повторяются.
    
    formula: {"per": 1|2|4, ...}
    n_fighters -- число бойцов в команде (только живые: мёртвые из party удалены).

    Возвращает список боевых экземпляров:
      {"pool": int, "monster": int,       # ссылка в data.MONSTERS
       "hp": int,                          # текущее HP (мутабельное)
       "max_hp": int, "at": int, "df": int, "xp": int, "gd": int}  # кэш из data
    """
    per = formula["per"]
    n_monsters = max(1, n_fighters // per)
    
    # Пул этажа: все карты из пулов, доступных на этом этаже.
    pool_indices = data.MONSTER_POOLS_BY_FLOOR.get(floor_index, [])
    pool = []
    for pool_index in pool_indices:
        for monster_index in range(len(data.MONSTERS[pool_index])):
            pool.append({"pool": pool_index, "monster": monster_index})
    
    # Монстры в одном бою не повторяются: не больше, чем карт в пуле.
    n_monsters = min(n_monsters, len(pool))
    random.shuffle(pool)
    selected = pool[:n_monsters]
    
    # Отобранные монстры
    monsters = []
    for card in selected:
        pool_index = card["pool"]
        monster_index = card["monster"]
        src = data.MONSTERS[pool_index][monster_index]
        monsters.append({
            "pool": pool_index,
            "monster": monster_index,
            "hp": src["hp"],
            "max_hp": src["hp"],
            "at": src["at"],
            "df": src["df"],
            "xp": src["xp"],
            "gd": src["gd"],
        })
    return monsters

# ============================================================
# Бой
# ============================================================
def run_combat(party: list, monsters: list, floor_index: int) -> dict:
    """Проводит бой до победы или поражения команды.

    party    -- список бойцов (живые и мёртвые; мёртвые остаются до конца боя,
               чтобы после боя можно было распределить их снаряжение/золото,
               и только затем party очищается от тел).
    monsters -- список боевых экземпляров из draw_monsters.
    floor_index -- 0..3 (для лога).

    Возвращает combat_log:
      {"floor": int,
       "monsters_start": [{"pool": int, "monster": int}, ...],
       "rounds": [{"round": int, "actions": [...]}, ...],
       "result": "win"|"lose"|"stuck",
       "xp_gained": int, "gold_gained": int}
    """
    combat_log = {
        "floor": floor_index,
        "monsters_start": [
            {"pool": m["pool"], "monster": m["monster"]} for m in monsters
        ],
        "rounds": [],
        "result": None,
        "xp_gained": 0,
        "gold_gained": 0,
    }
    round_num = 0
    while True:
        round_num += 1

        # 1. Инициатива: каждый живой участник бросает d6 отдельно за себя.
        #    Состав party в течение раунда не меняется -- индексы стабильны.
        participants = []
        for i, b in enumerate(party):
            if b["hp"] > 0:
                participants.append(("boiets", i, roll_d6()))
        for i, m in enumerate(monsters):
            if m["hp"] > 0:
                participants.append(("monster", i, roll_d6()))
        # при равенстве -- случайный порядок: перемешиваем до сортировки
        random.shuffle(participants)
        participants.sort(key=lambda x: x[2], reverse=True)

        # 2. Действия в порядке инициативы.
        round_actions = []
        for kind, idx, init in participants:
            if kind == "boiets":
                b = party[idx]
                if b["hp"] <= 0:
                    continue  # погиб в этом же раунде до своего хода
                alive = [j for j, m in enumerate(monsters) if m["hp"] > 0]
                if not alive:
                    break
                target_j = random.choice(alive)
                target = monsters[target_j]
                roll = roll_d6()
                dmg = max(0, roll + b["at"] - target["df"])
                target["hp"] -= dmg
                round_actions.append({
                    "actor": "boiets",
                    "actor_index": idx,
                    "target_index": target_j,
                    "roll": roll,
                    "damage": dmg,
                    "target_hp": target["hp"],
                })
            else:
                m = monsters[idx]
                if m["hp"] <= 0:
                    continue
                alive = [j for j, b in enumerate(party) if b["hp"] > 0]
                if not alive:
                    break
                # монстр выбирает цель random.randint(1, N)
                target_idx = random.randint(1, len(alive)) - 1
                target = party[alive[target_idx]]
                roll = roll_d6()
                dmg = max(0, roll + m["at"] - target["df"])
                target["hp"] -= dmg
                round_actions.append({
                    "actor": "monster",
                    "actor_index": idx,
                    "target_index": alive[target_idx],
                    "roll": roll,
                    "damage": dmg,
                    "target_hp": target["hp"],
                })

        combat_log["rounds"].append({
            "round": round_num,
            "actions": round_actions,
        })

        # 3. Проверка завершения боя.
        monsters_alive = [m for m in monsters if m["hp"] > 0]
        party_alive = [b for b in party if b["hp"] > 0]
        if not monsters_alive:
            combat_log["result"] = "win"
            break
        if not party_alive:
            combat_log["result"] = "lose"
            break
        if round_num > config.MAX_COMBAT_STEPS:
            # защита от бесконечного боя (не должно случаться)
            combat_log["result"] = "stuck"
            break

    # 4. Награда при победе (делим между выжившими).
    if combat_log["result"] == "win":
        survivors = [b for b in party if b["hp"] > 0]
        total_xp = sum(m["xp"] for m in monsters)
        total_gd = sum(m["gd"] for m in monsters)
        if survivors:
            xp_share = total_xp // len(survivors)
            xp_rest = total_xp % len(survivors)
            for i, b in enumerate(survivors):
                b["xp"] += xp_share
                if i == 0:  # остаток первому (rusher)
                    b["xp"] += xp_rest
            gd_share = total_gd // len(survivors)
            gd_rest = total_gd % len(survivors)
            for i, b in enumerate(survivors):
                b["gold"] += gd_share
                if i == 0:
                    b["gold"] += gd_rest
            combat_log["xp_gained"] = total_xp
            combat_log["gold_gained"] = total_gd

    # 5. Чистка party от тел после боя (распределение снаряжения --
    #    сюда же, когда появится снаряжение; сейчас распределять нечего).
    party[:] = [b for b in party if b["hp"] > 0]

    return combat_log

# ============================================================
# Разрешение тайла (варианты действий)
# ============================================================

def resolve_tile(position: int, floor_state: dict, party: list) -> list:
    """Разрешает клетку position: при необходимости вытягивает тайл,
    возвращает список доступных Action.

    Не принимает решение -- только предлагает варианты.
    position -- желаемая позиция (может быть len(tiles) -- шаг за правый край).

    Монстры:
      - visited == False                              → [FIGHT, FLEE]
      - visited == True, revival, d6 == 1             → [FIGHT, FLEE]
      - visited == True, (не revival или d6 != 1)     → [SKIP]
    """
    tiles = floor_state["tiles"]
    
    # 1. Шаг за правый край: вытянуть новый тайл из колоды и положить в линию.
    if position == len(tiles):
        tile = floor_state["tiles_deck"].pop(0)
        tiles.append(tile)
        if tile["type"] == data.TileType.FORGE:
            floor_state["forge_found"] = True
    
    # 2. Взять тайл по позиции (уже существует: шаг назад или только что вытянутый).
    tile = tiles[position]
    
    # 3. Варианты действий по типу тайла.
    # кузница
    if tile["type"] == data.TileType.FORGE:
        return [data.Action.FORGE, data.Action.SKIP]
    # монстр
    if tile["type"] == data.TileType.MONSTER:
        if not tile["visited"]:
            return [data.Action.FIGHT, data.Action.FLEE]
        formula = tile["monster_formula"]
        if formula.get("revival") and roll_d6() == 1:
            return [data.Action.FIGHT, data.Action.FLEE]
        return [data.Action.SKIP]
    
    # сокровищница, событие, лагерь, торговец, старт -- пока только пропуск
    return [data.Action.SKIP]


# ============================================================
# Решения бота
# ============================================================
def bot_move(floor_state: dict, party: list, profile: str) -> int:
    """Решает, куда шагнуть: 1 (вперёд) или -1 (назад).

    Учитывает край линии и пустую колоду:
      - position == 0                           → только 1;
      - position == len(tiles)-1 и колода пуста → только -1 («стена» впереди);
      - иначе -- по профилю.

    Rusher: всегда 1, если может, иначе -1.
    Неизвестный профиль: случайный выбор из допустимых.
    """
    position = floor_state["position"]
    can_forward = not (
        position == len(floor_state["tiles"]) - 1
        and not floor_state["tiles_deck"]
    )
    can_back = position > 0

    if not can_forward and not can_back:
        # вырожденный случай: некуда идти (не должно случаться)
        return 0

    if profile == "rusher":
        if can_forward:
            return 1
        return -1

    # неизвестный профиль -- случайный выбор из допустимых
    options = []
    if can_forward:
        options.append(1)
    if can_back:
        options.append(-1)
    return random.choice(options)

def bot_decide(available: list, party: list, floor_state: dict, profile: str, monsters: list) -> int:
    """Выбирает одно Action из списка доступных по профилю.
    available -- варианты на текущем тайле (len > 1; при len == 1 не вызывается).
    monsters  -- монстры, вытянутые до решения (None, если боя нет).

    Rusher: FORGE > FIGHT > SKIP.
    Неизвестный профиль: случайное действие из доступных.
    """
    if profile == "rusher":
        if data.Action.FORGE in available:
            return data.Action.FORGE
        if data.Action.FIGHT in available:
            return data.Action.FIGHT
        return data.Action.SKIP

    # по умолчанию -- первый вариант
    return random.choice(available)


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
        free_events = free_phase(party, floor_state)

        # 2. решение о направлении перемещения
        move = bot_move(floor_state, party, profile)
        
        # 3. разрешение клетки (при необходимости тянет тайл)
        target_position = floor_state["position"] + move
        available = resolve_tile(target_position, floor_state, party)
        
        # 4. смена позиции + инкремент шагов
        floor_state["position"] = target_position
        floor_state["floor_steps"] += 1
        tile = floor_state["tiles"][floor_state["position"]]
        action_position = floor_state["position"]  # позиция тайла действия
        
        # 5. если возможен бой -- тянем монстров (бот их «видит»)
        monsters = None
        if data.Action.FIGHT in available:
            monsters = draw_monsters(
                floor_index, len(party), tile["monster_formula"]
            )

        # 6. выбор действия ботом
        if len(available) == 1:
            action = available[0]
        else:
            action = bot_decide(available, party, floor_state, profile, monsters)

        # 7. обработка действия
        combat_log = None
        flee_roll = None
        fight = False
        
        if action == data.Action.FIGHT:
            fight = True
        elif action == data.Action.FLEE:
            flee_roll = roll_d6()
            if flee_roll <= 3:
                # побег удался: шаг назад, −1 HP каждому
                floor_state["position"] = max(0, floor_state["position"] - 1)
                for b in party:
                    b["hp"] = max(0, b["hp"] - 1)
                # смерть от −1 HP: чистка party от трупов
                party[:] = [b for b in party if b["hp"] > 0]
                combat_log = {"result": "flee"}
            else:
                # побег не удался - начинаем бой
                fight = True
        
        # 8. единая точка вызова run_combat
        if fight:
            combat_log = run_combat(party, monsters, floor_index)
            tile["visited"] = True
            if combat_log["result"] == "stuck":
                # сигнал ошибки симуляции -- прерываем партию
                log["final_floor"] = floor_index
                log["result"] = "stuck"
                return log
            
        # 9. запись шага в лог
        log["steps"].append({
            "step": step_num,
            "floor": floor_index,
            "position": action_position,
            "tile_id": tile["id"],
            "available": [int(a) for a in available],
            "action": int(action),
            "free_events": free_events,
            "combat": combat_log,
            "flee_roll": flee_roll,
            "party": [snapshot_boiets(b) for b in party],
        })
        step_num += 1

        # 10. проверка смерти команды
        if not party:
            log["final_floor"] = floor_index
            log["result"] = "dead"
            return log

        # 11. обработка перехода на следующий этаж
        if action == data.Action.FORGE:
            floor_index += 1
            if floor_index >= 4:
                break
            floor_state = create_floor_state(floor_index)

        # 12. защита от бесконечного цикла
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
        f"reach4: {stats.get('reached_floor_4', 0)} | "
        f"stuck: {stats.get('stuck', 0)} | "
        f"dead: {stats.get('dead', 0)} | "
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
    stats = {}
    start_time = time.time()

    for i in range(n_games):
        seed = (seed_base + i) if seed_base is not None else None
        game_log = play_one_game(class_name, profile, seed)
        result = game_log["result"]
        stats[result] = stats.get(result, 0) + 1

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
        "seed_base": seed_base,
        "project_version": config.PROJECT_VERSION,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(os.path.join(run_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"Готово. Логи: {run_dir}")
    print(f"Дошли до 4-го этажа: {stats.get('reached_floor_4', 0)} / {n_games}")
    print(f"Погибли: {stats.get('dead', 0)}")
    print(f"Застряли: {stats.get('stuck', 0)}")


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