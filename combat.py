"""Бой Forge & Die II: раунды, инициатива, атаки, награда.

Вынесено из simulator.py (6.0b). Пока -- чистый перенос, поведение
не менялось. Дальше (6.1+) сюда приедут урон/атаки/лечение/искра/стойкость.
"""
import random
import config

# ============================================================
# Утилиты
# ============================================================
def roll_d6() -> int:
    """Бросок d6 (дубль simulator.roll_d6 -- чтобы не было циклического импорта)."""
    return random.randint(1, 6)
# ============================================================
# Б О Й
# ============================================================
def run_combat(party: list, monsters: list) -> tuple:
    """Проводит бой до победы или поражения команды.

       party -- боевые копии (make_fighter_copy), monsters -- боевые экземпляры.
       Возвращает (combat_log, changes):
       changes -- список дельт по порядку party:
       {"hp_delta", "xp_delta", "gold_delta"}. Оригиналы не трогаются.
    """
    hp_start = [b["hp"] for b in party]
    combat_log = {
        "party": [
            {**({"init": b["init"]} if b.get("init") else {}),
             "class": b["class"], "level": b["level"],
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

        hp_start_round = {
            "b": [b["hp"] for b in party],
            "m": [m["hp"] for m in monsters],
        }

        monsters_alive = [m for m in monsters if m["hp"] > 0]
        party_alive = [b for b in party if b["hp"] > 0]
        if not party_alive:
            combat_log["result"] = "lose"
        elif not monsters_alive:
            combat_log["result"] = "win"
        elif round_num > config.MAX_COMBAT_STEPS:
            combat_log["result"] = "stuck"

        if combat_log["result"] is not None:
            combat_log["rounds"].append({
                "round": round_num,
                "hp_start_round": hp_start_round,
            })
            break

        participants = []
        init_b = [None] * len(party)
        init_m = [None] * len(monsters)
        for i, b in enumerate(party):
            if b["hp"] > 0:
                r = roll_d6() + b.get("init", 0)
                participants.append(("b", i, r))
                init_b[i] = r
        for i, m in enumerate(monsters):
            if m["hp"] > 0:
                r = roll_d6() + m.get("init", 0)
                participants.append(("m", i, r))
                init_m[i] = r
        random.shuffle(participants)
        participants.sort(key=lambda x: x[2], reverse=True)

        round_actions = []
        for kind, idx, init in participants:
            if kind == "b":
                b = party[idx]
                if b["hp"] <= 0:
                    continue
                alive = [j for j, m in enumerate(monsters) if m["hp"] > 0]
                if not alive:
                    break
                target_j = random.choice(alive)
                target = monsters[target_j]
                roll = roll_d6()
                dmg = max(0, roll + b["at"] - target["df"])
                target["hp"] -= dmg
                target["hp"] = max(0, target["hp"])
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
                target["hp"] = max(0, target["hp"])
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

    if combat_log["result"] == "win":
        survivors = [b for b in party if b["hp"] > 0]
        total_xp = sum(m["xp"] for m in monsters)
        total_gd = sum(m["gd"] for m in monsters)
        if survivors:
            xp_share = total_xp // len(survivors)
            xp_rest = total_xp % len(survivors)
            for i, b in enumerate(survivors):
                b["xp"] += xp_share
                if i == 0:
                    b["xp"] += xp_rest
            gd_share = total_gd // len(survivors)
            gd_rest = total_gd % len(survivors)
            for i, b in enumerate(survivors):
                b["gold"] += gd_share
                if i == 0:
                    b["gold"] += gd_rest
            combat_log["xp_gained"] = total_xp
            combat_log["gold_gained"] = total_gd

    changes = [
        {"hp_delta": party[i]["hp"] - hp_start[i],
         "xp_delta": party[i]["xp"],
         "gold_delta": party[i]["gold"]}
        for i in range(len(party))
    ]
    return combat_log, changes
