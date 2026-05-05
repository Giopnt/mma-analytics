with stats as (
    select * from {{ ref('mart_fighter_stats') }}
)

select
    s.fighter_id,
    s.name                         as fighter_name,
    s.total_fights, s.wins, s.losses, s.nc_draws,
    s.finish_rate_pct, s.primary_weight_class,
    s.wins_by_ko, s.wins_by_sub, s.wins_by_dec,
    s.avg_sig_strike_accuracy, s.avg_sig_landed_per_fight,
    s.career_sig_landed, s.career_sig_attempted, s.avg_knockdowns_per_fight,
    s.avg_takedown_accuracy, s.avg_td_per_fight,
    s.career_td_landed, s.avg_ctrl_min_per_fight,
    s.title_fights, s.last_fight_date
from stats s
order by s.wins desc
