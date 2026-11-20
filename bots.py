"""Бот: стратегии принятия решений (реализация Solver).

Сюда переехали bot_move/bot_decide/bot_distribute/bot_trade и их хелперы
из simulator.py. Логика не менялась.
"""
import random

import data
from equipment import get_equipment
from solvers import Solver


# ============================================================
# BotSolver -- обёртка над свободными bot_* функциями
# ============================================================
class BotSolver(Solver):
    """Решатель-бот. profile -- стиль ("rusher"/"cautious"/...)."""

    def __init__(self, profile: str):
        self.profile = profile

    def move(self, floor_state, party):
        return bot_move(floor_state, party, self.profile)

    def decide(self, available, party, floor_state, monsters):
        return bot_decide(available, party, floor_state, self.profile, monsters)

    def distribute(self, party):
        return bot_distribute(party, self.profile)

    def trade(self, party):
        return bot_trade(party, self.profile)

# ============================================================
# Утилиты
# ============================================================
def _item_value(code: str) -> int:
    """Ключ сортировки: W/S ценятся вдвое (приоритет экипировки)."""
    item = get_equipment(code)
    slot = code[1]
    return item["price"] * 2 if slot in ("W", "S") else item["price"]

def _fits_class(code: str, boiets: dict) -> bool:
    """Подходит ли предмет бойцу по классу (None -- всем)."""
    item = get_equipment(code)
    return item["class"] is None or item["class"] == boiets["class"]

# ============================================================
# Функции-стратегии, Решения бота (перенесены из simulator.py)
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
    monsters  -- противники, вытянутые до решения (None, если боя нет).

    Rusher: HIRE > FORGE > FIGHT > SKIP > FLEE.
    Неизвестный профиль: случайное действие из доступных.
    """
    if profile == "rusher":
        if data.Action.HIRE in available:
            return data.Action.HIRE
        if data.Action.FORGE in available:
            return data.Action.FORGE
        if data.Action.FIGHT in available:
            return data.Action.FIGHT
        if data.Action.SKIP in available:
            return data.Action.SKIP
        if data.Action.FLEE in available:
            return data.Action.FLEE
        # страховка: не должно случаться, если available не пуст
        return available[0]

    # по умолчанию -- первый вариант
    return random.choice(available)

def bot_trade(party: list, profile: str) -> list:
    """Выбирает сделки на торговце: продажа неэкипированных W/S (price > 0).

    Возвращает список (boiets_idx, code). Мусор (price == 0) не трогаем --
    его срежет trim_inventories, а в сортировке он и так в конце.
    На будущее: если code -- эликсир (E), сделка означает покупку (TODO).
    """
    deals = []
    for idx, b in enumerate(party):
        if b["hp"] <= 0:
            continue
        for code in b["inventory"]:
            slot = code[1]
            if slot not in ("W", "S"):
                continue
            if code == b["equipped_weapon"] or code == b["equipped_armor"]:
                continue
            if get_equipment(code)["price"] <= 0:
                continue
            deals.append((idx, code))
    return deals

def bot_distribute(party: list, profile: str) -> tuple:
    """Перераспределяет снаряжение и золото между живыми бойцами.

    Трупы -- источник (их inventory/gold идут в общий котёл), но не получатели.
    Ценность для сортировки: price*2 для W/S, price для A.
    Экипировка по кругу: первый подходящий (класс + свободный слот W/S).
    Остаток -- по свободным местам (лимит 6).
    Золото -- поровну живым, остаток лидеру (первый живой).

    В лог пишутся только реальные изменения (before/after по каждому бойцу).
    Возвращает (events, trash): trash -- предметы, не попавшие никому
    (остаток pool), для возврата в колоды.
    """
    events = []
    trash = []
    alive = [b for b in party if b["hp"] > 0]
    if not alive:
        return events, trash

    # Снимок "до" (по индексам в party; внутри функции party не меняется)
    before = []
    for b in party:
        before.append({
            "inventory": list(b["inventory"]),
            "equipped_weapon": b["equipped_weapon"],
            "equipped_armor": b["equipped_armor"],
            "gold": b["gold"],
        })

    # 1. Сбор
    pool = []
    for b in party:
        pool.extend(b["inventory"])
        b["inventory"] = []
        b["equipped_weapon"] = None
        b["equipped_armor"] = None

    # 2. Сортировка
    pool.sort(key=lambda c: (_item_value(c), c), reverse=True)

    # 3. Экипировка по кругу
    while True:
        taken_this_round = False
        for b in alive:
            for i, code in enumerate(pool):
                if not _fits_class(code, b):
                    continue
                slot = code[1]
                if slot == "W" and b["equipped_weapon"] is not None:
                    continue
                if slot == "S" and b["equipped_armor"] is not None:
                    continue
                pool.pop(i)
                b["inventory"].append(code)
                if slot == "W":
                    b["equipped_weapon"] = code
                elif slot == "S":
                    b["equipped_armor"] = code
                taken_this_round = True
                break
        if not taken_this_round:
            break

    # 4. Остаток -- по свободным местам (лимит 6), по кругу
    if pool:
        while pool:
            moved = False
            for b in alive:
                if not pool:
                    break
                if len(b["inventory"]) < 6:
                    b["inventory"].append(pool.pop(0))
                    moved = True
            if not moved:
                break   # все инвентари полны -- остаток в trash

    # Остаток pool -- в trash (возврат в колоды)
    trash.extend(pool)

    # 5. Золото
    total_gold = sum(b["gold"] for b in party)
    for b in party:
        b["gold"] = 0
    share = total_gold // len(alive)
    remainder = total_gold - share * len(alive)
    for b in alive:
        b["gold"] = share
    alive[0]["gold"] += remainder

    # 6. Дифф "до/после" -- только реальные изменения, трупы пропускаем
    for idx, b in enumerate(party):
        if b["hp"] <= 0:
            continue                          # труп: его добро ушло, видно у получателей
        bef = before[idx]
        # инвентарь
        if bef["inventory"] != b["inventory"]:
            events.append({"event": "loot", "class": b["class"],
                           "before": bef["inventory"], "after": list(b["inventory"])})
        # экипировка -- только изменившиеся поля
        eq = {}
        if bef["equipped_weapon"] != b["equipped_weapon"]:
            eq["weapon"] = {"before": bef["equipped_weapon"],
                            "after": b["equipped_weapon"]}
        if bef["equipped_armor"] != b["equipped_armor"]:
            eq["armor"] = {"before": bef["equipped_armor"],
                           "after": b["equipped_armor"]}
        if eq:
            events.append({"event": "equip", "class": b["class"], **eq})
        # золото
        if bef["gold"] != b["gold"]:
            events.append({"event": "gold", "class": b["class"],
                           "before": bef["gold"], "after": b["gold"]})

    return events, trash