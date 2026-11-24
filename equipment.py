"""Снаряжение: предметы и пересчёт характеристик бойца.

Качество: code[0].U (обычный), R (редкий), V (волшебный), L (легендарный).
Слоты: code[1]. W (оружие), S (броня), A (аксессуар), E (эликсир).
Вынесено из simulator.py. Зависит только от data.py (только читает).
Эликсиры (slot "E") в колоды снаряжения не попадают — только торговец;
выбывшие эликсиры исчезают (collect_trash их пропускает).
"""
import random
import data

# ============================================================
# Доступ к предметам
# ============================================================

def get_equipment(code: str) -> dict:
    """Возвращает запись предмета из data.EQUIPMENT по коду.

    KeyError, если кода нет -- лучше упасть громко, чем молча.
    """
    for item in data.EQUIPMENT:
        if item["code"] == code:
            return item
    raise KeyError(f"Неизвестный код снаряжения: {code!r}")

def get_quality(code: str) -> str:
    """Качество предмета: "U" | "R" | "V" | "L" (первый символ кода)."""
    return code[0]

def get_slot(code: str) -> str:
    """Слот предмета: "W" | "S" | "A" | "E" (второй символ кода)."""
    return code[1]

def is_elixir(code: str) -> bool:
    """Эликсир ли это (slot "E")."""
    return get_slot(code) == "E"

# ============================================================
# Пересчёт характеристик
# ============================================================
def recalc_stats(boiets: dict) -> None:
    """Пересчитывает at/df/max_hp бойца с учётом снаряжения.

    База -- data.CLASSES[class][level-1]["bonus"].
    Бонусы: equipped_weapon + equipped_armor + все аксессуары (slot=="A")
    из inventory. Неэкипированные W/S в inventory бонусов не дают.
    Эликсиры (slot "E") в recalc_stats не участвуют (эффект разовый).
    init -- база класса + снаряжение (временный init_bonus_temp -- в бою).
    hp клэмпится вниз по новому max_hp (не лечит).
    """
    base_bonus = data.CLASSES[boiets["class"]][boiets["level"] - 1]["bonus"]
    at = base_bonus.get("at", 0)
    df = base_bonus.get("df", 0)
    max_hp = base_bonus.get("hp", 0)
    init = base_bonus.get("init", 0)

    codes = []
    if boiets.get("equipped_weapon"):
        codes.append(boiets["equipped_weapon"])
    if boiets.get("equipped_armor"):
        codes.append(boiets["equipped_armor"])
    for code in boiets["inventory"]:
        item = get_equipment(code)
        if code not in codes and item["code"][1] == "A":  # слот "A" аксессуар
            codes.append(code)

    for code in codes:
        bonus = get_equipment(code)["bonus"]
        at += bonus.get("at", 0)
        df += bonus.get("df", 0)
        max_hp += bonus.get("hp", 0)
        init += bonus.get("init", 0)

    boiets["at"] = at
    boiets["df"] = df
    boiets["max_hp"] = max_hp
    
    # если бонуса нет init == 0, не храним его
    if init != 0:
        boiets["init"] = init
    elif "init" in boiets:
        del boiets["init"]

    if boiets["hp"] > max_hp:
        boiets["hp"] = max_hp

# ============================================================
# Выдача и возврат предметов (колоды по качеству)
# ============================================================
def grant_item(boiets: dict, code: str, equipment_decks: dict) -> bool:
    """Выдаёт предмет бойцу: убирает из колоды, кладёт в inventory.

    Эликсиры (slot "E") в колодах не лежат: кладём напрямую в inventory,
    колоду не трогаем. Для остальных -- remove из колоды качества.
    Экипировку не трогает (её разрулит bot_distribute в free_phase).
    Возвращает True, если выдано; False -- если карточки не было в колоде
    (только для не-эликсиров).
    """
    if is_elixir(code):
        boiets["inventory"].append(code)
        return True
    deck = equipment_decks[get_quality(code)]
    if code not in deck:
        return False
    deck.remove(code)
    boiets["inventory"].append(code)
    return True

def collect_trash(trash: list, equipment_decks: dict) -> None:
    """Возвращает выбывшие предметы в колоды по качеству.

    Эликсиры (slot "E") не возвращаются: расходник, исчезает.
    Не перемешивает: каждый код вставляется в случайное место колоды
    (включая начало и конец), что эквивалентно «подмешать карту».
    """
    for code in trash:
        if is_elixir(code):
            continue
        deck = equipment_decks[get_quality(code)]
        deck.insert(random.randint(0, len(deck)), code)
    trash.clear()

def trim_inventories(party: list) -> tuple:
    """Обрезает inventory до 6 у всех в party (живых и трупов).

    Возвращает (events, trash): trash -- обрезанные предметы (для колод).
    Эликсиры, попавшие в trash, дальше выбросит collect_trash.
    """
    events = []
    trash = []
    for b in party:
        if len(b["inventory"]) > 6:
            dropped = b["inventory"][6:]
            b["inventory"] = b["inventory"][:6]
            events.append({"event": "trim", "class": b["class"],
                           "dropped": list(dropped)})
            trash.extend(dropped)
    return events, trash

# ============================================================
# Сокровищница
# ============================================================
def _roll_quality(floor_index: int, d6: int) -> str:
    """Качество предмета в сокровищнице (RULES.md §6.2).

    Возвращает "U"/"R"/"V"/"L" по таблице data.EQUIPMENT_QUALITY_TABLE.
    """
    return data.EQUIPMENT_QUALITY_TABLE[d6 - 1][floor_index]

def resolve_treasure(tile: dict, floor_state: dict, equipment_decks: dict) -> None:
    """Бросает d6 (§6.1) и фиксирует результат в tile["treasure"].

    kind: "gold" | "equipment" | "mimic".
    d6 4-6 -- карта снаряжения: сначала качество (§6.2), затем тянем из
    колоды качества. Если колода пуста -- компенсация золотом (d6=2-3).
    Эликсиры в колоды не попадают, поэтому сокровищница их не выдаёт.
    """
    fi = floor_state["floor_index"]
    d6 = random.randint(1, 6)
    if d6 == 1:
        tile["treasure"] = {"kind": "mimic"}
        return
    if d6 <= 3:
        tile["treasure"] = {"kind": "gold", "amount": [3, 6, 12, 24][fi]}
        return
    # d6 4-6: карта снаряжения -- сначала качество (§6.2)
    quality_d6 = random.randint(1, 6)
    quality = _roll_quality(fi, quality_d6)
    deck = equipment_decks[quality]
    if not deck:
        # колода качества пуста -- компенсация золотом (d6=2-3)
        tile["treasure"] = {"kind": "gold", "amount": [3, 6, 12, 24][fi],
                            "note": "deck_empty"}
        return
    code = random.choice(deck)          # выбрать, НЕ забирать (заберёт grant_item)
    if d6 == 6:
        tile["treasure"] = {"kind": "equipment", "code": code,
                            "gold": [3, 6, 12, 24][fi]}
    else:
        tile["treasure"] = {"kind": "equipment", "code": code}

# ============================================================
# Торговец
# ============================================================
def resolve_trade(party: list, deals: list) -> list:
    """Применяет сделки на торговце.

    Сделка (boiets_idx, code). Тип определяется по code[1]:
      - "E": покупка. Списывает price у бойца, кладёт эликсир в inventory.
             Если золота не хватает -- отказ (trade_no_gold), сделка
             не применяется.
      - иначе: продажа. Удаляет code из inventory, начисляет price.
             Если code нет в inventory -- отказ (trade_miss).

    resolve_trade идёт строго по списку, не переупорядочивает.
    Возвращает events для лога.
    """
    events = []
    for idx, code in deals:
        if idx >= len(party):
            continue
        b = party[idx]
        price = get_equipment(code)["price"]
        if is_elixir(code):
            # покупка
            if b["gold"] < price:
                events.append({"event": "trade_no_gold", "class": b["class"],
                               "code": code, "price": price})
                continue
            b["gold"] -= price
            b["inventory"].append(code)
            events.append({"event": "trade_buy", "class": b["class"],
                           "code": code, "price": price})
        else:
            # продажа
            if code in b["inventory"]:
                b["inventory"].remove(code)
                b["gold"] += price
                events.append({"event": "trade_sell", "class": b["class"],
                               "code": code, "price": price})
            else:
                events.append({"event": "trade_miss", "class": b["class"],
                               "code": code})
    return events