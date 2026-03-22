import math
from core.models import ArbitrageOpportunity

class Graph:
    """
    Represents a directed graph where nodes are currencies and edges contain
    exchange rates and available liquidity.
    
    Edge weights are calculated as negative natural logarithms of exchange rates 
    to enable additive shortest-path calculations. Liquidity is tracked to calculate 
    bottleneck capacity along arbitrage paths, preventing execution on shallow order books.
    """
    def __init__(self) -> None:
        """
        Initializes an empty graph and a set to track unique currencies.
        """
        self.graph: dict[str, dict[str, tuple[float, float]]] = {}
        self.currencies: set[str] = set()

    def add_rate(self, base: str, quote: str, rate: float, volume: float) -> None:
        """
        Adds an exchange rate and its associated available liquidity to the graph.
        """
        if rate <= 0 or volume <= 0 or math.isnan(rate) or math.isinf(rate):
            return

        if base not in self.graph:
            self.graph[base] = {}

        self.graph[base][quote] = (-math.log(rate), volume)

        self.currencies.add(base)
        self.currencies.add(quote)

    def bellman_ford(self, start: str) -> ArbitrageOpportunity | None:
        """
        Executes the Bellman-Ford algorithm to detect negative weight cycles
        and calculates their corresponding bottleneck capacity.
        """
        distances = {c: float("inf") for c in self.currencies}
        predecessors: dict[str, str | None] = {c: None for c in self.currencies}

        distances[start] = 0

        for i in range(len(self.currencies)):
            updated = False

            for u in self.graph:
                for v, (weight, _) in self.graph[u].items():
                    if distances[u] + weight < distances[v]:
                        distances[v] = distances[u] + weight
                        predecessors[v] = u
                        updated = True

                        if i == len(self.currencies) - 1:
                            cycle = self._retrieve_cycle(v, predecessors)
                            cycle = self._rotate_cycle(cycle, start)

                            if not cycle:
                                return None

                            profit, max_vol = self._calculate_profit_and_bottleneck(cycle)

                            return ArbitrageOpportunity(
                                path=cycle,
                                expected_profit_pct=profit,
                                max_trade_amount=max_vol
                            )

            if not updated:
                break

        return None

    def _calculate_profit_and_bottleneck(self, path: list[str]) -> tuple[float, float]:
        """
        Calculates the net profit percentage and the bottleneck capacity of a cycle.
        """
        balance = 1.0
        bottleneck_vol = float("inf")

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            
            weight, volume = self.graph[u][v]
            rate = math.exp(-weight)
            
            bottleneck_vol = min(bottleneck_vol, volume)
            balance *= rate

        return ((balance - 1.0) * 100), bottleneck_vol

    @staticmethod
    def _retrieve_cycle(end: str, predecessors: dict[str, str | None]) -> list[str]:
        """
        Backtracks through the predecessor dictionary to safely extract the cycle path.
        """
        cycle = []
        for _ in range(len(predecessors)):
            if end is None or end in cycle: 
                break
            cycle.append(end)
            end = predecessors.get(end)
            
        if end is not None:
            cycle.append(end)
            idx = cycle.index(end)
            cycle = cycle[idx:]
            
        cycle.reverse()
        return cycle

    @staticmethod
    def _rotate_cycle(path: list[str], start: str) -> list[str] | None:
        """
        Shifts the cycle array to begin and end with the designated start currency.
        """
        if start not in path:
            return None

        idx = path.index(start)
        path = path[:-1]
        path = path[idx:] + path[:idx]
        path.append(start)
        return path