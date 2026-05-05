CREATE TABLE IF NOT EXISTS dim_event (
    event_id    VARCHAR(32)  PRIMARY KEY,
    event_name  TEXT         NOT NULL,
    event_date  DATE,
    location    TEXT,
    city        TEXT         GENERATED ALWAYS AS (split_part(location, ',', 1)) STORED,
    country     TEXT         GENERATED ALWAYS AS (trim(split_part(location, ',', -1))) STORED
);

CREATE TABLE IF NOT EXISTS dim_fighter (
    fighter_id  SERIAL  PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_method (
    method_id     SERIAL  PRIMARY KEY,
    method        TEXT    NOT NULL,
    method_detail TEXT    NOT NULL DEFAULT '',
    UNIQUE (method, method_detail)
);

INSERT INTO dim_method (method, method_detail) VALUES
    ('KO/TKO',               ''),
    ('Submission',           ''),
    ('Decision - Unanimous', ''),
    ('Decision - Split',     ''),
    ('Decision - Majority',  ''),
    ('No Contest',           ''),
    ('DQ',                   ''),
    ('Draw',                 '')
ON CONFLICT (method, method_detail) DO NOTHING;

CREATE TABLE IF NOT EXISTS fact_fight (
    fight_id        VARCHAR(32)  PRIMARY KEY,
    event_id        VARCHAR(32)  NOT NULL REFERENCES dim_event(event_id),
    fighter_a_id    INT          NOT NULL REFERENCES dim_fighter(fighter_id),
    fighter_b_id    INT          NOT NULL REFERENCES dim_fighter(fighter_id),
    winner_id       INT          REFERENCES dim_fighter(fighter_id),
    method_id       INT          REFERENCES dim_method(method_id),
    weight_class    TEXT,
    round_stopped   SMALLINT,
    time_stopped    VARCHAR(10),
    result          VARCHAR(10),
    is_title_fight  BOOLEAN  DEFAULT FALSE,
    is_main_event   BOOLEAN  DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_fact_fight_event   ON fact_fight(event_id);
CREATE INDEX IF NOT EXISTS idx_fact_fight_winner  ON fact_fight(winner_id);
CREATE INDEX IF NOT EXISTS idx_fact_fight_method  ON fact_fight(method_id);
CREATE INDEX IF NOT EXISTS idx_fact_fight_a       ON fact_fight(fighter_a_id);
CREATE INDEX IF NOT EXISTS idx_fact_fight_b       ON fact_fight(fighter_b_id);

CREATE TABLE IF NOT EXISTS fact_fight_round (
    id                      SERIAL      PRIMARY KEY,
    fight_id                VARCHAR(32) NOT NULL REFERENCES fact_fight(fight_id),
    round_num               SMALLINT    NOT NULL,
    fighter_id              INT         NOT NULL REFERENCES dim_fighter(fighter_id),
    knockdowns              SMALLINT DEFAULT 0,
    sig_strikes_landed      SMALLINT DEFAULT 0,
    sig_strikes_attempted   SMALLINT DEFAULT 0,
    total_strikes_landed    SMALLINT DEFAULT 0,
    total_strikes_attempted SMALLINT DEFAULT 0,
    takedowns_landed        SMALLINT DEFAULT 0,
    takedowns_attempted     SMALLINT DEFAULT 0,
    submission_attempts     SMALLINT DEFAULT 0,
    reversals               SMALLINT DEFAULT 0,
    control_time_sec        SMALLINT DEFAULT 0,
    head_landed             SMALLINT DEFAULT 0,
    head_attempted          SMALLINT DEFAULT 0,
    body_landed             SMALLINT DEFAULT 0,
    body_attempted          SMALLINT DEFAULT 0,
    leg_landed              SMALLINT DEFAULT 0,
    leg_attempted           SMALLINT DEFAULT 0,
    distance_landed         SMALLINT DEFAULT 0,
    distance_attempted      SMALLINT DEFAULT 0,
    clinch_landed           SMALLINT DEFAULT 0,
    clinch_attempted        SMALLINT DEFAULT 0,
    ground_landed           SMALLINT DEFAULT 0,
    ground_attempted        SMALLINT DEFAULT 0,
    UNIQUE (fight_id, round_num, fighter_id)
);

CREATE INDEX IF NOT EXISTS idx_ffr_fight   ON fact_fight_round(fight_id);
CREATE INDEX IF NOT EXISTS idx_ffr_fighter ON fact_fight_round(fighter_id);
CREATE INDEX IF NOT EXISTS idx_ffr_round   ON fact_fight_round(round_num);

CREATE OR REPLACE VIEW v_fighter_career AS
SELECT
    f.fighter_id,
    f.name,
    COUNT(*)                                                                    AS total_fights,
    COUNT(*) FILTER (WHERE ff.winner_id = f.fighter_id)                        AS wins,
    COUNT(*) FILTER (WHERE ff.result = 'win' AND ff.winner_id != f.fighter_id) AS losses,
    COUNT(*) FILTER (WHERE ff.result IN ('nc','draw'))                          AS nc_draw,
    COUNT(*) FILTER (WHERE ff.winner_id = f.fighter_id
                     AND m.method IN ('KO/TKO','Submission'))                   AS finish_wins
FROM dim_fighter f
JOIN fact_fight ff ON f.fighter_id IN (ff.fighter_a_id, ff.fighter_b_id)
JOIN dim_method m  ON ff.method_id = m.method_id
GROUP BY f.fighter_id, f.name;
