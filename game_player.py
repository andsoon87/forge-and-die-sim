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
    except (IndexError, KeyError):
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

        self.root.title(f"Forge & Die II — Game Player — {os.path.basename(log_path)}")
        self.root.geometry("1200x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_widgets()
        self.draw_map()
        self.fill_steps_table()
        self.show_properties_empty()

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

        # График (пока пустой)
        plot_frame = tk.Frame(self.root)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.fig = Figure(figsize=(10, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.draw_plot()

        # Галочки (пока не подключены)
        checks = tk.Frame(self.root)
        checks.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(checks, text="График:").pack(side=tk.LEFT)
        for key, label in [
            ("hp_total", "HP сумма"),
            ("gold_total", "золото сумма"),
            ("xp_total", "XP сумма"),
            ("boiets_count", "бойцов"),
            ("tile_type", "тип тайла"),
            ("action", "действие"),
        ]:
            var = tk.BooleanVar(value=self.settings["plot"].get(key, False))
            self.settings["plot"][key] = var
            self.plot_vars[key] = var
            tk.Checkbutton(checks, text=label, variable=var).pack(side=tk.LEFT)

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
        """Клик по шагу -> выделить шаг (пока только запоминаем, свойства — шаг 4)."""
        sel = self.steps_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.selection = ("step", idx)
        self.draw_map()
        # свойства шага — шаг 4, пока заглушка
        self.show_properties_step(idx)

    # --------------------------------------------------------
    # Панель свойств
    # --------------------------------------------------------
    def show_properties_empty(self):
        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, "Ничего не выбрано.")
        self.open_combat_btn.config(state=tk.DISABLED)

    def show_properties_tile(self, floor: int, pos: int):
        tile_id = self.game_world[floor][pos]
        lines = [
            f"Тайл {tile_id}, этаж {floor + 1}, позиция {pos}",
            "",
            f"id:       {tile_id}",
            f"этаж:     {floor + 1}",
            f"позиция:  {pos}",
            f"тип:      {tile_type_name(tile_id)}",
            f"название: —",
        ]
        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, "\n".join(lines))
        self.open_combat_btn.config(state=tk.DISABLED)

    def show_properties_step(self, idx: int):
        # Заглушка шага 4 — пока просто сообщение
        self.props_text.delete("1.0", tk.END)
        self.props_text.insert(tk.END, f"Шаг {idx}\n\n(свойства шага — шаг 4)")
        self.open_combat_btn.config(state=tk.DISABLED)

    def open_combat(self):
        # Заглушка шага 4
        pass

    # --------------------------------------------------------
    # График (заглушка)
    # --------------------------------------------------------
    def draw_plot(self):
        self.ax.clear()
        self.ax.set_xlabel("Шаг")
        self.ax.set_ylabel("Значение")
        self.ax.set_title("График (пока пусто)")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

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