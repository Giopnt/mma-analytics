with source as (
    select
        ff.*,
        m.method        as method_raw,
        m.method_detail as method_detail
    from {{ source('warehouse', 'fact_fight') }} ff
    left join {{ source('warehouse', 'dim_method') }} m on ff.method_id = m.method_id
),

normalised as (
    select
        fight_id, event_id, fighter_a_id, fighter_b_id, winner_id,
        method_id, weight_class, round_stopped, time_stopped,
        result, is_title_fight, is_main_event,
        method_raw, method_detail,

        case method_raw
            when 'U-DEC'      then 'Decision - Unanimous'
            when 'S-DEC'      then 'Decision - Split'
            when 'M-DEC'      then 'Decision - Majority'
            when 'KO/TKO'     then 'KO/TKO'
            when 'SUB'        then 'Submission'
            when 'Overturned' then 'No Contest'
            when 'DQ'         then 'DQ'
            when 'Draw'       then 'Draw'
            else method_raw
        end as method_clean,

        case
            when method_raw in ('KO/TKO') then 'finish'
            when method_raw in ('SUB')    then 'finish'
            when method_raw like '%DEC%'  then 'decision'
            else 'other'
        end as finish_type,

        method_raw in ('KO/TKO', 'SUB') as is_finish

    from source
)

select * from normalised
