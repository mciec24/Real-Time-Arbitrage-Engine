import math

class Graph:

    def __init__(self) -> None:
        #słownik słowników do reprezentacji krawedzi
        self.graph: dict[str, dict[str, float]]= {}
        self.currencies: set[str] = set()


    def add_rate(self, base_currency: str, other_currency: str, rate: float) -> None:
        if base_currency not in self.graph:
            self.graph[base_currency] = {}

        self.graph[base_currency][other_currency] = -math.log(rate)
        self.currencies.add(base_currency)
        self.currencies.add(other_currency)


    def bellman_ford(self, start_currency: str) -> bool | list[str]:
        predecessors: dict[str, str | None] = {}
        distances:dict[str, float] = {}
        for currency in self.currencies:
            predecessors[currency] = None
            distances[currency] = float('inf')
        distances[start_currency] = 0
        for i in range(len(self.currencies)):
            has_changed = False
            for elem, targets in self.graph.items():
                for currency, weight in targets.items():
                    if distances[currency] > distances[elem] + weight:
                        if i == len(self.currencies) - 1:
                            path = Graph.retrieve_path(currency, predecessors)
                            path = Graph.rotate_cycle(path, start_currency)

                            if not path: # Jeśli rotateCycle zwróciło False
                                print("Znalazłem arbitraż, ale nie zawiera naszej waluty bazowej. Odrzucam!")
                                return False
                            
                            print("Ujemny cykl")
                            return path
                        distances[currency] = distances[elem] + weight
                        predecessors[currency] = elem
                        has_changed = True
        #skoro w pierwszej iteracji niz sie nie poprawilo to znaczy ze nie ma arbitrazu
            if not has_changed:
                break
        print("Nie ma arbitrazu na rynku")
        return False
    @staticmethod
    def retrieve_path(end_currency: str, predecessors: dict[str, str|None]) -> list[str]:
        path = []
        while end_currency not in path:
            path.append(end_currency)
            end_currency = predecessors[end_currency]
        path.append(end_currency)
        #obciecie ogona zeby wydobyc sama petle
        start_index = path.index(end_currency)
        clean_cycle = path[start_index:]
        clean_cycle.reverse()
        return clean_cycle
    @staticmethod
    def rotate_cycle(path: list[str], start_currency: str) -> list[str] | bool:
        #odrzucam cykl ktory nie zawiera mojej waluty bazowej
        if start_currency not in path:
            return False
        idx = path.index(start_currency)
        path.pop()
        path = path[idx:] + path[:idx]
        path.append(start_currency)
        return path
