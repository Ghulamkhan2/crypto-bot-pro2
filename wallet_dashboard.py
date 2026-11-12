import json
import os

STARTING_BALANCE = 100.0
POSITIONS_FILE = "demo_positions.json"

def main():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    invested = sum(
        float(p.get("investment", 0))
        for p in positions.values()
    )

    available = STARTING_BALANCE - invested

    print("\n===== DEMO WALLET DASHBOARD =====")
    print("Wallet Type: DEMO")
    print("Starting Balance:", STARTING_BALANCE, "USDT")
    print("Invested Balance:", round(invested, 4), "USDT")
    print("Available Balance:", round(available, 4), "USDT")
    print("Open Trades:", len(positions))
    print("================================")

if __name__ == "__main__":
    main()
