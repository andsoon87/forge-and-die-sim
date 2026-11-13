"""Плеер журналов Forge & Die II (одна партия).

Читает JSON-лог партии, показывает:
- карту этажей (game_world);
- таблицу шагов;
- панель свойств (тайл или шаг);
- график и галочки (пока заглушки);
- экспорт в TSV (позже).

Настройки сохраняются в ~/.config/forge-and-die-sim/game_player.json.
"""

import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import config
import data


# ============================================================
# Настройки
# ============================================================
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".config", "forge-and-die-sim")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "game_player.json")

# Без дефолтов: нет файла -> всё выключено.
DEFAULT_SETTINGS = {
    "last_dir": "",
    "plot": {},   # сюда будем складывать галочки (ключ -> bool)
}


def load_settings() -> dict:
    if not os.path.isfile(SETTINGS_FILE):
        return {"last_dir": "", "plot": {}}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        s.setdefault("last_dir", "")
        s.setdefault("plot", {})
        return s
    except Exception:
        return {"last_dir": "", "plot": {}}


def save_settings(settings: dict) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    to_save = {
        "last_dir": settings.get("last_dir", ""),
        "plot": {
            k: (v.get() if isinstance(v, tk.BooleanVar) else bool(v))
            for k, v in settings.get("plot", {}).items()
        },
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


# ============================================================
# Человекочитаемые имена
# ============================================================
def tile_type_name(tile_id: int) -> str:
    try:
        t = data.TILES[tile_id]["type"]
        return data.TILE_TYPE_NAMES.get(t, str(t))
    except (IndexError, KeyError, TypeError):
        return "?"


def action_name(code: int) -> str:
    try:
        return data.ACTION_NAMES.get(data.Action(code), str(code))
    except ValueError:
        return str(code)


def result_name(result: str) -> str:
    return {"win": "победа", "dead": "погибли", "stuck": "застряли"}.get(result, result)


# ============================================================
# Цвета типов тайлов (презентация)
# ============================================================
TILE_TYPE_COLORS = {
    data.TileType.START: "#8fbf6f",
    data.TileType.FORGE: "#e8a33d",
    data.TileType.MONSTER: "#c0504d",
    data.TileType.TREASURE: "#e3c44a",
    data.TileType.EVENT: "#5b8fd6",
    data.TileType.CAMP: "#9b6fbf",
    data.TileType.TRADER: "#a9744f",
}

MAP_ROW_HEIGHT = 22      # высота строки этажа (px)
MAP_PAD = 10             # отступы вокруг карты
MAP_SLOTS = 61           # фиксированное число слотов


# ============================================================
# Приложение
# ============================================================
class GamePlayerApp:
    def __init__(self, root: tk.Tk, log: dict, log_path: str, settings: dict):
        self.root = root
        self.log = log
        self.log_path = log_path
        self.settings = settings
        self.steps = log.get("steps", [])
        self.game_world = log.get("game_world", [])

        # Текущее выделение: ("tile", floor, pos) или ("step", index) или None
        self.selection = None

        # Галочки графика: ключ -> BooleanVar
        self.plot_vars = {}
        self.series = None
        self.cursor_line = None

        self.root.title(f"Forge & Die II — Game Player — {os.path.basename(log_path)}")
        self.root.geometry("1200x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_widgets()
        self.draw_map()
        self.fill_steps_table()
        self.show_properties_empty()
    # --------------------------------------------------------
    # Расчёт метрик
    # --------------------------------------------------------
    def compute_series(self):
        """Считает метрики по шагам для графика и TSV."""
        hp_total = []
        gold_total = []
        xp_total = []
        level_total = []
        boiets_count = []
        per_boiets = {i: {"hp": [], "gold": [], "xp": [], "level": []}
                      for i in range(4)}

        for step in self.steps:
            party = step.get("party", [])
            hp_total.append(sum(b["hp"] for b in party))
            gold_total.append(sum(b["gold"] for b in party))
            xp_total.append(sum(b["xp"] for b in party))
            level_total.append(sum(b["level"] for b in party))
            boiets_count.append(len(party))
            for i in range(4):
                if i < len(party):
                    b = party[i]
                    per_boiets[i]["hp"].append(b["hp"])
                    per_boiets[i]["gold"].append(b["gold"])
                    per_boiets[i]["xp"].append(b["xp"])
                    per_boiets[i]["level"].append(b["level"])
                else:
                    per_boiets[i]["hp"].append(None)
                    per_boiets[i]["gold"].append(None)
                    per_boiets[i]["xp"].append(None)
                    per_boiets[i]["level"].append(None)

        self.series = {
            "hp_total": hp_total,
            "gold_total": gold_total,
            "xp_total": xp_total,
            "level_total": level_total,
            "boiets_count": boiets_count,
            "boiets": per_boiets,
        }
    
    # --------------------------------------------------------
    def create_widgets(self):
        # Заголовок партии (две строки)
        header = tk.Frame(self.root)
        header.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        game_id = self.log.get("game_id", "?")
        run_id = self.log.get("run_id", "?")
        big = f"Forge & Die II — партия {game_id:04d} — прогон {run_id}"
        tk.Label(header, text=big, font=("TkDefaultFont", 13, "bold"),
                 anchor="w").pack(side=tk.TOP, fill=tk.X)

        profile = self.log.get("profile", "?")
        klass = self.log.get("class", "?")
        result = self.log.get("result", "?")
        final_floor = self.log.get("final_floor", 0)
        seed = self.log.get("seed", "?")
        small = (f"профиль бота: {profile}, стартовый боец: {klass}, "
                 f"результат: {result_name(result)} ({result}), "
                 f"финальный этаж {final_floor + 1}, зерно (seed): {seed}")
        tk.Label(header, text=small, font=("TkDefaultFont", 9),
                 anchor="w").pack(side=tk.TOP, fill=tk.X)

        # Карта
        map_frame = tk.Frame(self.root)
        map_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.map_canvas = tk.Canvas(map_frame, height=4 * MAP_ROW_HEIGHT + 2 * MAP_PAD,
                                    bg="#f0f0f0", highlightthickness=0)
        self.map_canvas.pack(fill=tk.X, expand=False)
        self.map_canvas.bind("<Button-1>", self.on_map_click)
        self.map_canvas.bind("<Configure>", lambda e: self.draw_map())

        # Легенда под картой: цветной квадратик + название типа тайла
        legend_frame = tk.Frame(self.root)
        legend_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
        for tile_type, name in data.TILE_TYPE_NAMES.items():
            color = TILE_TYPE_COLORS.get(tile_type, "#999999")
            item = tk.Frame(legend_frame)
            item.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(item, bg=color, width=2, height=1,
                     relief=tk.SOLID, borderwidth=1).pack(side=tk.LEFT)
            tk.Label(item, text=name, anchor="w").pack(side=tk.LEFT, padx=(3, 0))

        # Средний блок: свойства (слева) + таблица шагов (справа)
        middle = tk.Frame(self.root)
        middle.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Свойства
        props_frame = tk.Frame(middle)
        props_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(props_frame, text="Свойства", anchor="w").pack(side=tk.TOP, fill=tk.X)
        self.props_text = tk.Text(props_frame, width=45, height=14, wrap=tk.WORD,
                                  font=("Courier", 10))
        self.props_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.open_combat_btn = tk.Button(props_frame, text="Открыть бой",
                                         command=self.open_combat, state=tk.DISABLED)
        self.open_combat_btn.pack(side=tk.TOP, anchor="w", pady=3)

        # Таблица шагов
        steps_frame = tk.Frame(middle)
        steps_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        tk.Label(steps_frame, text="Шаги", anchor="w").pack(side=tk.TOP, fill=tk.X)
        cols = ("step", "floor", "position", "tile_id", "action", "combat")
        self.steps_tree = ttk.Treeview(steps_frame, columns=cols, show="headings", height=14)
        for c, w in [("step", 60), ("floor", 60), ("position", 70),
                     ("tile_id", 70), ("action", 120), ("combat", 160)]:
            self.steps_tree.heading(c, text=c)
            self.steps_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(steps_frame, orient="vertical", command=self.steps_tree.yview)
        self.steps_tree.configure(yscrollcommand=vsb.set)
        self.steps_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)
        self.steps_tree.bind("<<TreeviewSelect>>", self.on_step_click)

        # График
        plot_frame = tk.Frame(self.root)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.fig = Figure(figsize=(10, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.mpl_connect("button_press_event", self.on_plot_click)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Галочки (общие) + кнопка «Детали бойцов…»
        checks = tk.Frame(self.root)
        checks.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(checks, text="График:").pack(side=tk.LEFT)
        for key, label in [
            ("hp_total", "HP сумма"),
            ("gold_total", "золото сумма"),
            ("xp_total", "XP сумма"),
            ("level_total", "уровень сумма"),
            ("boiets_count", "бойцов"),
            ("tile_type", "тип тайла (TSV)"),
            ("action", "действие (TSV)"),
        ]:
            var = tk.BooleanVar(value=self.settings["plot"].get(key, False))
            self.settings["plot"][key] = var
            self.plot_vars[key] = var
            tk.Checkbutton(checks, text=label, variable=var,
                           command=self.on_plot_var_changed).pack(side=tk.LEFT)
        tk.Button(checks, text="Детали бойцов…",
                  command=self.open_boiets_details).pack(side=tk.LEFT, padx=5)
        tk.Button(checks, text="Экспорт в TSV",
                  command=self.export_tsv).pack(side=tk.LEFT, padx=5)
        self.draw_plot()

    # --------------------------------------------------------
    # Карта
    # --------------------------------------------------------
    def draw_map(self):
        c = self.map_canvas
        c.delete("all")
        width = c.winfo_width()
        if width <= 1:
            # до первого Configure ширина может быть 1 — ничего не рисуем
            return

        cell_w = max(4, (width - 2 * MAP_PAD) / MAP_SLOTS)
        n_floors = len(self.game_world)

        for floor in range(n_floors):
            tiles = self.game_world[floor]
            y0 = MAP_PAD + floor * MAP_ROW_HEIGHT
            y1 = y0 + MAP_ROW_HEIGHT - 2
            for pos, tile_id in enumerate(tiles):
                x0 = MAP_PAD + pos * cell_w
                x1 = x0 + cell_w - 1
                color = "#999999"
                try:
                    t = data.TILES[tile_id]["type"]
                    color = TILE_TYPE_COLORS.get(t, "#999999")
                except (IndexError, KeyError):
                    pass
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline="#666666",
                                   tags=("tile", f"tile_{floor}_{pos}"))

        # Обводка выделенного тайла
        if self.selection and self.selection[0] == "tile":
            _, floor, pos = self.selection
            tiles = self.game_world[floor] if floor < len(self.game_world) else []
            if pos < len(tiles):
                x0 = MAP_PAD + pos * cell_w
                x1 = x0 + cell_w - 1
                y0 = MAP_PAD + floor * MAP_ROW_HEIGHT
                y1 = y0 + MAP_ROW_HEIGHT - 2
                c.create_rectangle(x0, y0, x1, y1, outline="#000000", width=2)

        # Фишка выделенного шага
        if self.selection and self.selection[0] == "step":
            idx = self.selection[1]
            if 0 <= idx < len(self.steps):
                step = self.steps[idx]
                floor = step["floor"]
                pos = step["position"]
                tiles = self.game_world[floor] if floor < len(self.game_world) else []
                if pos < len(tiles):
                    x0 = MAP_PAD + pos * cell_w
                    cx = x0 + cell_w / 2
                    cy = MAP_PAD + floor * MAP_ROW_HEIGHT + (MAP_ROW_HEIGHT - 2) / 2
                    r = max(2, cell_w / 3)
                    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  fill="white", outline="black", width=2)

    def on_map_click(self, event):
        """Клик по клетке карты -> выделить тайл."""
        c = self.map_canvas
        width = c.winfo_width()
        if width <= 1:
            return
        cell_w = max(4, (width - 2 * MAP_PAD) / MAP_SLOTS)
        x = event.x - MAP_PAD
        y = event.y - MAP_PAD
        if x < 0 or y < 0:
            return
        pos = int(x // cell_w)
        floor = int(y // MAP_ROW_HEIGHT)
        if floor >= len(self.game_world):
            return
        if pos >= len(self.game_world[floor]):
            return
        # сброс выделения шага
        self.steps_tree.selection_remove(self.steps_tree.selection())
        self.selection = ("tile", floor, pos)
        self.draw_map()
        self.show_properties_tile(floor, pos)
        self.draw_plot()

    # --------------------------------------------------------
    # Таблица шагов
    # --------------------------------------------------------
    def fill_steps_table(self):
        for item in self.steps_tree.get_children():
            self.steps_tree.delete(item)
        for idx, step in enumerate(self.steps):
            combat = step.get("combat")
            combat_short = ""
            if combat:
                r = combat.get("result", "?")
                n = len(combat.get("rounds", []))
                combat_short = f"{r}, {n} р."
            self.steps_tree.insert("", "end", iid=str(idx), values=(
                step.get("step", idx),
                step.get("floor", 0) + 1,
                step.get("position", 0),
                step.get("tile_id", "?"),
                action_name(step.get("action", -1)),
                combat_short,
            ))

    def on_step_click(self, event):
        sel = self.steps_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.selection = ("step", idx)
        self.draw_map()
        self.show_properties_step(idx)

        step = self.steps[idx]
        combat = step.get("combat")
        if combat and combat.get("rounds"):
            self.open_combat_btn.config(state=tk.NORMAL)
        else:
            self.open_combat_btn.config(state=tk.DISABLED)

        self.draw_plot()

    # --------------------------------------------------------
    # Панель свойств
    # --------------------------------------------------------
    def show_properties_empty(self):
        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, "Ничего не выбрано.")
        self.open_combat_btn.config(state=tk.DISABLED)

    def show_properties_tile(self, floor: int, pos: int):
        tile_id = self.game_world[floor][pos]
        try:
            name = data.TILES[tile_id]["name"]
        except (IndexError, KeyError, TypeError):
            name = "—"
        lines = [
            f"Тайл {tile_id}, этаж {floor + 1}, позиция {pos}",
            "",
            f"id:       {tile_id}",
            f"этаж:     {floor + 1}",
            f"позиция:  {pos}",
            f"тип:      {tile_type_name(tile_id)}",
            f"название: {name}",
        ]
        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, "\n".join(lines))
        self.open_combat_btn.config(state=tk.DISABLED)

    def show_properties_step(self, idx: int):
        step = self.steps[idx]
        lines = [f"Шаг {step.get('step', idx)}", ""]

        # Бойцы
        party = step.get("party", [])
        if party:
            lines.append("Бойцы:")
            for b in party:
                cls = data.CLASS_NAMES.get(b["class"], b["class"])
                lines.append(
                    f"  {cls} ур.{b['level']}, "
                    f"HP {b['hp']}/{b['max_hp']}, "
                    f"XP {b['xp']}, золото {b['gold']}"
                )
            lines.append("")

        # События в начале хода
        free_events = step.get("free_events", [])
        if free_events:
            lines.append("В начале хода:")
            for ev in free_events:
                if ev.get("event") == "level_up":
                    cls = data.CLASS_NAMES.get(ev["class"], ev["class"])
                    lines.append(
                        f"  новый уровень "
                        f"({cls} {ev['from_level']}→{ev['to_level']})"
                    )
                elif ev.get("event") == "death":
                    cls = data.CLASS_NAMES.get(ev["class"], ev["class"])
                    lines.append(f"  погиб: {cls} ур.{ev['level']}")
                else:
                    lines.append(f"  {ev}")
            lines.append("")

        # Ход
        lines.append("Ход:")
        floor = step.get("floor", 0) + 1
        pos = step.get("position", 0)
        tile_id = step.get("tile_id", "?")
        lines.append(f"  этаж: {floor}, позиция: {pos}, тайл: ({tile_id}) {tile_type_name(tile_id)}")

        avail = ", ".join(action_name(a) for a in step.get("available", []))
        lines.append(f"  доступно: {avail}")
        lines.append(f"  выбрано:  {action_name(step.get('action', -1))}")

        flee_roll = step.get("flee_roll")
        if flee_roll is not None:
            outcome = "побег" if flee_roll <= 3 else "неудача"
            lines.append(f"  попытка бегства: d6={flee_roll} ({outcome})")

        camp = step.get("camp")
        if camp:
            cls = data.CLASS_NAMES.get(camp["class"], camp["class"])
            present = camp.get("present")
            attitude = camp.get("attitude")
            lines.append("")
            lines.append("Лагерь:")
            lines.append(f"  класс: {cls}, уровень: {camp.get('level')}")
            lines.append(f"  настрой: {attitude} (present={present})")
            rolls = camp.get("rolls")
            if rolls:
                lines.append(
                    f"  броски: present={rolls.get('present')}, "
                    f"level={rolls.get('level')}, "
                    f"attitude={rolls.get('attitude')}"
                )
            else:
                lines.append("  броски: — (повторный визит)")

        combat = step.get("combat")
        if combat:
            rounds = len(combat.get("rounds", []))
            res = combat.get("result", "?")
            res_ru = {"win": "Победа", "lose": "Поражение",
                      "flee": "Побег", "stuck": "Зависание"}.get(res, res)
            xp = combat.get("xp_gained", 0)
            gd = combat.get("gold_gained", 0)
            lines.append(f"  бой: {res_ru}, {rounds} раунда, XP +{xp}, золото +{gd}")
            monsters = combat.get("monsters", [])
            if monsters:
                names = []
                for m in monsters:
                    t = m.get("type")
                    if t == "monster":
                        pool = m["pool"]
                        monster = m["monster"]
                        try:
                            name = data.MONSTERS[pool][monster]["name"]
                        except (IndexError, KeyError):
                            name = "?"
                        names.append(f"({pool + 1}.{monster + 1}) {name}")
                    elif t == "camp":
                        cls = data.CLASS_NAMES.get(m["class"], m["class"])
                        names.append(f"{cls} ур.{m['level']}")
                    else:
                        names.append("?")
                lines.append(f"    противники: {', '.join(names)}")

        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, "\n".join(lines))

    def open_combat(self):
        if not self.selection or self.selection[0] != "step":
            return
        idx = self.selection[1]
        step = self.steps[idx]
        combat = step.get("combat")
        if not combat or not combat.get("rounds"):
            return
        combat_player_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "combat_player.py"
        )
        try:
            subprocess.Popen([sys.executable, combat_player_path,
                              self.log_path, str(idx)])
        except Exception as e:
            messagebox.showerror("Ошибка запуска", str(e))

    # --------------------------------------------------------
    # График
    # --------------------------------------------------------
    def draw_plot(self):
        self.ax.clear()
        self.ax.set_xlabel("Шаг")
        self.ax.set_ylabel("Значение")
        self.ax.set_title("Метрики по шагам")
        self.ax.grid(True, alpha=0.3)

        if not self.series:
            self.compute_series()

        xs = list(range(len(self.steps)))
        s = self.series

        # общие числовые
        for key, label in [
            ("hp_total", "HP сумма"),
            ("gold_total", "золото сумма"),
            ("xp_total", "XP сумма"),
            ("level_total", "уровень сумма"),
            ("boiets_count", "бойцов"),
        ]:
            var = self.plot_vars.get(key)
            if var is not None and var.get():
                self.ax.plot(xs, s[key], linewidth=1.5, label=label)

        # детали по бойцам
        for i in range(4):
            for sub, label_sub in [
                ("hp", "HP"), ("gold", "золото"),
                ("xp", "XP"), ("level", "уровень"),
            ]:
                key = f"boiets_{i+1}_{sub}"
                var = self.plot_vars.get(key)
                if var is not None and var.get():
                    self.ax.plot(xs, s["boiets"][i][sub],
                                 linewidth=1.2, label=f"Б{i+1} {label_sub}")

        # курсор на выделенном шаге
        self.cursor_line = None
        if self.selection and self.selection[0] == "step":
            idx = self.selection[1]
            if 0 <= idx < len(self.steps):
                self.cursor_line = self.ax.axvline(
                    x=idx, color="red", linestyle="--", linewidth=1
                )

        if self.ax.get_legend_handles_labels()[0]:
            self.ax.legend(loc="upper right", fontsize=8)

        self.canvas.draw()

    # --------------------------------------------------------
    def on_plot_var_changed(self):
        self.draw_plot()    
    
    # --------------------------------------------------------
    def export_tsv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".tsv",
            filetypes=[("TSV", "*.tsv"), ("All files", "*.*")],
            initialfile=os.path.splitext(os.path.basename(self.log_path))[0] + ".tsv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                self._write_tsv(f)
            messagebox.showinfo("Экспорт", f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _write_tsv(self, f):
        if not self.series:
            self.compute_series()

        # Список колонок: (ключ, заголовок, тип)
        # тип: "series" — из self.series (число), "step" — из шага (категориальное)
        columns = [("step", "step", "step")]

        # общие числовые
        for key, label in [
            ("hp_total", "hp_total"),
            ("gold_total", "gold_total"),
            ("xp_total", "xp_total"),
            ("level_total", "level_total"),
            ("boiets_count", "boiets_count"),
        ]:
            var = self.plot_vars.get(key)
            if var is not None and var.get():
                columns.append((key, label, "series"))

        # детали по бойцам
        for i in range(4):
            for sub in ("hp", "gold", "xp", "level"):
                key = f"boiets_{i+1}_{sub}"
                var = self.plot_vars.get(key)
                if var is not None and var.get():
                    columns.append((key, key, "boiets_series"))

        # категориальные
        if self.plot_vars.get("tile_type") and self.plot_vars["tile_type"].get():
            columns.append(("tile_type", "tile_type", "step_tile_type"))
        if self.plot_vars.get("action") and self.plot_vars["action"].get():
            columns.append(("action", "action", "step_action"))

        # заголовок
        f.write("\t".join(label for _, label, _ in columns) + "\n")

        # строки
        for idx, step in enumerate(self.steps):
            row = []
            for key, label, kind in columns:
                if kind == "step":
                    row.append(str(step.get("step", idx)))
                elif kind == "series":
                    row.append(str(self.series[key][idx]))
                elif kind == "boiets_series":
                    # ключ вида boiets_1_hp -> i=0, sub="hp"
                    parts = key.split("_")
                    bi = int(parts[1]) - 1
                    sub = parts[2]
                    val = self.series["boiets"][bi][sub][idx]
                    row.append("" if val is None else str(val))
                elif kind == "step_tile_type":
                    row.append(tile_type_name(step.get("tile_id", "?")))
                elif kind == "step_action":
                    row.append(action_name(step.get("action", -1)))
            f.write("\t".join(row) + "\n")    
    
    # --------------------------------------------------------
    def open_boiets_details(self):
        win = tk.Toplevel(self.root)
        win.title("Детали бойцов")
        win.transient(self.root)
        win.grab_set()

        temp_vars = {}
        for i in range(4):
            frame = tk.LabelFrame(win, text=f"Боец {i+1}")
            frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=3)
            for sub, label_sub in [
                ("hp", "HP"), ("gold", "золото"),
                ("xp", "XP"), ("level", "уровень"),
            ]:
                key = f"boiets_{i+1}_{sub}"
                existing = self.plot_vars.get(key)
                value = existing.get() if existing is not None else False
                var = tk.BooleanVar(value=value)
                temp_vars[key] = var
                tk.Checkbutton(frame, text=label_sub,
                               variable=var).pack(side=tk.LEFT)

        btns = tk.Frame(win)
        btns.pack(side=tk.TOP, pady=5)

        def on_ok():
            for key, var in temp_vars.items():
                if key in self.plot_vars:
                    self.plot_vars[key].set(var.get())
                else:
                    self.plot_vars[key] = var
                    self.settings["plot"][key] = var
            win.destroy()
            self.draw_plot()

        def on_cancel():
            win.destroy()

        tk.Button(btns, text="ОК", command=on_ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Отмена", command=on_cancel).pack(side=tk.LEFT, padx=5)    
    
    # --------------------------------------------------------
    def on_plot_click(self, event):
        if event.xdata is None:
            return
        idx = int(round(event.xdata))
        if idx < 0:
            idx = 0
        if idx >= len(self.steps):
            idx = len(self.steps) - 1
        # выделяем шаг в таблице; синхронизация через on_step_click
        self.steps_tree.selection_set(str(idx))
        self.steps_tree.see(str(idx))    
    
    # --------------------------------------------------------
    def on_close(self):
        save_settings(self.settings)
        self.root.destroy()


# ============================================================
# main
# ============================================================
def main():
    settings = load_settings()

    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]
    if not path:
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Выберите JSON-лог партии",
            initialdir=settings.get("last_dir") or (
                config.LOGS_DIR if os.path.isdir(config.LOGS_DIR) else "."
            ),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        root.destroy()
    if not path:
        return

    settings["last_dir"] = os.path.dirname(path)
    with open(path, "r", encoding="utf-8") as f:
        log = json.load(f)

    root = tk.Tk()
    app = GamePlayerApp(root, log, path, settings)
    root.mainloop()


if __name__ == "__main__":
    main()