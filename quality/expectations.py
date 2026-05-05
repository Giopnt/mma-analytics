"""
MMA Pipeline — Data Quality Suite
===================================
Uses Great Expectations to validate data at two checkpoints:

  1. Raw JSON (post-scrape) — validates scraped fight files before loading
  2. PostgreSQL (post-load)  — validates warehouse tables after loading

Run from project root (mma-analytics/):

    python -m quality.expectations              # run all checks
    python -m quality.expectations --raw-only   # only check JSON files
    python -m quality.expectations --db-only    # only check warehouse tables
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


# ── Helpers ────────────────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name   = name
        self.passed = passed
        self.detail = detail

    def __repr__(self):
        icon = PASS if self.passed else FAIL
        msg  = f"{icon}  {self.name}"
        if self.detail:
            msg += f"  ({self.detail})"
        return msg


class Suite:
    def __init__(self, name: str):
        self.name    = name
        self.results: list[CheckResult] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        r = CheckResult(name, condition, detail)
        self.results.append(r)
        return r

    def summary(self) -> tuple[int, int]:
        passed = sum(1 for r in self.results if r.passed)
        return passed, len(self.results)

    def print_report(self):
        passed, total = self.summary()
        print(f"\n{'─'*55}")
        print(f"  {self.name}")
        print(f"{'─'*55}")
        for r in self.results:
            print(f"  {r}")
        print(f"{'─'*55}")
        icon = PASS if passed == total else FAIL
        print(f"  {icon}  {passed}/{total} checks passed")
        print()


# ── Raw JSON checks ────────────────────────────────────────────────────────────

def check_raw_json(raw_data_path: str = "./data/raw") -> Suite:
    """Validate scraped JSON files before they hit the database."""
    suite      = Suite("Raw JSON — post-scrape validation")
    events_dir = Path(raw_data_path) / "events"
    fights_dir = Path(raw_data_path) / "fights"

    event_files = list(events_dir.glob("*.json")) if events_dir.exists() else []
    fight_files = list(fights_dir.rglob("*.json")) if fights_dir.exists() else []

    # ── File existence ─────────────────────────────────────────────────────────
    suite.check("Event files exist",       len(event_files) > 0,   f"{len(event_files)} files found")
    suite.check("Fight files exist",       len(fight_files) > 0,   f"{len(fight_files)} files found")

    if not event_files:
        return suite

    # ── Event file schema ──────────────────────────────────────────────────────
    required_event_keys = {"event_id", "event_name", "date", "location", "fights", "fight_count"}
    missing_keys_count  = 0

    for f in event_files:
        data = json.loads(f.read_text())
        missing = required_event_keys - set(data.keys())
        if missing:
            missing_keys_count += 1

    suite.check("All event files have required keys", missing_keys_count == 0,
                f"{missing_keys_count} files missing keys" if missing_keys_count else "")

    # ── Fight count consistency ────────────────────────────────────────────────
    inconsistent = 0
    for f in event_files:
        data = json.loads(f.read_text())
        if data.get("fight_count", 0) != len(data.get("fights", [])):
            inconsistent += 1

    suite.check("fight_count matches actual fights array length", inconsistent == 0,
                f"{inconsistent} inconsistent" if inconsistent else "")

    # ── Fight file schema ──────────────────────────────────────────────────────
    if fight_files:
        required_fight_keys = {"fight_id", "fighters", "rounds", "round_count"}
        bad_fights = 0
        empty_rounds = 0

        for f in fight_files:
            data    = json.loads(f.read_text())
            missing = required_fight_keys - set(data.keys())
            if missing:
                bad_fights += 1
            if len(data.get("rounds", [])) == 0:
                empty_rounds += 1

        suite.check("All fight files have required keys", bad_fights == 0,
                    f"{bad_fights} files missing keys" if bad_fights else "")
        suite.check("No fight files have empty rounds", empty_rounds == 0,
                    f"{empty_rounds} files with 0 rounds" if empty_rounds else "")

        # ── Strikes: landed never exceeds attempted ────────────────────────────
        violations = 0
        for f in fight_files[:50]:   # sample first 50 for speed
            data = json.loads(f.read_text())
            for rnd in data.get("rounds", []):
                for fighter in rnd.get("fighters", []):
                    sig = fighter.get("sig_strikes", {})
                    if sig.get("landed", 0) > sig.get("attempted", 0):
                        violations += 1

        suite.check("Sig strikes landed ≤ attempted", violations == 0,
                    f"{violations} violations in sample" if violations else "sampled 50 files")

    # ── Winner is one of the fighters ─────────────────────────────────────────
    bad_winner = 0
    for f in event_files:
        data = json.loads(f.read_text())
        for fight in data.get("fights", []):
            winner  = fight.get("winner", "")
            fighters = fight.get("fighters", [])
            result  = fight.get("result", "")
            if result == "win" and winner and winner not in fighters:
                bad_winner += 1

    suite.check("Winner is always one of the two fighters", bad_winner == 0,
                f"{bad_winner} fights with invalid winner" if bad_winner else "")

    # ── Weight class values are non-empty ─────────────────────────────────────
    missing_wc = 0
    for f in event_files:
        data = json.loads(f.read_text())
        for fight in data.get("fights", []):
            if not fight.get("weight_class", "").strip():
                missing_wc += 1

    suite.check("All fights have a weight class", missing_wc == 0,
                f"{missing_wc} fights missing weight class" if missing_wc else "")

    return suite


# ── Database checks ────────────────────────────────────────────────────────────

def check_database() -> Suite:
    """Validate PostgreSQL warehouse tables after loading."""
    suite = Suite("PostgreSQL warehouse — post-load validation")

    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")

        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5433")),
            dbname=os.getenv("DB_NAME", "mma_warehouse"),
            user=os.getenv("DB_USER", "mma"),
            password=os.getenv("DB_PASSWORD", "mma_pass"),
        )
    except Exception as e:
        suite.check("Database connection", False, str(e))
        return suite

    suite.check("Database connection", True)

    with conn.cursor() as cur:

        # ── Row counts ─────────────────────────────────────────────────────────
        for table, min_rows in [
            ("dim_event",        1),
            ("dim_fighter",      10),
            ("fact_fight",       10),
            ("fact_fight_round", 10),
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            suite.check(f"{table} has data", count >= min_rows, f"{count:,} rows")

        # ── No orphaned fights (FK integrity) ─────────────────────────────────
        cur.execute("""
            SELECT COUNT(*) FROM fact_fight ff
            LEFT JOIN dim_event de ON ff.event_id = de.event_id
            WHERE de.event_id IS NULL
        """)
        orphans = cur.fetchone()[0]
        suite.check("No fights with missing event FK", orphans == 0,
                    f"{orphans} orphaned rows" if orphans else "")

        # ── No duplicate fight IDs ─────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM (SELECT fight_id, COUNT(*) FROM fact_fight GROUP BY fight_id HAVING COUNT(*) > 1) t")
        dupes = cur.fetchone()[0]
        suite.check("No duplicate fight_ids", dupes == 0,
                    f"{dupes} duplicates" if dupes else "")

        # ── No duplicate round rows ────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM (SELECT fight_id, round_num, fighter_id, COUNT(*) FROM fact_fight_round GROUP BY fight_id, round_num, fighter_id HAVING COUNT(*) > 1) t")
        dupes = cur.fetchone()[0]
        suite.check("No duplicate (fight, round, fighter) combos", dupes == 0,
                    f"{dupes} duplicates" if dupes else "")

        # ── Strikes: landed never exceeds attempted ────────────────────────────
        cur.execute("SELECT COUNT(*) FROM fact_fight_round WHERE sig_strikes_landed > sig_strikes_attempted")
        violations = cur.fetchone()[0]
        suite.check("Sig strikes landed ≤ attempted (DB)", violations == 0,
                    f"{violations} violations" if violations else "")

        cur.execute("SELECT COUNT(*) FROM fact_fight_round WHERE takedowns_landed > takedowns_attempted")
        violations = cur.fetchone()[0]
        suite.check("Takedowns landed ≤ attempted (DB)", violations == 0,
                    f"{violations} violations" if violations else "")

        # ── Round numbers are valid (1–5) ──────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM fact_fight_round WHERE round_num < 1 OR round_num > 5")
        bad_rounds = cur.fetchone()[0]
        suite.check("Round numbers are between 1 and 5", bad_rounds == 0,
                    f"{bad_rounds} invalid round numbers" if bad_rounds else "")

        # ── Every fight has at least one round row ─────────────────────────────
        cur.execute("""
            SELECT COUNT(*) FROM fact_fight ff
            LEFT JOIN fact_fight_round ffr ON ff.fight_id = ffr.fight_id
            WHERE ffr.fight_id IS NULL
        """)
        no_rounds = cur.fetchone()[0]
        suite.check("Every fight has round stats", no_rounds == 0,
                    f"{no_rounds} fights missing round data" if no_rounds else "")

        # ── Result values are from expected set ────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM fact_fight WHERE result NOT IN ('win', 'nc', 'draw', 'dq')")
        bad_results = cur.fetchone()[0]
        suite.check("Result values are valid (win/nc/draw/dq)", bad_results == 0,
                    f"{bad_results} invalid values" if bad_results else "")

        # ── Winners only set for 'win' result ──────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM fact_fight WHERE result != 'win' AND winner_id IS NOT NULL")
        bad_winners = cur.fetchone()[0]
        suite.check("winner_id only set when result = 'win'", bad_winners == 0,
                    f"{bad_winners} anomalies" if bad_winners else "")

    conn.close()
    return suite


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MMA data quality checks")
    parser.add_argument("--raw-only", action="store_true")
    parser.add_argument("--db-only",  action="store_true")
    args = parser.parse_args()

    raw_path = os.getenv("RAW_DATA_PATH", "./data/raw")
    all_passed = True

    if not args.db_only:
        suite = check_raw_json(raw_path)
        suite.print_report()
        passed, total = suite.summary()
        if passed < total:
            all_passed = False

    if not args.raw_only:
        suite = check_database()
        suite.print_report()
        passed, total = suite.summary()
        if passed < total:
            all_passed = False

    if not all_passed:
        log.error("Some checks failed — review output above.")
        sys.exit(1)
    else:
        log.info("All quality checks passed.")


if __name__ == "__main__":
    main()
