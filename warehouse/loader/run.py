#!/usr/bin/env python3
"""
Run from project root:

    python -m warehouse.loader.run
    python -m warehouse.loader.run --events-only
    python -m warehouse.loader.run --rounds-only
    python -m warehouse.loader.run --verify
"""

import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def verify(conn):
    tables = ["dim_event", "dim_fighter", "dim_method", "fact_fight", "fact_fight_round"]
    with conn.cursor() as cur:
        print("\n── Row counts ────────────────────────")
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t:<25} {cur.fetchone()[0]:>6,}")

        print("\n── Top 5 fighters by wins ────────────")
        cur.execute("SELECT f.name, COUNT(*) AS wins FROM fact_fight ff JOIN dim_fighter f ON ff.winner_id = f.fighter_id GROUP BY f.name ORDER BY wins DESC LIMIT 5")
        for row in cur.fetchall():
            print(f"  {row[0]:<30} {row[1]} wins")

        print("\n── Finish methods ────────────────────")
        cur.execute("SELECT m.method, COUNT(*) AS fights FROM fact_fight ff JOIN dim_method m ON ff.method_id = m.method_id GROUP BY m.method ORDER BY fights DESC")
        for row in cur.fetchall():
            print(f"  {row[0]:<35} {row[1]}")
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-only", action="store_true")
    parser.add_argument("--rounds-only", action="store_true")
    parser.add_argument("--verify",      action="store_true")
    args = parser.parse_args()

    from .db import get_conn

    if args.verify:
        conn = get_conn()
        verify(conn)
        conn.close()
        return

    raw_path = os.getenv("RAW_DATA_PATH", "./data/raw")

    if not args.rounds_only:
        log.info("=== Loading events & fights ===")
        from .load_events import load_all_events
        load_all_events(raw_path)

    if not args.events_only:
        log.info("=== Loading round stats ===")
        from .load_rounds import load_all_rounds
        load_all_rounds(raw_path)

    log.info("=== Done — run with --verify to check row counts ===")


if __name__ == "__main__":
    main()
