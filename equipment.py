"""Снаряжение: предметы и пересчёт характеристик бойца.

Вынесено из simulator.py. Зависит только от data.py (только читает).
В 5.3 сюда переедут grant_item/collect_trash/trim_inventories/resolve_trade
и эликсиры.
"""
import data


def get_equipment(code: str) -> dict:
    """Возвращает запись предмета из data.EQUIPMENT по коду.

    KeyError, если кода нет -- лучше упасть громко, чем молча.
    """
    for item in data.EQUIPMENT:
        if item["code"] == code:
            return item
    raise KeyError(f"Неизвестный код снаряжения: {code!r}")


def recalc_stats(boiets: dict) -> None:
    """Пересчитывает at/df/max_hp бойца с учётом снаряжения.

    База -- data.CLASSES[class][level-1].
    Бонусы: equipped_weapon + equipped_armor + все аксессуары (slot=="A")
    из inventory. Неэкипированные W/S в inventory бонусов не дают.
    hp клэмпится вниз по новому max_hp (не лечит).
    """
    base = data.CLASSES[boiets["class"]][boiets["level"] - 1]
    at = base["at"]
    df = base["df"]
    max_hp = base["hp"]

    codes = []
    if boiets.get("equipped_weapon"):
        codes.append(boiets["equipped_weapon"])
    if boiets.get("equipped_armor"):
        codes.append(boiets["equipped_armor"])
    for code in boiets["inventory"]:
        item = get_equipment(code)
        if code not in codes and item["code"][1] == "A":  # slot "A"
            codes.append(code)

    for code in codes:
        bonus = get_equipment(code)["bonus"]
        at += bonus.get("at", 0)
        df += bonus.get("df", 0)
        max_hp += bonus.get("hp", 0)

    boiets["at"] = at
    boiets["df"] = df
    boiets["max_hp"] = max_hp
    if boiets["hp"] > max_hp:
        boiets["hp"] = max_hp
