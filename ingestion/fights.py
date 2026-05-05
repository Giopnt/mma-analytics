import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .utils import BASE_URL, log, fetch


@dataclass
class FightStub:
    fight_id: str
    event_id: str
    fighters: list[str]
    winner: str
    result: str
    method: str
    method_detail: str
    round_stopped: int
    time: str
    weight_class: str
    is_title_fight: bool
    is_main_event: bool
    url: str


def _extract_fight_id(url: str) -> str | None:
    match = re.search(r"/fight-details/([a-f0-9]+)", url)
    return match.group(1) if match else None


def _parse_round(raw: str) -> int:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return 0


def _classify_result(method: str) -> str:
    m = method.lower()
    if "no contest" in m:
        return "nc"
    if "draw" in m:
        return "draw"
    if "dq" in m or "disqualification" in m:
        return "dq"
    return "win"


def scrape_event_fights(session, event_id: str) -> dict:
    url = f"{BASE_URL}/event-details/{event_id}"
    log.info(f"  Fetching event {event_id} ...")
    html = fetch(session, url)
    soup = BeautifulSoup(html, "lxml")

    event_name = ""
    name_tag = soup.find("h2", class_="b-content__title")
    if name_tag:
        event_name = name_tag.get_text(strip=True)

    meta: dict[str, str] = {}
    for li in soup.find_all("li", class_="b-list__box-list-item"):
        text = li.get_text(" ", strip=True)
        if ":" in text:
            key, _, val = text.partition(":")
            meta[key.strip().lower()] = val.strip()

    fights_table = soup.find("table", class_="b-fight-details__table")
    fights: list[dict] = []

    if fights_table:
        rows = fights_table.find_all("tr", class_="b-fight-details__table-row")
        is_main_event = True

        for row in rows:
            cols = row.find_all("td", class_="b-fight-details__table-col")
            if len(cols) < 10:
                continue

            fighter_tags = cols[1].find_all("p")
            if len(fighter_tags) < 2:
                is_main_event = False
                continue

            fighter_a = fighter_tags[0].get_text(strip=True)
            fighter_b = fighter_tags[1].get_text(strip=True)

            if not fighter_a or not fighter_b:
                is_main_event = False
                continue

            weight_class   = cols[6].get_text(strip=True)
            is_title_fight = "Title" in weight_class or "Championship" in weight_class

            method_tags   = cols[7].find_all("p")
            method        = method_tags[0].get_text(strip=True) if method_tags else ""
            method_detail = method_tags[1].get_text(strip=True) if len(method_tags) > 1 else ""

            round_stopped = _parse_round(cols[8].get_text(strip=True))
            fight_time    = cols[9].get_text(strip=True)
            result        = _classify_result(method)

            winner = ""
            result_icons = cols[0].find_all("i")
            if result_icons:
                icon_class = " ".join(result_icons[0].get("class", []))
                if "green" in icon_class or "win" in icon_class.lower():
                    winner = fighter_a
            if not winner and result == "win":
                winner = fighter_a

            fight_link = row.get("data-link", "")
            if not fight_link:
                link_tag = row.find("a", href=re.compile(r"/fight-details/"))
                fight_link = link_tag["href"] if link_tag else ""

            fight_id = _extract_fight_id(fight_link)
            if not fight_id:
                is_main_event = False
                continue

            fights.append({
                "fight_id":       fight_id,
                "event_id":       event_id,
                "fighters":       [fighter_a, fighter_b],
                "winner":         winner,
                "result":         result,
                "method":         method,
                "method_detail":  method_detail,
                "round_stopped":  round_stopped,
                "time":           fight_time,
                "weight_class":   weight_class,
                "is_title_fight": is_title_fight,
                "is_main_event":  is_main_event,
                "url":            fight_link,
            })

            is_main_event = False

    return {
        "event_id":    event_id,
        "event_name":  event_name,
        "date":        meta.get("date", ""),
        "location":    meta.get("location", ""),
        "fights":      fights,
        "fight_count": len(fights),
    }
