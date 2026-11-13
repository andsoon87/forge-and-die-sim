"""Просмотр прогона Forge & Die II.

Читает папку прогона (meta.json + game_*.json + stats.json),
показывает сводку, таблицы, гистограммы и экспорт в TSV.

Из таблицы можно открыть партию в game_player.py (двойной клик
или контекстное меню).

Настройки (галочки TSV, последняя папка) сохраняются в
~/.config/forge-and-die-sim/run_player.json.
"""

import glob
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
# Настройки (сохранение между запусками)
# ============================================================
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".config", "forge-and-die-sim")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "run_player.json")

DEFAULT_SETTINGS = {
    "last_run_dir": "",
    "tsv_cols": {
        "summary": True,
        "final_floor": True,
        "averages": True,
        "hist_steps": False,
    },
}


def load_settings() -> dict:
    if not os.path.isfile(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        # добиваем недостающие ключи
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, v)
        for k, v in DEFAULT_SETTINGS["tsv_cols"].items():
            s["tsv_cols"].setdefault(k, v)
        return s
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    # преобразуем BooleanVar → bool
    to_save = {
        "last_run_dir": settings.get("last_run_dir", ""),
        "tsv_cols": {
            k: (v.get() if isinstance(v, tk.BooleanVar) else bool(v))
            for k, v in settings.get("tsv_cols", {}).items()
        },
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

# ============================================================
# Загрузка прогона
# ============================================================
def load_run(run_dir: str) -> dict:
    meta_path = os.path.join(run_dir, "meta.json")
    stats_path = os.path.join(run_dir, "stats.json")
    games = []

    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {}

    if os.path.isfile(stats_path):
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
    else:
        stats = {}

    for path in sorted(glob.glob(os.path.join(run_dir, "game_*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            game = json.load(f)
        game["_path"] = path
        # fallback: game_id из имени файла, если поля нет
        if "game_id" not in game:
            base = os.path.basename(path)
            try:
                game["game_id"] = int(base[len("game_"):-len(".json")])
            except ValueError:
                game["game_id"] = 0
        games.append(game)

    return {"meta": meta, "stats": stats, "games": games}

# ============================================================
# Подсчёт статистики
# ============================================================
def compute_stats(run: dict) -> dict:
    games = run["games"]
    n = len(games)

    final_floor_counts = {}
    steps_list = []
    result_list = []
    final_levels = []
    final_hp = []
    final_gold = []
    final_xp = []

    for g in games:
        ff = g.get("final_floor", 0)
        final_floor_counts[ff] = final_floor_counts.get(ff, 0) + 1
        steps_list.append(len(g.get("steps", [])))
        result_list.append(g.get("result", "?"))

        # последний шаг
        if g.get("steps"):
            last = g["steps"][-1]
            party = last.get("party", [])
            if party:
                final_levels.append(party[0]["level"])
                final_hp.append(sum(b["hp"] for b in party))
                final_gold.append(sum(b["gold"] for b in party))
                final_xp.append(sum(b["xp"] for b in party))

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    return {
        "games_total": n,
        "win": run["stats"].get("win", 0),
        "stuck": run["stats"].get("stuck", 0),
        "dead": run["stats"].get("dead", 0),
        "final_floor_counts": final_floor_counts,
        "avg_steps": avg(steps_list),
        "avg_final_level": avg(final_levels),
        "avg_final_hp": avg(final_hp),
        "avg_final_gold": avg(final_gold),
        "avg_final_xp": avg(final_xp),
        "steps_list": steps_list,
        "final_floor_list": [g.get("final_floor", 0) for g in games],
    }

# ============================================================
# Приложение
# ============================================================
class RunPlayerApp:
    def __init__(self, root: tk.Tk, run_dir: str, settings: dict):
        self.root = root
        self.run_dir = run_dir
        self.settings = settings
        self.run = None
        self.stats = None

        self.root.title(f"Forge & Die II — Run Player -- {os.path.basename(run_dir.rstrip('/'))}")
        self.root.geometry("1000x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_widgets()
        self.load_and_show()

    # --------------------------------------------------------
    def create_widgets(self):
        top = tk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Label(top, text="Прогон:").pack(side=tk.LEFT)
        self.run_label = tk.Label(top, text=self.run_dir, anchor="w")
        self.run_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(top, text="Выбрать…", command=self.choose_run).pack(side=tk.LEFT)
        tk.Button(top, text="Обновить", command=self.load_and_show).pack(side=tk.LEFT, padx=2)

        # Сводка
        summary_frame = tk.Frame(self.root)
        summary_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.summary_text = tk.Text(summary_frame, height=10, wrap=tk.WORD, font=("Courier", 10))
        self.summary_text.pack(fill=tk.X)

        # Таблица партий
        table_frame = tk.Frame(self.root)
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(table_frame, text="Партии (двойной клик — открыть в game_player):", anchor="w").pack(side=tk.TOP, fill=tk.X)
        
        columns = ("game_id", "steps", "result")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("game_id", text="game_id", command=lambda: self.sort_by("game_id"))
        self.tree.heading("steps", text="steps", command=lambda: self.sort_by("steps"))
        self.tree.heading("result", text="result", command=lambda: self.sort_by("result"))
        self.tree.column("game_id", width=80, anchor="center")
        self.tree.column("steps", width=80, anchor="center")
        self.tree.column("result", width=160, anchor="center")
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)
        
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        
        # Контекстное меню
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Открыть в плеере", command=self.open_selected_in_player)
        self.context_menu.add_command(label="Открыть папку", command=self.open_selected_folder)
        self.context_menu.add_command(label="Скопировать game_id", command=self.copy_selected_game_id)

        # Экспорт
        export = tk.Frame(self.root)
        export.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Button(export, text="Экспорт в TSV", command=self.export_tsv).pack(side=tk.LEFT)
        tk.Label(export, text="  Таблицы:").pack(side=tk.LEFT)
        for key, label in [
            ("summary", "сводка"),
            ("final_floor", "финальный этаж"),
            ("averages", "средние"),
            ("hist_steps", "гистограмма шагов"),
        ]:
            var = tk.BooleanVar(value=self.settings["tsv_cols"].get(key, True))
            self.settings["tsv_cols"][key] = var
            tk.Checkbutton(export, text=label, variable=var).pack(side=tk.LEFT)

        # Графики (две гистограммы)
        plots_frame = tk.Frame(self.root)
        plots_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.fig = Figure(figsize=(10, 4), dpi=100)
        self.ax1 = self.fig.add_subplot(121)
        self.ax2 = self.fig.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plots_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --------------------------------------------------------
    def choose_run(self):
        path = filedialog.askdirectory(
            title="Выберите папку прогона",
            initialdir=self.settings.get("last_run_dir") or (
                config.LOGS_DIR if os.path.isdir(config.LOGS_DIR) else "."
            ),
        )
        if not path:
            return
        self.run_dir = path
        self.settings["last_run_dir"] = path
        self.run_label.config(text=path)
        self.load_and_show()

    # --------------------------------------------------------
    def load_and_show(self):
        try:
            self.run = load_run(self.run_dir)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return
        self.stats = compute_stats(self.run)
        self.show_summary()
        self.fill_table()
        self.draw_plots()

    # --------------------------------------------------------
    def show_summary(self):
        meta = self.run["meta"]
        s = self.stats
        lines = [
            f"Прогон: {meta.get('run_id', '?')}",
            f"Профиль: {meta.get('profile', '?')} | Класс: {meta.get('class', '?')} | Партий: {s['games_total']}",
            f"Версия: {meta.get('project_version', '?')} | Начат: {meta.get('started_at', '?')} | Закончен: {meta.get('finished_at', '?')}",
            "",
            f"Победа: {s['win']} ({self._pct(s['win'], s['games_total'])})",
            f"Погибли: {s['dead']} ({self._pct(s['dead'], s['games_total'])})",
            f"Застряли: {s['stuck']} ({self._pct(s['stuck'], s['games_total'])})",
            "",
            f"Среднее число шагов: {s['avg_steps']:.1f}",
            f"Средний финальный уровень: {s['avg_final_level']:.2f}",
            f"Среднее HP (сумма): {s['avg_final_hp']:.1f}",
            f"Среднее золото (сумма): {s['avg_final_gold']:.1f}",
            f"Среднее XP (сумма): {s['avg_final_xp']:.1f}",
        ]
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, "\n".join(lines))

    # --------------------------------------------------------
    def fill_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for g in self.run["games"]:
            self.tree.insert("", "end", values=(
                g.get("game_id", 0),
                len(g.get("steps", [])),
                g.get("result", "?"),
            ))

    # --------------------------------------------------------
    def sort_by(self, key: str):
        """Сортировка таблицы по клику на заголовок."""
        games = self.run["games"]
        if key == "game_id":
            games.sort(key=lambda g: g.get("game_id", 0))
        elif key == "steps":
            games.sort(key=lambda g: len(g.get("steps", [])))
        elif key == "result":
            games.sort(key=lambda g: g.get("result", ""))
        self.fill_table()
        
    # --------------------------------------------------------
    def _selected_game(self):
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        if not values:
            return None
        try:
            game_id = int(values[0])
        except ValueError:
            return None
        for g in self.run["games"]:
            if g.get("game_id") == game_id:
                return g
        return None
    
    # --------------------------------------------------------
    def on_double_click(self, event):
        self.open_selected_in_player()
    
    # --------------------------------------------------------
    def on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.context_menu.post(event.x_root, event.y_root)
    
    # --------------------------------------------------------
    def open_selected_in_player(self):
        g = self._selected_game()
        if not g:
            return
        path = g.get("_path")
        if not path:
            messagebox.showerror("Ошибка", "Не найден путь к логу партии")
            return
        game_player_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_player.py")
        try:
            subprocess.Popen([sys.executable, game_player_path, path])
        except Exception as e:
            messagebox.showerror("Ошибка запуска", str(e))   
    
    # --------------------------------------------------------
    def open_selected_folder(self):
        g = self._selected_game()
        if not g:
            return
        path = g.get("_path")
        if not path:
            return
        folder = os.path.dirname(path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
    # --------------------------------------------------------
    def copy_selected_game_id(self):
        g = self._selected_game()
        if not g:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(g.get("game_id", "")))
    
    # --------------------------------------------------------
    def draw_plots(self):
        s = self.stats

        # гистограмма финального этажа
        self.ax1.clear()
        floors = sorted(s["final_floor_counts"])
        counts = [s["final_floor_counts"][f] for f in floors]
        labels = [str(f + 1) for f in floors]
        self.ax1.bar(labels, counts, color="tab:blue")
        self.ax1.set_xlabel("Финальный этаж")
        self.ax1.set_ylabel("Партий")
        self.ax1.set_title("Распределение по финальному этажу")
        self.ax1.grid(True, axis="y", alpha=0.3)

        # гистограмма числа шагов
        self.ax2.clear()
        if s["steps_list"]:
            self.ax2.hist(s["steps_list"], bins=30, color="tab:green", alpha=0.7)
            self.ax2.set_xlabel("Шагов за партию")
            self.ax2.set_ylabel("Партий")
            self.ax2.set_title("Распределение длины партии")
            self.ax2.grid(True, axis="y", alpha=0.3)

        self.fig.tight_layout()
        self.canvas.draw()

    # --------------------------------------------------------
    def export_tsv(self):
        if not self.stats:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".tsv",
            filetypes=[("TSV", "*.tsv"), ("All files", "*.*")],
            initialfile=os.path.basename(self.run_dir.rstrip("/")) + ".tsv",
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
        cols = self.settings["tsv_cols"]
        s = self.stats

        if cols["summary"].get():
            f.write("# Сводка\n")
            f.write("key\tvalue\n")
            f.write(f"run_id\t{self.run['meta'].get('run_id', '?')}\n")
            f.write(f"games_total\t{s['games_total']}\n")
            f.write(f"win\t{s['win']}\n")
            f.write(f"dead\t{s['dead']}\n")
            f.write(f"stuck\t{s['stuck']}\n")
            f.write(f"avg_steps\t{s['avg_steps']:.2f}\n")
            f.write(f"avg_final_level\t{s['avg_final_level']:.2f}\n")
            f.write(f"avg_final_hp\t{s['avg_final_hp']:.2f}\n")
            f.write(f"avg_final_gold\t{s['avg_final_gold']:.2f}\n")
            f.write(f"avg_final_xp\t{s['avg_final_xp']:.2f}\n")
            f.write("\n")

        if cols["final_floor"].get():
            f.write("# Финальный этаж\n")
            f.write("floor\tgames\tpercent\n")
            for fl in sorted(s["final_floor_counts"]):
                cnt = s["final_floor_counts"][fl]
                f.write(f"{fl + 1}\t{cnt}\t{self._pct(cnt, s['games_total'])}\n")
            f.write("\n")

        if cols["averages"].get():
            f.write("# Средние показатели\n")
            f.write("metric\tvalue\n")
            f.write(f"avg_final_level\t{s['avg_final_level']:.2f}\n")
            f.write(f"avg_final_hp\t{s['avg_final_hp']:.2f}\n")
            f.write(f"avg_final_gold\t{s['avg_final_gold']:.2f}\n")
            f.write(f"avg_final_xp\t{s['avg_final_xp']:.2f}\n")
            f.write("\n")

        if cols["hist_steps"].get():
            f.write("# Длина партии (шаги)\n")
            f.write("step\n")
            for v in s["steps_list"]:
                f.write(f"{v}\n")
            f.write("\n")

    # --------------------------------------------------------
    @staticmethod
    def _pct(part, total):
        return f"{(part / total * 100):.1f}%" if total else "0.0%"

    def on_close(self):
        save_settings(self.settings)
        self.root.destroy()

# ============================================================
# main
# ============================================================
def main():
    settings = load_settings()

    run_dir = None
    if len(sys.argv) > 1:
        run_dir = sys.argv[1]
    if not run_dir:
        saved = settings.get("last_run_dir", "")
        if saved and os.path.isdir(saved):
            run_dir = saved
    if not run_dir:
        root = tk.Tk()
        root.withdraw()
        run_dir = filedialog.askdirectory(
            title="Выберите папку прогона",
            initialdir=settings.get("last_run_dir") or (
                config.LOGS_DIR if os.path.isdir(config.LOGS_DIR) else "."
            ),
        )
        root.destroy()
    if not run_dir:
        return

    settings["last_run_dir"] = run_dir
    root = tk.Tk()
    app = RunPlayerApp(root, run_dir, settings)
    root.mainloop()

if __name__ == "__main__":
    main()