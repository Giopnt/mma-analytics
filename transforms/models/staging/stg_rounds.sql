with source as (
    select * from {{ source('warehouse', 'fact_fight_round') }}
)

select
    id, fight_id, round_num, fighter_id,
    knockdowns,
    sig_strikes_landed, sig_strikes_attempted,
    total_strikes_landed, total_strikes_attempted,
    takedowns_landed, takedowns_attempted,
    submission_attempts, reversals, control_time_sec,
    head_landed, head_attempted,
    body_landed, body_attempted,
    leg_landed,  leg_attempted,
    distance_landed, distance_attempted,
    clinch_landed,   clinch_attempted,
    ground_landed,   ground_attempted,

    round(sig_strikes_landed::numeric / nullif(sig_strikes_attempted, 0) * 100, 1) as sig_strike_accuracy,
    round(takedowns_landed::numeric   / nullif(takedowns_attempted, 0) * 100, 1)   as takedown_accuracy,
    round(head_landed::numeric        / nullif(sig_strikes_landed, 0) * 100, 1)    as head_strike_pct

from source
