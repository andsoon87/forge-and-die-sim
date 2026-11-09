"""Конфигурация проекта Forge & Die Simulator."""
import os

# Версия проекта (см. README.md, раздел «Версионирование»)
PROJECT_VERSION = "0.1.0"
DEFAULT_SEED = None  # None = случайный; число = фиксированный

# Путь сохранения логов
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

# Симуляция
DEFAULT_GAMES = 100
DEFAULT_PROFILE = "rusher"
DEFAULT_CLASS = "warrior"
PROGRESS_EVERY = 10  # обновлять строку прогресса каждые N партий
MAX_FLOOR_STEPS = 200  # защита от бесконечного цикла на этаже

# Плеер
MAX_POINTS = 200  # максимум точек на графике HP