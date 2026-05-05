with results as (select * from {{ ref('int_fight_results') }}),
round_stats as (select * from {{ ref('int_fighter_round_stats') }}),
fighters as (select fighter_id, name from {{ source('warehouse', 'dim_fighter') }}),

fighter_fights as (
    select fighter_a_id as fighter_id, fight_id, winner_id, method, finish_type, is_finish, weight_class, round_stopped, result, is_title_fight, event_date from results
    union all
    select fighter_b_id as fighter_id, fight_id, winner_id, method, finish_type, is_finish, weight_class, round_stopped, result, is_title_fight, event_date from results
),

career as (
    select
        fighter_id,
        count(*)                                                         as total_fights,
        count(*) filter (where winner_id = fighter_id)                   as wins,
        count(*) filter (where result = 'win' and winner_id != fighter_id) as losses,
        count(*) filter (where result in ('nc', 'draw'))                 as nc_draws,
        count(*) filter (where winner_id = fighter_id and method = 'KO/TKO')    as wins_by_ko,
        count(*) filter (where winner_id = fighter_id and method = 'Submission') as wins_by_sub,
        count(*) filter (where winner_id = fighter_id and finish_type = 'decision') as wins_by_dec,
        round(count(*) filter (where winner_id = fighter_id and is_finish)::numeric / nullif(count(*) filter (where winner_id = fighter_id), 0) * 100, 1) as finish_rate_pct,
        mode() within group (order by weight_class)                      as primary_weight_class,
        count(*) filter (where is_title_fight)                           as title_fights,
        max(event_date)                                                  as last_fight_date
    from fighter_fights
    group by fighter_id
),

avg_stats as (
    select
        fighter_id,
        round(avg(sig_strike_accuracy), 1)   as avg_sig_strike_accuracy,
        round(avg(takedown_accuracy), 1)      as avg_takedown_accuracy,
        round(avg(total_sig_landed), 1)       as avg_sig_landed_per_fight,
        round(avg(total_td_landed), 1)        as avg_td_per_fight,
        round(avg(total_ctrl_sec) / 60.0, 1) as avg_ctrl_min_per_fight,
        round(avg(total_knockdowns), 2)       as avg_knockdowns_per_fight,
        sum(total_sig_landed)                 as career_sig_landed,
        sum(total_sig_attempted)              as career_sig_attempted,
        sum(total_td_landed)                  as career_td_landed
    from round_stats
    group by fighter_id
)

select
    f.fighter_id, f.name,
    c.total_fights, c.wins, c.losses, c.nc_draws,
    c.wins_by_ko, c.wins_by_sub, c.wins_by_dec,
    c.finish_rate_pct, c.primary_weight_class, c.title_fights, c.last_fight_date,
    s.avg_sig_strike_accuracy, s.avg_sig_landed_per_fight,
    s.career_sig_landed, s.career_sig_attempted,
    s.avg_takedown_accuracy, s.avg_td_per_fight,
    s.career_td_landed, s.avg_ctrl_min_per_fight, s.avg_knockdowns_per_fight
from fighters f
join career c on f.fighter_id = c.fighter_id
left join avg_stats s on f.fighter_id = s.fighter_id
order by c.wins desc
