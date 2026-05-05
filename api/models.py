from datetime import date
from typing import Optional
from pydantic import BaseModel


class FighterStats(BaseModel):
    fighter_id:               int
    name:                     str
    total_fights:             int
    wins:                     int
    losses:                   int
    nc_draws:                 int
    finish_rate_pct:          Optional[float]
    primary_weight_class:     Optional[str]
    wins_by_ko:               int
    wins_by_sub:              int
    wins_by_dec:              int
    avg_sig_strike_accuracy:  Optional[float]
    avg_sig_landed_per_fight: Optional[float]
    career_sig_landed:        Optional[int]
    career_sig_attempted:     Optional[int]
    avg_knockdowns_per_fight: Optional[float]
    avg_takedown_accuracy:    Optional[float]
    avg_td_per_fight:         Optional[float]
    career_td_landed:         Optional[int]
    avg_ctrl_min_per_fight:   Optional[float]
    title_fights:             int
    last_fight_date:          Optional[date]


class HeadToHead(BaseModel):
    fight_id:      str
    event_name:    str
    event_date:    Optional[date]
    winner_name:   Optional[str]
    method:        Optional[str]
    round_stopped: Optional[int]
    time_stopped:  Optional[str]
    weight_class:  Optional[str]


class MatchupResponse(BaseModel):
    fighter_a:    FighterStats
    fighter_b:    FighterStats
    head_to_head: list[HeadToHead]


class FighterSummary(BaseModel):
    fighter_id:           int
    name:                 str
    total_fights:         int
    wins:                 int
    losses:               int
    primary_weight_class: Optional[str]
    finish_rate_pct:      Optional[float]
    last_fight_date:      Optional[date]


class EventSummary(BaseModel):
    event_id:         str
    event_name:       str
    event_date:       Optional[date]
    location:         Optional[str]
    total_fights:     int
    total_finishes:   int
    finish_rate_pct:  Optional[float]
    ko_tko_count:     int
    submission_count: int
    decision_count:   int
