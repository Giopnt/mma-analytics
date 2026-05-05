import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from .utils import BASE_URL, log, fetch, make_session


@dataclass
class EventStub:
    event_id: str
    name: str
    date: str
    location: str
    url: str


def _parse_date(raw: str) -> str:
    from datetime import datetime
    raw = raw.strip()
    for fmt in ("%B %d, %Y", "%b. %d, %Y", "%B %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _extract_event_id(url: str) -> Optional[str]:
    match = re.search(r"/event-details/([a-f0-9]+)", url)
    return match.group(1) if match else None


def scrape_event_list(session=None) -> list[EventStub]:
    if session is None:
        session = make_session()

    url = f"{BASE_URL}/statistics/events/completed?page=all"
    log.info("Fetching event index ...")
    html = fetch(session, url)
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table", class_="b-statistics__table-events")
    if table is None:
        raise ValueError("Could not find events table — page structure may have changed.")

    events: list[EventStub] = []

    for row in table.find_all("tr", class_="b-statistics__table-row"):
        cells = row.find_all("td", class_="b-statistics__table-col")
        if len(cells) < 2:
            continue

        link_tag = cells[0].find("a", class_="b-link")
        if link_tag is None:
            continue

        href     = link_tag.get("href", "")
        event_id = _extract_event_id(href)
        name     = link_tag.get_text(strip=True)

        if not event_id or not name:
            continue

        location = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        date_raw = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        date     = _parse_date(date_raw) if date_raw else ""

        events.append(EventStub(
            event_id=event_id,
            name=name,
            date=date,
            location=location,
            url=href,
        ))

    log.info(f"Found {len(events)} events.")
    return events
