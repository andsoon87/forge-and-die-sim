"""Плеер журналов Forge & Die v2.0.

Читает JSON-лог партии, показывает шаги, состояние бойцов,
график суммарного HP и экспорт в TSV.
"""

import json
import os
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
# Загрузка сохраненных параметров
# ============================================================
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".config", "forge-and-die-sim")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "player.json")

DEFAULT_SETTINGS = {
    "last_dir": "",
    "tsv_cols": {
        "step": True,
        "floor": True,
        "tile_index": True,
        "tile_type": True,
        "action": True,
        "boiets_count": True,
        "hp_total": True,
        "gold_total": True,
        "xp_total": True,
        "boiets_detail": False,
    },
}


def load_settings() -> dict:
    if not os.path.isfile(SETTINGS_FILE):
        return json.loads(json.dumps(DEFAULT_SETTINGS))  # глубокая копия
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, v)
        for k, v in DEFAULT_SETTINGS["tsv_cols"].items():
            s["tsv_cols"].setdefault(k, v)
        return s
    except Exception:
        return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(settings: dict) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    to_save = {
        "last_dir": settings.get("last_dir", ""),
        "tsv_cols": {
            k: (v.get() if isinstance(v, tk.BooleanVar) else bool(v))
            for k, v in settings.get("tsv_cols", {}).items()
        },
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


# ============================================================
# Загрузка лога
# ============================================================

def load_log(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Человекочитаемые имена
# ============================================================

def tile_type_name(code: int) -> str:
    try:
        return data.TILE_TYPE_NAMES.get(data.TileType(code), str(code))
    except ValueError:
        return str(code)


def action_name(code: int) -> str:
    try:
        return data.ACTION_NAMES.get(data.Action(code), str(code))
    except ValueError:
        return str(code)


# ============================================================
# Агрегация HP для графика
# ============================================================

def hp_series(log: dict) -> list:
    """Суммарное HP всех бойцов на каждом шаге."""
    series = []
    for step in log.get("steps", []):
        total = sum(b["hp"] for b in step.get("party", []))
        series.append(total)
    return series


def aggregate(series: list, max_points: int) -> list:
    """Сжимает ряд до max_points (среднее по группам)."""
    n = len(series)
    if n <= max_points:
        return series
    step = n / max_points
    result = []
    for i in range(max_points):
        start = int(i * step)
        end = int((i + 1) * step)
        chunk = series[start:end]
        result.append(sum(chunk) / len(chunk) if chunk else 0)
    return result


# ============================================================
# Приложение
# ============================================================

class PlayerApp:
    def __init__(self, root, log, log_path, settings):
        self.root = root
        self.log = log
        self.log_path = log_path
        self.settings = settings
        self.steps = log.get("steps", [])
        self.current = 0
        self.total = len(self.steps)

        self.root.title(f"Forge & Die — Player — {os.path.basename(log_path)}")
        self.root.geometry("1000x750")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_widgets()
        self.draw_plot()
        self.show_step(0)

    # --------------------------------------------------------
    def create_widgets(self):
        # Верхняя панель навигации
        nav = tk.Frame(self.root)
        nav.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Button(nav, text="⏮ В начало", command=lambda: self.goto(0)).pack(side=tk.LEFT)
        tk.Button(nav, text="◀ Назад", command=self.prev_step).pack(side=tk.LEFT, padx=2)

        self.step_var = tk.StringVar(value="0")
        tk.Entry(nav, textvariable=self.step_var, width=6).pack(side=tk.LEFT, padx=5)
        tk.Label(nav, text=f"/ {self.total - 1}").pack(side=tk.LEFT)
        tk.Button(nav, text="Перейти", command=self.goto_entry).pack(side=tk.LEFT, padx=2)

        tk.Button(nav, text="Вперёд ▶", command=self.next_step).pack(side=tk.LEFT, padx=2)
        tk.Button(nav, text="⏭ В конец", command=lambda: self.goto(self.total - 1)).pack(side=tk.LEFT)

        # Информационная панель
        info = tk.Frame(self.root)
        info.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.info_text = tk.Text(info, height=14, wrap=tk.WORD, font=("Courier", 10))
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Панель экспорта
        export = tk.Frame(self.root)
        export.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Button(export, text="Экспорт в TSV", command=self.export_tsv).pack(side=tk.LEFT)
        tk.Label(export, text="  Колонки:").pack(side=tk.LEFT)

        self.col_vars = {}
        cols = [
            ("step", "шаг", True),
            ("floor", "этаж", True),
            ("tile_index", "позиция", True),
            ("tile_type", "тип тайла", True),
            ("action", "действие", True),
            ("boiets_count", "бойцов", True),
            ("hp_total", "HP сумма", True),
            ("gold_total", "золото сумма", True),
            ("xp_total", "XP сумма", True),
            ("boiets_detail", "детали бойцов", False),
        ]
        for key, label, default in cols:
            var = tk.BooleanVar(value=self.settings["tsv_cols"].get(key, default))
            self.col_vars[key] = var
            tk.Checkbutton(export, text=label, variable=var).pack(side=tk.LEFT)

        # График
        plot_frame = tk.Frame(self.root)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.fig = Figure(figsize=(9, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --------------------------------------------------------
    def draw_plot(self):
        series = hp_series(self.log)
        if not series:
            return
        agg = aggregate(series, config.MAX_POINTS)
        n_agg = len(agg)
        # ось X: реальные номера шагов (0 .. total-1), сжатые до n_agg точек
        if n_agg == len(series):
            xs = list(range(len(series)))
        else:
            step = len(series) / n_agg
            xs = [int(i * step) for i in range(n_agg)]

        self.ax.clear()
        self.ax.plot(xs, agg, color="tab:blue", linewidth=1.5, label="HP (сумма)")
        self.ax.set_xlabel("Шаг")
        self.ax.set_ylabel("HP")
        self.ax.set_title("Суммарное HP бойцов по шагам")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc="upper right")

        self.cursor = self.ax.axvline(x=0, color="red", linestyle="--", linewidth=1)
        self.canvas.draw()

    # --------------------------------------------------------
    def show_step(self, n: int):
        if not self.steps:
            return
        n = max(0, min(n, self.total - 1))
        self.current = n
        self.step_var.set(str(n))

        step = self.steps[n]
        lines = []
        lines.append(f"Шаг {step['step']}  |  Этаж {step['floor'] + 1}  |  Позиция {step['tile_index']}")
        lines.append(f"Тип тайла: {tile_type_name(step['tile_type'])}")
        avail = ", ".join(action_name(a) for a in step.get("available", []))
        lines.append(f"Доступно: {avail}")
        lines.append(f"Выбрано:  {action_name(step['action'])}")
        lines.append("")
        lines.append("Бойцы:")
        for b in step.get("party", []):
            lines.append(
                f"  {b['class']:<8} ур.{b['level']}  "
                f"HP {b['hp']}/{b['max_hp']}  XP {b['xp']}  золото {b['gold']}"
            )
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, "\n".join(lines))

        # курсор на графике
        if hasattr(self, "cursor"):
            self.cursor.set_xdata([step["step"], step["step"]])
            self.canvas.draw_idle()

    # --------------------------------------------------------
    def goto(self, n: int):
        self.show_step(n)

    def goto_entry(self):
        try:
            n = int(self.step_var.get())
        except ValueError:
            return
        self.show_step(n)

    def next_step(self):
        self.show_step(self.current + 1)

    def prev_step(self):
        self.show_step(self.current - 1)

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
        cols = self.col_vars
        header = []
        if cols["step"].get():
            header.append("step")
        if cols["floor"].get():
            header.append("floor")
        if cols["tile_index"].get():
            header.append("tile_index")
        if cols["tile_type"].get():
            header.append("tile_type")
        if cols["action"].get():
            header.append("action")
        if cols["boiets_count"].get():
            header.append("boiets_count")
        if cols["hp_total"].get():
            header.append("hp_total")
        if cols["gold_total"].get():
            header.append("gold_total")
        if cols["xp_total"].get():
            header.append("xp_total")
        if cols["boiets_detail"].get():
            for i in range(1, 5):
                header += [f"boiets_{i}_class", f"boiets_{i}_level",
                           f"boiets_{i}_hp", f"boiets_{i}_xp", f"boiets_{i}_gold"]
        f.write("\t".join(header) + "\n")

        for step in self.steps:
            row = []
            party = step.get("party", [])
            if cols["step"].get():
                row.append(str(step["step"]))
            if cols["floor"].get():
                row.append(str(step["floor"] + 1))
            if cols["tile_index"].get():
                row.append(str(step["tile_index"]))
            if cols["tile_type"].get():
                row.append(tile_type_name(step["tile_type"]))
            if cols["action"].get():
                row.append(action_name(step["action"]))
            if cols["boiets_count"].get():
                row.append(str(len(party)))
            if cols["hp_total"].get():
                row.append(str(sum(b["hp"] for b in party)))
            if cols["gold_total"].get():
                row.append(str(sum(b["gold"] for b in party)))
            if cols["xp_total"].get():
                row.append(str(sum(b["xp"] for b in party)))
            if cols["boiets_detail"].get():
                for i in range(4):
                    if i < len(party):
                        b = party[i]
                        row += [b["class"], str(b["level"]), str(b["hp"]),
                                str(b["xp"]), str(b["gold"])]
                    else:
                        row += ["", "", "", "", ""]
            f.write("\t".join(row) + "\n")

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
    log = load_log(path)
    root = tk.Tk()
    app = PlayerApp(root, log, path, settings)
    root.mainloop()


if __name__ == "__main__":
    main()
