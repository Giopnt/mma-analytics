with results as (
    select * from {{ ref('int_fight_results') }}
)

select
    event_id, event_name, event_date, event_year, location, country,
    count(*)                                         as total_fights,
    count(*) filter (where is_finish)                as total_finishes,
    count(*) filter (where method = 'KO/TKO')        as ko_tko_count,
    count(*) filter (where method = 'Submission')     as submission_count,
    count(*) filter (where finish_type = 'decision') as decision_count,
    count(*) filter (where is_title_fight)           as title_fights,
    round(count(*) filter (where is_finish)::numeric / nullif(count(*), 0) * 100, 1) as finish_rate_pct,
    round(avg(round_stopped), 1)                     as avg_round_stopped
from results
group by event_id, event_name, event_date, event_year, location, country
order by event_date desc
