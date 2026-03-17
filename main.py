from core.graph_engine import Graph

if __name__ == "__main__":
    engine = Graph()
# Ścieżka zysku to: PLN -> USD -> EUR -> PLN
    engine.add_rate('PLN', 'USD', 0.25)   # Za 1 PLN kupujesz 0.25 USD
    engine.add_rate('USD', 'EUR', 0.90)   # Za 1 USD kupujesz 0.90 EUR
    engine.add_rate('EUR', 'PLN', 4.60)   # Za 1 EUR kupujesz 4.60 PLN
    
    # Dodajemy "Ogon" (Ślepą uliczkę do franka), żeby sprawdzić Twoje chirurgiczne cięcie!
    engine.add_rate('PLN', 'CHF', 0.21)

    wynik = engine.bellman_ford('PLN')
    print(wynik)
