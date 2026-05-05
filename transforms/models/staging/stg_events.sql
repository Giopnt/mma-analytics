with source as (
    select * from {{ source('warehouse', 'dim_event') }}
)

select
    event_id,
    event_name,
    event_date,
    location,
    city,
    country,
    extract(year  from event_date)::int as event_year,
    extract(month from event_date)::int as event_month
from source
where event_id is not null
