import re
from bs4 import BeautifulSoup

from .utils import BASE_URL, log, fetch


def _parse_landed_attempted(raw: str) -> dict:
    raw = raw.strip()
    match = re.match(r"(\d+)\s+of\s+(\d+)", raw, re.IGNORECASE)
    if match:
        return {"landed": int(match.group(1)), "attempted": int(match.group(2))}
    try:
        return {"landed": int(raw), "attempted": int(raw)}
    except ValueError:
        return {"landed": 0, "attempted": 0}


def _parse_time_seconds(raw: str) -> int:
    raw = raw.strip()
    match = re.match(r"(\d+):(\d{2})", raw)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 0


def _parse_totals_table(table) -> list[list[dict]]:
    rows = table.find_all("tr", class_="b-fight-details__table-row")
    rounds = []

    for row in rows:
        cols = row.find_all("td", class_="b-fight-details__table-col")
        if len(cols) < 10:
            continue

        def cell_texts(idx):
            ps = cols[idx].find_all("p")
            a = ps[0].get_text(strip=True) if len(ps) > 0 else "0"
            b = ps[1].get_text(strip=True) if len(ps) > 1 else "0"
            return a, b

        kd_a,   kd_b   = cell_texts(1)
        sig_a,  sig_b  = cell_texts(2)
        tot_a,  tot_b  = cell_texts(4)
        td_a,   td_b   = cell_texts(5)
        sub_a,  sub_b  = cell_texts(7)
        rev_a,  rev_b  = cell_texts(8)
        ctrl_a, ctrl_b = cell_texts(9)

        def build(kd, sig, tot, td, sub, rev, ctrl):
            return {
                "knockdowns":          int(kd) if kd.isdigit() else 0,
                "sig_strikes":         _parse_landed_attempted(sig),
                "total_strikes":       _parse_landed_attempted(tot),
                "takedowns":           _parse_landed_attempted(td),
                "submission_attempts": int(sub) if sub.isdigit() else 0,
                "reversals":           int(rev) if rev.isdigit() else 0,
                "control_time_sec":    _parse_time_seconds(ctrl),
            }

        rounds.append([
            build(kd_a, sig_a, tot_a, td_a, sub_a, rev_a, ctrl_a),
            build(kd_b, sig_b, tot_b, td_b, sub_b, rev_b, ctrl_b),
        ])

    return rounds


def _parse_breakdown_table(table) -> list[list[dict]]:
    rows = table.find_all("tr", class_="b-fight-details__table-row")
    rounds = []

    for row in rows:
        cols = row.find_all("td", class_="b-fight-details__table-col")
        if len(cols) < 9:
            continue

        def cell_texts(idx):
            ps = cols[idx].find_all("p")
            a = ps[0].get_text(strip=True) if len(ps) > 0 else "0 of 0"
            b = ps[1].get_text(strip=True) if len(ps) > 1 else "0 of 0"
            return a, b

        head_a,   head_b   = cell_texts(3)
        body_a,   body_b   = cell_texts(4)
        leg_a,    leg_b    = cell_texts(5)
        dist_a,   dist_b   = cell_texts(6)
        clinch_a, clinch_b = cell_texts(7)
        ground_a, ground_b = cell_texts(8)

        def build(head, body, leg, dist, clinch, ground):
            return {
                "by_target": {
                    "head": _parse_landed_attempted(head),
                    "body": _parse_landed_attempted(body),
                    "leg":  _parse_landed_attempted(leg),
                },
                "by_position": {
                    "distance": _parse_landed_attempted(dist),
                    "clinch":   _parse_landed_attempted(clinch),
                    "ground":   _parse_landed_attempted(ground),
                },
            }

        rounds.append([
            build(head_a, body_a, leg_a, dist_a, clinch_a, ground_a),
            build(head_b, body_b, leg_b, dist_b, clinch_b, ground_b),
        ])

    return rounds


def scrape_fight_rounds(session, fight_id: str, fighter_names: list[str]) -> dict:
    url = f"{BASE_URL}/fight-details/{fight_id}"
    log.debug(f"    Fetching fight {fight_id} ...")
    html = fetch(session, url)
    soup = BeautifulSoup(html, "lxml")

    # Fetch ALL tables — per-round ones have no class when collapsed
    tables = soup.find_all("table")

    if len(tables) < 2:
        log.warning(f"    Fight {fight_id}: only {len(tables)} table(s) found.")
        return {"fight_id": fight_id, "rounds": [], "fighters": fighter_names}

    totals_rounds    = _parse_totals_table(tables[1])    if len(tables) > 1 else []
    breakdown_rounds = _parse_breakdown_table(tables[3]) if len(tables) > 3 else []

    n_rounds = max(len(totals_rounds), len(breakdown_rounds))
    rounds_out = []

    for i in range(n_rounds):
        totals    = totals_rounds[i]    if i < len(totals_rounds)    else [{}, {}]
        breakdown = breakdown_rounds[i] if i < len(breakdown_rounds) else [{}, {}]

        fighter_stats = []
        for f_idx in range(2):
            name = fighter_names[f_idx] if f_idx < len(fighter_names) else f"fighter_{f_idx}"
            stats = {
                "fighter": name,
                **totals[f_idx],
                "sig_strike_detail": breakdown[f_idx] if breakdown else {},
            }
            fighter_stats.append(stats)

        rounds_out.append({"round": i + 1, "fighters": fighter_stats})

    return {
        "fight_id":    fight_id,
        "fighters":    fighter_names,
        "rounds":      rounds_out,
        "round_count": len(rounds_out),
    }
