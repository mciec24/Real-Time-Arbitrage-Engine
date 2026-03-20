import math
from typing import Dict, List, Optional
from core.models import ArbitrageOpportunity


class Graph:
    """
    Represents a directed graph where nodes are currencies and edges are exchange rates.
    
    Edge weights are calculated as the negative natural logarithm of the exchange rate. 
    This transforms the multiplicative nature of exchange rates into an additive 
    shortest-path problem, allowing the Bellman-Ford algorithm to find profitable 
    arbitrage opportunities (which correspond to negative weight cycles).
    """
    def __init__(self) -> None:
        """
        Initializes an empty graph and a set to track unique currencies.
        """
        self.graph: Dict[str, Dict[str, float]] = {}
        self.currencies: set[str] = set()

    def add_rate(self, base: str, quote: str, rate: float) -> None:
        """
        Adds an exchange rate to the graph.

        Defends against invalid API data by silently ignoring rates that are 
        zero, negative, NaN (Not a Number), or infinite.

        Args:
            base (str): The symbol of the base currency (e.g., 'USD').
            quote (str): The symbol of the quote currency (e.g., 'EUR').
            rate (float): The exchange rate from base to quote.
        """
        if rate <= 0 or math.isnan(rate) or math.isinf(rate):
            return

        if base not in self.graph:
            self.graph[base] = {}

        # Transform multiplicative arbitrage into an additive shortest-path problem
        self.graph[base][quote] = -math.log(rate)

        self.currencies.add(base)
        self.currencies.add(quote)

    def bellman_ford(self, start: str) -> Optional[ArbitrageOpportunity]:
        """
        Executes the Bellman-Ford algorithm to detect negative weight cycles.

        Args:
            start (str): The currency symbol from which to start the detection 
                and to which the arbitrage cycle should ultimately return.

        Returns:
            Optional[ArbitrageOpportunity]: An object containing the arbitrage path 
            and expected profit percentage if a cycle is found; otherwise, None.
        """
        distances = {c: float("inf") for c in self.currencies}
        predecessors: Dict[str, Optional[str]] = {c: None for c in self.currencies}

        distances[start] = 0

        # Relax edges |V| times. The last iteration (i == |V| - 1) detects cycles.
        for i in range(len(self.currencies)):
            updated = False

            for u in self.graph:
                for v, weight in self.graph[u].items():
                    if distances[u] + weight < distances[v]:
                        distances[v] = distances[u] + weight
                        predecessors[v] = u
                        updated = True

                        # If distances update on the |V|-th iteration, a negative cycle exists
                        if i == len(self.currencies) - 1:
                            cycle = self._retrieve_cycle(v, predecessors)
                            cycle = self._rotate_cycle(cycle, start)

                            # Discard cycles that don't include our base currency
                            if not cycle:
                                return None

                            profit = self._calculate_profit(cycle)

                            return ArbitrageOpportunity(
                                path=cycle,
                                expected_profit_pct=profit
                            )

            # Early exit if no distances were updated (no cycles possible)
            if not updated:
                break

        return None

    def _calculate_profit(self, path: List[str]) -> float:
        """
        Calculates the net profit percentage of a given arbitrage cycle.

        Args:
            path (List[str]): The sequence of currencies representing the arbitrage cycle.

        Returns:
            float: The expected profit as a percentage (e.g., 1.5 for 1.5% profit).
        """
        balance = 1.0

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            weight = self.graph[u][v]
            
            # Revert the negative logarithm back to the original exchange rate
            rate = math.exp(-weight)
            balance *= rate

        return (balance - 1.0) * 100

    @staticmethod
    def _retrieve_cycle(end: str, predecessors: Dict[str, Optional[str]]) -> List[str]:
        """
        Backtracks through the predecessor dictionary to extract the cycle path.

        Args:
            end (str): The node where the negative cycle was detected.
            predecessors (Dict[str, Optional[str]]): A dictionary mapping each node 
                to its predecessor in the shortest path tree.

        Returns:
            List[str]: The extracted cycle path in the correct execution order.
        """
        cycle = []
        while end not in cycle:
            cycle.append(end)
            # We know 'end' has a predecessor here because it's part of a cycle
            end = predecessors[end]  # type: ignore

        cycle.append(end)
        idx = cycle.index(end)
        cycle = cycle[idx:]
        cycle.reverse()
        return cycle

    @staticmethod
    def _rotate_cycle(path: List[str], start: str) -> Optional[List[str]]:
        """
        Shifts the cycle array so that it begins and ends with the designated start currency.

        Args:
            path (List[str]): The raw arbitrage cycle path.
            start (str): The target starting and ending currency.

        Returns:
            Optional[List[str]]: The rotated path starting and ending with 'start', 
            or None if 'start' is not present in the path.
        """
        if start not in path:
            return None

        idx = path.index(start)
        path = path[:-1]
        path = path[idx:] + path[:idx]
        path.append(start)
        return path