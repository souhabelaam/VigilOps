-- One row per app per sample (about every 5 s), same columns as ml/data/prepared/*.csv.
-- Rates are empty (NULL) when they cannot be computed (first sample, counter reset, no requests).
CREATE TABLE IF NOT EXISTS metric_rates (
    id             BIGSERIAL PRIMARY KEY,
    ts             TIMESTAMPTZ      NOT NULL,   -- when the collector read the app
    app            TEXT             NOT NULL,   -- notes-api or report-api
    cpu_pct        DOUBLE PRECISION,
    req_per_s      DOUBLE PRECISION,
    avg_latency_ms DOUBLE PRECISION,
    memory_mb      DOUBLE PRECISION,
    reset          BOOLEAN          NOT NULL DEFAULT FALSE,  -- counters went down: the app restarted
    UNIQUE (app, ts)                            -- the same sample can never be stored twice
);

-- the anomaly service will ask "latest rows for this app", so index for that
CREATE INDEX IF NOT EXISTS idx_metric_rates_app_ts ON metric_rates (app, ts DESC);
