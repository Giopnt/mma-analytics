import hashlib
import json
import logging
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL = "http://ufcstats.com"
RAW_DIR  = Path("data/raw")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY = 1.5


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def fetch(session: requests.Session, url: str) -> str:
    time.sleep(REQUEST_DELAY)
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def content_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def save_json(path: Path, data: dict) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_hash = content_hash(data)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if content_hash(existing) == new_hash:
            return False
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def load_json(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def event_path(event_id: str) -> Path:
    return RAW_DIR / "events" / f"{event_id}.json"


def fight_path(event_id: str, fight_id: str) -> Path:
    return RAW_DIR / "fights" / event_id / f"{fight_id}.json"
