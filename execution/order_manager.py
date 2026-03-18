import math
from config.settings import config

class OrderManager:
    def __init__(self, engine):
        self.engine = engine
        self.paper_trading = True
        self.initial_balance = config.INITIAL_BALANCE 

    def execute_arbitrage(self, path: list[str]):
        print("\n" + "="*50)
        print(f"🚀 STARTING VIRTUAL EXECUTION (PAPER TRADING)")
        print(f"📍 Path to execute: {' -> '.join(path)}")
        
        current_balance = self.initial_balance
        start_coin = path[0]
        
        print(f"💰 Starting balance: {current_balance:.4f} {start_coin}")
        print("-" * 50)

        for i in range(len(path) - 1):
            from_coin = path[i]
            to_coin = path[i+1]
            
            weight = self.engine.graph[from_coin][to_coin]
            real_rate = math.exp(-weight)
            
            current_balance = current_balance * real_rate
            
            print(f"STEP {i+1}: Exchanging {from_coin} to {to_coin}")
            print(f"   -> Rate: {real_rate:.6f}")
            print(f"   -> Current Balance: {current_balance:.4f} {to_coin}")

        print("-" * 50)
        
        profit = current_balance - self.initial_balance
        profit_percentage = (profit / self.initial_balance) * 100

        print(f" FINAL BALANCE: {current_balance:.4f} {start_coin}")
        print(f" PURE PROFIT: {profit:.4f} {start_coin} ({profit_percentage:.4f}%)")
        print("="*50 + "\n")