with fights as (
    select * from {{ ref('stg_fights') }}
),

events as (
    select * from {{ ref('stg_events') }}
),

fighters as (
    select fighter_id, name from {{ source('warehouse', 'dim_fighter') }}
)

select
    f.fight_id, f.event_id,
    e.event_name, e.event_date, e.event_year, e.location, e.country,
    f.fighter_a_id, fa.name as fighter_a_name,
    f.fighter_b_id, fb.name as fighter_b_name,
    f.winner_id,   fw.name as winner_name,
    f.method_clean  as method,
    f.method_detail,
    f.finish_type,
    f.is_finish,
    f.weight_class,
    f.round_stopped,
    f.time_stopped,
    f.result,
    f.is_title_fight,
    f.is_main_event
from fights f
join events   e  on f.event_id     = e.event_id
join fighters fa on f.fighter_a_id = fa.fighter_id
join fighters fb on f.fighter_b_id = fb.fighter_id
left join fighters fw on f.winner_id = fw.fighter_id
