import math
from typing import Dict, List, Optional
from core.models import ArbitrageOpportunity


class Graph:
    def __init__(self) -> None:
        self.graph: Dict[str, Dict[str, float]] = {}
        self.currencies: set[str] = set()

    def add_rate(self, base: str, quote: str, rate: float) -> None:
        if rate <= 0 or math.isnan(rate) or math.isinf(rate):
            return

        if base not in self.graph:
            self.graph[base] = {}

        self.graph[base][quote] = -math.log(rate)

        self.currencies.add(base)
        self.currencies.add(quote)

    def bellman_ford(self, start: str) -> Optional[ArbitrageOpportunity]:
        distances = {c: float("inf") for c in self.currencies}
        predecessors = {c: None for c in self.currencies}

        distances[start] = 0

        for i in range(len(self.currencies)):
            updated = False

            for u in self.graph:
                for v, weight in self.graph[u].items():
                    if distances[u] + weight < distances[v]:
                        distances[v] = distances[u] + weight
                        predecessors[v] = u
                        updated = True

                        if i == len(self.currencies) - 1:
                            cycle = self._retrieve_cycle(v, predecessors)
                            cycle = self._rotate_cycle(cycle, start)

                            if not cycle:
                                return None

                            profit = self._calculate_profit(cycle)

                            return ArbitrageOpportunity(
                                path=cycle,
                                expected_profit_pct=profit
                            )

            if not updated:
                break

        return None

    def _calculate_profit(self, path: List[str]) -> float:
        balance = 1.0

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            weight = self.graph[u][v]
            rate = math.exp(-weight)
            balance *= rate

        return (balance - 1.0) * 100

    @staticmethod
    def _retrieve_cycle(end: str, predecessors: Dict[str, str | None]) -> List[str]:
        cycle = []
        while end not in cycle:
            cycle.append(end)
            end = predecessors[end]

        cycle.append(end)
        idx = cycle.index(end)
        cycle = cycle[idx:]
        cycle.reverse()
        return cycle

    @staticmethod
    def _rotate_cycle(path: List[str], start: str) -> Optional[List[str]]:
        if start not in path:
            return None

        idx = path.index(start)
        path = path[:-1]
        path = path[idx:] + path[:idx]
        path.append(start)
        return path