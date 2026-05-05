with rounds as (
    select * from {{ ref('stg_rounds') }}
)

select
    fight_id,
    fighter_id,
    count(*)                            as rounds_fought,
    sum(sig_strikes_landed)             as total_sig_landed,
    sum(sig_strikes_attempted)          as total_sig_attempted,
    sum(total_strikes_landed)           as total_str_landed,
    sum(total_strikes_attempted)        as total_str_attempted,
    sum(knockdowns)                     as total_knockdowns,
    sum(takedowns_landed)               as total_td_landed,
    sum(takedowns_attempted)            as total_td_attempted,
    sum(submission_attempts)            as total_sub_attempts,
    sum(control_time_sec)               as total_ctrl_sec,
    sum(head_landed)                    as total_head_landed,
    sum(body_landed)                    as total_body_landed,
    sum(leg_landed)                     as total_leg_landed,
    sum(distance_landed)                as total_distance_landed,
    sum(clinch_landed)                  as total_clinch_landed,
    sum(ground_landed)                  as total_ground_landed,
    round(sum(sig_strikes_landed)::numeric / nullif(sum(sig_strikes_attempted), 0) * 100, 1) as sig_strike_accuracy,
    round(sum(takedowns_landed)::numeric   / nullif(sum(takedowns_attempted), 0) * 100, 1)   as takedown_accuracy
from rounds
group by fight_id, fighter_id
