"""
MMA Analytics API
Run from project root: uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import cursor
from .models import FighterStats, FighterSummary, MatchupResponse, HeadToHead, EventSummary

app = FastAPI(title="MMA Analytics API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def clean(name: str) -> str:
    return name.replace("+", " ").strip()


@app.get("/")
def root():
    return {"status": "ok", "message": "MMA Analytics API is running"}


@app.get("/fighters", response_model=list[FighterSummary])
def list_fighters(
    limit:        int = Query(50,  ge=1, le=500),
    offset:       int = Query(0,   ge=0),
    weight_class: str = Query(None),
    min_fights:   int = Query(1,   ge=1),
):
    sql = """
        SELECT fighter_id, name, total_fights, wins, losses,
               primary_weight_class, finish_rate_pct, last_fight_date
        FROM public_marts.mart_fighter_stats
        WHERE total_fights >= %(min_fights)s
        {wf}
        ORDER BY wins DESC, total_fights DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """.format(wf="AND primary_weight_class ILIKE %(wc)s" if weight_class else "")

    with cursor() as cur:
        cur.execute(sql, {"limit": limit, "offset": offset, "min_fights": min_fights,
                          "wc": f"%{weight_class}%" if weight_class else None})
        return cur.fetchall()


@app.get("/fighters/{name}", response_model=FighterStats)
def get_fighter(name: str):
    name = clean(name)
    with cursor() as cur:
        cur.execute("SELECT * FROM public_marts.mart_fighter_stats WHERE name ILIKE %(n)s LIMIT 1", {"n": f"%{name}%"})
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Fighter '{name}' not found")
        return row


@app.get("/matchup", response_model=MatchupResponse)
def matchup(
    fighter_a: str = Query(...),
    fighter_b: str = Query(...),
):
    fa_name = clean(fighter_a)
    fb_name = clean(fighter_b)

    with cursor() as cur:
        cur.execute(
            "SELECT *, fighter_name AS name FROM public_marts.mart_matchup WHERE fighter_name ILIKE %(a)s OR fighter_name ILIKE %(b)s",
            {"a": f"%{fa_name}%", "b": f"%{fb_name}%"},
        )
        rows = cur.fetchall()

    if len(rows) < 2:
        missing = []
        if not any(fa_name.lower() in r["fighter_name"].lower() for r in rows):
            missing.append(fa_name)
        if not any(fb_name.lower() in r["fighter_name"].lower() for r in rows):
            missing.append(fb_name)
        raise HTTPException(404, f"Fighter(s) not found: {', '.join(missing)}")

    fa = next((r for r in rows if fa_name.lower() in r["fighter_name"].lower()), rows[0])
    fb = next((r for r in rows if fb_name.lower() in r["fighter_name"].lower()), rows[1])

    with cursor() as cur:
        cur.execute(
            """
            SELECT fight_id, event_name, event_date, winner_name,
                   method, round_stopped, time_stopped, weight_class
            FROM public_intermediate.int_fight_results
            WHERE (fighter_a_name ILIKE %(a)s AND fighter_b_name ILIKE %(b)s)
               OR (fighter_a_name ILIKE %(b)s AND fighter_b_name ILIKE %(a)s)
            ORDER BY event_date DESC
            """,
            {"a": f"%{fa_name}%", "b": f"%{fb_name}%"},
        )
        h2h = cur.fetchall()

    return MatchupResponse(
        fighter_a=FighterStats(**fa),
        fighter_b=FighterStats(**fb),
        head_to_head=[HeadToHead(**row) for row in h2h],
    )


@app.get("/events", response_model=list[EventSummary])
def list_events(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with cursor() as cur:
        cur.execute(
            "SELECT event_id, event_name, event_date, location, total_fights, total_finishes, finish_rate_pct, ko_tko_count, submission_count, decision_count FROM public_marts.mart_event_summary ORDER BY event_date DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"limit": limit, "offset": offset},
        )
        return cur.fetchall()


@app.get("/events/{event_id}", response_model=EventSummary)
def get_event(event_id: str):
    with cursor() as cur:
        cur.execute("SELECT * FROM public_marts.mart_event_summary WHERE event_id = %(id)s", {"id": event_id})
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Event '{event_id}' not found")
        return row
