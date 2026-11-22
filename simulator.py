"""Симулятор Forge & Die II.

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
from equipment import (
    get_equipment, get_slot, recalc_stats,
    grant_item, collect_trash, trim_inventories,
    resolve_trade, resolve_treasure,
)
from solvers import make_solver

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
        "at": boiets["at"],
        "df": boiets["df"],
        "xp": boiets["xp"],
        "gold": boiets["gold"],
        "inventory": list(boiets["inventory"]),
        "equipped_weapon": boiets["equipped_weapon"],
        "equipped_armor": boiets["equipped_armor"],
    }

# ============================================================
# Инициализация
# ============================================================
def create_boiets(class_name: str, level: int = 1) -> dict:
    """Создаёт голого бойца указанного уровня (по умолчанию 1-го).

    Без стартового предмета: выдача -- отдельно, через grant_item.
    at/df/max_hp -- заглушки, заполняются recalc_stats ниже.
    """
    level_data = data.CLASSES[class_name][level - 1]  # индекс 0 -- уровень 1
    boiets = {
        "class": class_name,
        "level": level,
        "hp": level_data["hp"],
        "max_hp": 0,                 # заполнит recalc_stats
        "at": 0,                     # заполнит recalc_stats
        "df": 0,                     # заполнит recalc_stats
        "xp": 0,
        "gold": 10,
        "inventory": [],
        "equipped_weapon": None,
        "equipped_armor": None,
        "effects": [],
        "ability_uses": {},
    }
    recalc_stats(boiets)
    return boiets

def create_party(class_name: str, equipment_decks: dict) -> list:
    """Создаёт команду из одного бойца.

    Стартовый предмет класса выдаётся через grant_item (из колоды).
    Если карточки в колоде нет -- боец без предмета (на старте колоды полные,
    так что это не должно случиться).
    """
    b = create_boiets(class_name)
    start_code = data.STARTING_EQUIPMENT.get(class_name)
    if start_code:
        grant_item(b, start_code, equipment_decks)
    return [b]


def create_floor_state(floor_index: int) -> dict:
    """Создаёт состояние этажа: линия тайлов, колода, позиция."""
    start_tile = data.TILES[0].copy()
    start_tile["id"] = 0
    start_tile["visited"] = True  # старт уже посещён
    
    # Колода тайлов этажа: перемешиваем 60 карт без повторов в пределах этажа
    tiles_deck = []
    for i, t in enumerate(data.TILES):
        if i == 0:
            continue  # старт уже добавлен на поле
        tile_copy = t.copy()
        tile_copy["id"] = i
        tile_copy["visited"] = False
        tiles_deck.append(tile_copy)
    random.shuffle(tiles_deck)

    # Колода событий этажа: перемешиваем 20 карт, без повторов в пределах этажа.
    events_deck = [dict(card) for card in data.EVENTS]
    random.shuffle(events_deck)
    
    return {
        "floor_index": floor_index,
        "tiles": [start_tile],
        "position": 0,
        "floor_steps": 0,
        "forge_found": False,
        "tiles_deck": tiles_deck,
        "events_deck": events_deck,
        "active_effects": [],
    }

# ============================================================
# События: вычисление condition, select, effects
# ============================================================
def _resolve(value, boiets: dict, floor_index: int):
    """Резолвит операнд условия/эффекта.

    value -- число | строка-идентификатор | список из 4 (по этажам).
    Идентификаторы: gold, hp, max_hp, at, df, level, xp, class.
    """
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return value[floor_index]
    if isinstance(value, str):
        return boiets[value]
    raise TypeError(f"Неизвестный операнд: {value!r}")

def _compare(op: str, left, right) -> bool:
    """Сравнение с проверкой типов: <,<=,>,>= -- только числа; ==,!= -- числа/строки."""
    if op in ("==", "!="):
        result = (left == right)
        return result if op == "==" else not result
    if op in ("<", "<=", ">", ">="):
        if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            raise TypeError(f"Сравнение {op} требует чисел, получено {left!r}, {right!r}")
        if op == "<":  return left < right
        if op == "<=": return left <= right
        if op == ">":  return left > right
        return left >= right
    raise ValueError(f"Неизвестный оператор: {op!r}")

def eval_condition(cond, boiets: dict, floor_index: int, d6: int) -> bool:
    """Вычисляет condition для одного бойца. Чистая (d6 передан снаружи).

    cond -- True/False | {op, left, right} | {"d6", lo, hi} |
            {"and", ...} | {"or", ...} | {"not", expr}
    """
    if cond is True:
        return True
    if cond is False:
        return False
    if not isinstance(cond, dict):
        raise TypeError(f"Неизвестная форма condition: {cond!r}")

    if "and" in cond:
        return all(eval_condition(e, boiets, floor_index, d6) for e in cond["and"])
    if "or" in cond:
        return any(eval_condition(e, boiets, floor_index, d6) for e in cond["or"])
    if "not" in cond:
        return not eval_condition(cond["not"], boiets, floor_index, d6)
    if "d6" in cond:
        lo = _resolve(cond["d6"][0], boiets, floor_index)
        hi = _resolve(cond["d6"][1], boiets, floor_index)
        return lo <= d6 <= hi

    # сравнение: ровно один ключ-оператор
    if len(cond) != 1:
        raise ValueError(f"Ожидался один оператор, получено: {cond!r}")
    op = next(iter(cond))
    left, right = cond[op]
    return _compare(op, _resolve(left, boiets, floor_index),
                        _resolve(right, boiets, floor_index))

def resolve_select(sel: dict, party: list) -> list:
    """Возвращает список выбранных бойцов по select-выражению.

    {"all"} | {"random"} | {"max", field} | {"min", field}
    При равенстве max/min -- первый по порядку в party.
    """
    if "all" in sel:
        return list(party)
    if "random" in sel:
        return [random.choice(party)] if party else []
    if "max" in sel:
        if not party:
            return []
        field = sel["max"]
        best = max(party, key=lambda b: b[field])
        return [best]
    if "min" in sel:
        if not party:
            return []
        field = sel["min"]
        best = min(party, key=lambda b: b[field])
        return [best]
    raise ValueError(f"Неизвестный select: {sel!r}")

def play_event_rules(event: dict, party: list, floor_state: dict) -> dict:
    """Проигрывает правила события: select + d6 для condition.

    Возвращает {"effects": [...], "monsters": [(pool, index), ...]}.
    НЕ применяет эффекты (это делает apply_event); d6 бросается здесь,
    ровно один раз.
    """
    floor_index = floor_state["floor_index"]
    effects = []
    monsters = []
    handled = [False] * len(party)

    for rule in event["rules"]:
        targets = resolve_select(rule["select"], party)
        target_ids = {id(b) for b in targets}
        for i, b in enumerate(party):
            if handled[i] or id(b) not in target_ids:
                continue
            d6 = roll_d6()
            if eval_condition(rule["condition"], b, floor_index, d6):
                eff = {}
                for k, v in rule["effects"].items():
                    if k == "monster":
                        spec = v[floor_index]          # (pool, index)
                        monsters.append(tuple(spec))
                        continue
                    if k == "guide":
                        eff["guide"] = True
                        continue
                    eff[k] = _resolve(v, b, floor_index)
                effects.append({"select": [i], "effects": eff})
                handled[i] = True

    return {"effects": effects, "monsters": list(set(monsters))}

def apply_event(event_result: dict, party: list, floor_state: dict) -> list:
    """Применяет детерминированный результат события (из play_event_rules).
       event_result = {"effects": [{"select": [idx, ...], "effects": {...}}, ...]}
       select -- индексы бойцов в party (на момент проигрывания правил).
       gold/hp/xp -- сразу; turns -- в active_effects; guide -- _do_guide.
       monster -- не здесь (собран в tile["monsters"]).
       Возвращает event_log.
    """
    log = []
    for entry in event_result.get("effects", []):
        for idx in entry["select"]:
            if idx >= len(party):
                continue                    # боец погиб/выбыл между resolve и apply
            b = party[idx]
            for k, v in entry["effects"].items():
                if k == "guide":
                    log.extend(_do_guide(floor_state))
                elif k == "turns":
                    eff = {kk: vv for kk, vv in entry["effects"].items()
                           if kk != "turns"}
                    floor_state["active_effects"].append({
                        "target": b, "effects": eff,
                        "turns_left": v, "source": None,
                    })
                    log.append({"event": "effect_hung",
                                "class": b["class"], "turns": v})
                elif k == "gold":
                    b["gold"] = max(0, b["gold"] + v)
                    log.append({"event": "gold", "class": b["class"],
                                "delta": v, "after": b["gold"]})
                elif k == "hp":
                    b["hp"] = max(0, min(b["max_hp"], b["hp"] + v))
                    log.append({"event": "hp", "class": b["class"],
                                "delta": v, "after": b["hp"]})
                elif k == "xp":
                    b["xp"] += v
                    log.append({"event": "xp", "class": b["class"],
                                "delta": v, "after": b["xp"]})
    return log

def tick_active_effects(party: list, floor_state: dict) -> list:
    """Тикает active_effects: каждый эффект привязан к бойцу (target),
    применяется только к нему, turns_left уменьшается, истёкшие убираются.
    Эффекты на выбывших бойцах снимаются в cleanup_dead (после тика).
    """
    log = []
    remaining = []

    for eff in floor_state["active_effects"]:
        t = eff["target"]
        for k, amount in eff["effects"].items():
            if k == "hp":
                t["hp"] = max(0, min(t["max_hp"], t["hp"] + amount))
                log.append({"event": "hp", "class": t["class"],
                            "delta": amount, "after": t["hp"]})
            elif k == "gold":
                t["gold"] = max(0, t["gold"] + amount)
                log.append({"event": "gold", "class": t["class"],
                            "delta": amount, "after": t["gold"]})
            elif k == "xp":
                t["xp"] += amount
                log.append({"event": "xp", "class": t["class"],
                            "delta": amount, "after": t["xp"]})
        eff["turns_left"] -= 1
        if eff["turns_left"] > 0:
            remaining.append(eff)

    floor_state["active_effects"] = remaining
    return log

def _do_guide(floor_state: dict) -> list:
    """«Проводник»: тянет тайл справа от текущей позиции, если там пусто."""
    pos = floor_state["position"]
    tiles = floor_state["tiles"]
    if pos == len(tiles) - 1 and floor_state["tiles_deck"]:
        new_tile = floor_state["tiles_deck"].pop(0)
        tiles.append(new_tile)
        return [{"event": "guide", "tile_id": new_tile["id"]}]
    return [{"event": "guide_noop"}]

# ============================================================
# Свободная фаза
# ============================================================
# Проверка на умерших в пати
def cleanup_dead(party: list, floor_state: dict) -> tuple:
    """Убирает из party бойцов с hp<=0. Возвращает (events, wiped, trash).

    При смерти предметы бойца уходят в trash (для возврата в колоды).
    Золото не трогаем -- его распределение вне cleanup_dead.
    wiped=True, если до чистки кто-то был, а после чистки party пуст
    (вся команда погибла).
    """
    events = []
    trash = []
    had_any = len(party) > 0
    for b in party:
        if b["hp"] <= 0:
            events.append({
                "event": "death",
                "class": b["class"],
                "level": b["level"],
                "inventory": list(b["inventory"]),
                "equipped_weapon": b["equipped_weapon"],
                "equipped_armor": b["equipped_armor"],
            })
            trash.extend(b["inventory"])
            b["inventory"] = []
            b["equipped_weapon"] = None
            b["equipped_armor"] = None
    party[:] = [b for b in party if b["hp"] > 0]
    # убрать эффекты на выбывших бойцах
    floor_state["active_effects"] = [
        eff for eff in floor_state["active_effects"]
        if any(eff["target"] is b for b in party)
    ]
    wiped = had_any and not party
    return events, wiped, trash

# Проверка на повышение уровней
def check_level_up(boiets: dict) -> list:
    """Проверяет и применяет level-up. Возвращает список событий для лога.

    XP тратится при получении уровня (списывается xp_cost следующего уровня).
    Уровень повышается, пока хватает XP и уровень < 7.
    Мёртвых (hp<=0) не трогает -- страховка, обычно их уже убрал cleanup_dead.
    """
    if boiets["hp"] <= 0:
        return []
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
        old_base_hp = table[old_level - 1]["hp"]
        boiets["level"] += 1
        # лечение -- чистая классовая дельта (без снаряжения);
        # at/df/max_hp и клэмп hp -- в recalc_stats (free_phase)
        boiets["hp"] += next_level_data["hp"] - old_base_hp
        events.append({
            "event": "level_up",
            "class": boiets["class"],
            "from_level": old_level,
            "to_level": boiets["level"],
            "xp_spent": cost,
            "xp_left": boiets["xp"],
        })
    return events

def _apply_drink(party: list, floor_state: dict, solver) -> list:
    """Исполняет решения solver.drink: пьёт эликсиры, применяет эффект.

    Решение -- (boiets_idx, code). Проверяем: боец жив, code в его
    inventory, code -- эликсир. Удаляем из inventory, применяем hp
    (клэмп по max_hp). Эликсир исчезает (в колоду не возвращается).
    Не более 1 эликсира на бойца за ход -- гарантируется тем, что
    drink возвращает не больше одного (idx, code) на idx, но на всякий
    случай считаем локально.

    Возвращает events для лога.
    """
    events = []
    decisions = solver.drink(party, floor_state)
    drank = set()
    for idx, code in decisions:
        if idx >= len(party):
            continue
        b = party[idx]
        if b["hp"] <= 0:
            continue
        if idx in drank:
            continue
        if get_slot(code) != "E":
            continue
        if code not in b["inventory"]:
            continue
        b["inventory"].remove(code)
        heal = get_equipment(code)["bonus"].get("hp", 0)
        if heal > 0:
            b["hp"] = min(b["max_hp"], b["hp"] + heal)
        drank.add(idx)
        events.append({"event": "drink", "class": b["class"],
                       "code": code, "hp_after": b["hp"]})
    return events

# Свободная фаза
def free_phase(party: list, floor_state: dict, solver,
               equipment_decks: dict) -> tuple:
    """Свободная фаза в начале хода.

    1. Тик active_effects (болезнь и т.п.) -- может добить бойцов.
    2. solver.drink -- эликсиры (не более 1 на бойца; до distribute).
    3. solver.distribute -- перераспределение снаряжения и золота (трупы -- источник).
    4. trim_inventories -- обрезка инвентарей до 6.
    5. Чистка party от трупов (hp<=0); если погибла вся команда (wiped) -- (events, True).
    6. Повышение уровня (level-up) всем живым бойцам (hp += чистовая дельта класса).
    7. recalc_stats -- пересчёт параметров всем живым: at/df/max_hp с учётом снаряжения + клэмп hp.
    8. collect_trash -- возврат выбывших предметов в колоды по качеству (эликсиры исчезают).
    Возвращает (events, wiped).
    """
    events = []
    trash = []
    # 1. тик активных эффектов
    events.extend(tick_active_effects(party, floor_state))
    # 2. эликсиры (до distribute: выпитое освобождает слоты)
    drink_events = _apply_drink(party, floor_state, solver)
    events.extend(drink_events)    
    # 3. перераспределение снаряжения и золота
    ev, tr = solver.distribute(party)
    events.extend(ev); trash.extend(tr)
    # 4. обрезка инвентарей
    ev, tr = trim_inventories(party)
    events.extend(ev); trash.extend(tr)
    # 5. чистка от трупов
    dead_events, wiped, tr = cleanup_dead(party, floor_state)
    events.extend(dead_events); trash.extend(tr)
    if wiped:
        collect_trash(trash, equipment_decks)
        return events, True
    # 6. повышение уровня
    for b in party:
        events.extend(check_level_up(b))
    # 7. пересчёт характеристик
    for b in party:
        recalc_stats(b)
    collect_trash(trash, equipment_decks)
    return events, False

# ============================================================
# Колода монстров и вытягивание монстров и противников из лагерей
# ============================================================
def draw_monsters(floor_index: int, n_fighters: int, formula: dict) -> list:
    """Тянет монстров по формуле тайла.
    Монстры не кончаются: каждый бой -- свежий пул этажа.
    В одном бою монстры не повторяются.
    
    formula: {"per": 1|2|4, ...}
    n_fighters -- число бойцов в команде (только живые: мёртвые из party удалены).

    Возвращает список боевых экземпляров:
      {"source": {"type": "monster", "pool": int, "monster": int},  # для лога/плеера
       "hp": int,                                                   # текущее HP (мутабельное)
       "max_hp": int, "at": int, "df": int, "xp": int, "gd": int}   # кэш из data
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
            "source": {"type": "monster", "pool": pool_index, "monster": monster_index},
            "hp": src["hp"],
            "max_hp": src["hp"],
            "at": src["at"],
            "df": src["df"],
            "xp": src["xp"],
            "gd": src["gd"],
        })
    return monsters

def build_camp_monsters(class_name: str, level: int) -> list:
    """Создаёт боевой экземпляр обитателя лагеря для run_combat.

    Обитатель лагеря -- боец указанного класса и уровня. Инвентаря у него
    нет (временный экземпляр), но бонусы стартового предмета класса
    учитываются в at/df/max_hp. hp = max_hp (свежий).
    Награда: XP = уровню, золото = 10.
    """
    fighter = create_boiets(class_name, level)          # голый
    start_code = data.STARTING_EQUIPMENT.get(class_name)
    if start_code:
        bonus = get_equipment(start_code)["bonus"]
        fighter["at"] += bonus.get("at", 0)
        fighter["df"] += bonus.get("df", 0)
        fighter["max_hp"] += bonus.get("hp", 0)
        fighter["hp"] = fighter["max_hp"]
    return [{
        "source": {"type": "camp", "class": class_name, "level": level},
        "hp": fighter["hp"],
        "max_hp": fighter["max_hp"],
        "at": fighter["at"],
        "df": fighter["df"],
        "xp": level,
        "gd": 10,
    }]

def build_event_monsters(specs: list) -> list:
    """Создаёт боевых монстров по спецификациям (pool, index).

    (pool, index) -- конкретный;
    (pool, None)  -- случайный из пула pool;
    (None, None)  -- случайный из случайного пула (все 4).
    """
    monsters = []
    for pool, index in specs:
        if pool is None:
            pool = random.randrange(len(data.MONSTERS))
        if index is None:
            index = random.randrange(len(data.MONSTERS[pool]))
        src = data.MONSTERS[pool][index]
        monsters.append({
            "source": {"type": "monster", "pool": pool, "monster": index},
            "hp": src["hp"], "max_hp": src["hp"],
            "at": src["at"], "df": src["df"],
            "xp": src["xp"], "gd": src["gd"],
        })
    return monsters

def build_mimic(floor_index: int) -> list:
    """Создаёт боевой экземпляр мимика (один, независимо от размера команды).

    Статы -- из data.MIMICS[floor_index]. Награда -- xp/gd из той же записи.
    source: {"type": "mimic", "floor": floor_index} -- для лога/плеера.
    """
    src = data.MIMICS[floor_index]
    return [{
        "source": {"type": "mimic", "floor": floor_index},
        "hp": src["hp"],
        "max_hp": src["hp"],
        "at": src["at"],
        "df": src["df"],
        "xp": src["xp"],
        "gd": src["gd"],
    }]

# ============================================================
# Бой
# ============================================================
def run_combat(party: list, monsters: list) -> dict:
    """Проводит бой до победы или поражения команды.

    party    -- список бойцов (живые и мёртвые; мёртвые остаются до конца хода
                               чистка трупов -- в free_phase следующего хода).
    monsters -- список боевых экземпляров из draw_monsters или build_camp_monsters.
                У каждого есть "source" для лога:
                {"type": "monster", "pool", "monster"} или
                {"type": "camp", "class", "level"}.

    Возвращает combat_log:
    { "party": [{"class": "warrior", "level": 1,
                 "at": 2, "df": 3, "max_hp": 17}],
      "monsters": [m["source"] for m in monsters],
      "rounds": [{"round": int,
                  "hp_start_round": {"b": [hp...], "m": [hp...]},
                  "initiative": {"b": [roll_or_None...], "m": [roll_or_None...]},
                  "actions": [{"type": "attack",
                               "actor": "b"|"m", "actor_index": int,
                               "target_index": int, "roll": int, "damage": int}]},
                 ...,
                 {"round": N, "hp_start_round": {...} }  # финальный: без initiative и actions
      ],
      "result": "win"|"lose"|"stuck", "xp_gained": int, "gold_gained": int }
    """
    combat_log = {
        "party": [
            {"class": b["class"], "level": b["level"],
             "at": b["at"], "df": b["df"], "max_hp": b["max_hp"]}
            for b in party
        ],
        "monsters": [m["source"] for m in monsters],
        "rounds": [],
        "result": None,
        "xp_gained": 0,
        "gold_gained": 0,
    }
    round_num = 0
    
    while True:
        round_num += 1
         
        # 1. Снимок HP всех участников на начало раунда.
        hp_start_round = {
            "b": [b["hp"] for b in party],
            "m": [m["hp"] for m in monsters],
        }       
         
        # 2. Проверка завершения боя до броска инициативы
        monsters_alive = [m for m in monsters if m["hp"] > 0]
        party_alive = [b for b in party if b["hp"] > 0]
        if not party_alive:
            combat_log["result"] = "lose"
        elif not monsters_alive:
            combat_log["result"] = "win"
        elif round_num > config.MAX_COMBAT_STEPS:
            # защита от бесконечного боя (не должно случаться)
            combat_log["result"] = "stuck"
        
        if combat_log["result"] is not None:
            # финальный раунд: только снимок HP, без инициативы и действий
            combat_log["rounds"].append({
                "round": round_num,
                "hp_start_round": hp_start_round,
            })
            break

        # 3. Инициатива: каждый живой участник бросает d6 отдельно за себя.
        #    init_b/init_m — броски по порядку party/monsters, None для мёртвых.
        participants = []
        init_b = [None] * len(party)
        init_m = [None] * len(monsters)
        for i, b in enumerate(party):
            if b["hp"] > 0:
                r = roll_d6()
                participants.append(("b", i, r))
                init_b[i] = r
        for i, m in enumerate(monsters):
            if m["hp"] > 0:
                r = roll_d6()
                participants.append(("m", i, r))
                init_m[i] = r
        #    порядок действий: перемешиваем и сортируем по убыванию инициативы
        random.shuffle(participants)
        participants.sort(key=lambda x: x[2], reverse=True)

        # 4. Действия в порядке инициативы.
        round_actions = []
        for kind, idx, init in participants:
            if kind == "b":
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
                target["hp"] = max(0, target["hp"]) # клэмп hp
                round_actions.append({
                    "type": "attack",
                    "actor": "b",
                    "actor_index": idx,
                    "target_index": target_j,
                    "roll": roll,
                    "damage": dmg,
                })
            else:
                m = monsters[idx]
                if m["hp"] <= 0:
                    continue
                alive = [j for j, b in enumerate(party) if b["hp"] > 0]
                if not alive:
                    break
                target_idx = random.choice(alive)
                target = party[target_idx]
                roll = roll_d6()
                dmg = max(0, roll + m["at"] - target["df"])
                target["hp"] -= dmg
                target["hp"] = max(0, target["hp"]) # клэмп hp
                round_actions.append({
                    "type": "attack",
                    "actor": "m",
                    "actor_index": idx,
                    "target_index": target_idx,
                    "roll": roll,
                    "damage": dmg,
                })

        combat_log["rounds"].append({
            "round": round_num,
            "hp_start_round": hp_start_round,
            "initiative": {"b": init_b, "m": init_m},
            "actions": round_actions,
        })

    # 5. Награда при победе (делим между выжившими).
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

    # 6. Чистка трупов -- в free_phase следующего хода (cleanup_dead).
    #    Здесь party оставляем как есть: в шаге лога будут трупы с hp=0.
    return combat_log

# ============================================================
# Разрешение тайла (варианты действий)
# ============================================================
# Генерация лагеря: броски и варианты
def _roll_camp(tile: dict, floor_state: dict, party: list) -> dict:
    """Первый визит в лагерь: 3 броска (а,б,в) по §5 RULES.md.

    (а) есть ли кто-то: d6 >= 4 -> кто-то есть.
    (б) уровень обитателя: таблица §5 от этажа (только если present).
    (в) настрой: таблица §5 от числа бойцов в команде (только если present).

    Возвращает camp-словарь для tile["camp"].
    """
    floor_index = floor_state["floor_index"]
    roll_present = roll_d6()
    present = roll_present >= 4

    level = None
    attitude = None
    roll_level = None
    roll_attitude = None

    if present:
        # (б) уровень: таблица по этажу
        roll_level = roll_d6()
        level = data.CAMP_LEVEL_TABLE[roll_level - 1][floor_index]

        # (в) настрой: таблица по числу бойцов
        roll_attitude = roll_d6()
        n = len(party)
        if roll_attitude <= data.CAMP_ENEMY_MAX[n]:
            attitude = "enemy"
        elif roll_attitude <= data.CAMP_NEUTRAL_MAX[n]:
            attitude = "neutral"
        else:
            attitude = "friend"

    return {
        "class": data.CAMP_CLASS[tile["id"]],
        "present": present,
        "level": level,
        "attitude": attitude,
        "rolls": {"present": roll_present, "level": roll_level, "attitude": roll_attitude},
    }

# Действия в лагере
def _camp_available(camp: dict, party: list) -> list:
    """Варианты действий в лагере по состоянию обитателя и составу party."""
    if not camp["present"]:
        return [data.Action.SKIP]
    if camp["attitude"] == "neutral":
        return [data.Action.SKIP]
    if camp["attitude"] == "friend":
        already = any(b["class"] == camp["class"] for b in party)
        return [data.Action.SKIP] if already else [data.Action.HIRE, data.Action.SKIP]
    if camp["attitude"] == "enemy":
        return [data.Action.FIGHT, data.Action.FLEE]
    # страховка
    return [data.Action.SKIP]

def _camp_snapshot(tile: dict) -> dict:
    """Снимок лагеря для шага лога.

    rolls -- всегда из первого визита (исторические броски этого лагеря);
    при повторном визите rolls=None.
    """
    camp = tile.get("camp")
    if camp is None:
        return None
    return {
        "tile_id": tile["id"],
        "class": camp["class"],
        "present": camp["present"],
        "level": camp["level"],
        "attitude": camp["attitude"],
        "rolls": camp.get("rolls"),
    }

def _ensure_monsters(tile: dict, floor_state: dict, party: list, kind: str) -> None:
    """Собирает боевые экземпляры в tile["monsters"] один раз.

    kind: "monster" | "camp".
    """
    if tile.get("monsters"):
        return
    if kind == "camp":
        camp = tile["camp"]
        tile["monsters"] = build_camp_monsters(camp["class"], camp["level"])
    else:
        tile["monsters"] = draw_monsters(
            floor_state["floor_index"], len(party), tile["monster_formula"]
        )

# Разрешение тайла
def resolve_tile(position: int, floor_state: dict, party: list,
                 equipment_decks: dict) -> list:
    """Разрешает клетку position: при необходимости вытягивает тайл,
    возвращает список доступных Action.

    Не принимает решение -- только предлагает варианты.

    Лагерь: при первом визите делает 3 броска и пишет их в tile["camp"];
    при present=False или attitude="neutral" сразу ставит visited=True
    (исчерпан). Повторный визит -- те же броски из tile["camp"].

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
    # 3.1. кузница
    if tile["type"] == data.TileType.FORGE:
        return [data.Action.FORGE, data.Action.SKIP]
    # 3.2. монстр
    if tile["type"] == data.TileType.MONSTER:
        if not tile["visited"]:
            _ensure_monsters(tile, floor_state, party, "monster")
            return [data.Action.FIGHT, data.Action.FLEE]
        formula = tile["monster_formula"]
        if formula.get("revival") and roll_d6() == 1:
            _ensure_monsters(tile, floor_state, party, "monster")
            return [data.Action.FIGHT, data.Action.FLEE]
        return [data.Action.SKIP]
    # 3.3. лагерь
    if tile["type"] == data.TileType.CAMP:
        if tile["visited"]:
            return [data.Action.SKIP]
        camp = tile.get("camp")
        if camp is None:
            camp = _roll_camp(tile, floor_state, party)
            tile["camp"] = camp
            if (not camp["present"]) or camp["attitude"] == "neutral":
                tile["visited"] = True
        avail = _camp_available(camp, party)
        if data.Action.FIGHT in avail:
            _ensure_monsters(tile, floor_state, party, "camp")
        return avail
    # 3.4. событие: тянем карту, проигрываем правила (d6 -- здесь),
    #      фиксируем результат в tile["event_result"], собираем монстров.
    if tile["type"] == data.TileType.EVENT:
        if tile["visited"]:
            return [data.Action.SKIP]
        if tile.get("event") is None:
            if floor_state["events_deck"]:
                tile["event"] = floor_state["events_deck"].pop(0)
            else:
                tile["event"] = dict(data.EVENTS[0])
        if tile.get("event_result") is None:
            result = play_event_rules(tile["event"], party, floor_state)
            tile["event_result"] = {"effects": result["effects"]}
            if result["monsters"]:
                tile["monsters"] = build_event_monsters(result["monsters"])
        if tile.get("monsters"):
            return [data.Action.FIGHT, data.Action.FLEE]
        return [data.Action.EVENT]
    # 3.5. сокровищница
    if tile["type"] == data.TileType.TREASURE:
        if tile["visited"]:
            return [data.Action.SKIP]
        if tile.get("treasure") is None:
            resolve_treasure(tile, floor_state, equipment_decks)
        tr = tile["treasure"]
        if tr["kind"] == "mimic":
            # мимик -- бой; экземпляр собирается один раз
            if tile.get("monsters") is None:
                tile["monsters"] = build_mimic(floor_state["floor_index"])
            return [data.Action.FIGHT, data.Action.FLEE]
        return [data.Action.TREASURE]
    # 3.6. торговец: доступен всегда (visited -- только для лога)
    if tile["type"] == data.TileType.TRADER:
        tile["visited"] = True
        return [data.Action.TRADE]
    # старт -- только пропуск
    return [data.Action.SKIP]

# ============================================================
# Завершение партии
# ============================================================
def finalize_game(log: dict, game_world: list, floor_state: dict,
                  floor_index: int, result: str) -> dict:
    """Завершает партию: сохраняет текущий этаж в game_world,
    проставляет final_floor и result, возвращает лог."""
    game_world.append([t["id"] for t in floor_state["tiles"]])
    log["game_world"] = game_world
    log["final_floor"] = floor_index
    log["result"] = result
    return log

# ============================================================
# Главный цикл партии
# ============================================================
def play_one_game(class_name: str, solver, seed: int) -> dict:
    """Одна партия. Возвращает журнал."""
    random.seed(seed)

    # Колоды снаряжения по качеству (одна на игру).
    equipment_decks = {"U": [], "R": [], "V": [], "L": []}
    for item in data.EQUIPMENT:
        if item["code"][1] == "E":
            continue
        equipment_decks[item["code"][0]].append(item["code"])
    for q in equipment_decks:
        random.shuffle(equipment_decks[q])
    
    # создание команды
    party = create_party(class_name, equipment_decks)

    floor_index = 0
    floor_state = create_floor_state(floor_index)
    log = {
        "seed": seed,
        "profile": getattr(solver, "profile", None),
        "class": class_name,
        "steps": [],
    }
    game_world = []

    step_num = 0
    while floor_index < 4:
        # 1. свободная фаза (чистка трупов + level-up)
        free_events, wiped = free_phase(party, floor_state, solver, equipment_decks)
        if wiped:
            # вся команда погибла -- партия окончена
            return finalize_game(log, game_world, floor_state, floor_index, "dead")

        # 2. решение о направлении перемещения
        move = solver.move(floor_state, party)
        
        # 3. разрешение клетки (при необходимости тянет тайл)
        target_position = floor_state["position"] + move
        available = resolve_tile(target_position, floor_state, party, equipment_decks)
        
        # 4. смена позиции + инкремент шагов
        floor_state["position"] = target_position
        floor_state["floor_steps"] += 1
        tile = floor_state["tiles"][floor_state["position"]]
        action_position = floor_state["position"]  # позиция тайла действия
        
        # 5. противники уже собраны в resolve_tile (tile["monsters"])

        # 6. выбор действия ботом
        if len(available) == 1:
            action = available[0]
        else:
            action = solver.decide(available, party, floor_state, tile.get("monsters"))

        # 7. обработка действия
        combat_log = None
        flee_roll = None
        fight = False
        event_snapshot = None
        trade_snapshot = None
        
        # 7.1. найм
        if action == data.Action.HIRE:
            # нанять обитателя лагеря (если класс ещё не в команде -- resolve_tile
            # уже это проверила, здесь просто добавляем)
            camp = tile["camp"]
            cls = camp["class"]
            new_b = create_boiets(cls, camp["level"])
            start_code = data.STARTING_EQUIPMENT.get(cls)
            if start_code and not grant_item(new_b, start_code, equipment_decks):
                # карточки нет в колоде -- компенсация золотом (price)
                new_b["gold"] += get_equipment(start_code)["price"]
            party.append(new_b)
            tile["visited"] = True
        # 7.2. бой
        elif action == data.Action.FIGHT:
            fight = True
        # 7.3. бегство
        elif action == data.Action.FLEE:
            flee_roll = roll_d6()
            if flee_roll <= 3:
                # побег удался: шаг назад, −1 HP каждому
                floor_state["position"] = max(0, floor_state["position"] - 1)
                for b in party:
                    b["hp"] = max(0, b["hp"] - 1)
                # смерть от −1 HP: чистка трупов -- в free_phase следующего хода
                combat_log = {"result": "flee"}
            else:
                # побег не удался - начинаем бой
                fight = True
        # 7.4. событие
        elif action == data.Action.EVENT:
            tile["visited"] = True
            event_log = apply_event(tile["event_result"], party, floor_state)
            event_snapshot = {
                "id": tile["event"].get("id"),
                "name": tile["event"].get("name"),
                "log": event_log,
            }
        # 7.5. сокровищница (мимик сюда не доходит -- он уходит в FIGHT)
        elif action == data.Action.TREASURE:
            tile["visited"] = True
            tr = tile["treasure"]
            leader = party[0] if party else None
            if tr["kind"] == "gold":
                if leader:
                    leader["gold"] += tr["amount"]
            elif tr["kind"] == "equipment":
                if leader:
                    grant_item(leader, tr["code"], equipment_decks)  # remove + append
                    if "gold" in tr:
                        leader["gold"] += tr["gold"]
            tile["treasure"]["log"] = [
                {"event": "treasure", "kind": tr["kind"]}
            ]
        
        # 7.6. торговец
        elif action == data.Action.TRADE:
            deals = solver.trade(party, floor_state)
            trade_log = resolve_trade(party, deals)
            trade_snapshot = {"deals": len(deals), "log": trade_log}
        
        # 8. единая точка вызова run_combat
        if fight:
            combat_log = run_combat(party, tile["monsters"])
            if combat_log["result"] == "win":
                tile["visited"] = True
                tile["monsters"] = []
            if combat_log["result"] == "stuck":
                return finalize_game(log, game_world, floor_state, floor_index, "stuck")
            
        # 9. запись шага в лог
        camp_snapshot = None
        if tile["type"] == data.TileType.CAMP and tile.get("camp") is not None:
            camp_snapshot = _camp_snapshot(tile)
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
            "camp": camp_snapshot,
            "event": event_snapshot,
            "treasure": tile.get("treasure") if action == data.Action.TREASURE else None, 
            "trade": trade_snapshot,
            "party": [snapshot_boiets(b) for b in party],
        })
        step_num += 1

        # 10. обработка перехода на следующий этаж
        if action == data.Action.FORGE:
            floor_index += 1
            if floor_index >= 4:
                return finalize_game(log, game_world, floor_state, floor_index, "win")
            else:
                game_world.append([t["id"] for t in floor_state["tiles"]])
                floor_state = create_floor_state(floor_index)

        # 11. защита от бесконечного цикла
        if floor_state["floor_steps"] > config.MAX_FLOOR_STEPS:
            return finalize_game(log, game_world, floor_state, floor_index, "stuck")
    
    # защита от не штатного выхода из цикла
    return finalize_game(log, game_world, floor_state, floor_index, "stuck")

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
        f"win: {stats.get('win', 0)} | "
        f"stuck: {stats.get('stuck', 0)} | "
        f"dead: {stats.get('dead', 0)} | "
        f"{elapsed:.1f}s"
    )
    print(f"\r{line}", end="", flush=True)


def run_simulation(n_games: int, class_name: str, solver_kind: str,
                   profile: str, seed_base: int = None,
                   no_progress: bool = False) -> None:
    """Прогоняет N партий, пишет логи, выводит статистику."""
    run_id = make_run_id()
    run_dir = os.path.join(config.LOGS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    started_at = datetime.now().isoformat()
    stats = {}
    start_time = time.time()
    solver = make_solver(solver_kind, profile)

    for i in range(n_games):
        seed = (seed_base + i) if seed_base is not None else None
        game_log = play_one_game(class_name, solver, seed)
        game_log["game_id"] = i + 1
        game_log["run_id"] = run_id
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
        "solver_kind": solver_kind,
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
    print(f"Победа: {stats.get('win', 0)} / {n_games}")
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
    parser.add_argument("--solver", default="bot",
                        choices=["bot", "human", "nn"],
                        help="кто принимает решения (bot/human/nn)")
    parser.add_argument("--profile", default=config.DEFAULT_PROFILE,
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
        solver_kind=args.solver,
        profile=args.profile,
        seed_base=args.seed,
        no_progress=args.no_progress,
    )


if __name__ == "__main__":
    main()