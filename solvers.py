"""Решатели: кто принимает решения за команду.

Solver -- интерфейс (move/decide/distribute/trade).
BotSolver -- реализация для бота (в bots.py).
HumanSolver/NNSolver -- заглушки (после 8.0).
make_solver -- фабрика: по (kind, profile) создаёт нужный Solver.
"""

class Solver:
    """Интерфейс решателя. Движок не знает, кто за ним."""

    def move(self, floor_state, party):
        raise NotImplementedError

    def decide(self, available, party, floor_state, monsters):
        raise NotImplementedError

    def distribute(self, party):
        raise NotImplementedError

    def trade(self, party):
        raise NotImplementedError

class HumanSolver(Solver):
    """Заглушка: игра человеком (после 8.0)."""

    def move(self, floor_state, party):
        raise NotImplementedError("HumanSolver: будет после 8.0")

    def decide(self, available, party, floor_state, monsters):
        raise NotImplementedError("HumanSolver: будет после 8.0")

    def distribute(self, party):
        raise NotImplementedError("HumanSolver: будет после 8.0")

    def trade(self, party):
        raise NotImplementedError("HumanSolver: будет после 8.0")

class NNSolver(Solver):
    """Заглушка: нейросеть/генетика (после 8.0)."""

    def move(self, floor_state, party):
        raise NotImplementedError("NNSolver: будет после 8.0")

    def decide(self, available, party, floor_state, monsters):
        raise NotImplementedError("NNSolver: будет после 8.0")

    def distribute(self, party):
        raise NotImplementedError("NNSolver: будет после 8.0")

    def trade(self, party):
        raise NotImplementedError("NNSolver: будет после 8.0")

def make_solver(kind: str, profile: str):
    """Фабрика Solver по (kind, profile).

    kind:    "bot" | "human" | "nn"
    profile: "rusher" | "cautious" | "balanced" (только для bot)
    """
    if kind == "bot":
        from bots import BotSolver          # ленивый импорт (нет цикла)
        return BotSolver(profile)
    if kind == "human":
        return HumanSolver()
    if kind == "nn":
        return NNSolver()
    raise ValueError(f"Неизвестный solver kind: {kind!r}")
