# Real-Time Cyclic Arbitrage Engine

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Asyncio](https://img.shields.io/badge/asyncio-Enabled-success.svg)
![Pydantic](https://img.shields.io/badge/pydantic-V2-red.svg)
![WebSockets](https://img.shields.io/badge/websockets-RealTime-orange.svg)
![Docker](https://img.shields.io/badge/docker-Ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A highly optimized, asynchronous Python trading engine designed to detect multi-step cyclic arbitrage opportunities across cryptocurrency pairs in real-time. By leveraging Binance Level 2 Order Book WebSockets and the Bellman-Ford algorithm, this system continuously analyzes market inefficiencies and calculates viable trade routes while strictly accounting for available liquidity and exchange fees.

Unlike basic triangular arbitrage bots, this engine is designed to detect profitable cycles of any length (3-step, 4-step, and beyond) by modeling the market as a complete directed graph.

## Technical Highlights & Architecture

This project was built with a strong focus on concurrency, resilience, and Clean Code principles.

* **Non-blocking Architecture:** Utilizes Python's `asyncio` to consume high-frequency market data without interrupting the main event loop.
* **CPU-bound Offloading:** The computationally heavy Bellman-Ford cycle detection is strictly decoupled and executed via `asyncio.to_thread` to prevent stalling WebSocket ingestion.
* **Defensive & Resilient:** Features Exponential Backoff for handling network disconnects, safe JSON payload parsing, and thread-safe graceful shutdown signal handling (`loop.call_soon_threadsafe`) for cross-platform stability (Unix/Windows).
* **Strict Type Safety:** Fully typed using modern Python 3.10+ syntax (`|` union operators, built-in generics) and `pydantic-settings` for robust, immutable configuration management.
* **Memory Optimization:** Domain models are implemented using `@dataclass(slots=True, frozen=True)` to minimize the RAM footprint and instantiation time during high-frequency data streaming.

## The Math (How it Works)

Cyclic arbitrage occurs when a sequence of trades starting and ending with the same currency results in a net profit. 

The engine models the market order book as a directed graph:
* **Nodes** represent currencies (e.g., BTC, ETH, USDT).
* **Edges** represent exchange rates and available volume.

To find profitable arbitrage cycles (which inherently require multiplication of rates), we transform the rates using negative natural logarithms. This allows us to convert the multiplicative problem into an additive shortest-path problem.

For an exchange rate, the edge weight is calculated as:
weight = -ln(rate)

A profitable cycle of n steps exists if the product of the exchange rates is greater than 1:
rate_1 * rate_2 * ... * rate_n > 1

By applying the logarithmic transformation, finding a profit translates to finding a negative-weight cycle in the graph:
-ln(rate_1) - ln(rate_2) - ... - ln(rate_n) < 0

This is elegantly and efficiently solved using the Bellman-Ford algorithm.

> **Note on Slippage:** The engine dynamically tracks available order book liquidity (bottleneck capacity) along the detected path to ensure the theoretical profit isn't erased by executing on shallow order books.

## Project Structure

```text
arbitrage-engine/
├── config/
│   └── settings.py          # Pydantic V2 immutable configuration & .env parsing
├── core/
│   ├── graph_engine.py      # Directed graph state & Bellman-Ford algorithm
│   └── models.py            # Frozen Data Transfer Objects (DTOs) / slots=True
├── exchange/
│   └── binance_stream.py    # Asyncio WebSocket client & defensive parsing
├── execution/
│   └── order_manager.py     # Paper trading execution & bottleneck validation
├── tests/
│   ├── test_binance_stream.py
│   ├── test_graph_engine.py
│   └── test_order_manager.py
├── main.py                  # Entry point with cross-platform Graceful Shutdown
├── requirements.txt         # Project dependencies
├── Dockerfile               # Container build instructions
├── docker-compose.yml       # Orchestration & restart policies
└── README.md
```

## Setup & Installation

### Option A: Running with Docker (Recommended)

**1. Clone the repository**
```bash
git clone [https://github.com/mciec24/Real-Time-Arbitrage-Engine.git](https://github.com/mciec24/Real-Time-Arbitrage-Engine.git)
cd Real-Time-Arbitrage-Engine
```

**2. Configure Environment Variables**
Create a `.env` file in the root directory:
```env
INITIAL_BALANCE=100.0
MIN_PROFIT_PCT=0.1
MAX_LATENCY_MS=50
```

**3. Build and Run the Container**
```bash
docker compose up -d --build
```

### Option B: Local Setup (Development)

**1. Create and activate a virtual environment**
```bash
python -m venv venv
# On Unix/macOS:
source venv/bin/activate  
# On Windows:
venv\Scripts\activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the Engine**
```bash
python main.py
```

## Testing

The project uses `pytest` for unit and asynchronous testing. To run the suite:
```bash
pytest -v
```

## Future Improvements

* **Dynamic Volume Normalization:** Normalizing volumes for accurate bottleneck calculations across mixed-currency paths.
* **Double-Buffering Locks:** Dual-graph pointer swap mechanism to reduce lock contention.
* **Live Execution:** Integration with the Binance REST API for real-time order routing.