"""Плеер одного боя Forge & Die II.

Читает JSON-лог партии и номер шага с боем, показывает:
- заголовок: шаг, игра, прогон, результат боя;
- левая панель — бойцы команды (class, level, at, df, hp/max_hp, инициатива);
- правая панель — монстры (at, df, hp/max_hp, инициатива);
- средняя верх — список раундов;
- средняя низ — текст действий выделенного раунда.

Запуск: python combat_player.py <log_path> <step_index>
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import data

# ============================================================
# Человекочитаемые имена
# ============================================================
def opponent_name(source: dict) -> str:
    """Готовая строка противника по source: монстр или обитатель лагеря."""
    t = source.get("type")
    if t == "monster":
        pool = source["pool"]
        monster = source["monster"]
        try:
            name = data.MONSTERS[pool][monster]["name"]
        except (IndexError, KeyError):
            name = "?"
        return f"({pool + 1}.{monster + 1}) {name}"
    if t == "camp":
        cls = data.CLASS_NAMES.get(source["class"], source["class"])
        return f"{cls} ур.{source['level']}"
    return "?"

def opponent_stats(source: dict) -> dict:
    """Базовые статы противника из data: at, df, hp."""
    t = source.get("type")
    if t == "monster":
        return data.MONSTERS[source["pool"]][source["monster"]]
    if t == "camp":
        return data.CLASSES[source["class"]][source["level"] - 1]
    return {"at": "?", "df": "?", "hp": "?"}

def result_name(result: str) -> str:
    return {"win": "победа", "lose": "поражение",
            "stuck": "зависание"}.get(result, result)

def combat_title(monsters: list) -> str:
    """Заголовок боя по типу противников (все одного типа)."""
    types = {m.get("type") for m in monsters}
    if types == {"monster"}:
        return "Бой с монстрами"
    if types == {"camp"}:
        return "Бой с обитателем лагеря"
    return "Бой"

# ============================================================
# Приложение
# ============================================================
class CombatPlayerApp:
    def __init__(self, root: tk.Tk, log: dict, step_index: int):
        self.root = root
        self.log = log
        self.step_index = step_index
        self.step = log["steps"][step_index]
        self.combat = self.step["combat"]
        self.rounds = self.combat.get("rounds", [])
        self.party = self.combat.get("party", [])
        self.monsters = self.combat.get("monsters", [])

        game_id = log.get("game_id", "?")
        run_id = log.get("run_id", "?")

        self.root.title(
            f"Forge & Die II — Combat Player — игра {game_id:04d}, шаг {step_index}"
        )
        self.root.geometry("600x600")

        self.create_widgets(game_id, run_id)
        self.fill_rounds()
        if self.rounds:
            self.select_round(len(self.rounds) - 1)

    # --------------------------------------------------------
    def create_widgets(self, game_id, run_id):
        # Заголовок
        header = tk.Frame(self.root)
        header.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        line1 = f"Бой на шаге {self.step_index}, игры {game_id:04d}, прогона {run_id}"
        tk.Label(header, text=line1, font=("TkDefaultFont", 12, "bold"),
                 anchor="w").pack(side=tk.TOP, fill=tk.X)

        res = result_name(self.combat.get("result", "?"))
        xp = self.combat.get("xp_gained", 0)
        gd = self.combat.get("gold_gained", 0)
        title = combat_title(self.monsters)
        line2 = f"{title}. Результат: {res}, XP +{xp}, золото +{gd}"
        tk.Label(header, text=line2, font=("TkDefaultFont", 9),
                 anchor="w").pack(side=tk.TOP, fill=tk.X)
        
        # Действия — прижаты к низу, на всю ширину, фиксированная высота
        actions_frame = tk.Frame(self.root)
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=5, pady=(0, 5))
        tk.Label(actions_frame, text="Действия", anchor="w").pack(side=tk.TOP, fill=tk.X)
        self.actions_text = tk.Text(actions_frame, height=9, wrap=tk.WORD, font=("Courier", 12))
        self.actions_text.pack(side=tk.TOP, fill=tk.X)

        # Верхний ряд: Три панели
        body = tk.Frame(self.root)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая: бойцы
        left = tk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text="Бойцы", anchor="w").pack(side=tk.TOP, fill=tk.X)
        self.party_text = tk.Text(left, width=1, wrap=tk.WORD, font=("Courier", 12))
        self.party_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Средняя: раунды
        middle = tk.Frame(body)
        middle.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        tk.Label(middle, text="Раунды", anchor="w").pack(side=tk.TOP, fill=tk.X)
        self.rounds_tree = ttk.Treeview(middle, columns=("round",), show="headings", height=14)
        self.rounds_tree.heading("round", text="Раунд")
        self.rounds_tree.column("round", width=1, anchor="center")
        self.rounds_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.rounds_tree.bind("<<TreeviewSelect>>", self.on_round_select)

        # Правая: монстры
        right = tk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(right, text="Монстры", anchor="w").pack(side=tk.TOP, fill=tk.X)
        self.monsters_text = tk.Text(right, width=1, wrap=tk.WORD, font=("Courier", 12))
        self.monsters_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # --------------------------------------------------------
    def fill_rounds(self):
        for item in self.rounds_tree.get_children():
            self.rounds_tree.delete(item)
        for idx, r in enumerate(self.rounds):
            self.rounds_tree.insert("", "end", iid=str(idx),
                                    values=(f"Раунд {r.get('round', idx + 1)}",))

    def select_round(self, idx: int):
        self.rounds_tree.selection_set(str(idx))
        self.rounds_tree.see(str(idx))

    def on_round_select(self, event):
        sel = self.rounds_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.update_panels(idx)
        self.update_actions(idx)

    # --------------------------------------------------------
    def update_panels(self, round_idx: int):
        """Левая/правая панели: HP и инициатива на начало выделенного раунда."""
        r = self.rounds[round_idx]
        hp_start = r.get("hp_start_round", {"b": [], "m": []})
        hp_b = hp_start.get("b", [])
        hp_m = hp_start.get("m", [])
        initiative = r.get("initiative")
        init_b = initiative.get("b", []) if initiative else []
        init_m = initiative.get("m", []) if initiative else []

        # Бойцы
        lines = []
        for i, b in enumerate(self.party):
            hp = hp_b[i] if i < len(hp_b) else "?"
            init = init_b[i] if i < len(init_b) else None
            cls = data.CLASS_NAMES.get(b["class"], b["class"])
            lines.append(
                f"{cls} ур.{b['level']}\n"
                f"  at: {b['at']}, df: {b['df']},\n"
                f"  hp: {hp}/{b['max_hp']},"
            )
            if init is not None:
                lines.append(f"  инициатива: {init}")
        self.party_text.delete("1.0", tk.END)
        self.party_text.insert(tk.END, "\n\n".join(lines) if lines else "—")

        # Противники (монстры или обитатели лагерей)
        lines = []
        for i, src_entry in enumerate(self.monsters):
            src = opponent_stats(src_entry)
            hp = hp_m[i] if i < len(hp_m) else "?"
            init = init_m[i] if i < len(init_m) else None
            lines.append(
                f"{opponent_name(src_entry)}\n"
                f"  at: {src['at']}, df: {src['df']},\n"
                f"  hp: {hp}/{src['hp']},"
            )
            if init is not None:
                lines.append(f"  инициатива: {init}")
        self.monsters_text.delete("1.0", tk.END)
        self.monsters_text.insert(tk.END, "\n\n".join(lines) if lines else "—")

    # --------------------------------------------------------
    def update_actions(self, round_idx: int):
        """Текстовая панель: действия выделенного раунда."""
        r = self.rounds[round_idx]
        actions = r.get("actions", [])
        is_final = "initiative" not in r

        if is_final:
            res = result_name(self.combat.get("result", "?"))
            xp = self.combat.get("xp_gained", 0)
            gd = self.combat.get("gold_gained", 0)
            text = (f"Бой завершён: {res}.\n"
                    f"XP +{xp}, золото +{gd}")
        else:
            if not actions:
                text = "(в этом раунде не было действий)"
            else:
                lines = ["Действия:"]
                for n, a in enumerate(actions, start=1):
                    actor = self.action_actor_name(a)
                    target = self.action_target_name(a)
                    lines.append(
                        f"  {n}. {actor} атакует {target}: "
                        f"d6={a.get('roll', '?')}, урон {a.get('damage', '?')}"
                    )
                text = "\n".join(lines)

        self.actions_text.delete("1.0", tk.END)
        self.actions_text.insert(tk.END, text)

    # --------------------------------------------------------
    def action_actor_name(self, a: dict) -> str:
        kind = a.get("actor")
        idx = a.get("actor_index", 0)
        if kind == "b":
            if idx < len(self.party):
                b = self.party[idx]
                return data.CLASS_NAMES.get(b["class"], b["class"])
            return f"боец {idx}"
        if idx < len(self.monsters):
            return opponent_name(self.monsters[idx])
        return f"противник {idx}"

    def action_target_name(self, a: dict) -> str:
        idx = a.get("target_index", 0)
        if a.get("actor") == "b":
            # боец бил противника
            if idx < len(self.monsters):
                return opponent_name(self.monsters[idx])
            return f"противник {idx}"
        else:
            # противник бил бойца
            if idx < len(self.party):
                b = self.party[idx]
                return data.CLASS_NAMES.get(b["class"], b["class"])
            return f"боец {idx}"

# ============================================================
# main
# ============================================================
def main():
    if len(sys.argv) < 3:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "combat_player",
            "Запускайте из game_player (кнопка «Открыть бой»).\n"
            "Использование: combat_player.py <log_path> <step_index>"
        )
        root.destroy()
        return

    log_path = sys.argv[1]
    try:
        step_index = int(sys.argv[2])
    except ValueError:
        return

    if not os.path.isfile(log_path):
        return

    with open(log_path, "r", encoding="utf-8") as f:
        log = json.load(f)

    steps = log.get("steps", [])
    if step_index < 0 or step_index >= len(steps):
        return
    if not steps[step_index].get("combat"):
        return

    root = tk.Tk()
    app = CombatPlayerApp(root, log, step_index)
    root.mainloop()


if __name__ == "__main__":
    main()
