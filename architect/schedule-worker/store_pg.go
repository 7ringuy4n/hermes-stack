// Postgres schedule store — used when DATABASE_URL is set.
// SQLite remains the migrate/fallback path in main.go when DATABASE_URL is empty.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

const pgSchema = `
CREATE TABLE IF NOT EXISTS public.schedules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  cron_expr TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  cadence TEXT NOT NULL DEFAULT 'once',
  text TEXT NOT NULL DEFAULT '',
  fire_text TEXT NOT NULL DEFAULT '',
  origin_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  next_run_at TIMESTAMPTZ,
  last_fired_at TIMESTAMPTZ,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS schedules_due_idx ON public.schedules (enabled, next_run_at);

CREATE TABLE IF NOT EXISTS public.schedule_executions (
  execution_id TEXT PRIMARY KEY,
  schedule_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  thread_id TEXT NOT NULL DEFAULT '',
  user_id TEXT,
  status TEXT NOT NULL,
  triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  accepted_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  detail TEXT NOT NULL DEFAULT '',
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS schedule_executions_sched_idx
  ON public.schedule_executions (schedule_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS schedule_executions_corr_idx
  ON public.schedule_executions (correlation_id);
CREATE INDEX IF NOT EXISTS schedule_executions_thread_idx
  ON public.schedule_executions (thread_id, triggered_at DESC);
`

func usingPostgres() bool {
	return strings.TrimSpace(os.Getenv("DATABASE_URL")) != ""
}

func splitSQLStatements(blob string) []string {
	out := []string{}
	for _, part := range strings.Split(blob, ";") {
		var lines []string
		for _, ln := range strings.Split(part, "\n") {
			trim := strings.TrimSpace(ln)
			if trim == "" || strings.HasPrefix(trim, "--") {
				continue
			}
			lines = append(lines, ln)
		}
		stmt := strings.TrimSpace(strings.Join(lines, "\n"))
		if stmt != "" {
			out = append(out, stmt)
		}
	}
	return out
}

func applyPgSchema(pg *sql.DB) error {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	// Workflow owns wf.schedules. This worker stores in public.
	if _, err := pg.ExecContext(ctx, "SET search_path TO public"); err != nil {
		return err
	}
	for _, stmt := range splitSQLStatements(pgSchema) {
		if _, err := pg.ExecContext(ctx, stmt); err != nil {
			return fmt.Errorf("schema %q: %w", stmt[:min(48, len(stmt))], err)
		}
	}
	var n int
	if err := pg.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM information_schema.tables
		 WHERE table_schema='public' AND table_name IN ('schedules','schedule_executions')`,
	).Scan(&n); err != nil {
		return err
	}
	if n < 2 {
		return fmt.Errorf("public schedule tables incomplete (found %d of 2); wf.schedules is not this worker", n)
	}
	return nil
}

func openPostgres(dsn string) (*sql.DB, error) {
	pg, err := sql.Open("pgx", dsn)
	if err != nil {
		return nil, err
	}
	pg.SetMaxOpenConns(8)
	pg.SetMaxIdleConns(2)
	pg.SetConnMaxLifetime(time.Hour)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := pg.PingContext(ctx); err != nil {
		_ = pg.Close()
		return nil, err
	}
	if err := applyPgSchema(pg); err != nil {
		_ = pg.Close()
		return nil, err
	}
	log.Printf("schedule-worker postgres store ready (public.schedules)")
	return pg, nil
}

func claimDueSchedulePG(now time.Time) (*scheduleRow, string, string, error) {
	tx, err := db.Begin()
	if err != nil {
		return nil, "", "", err
	}
	defer func() { _ = tx.Rollback() }()

	row := tx.QueryRow(`
SELECT id, name, cron_expr, timezone, cadence, text, fire_text,
       origin_json::text, context_json::text,
       EXTRACT(EPOCH FROM next_run_at)::bigint,
       EXTRACT(EPOCH FROM last_fired_at)::bigint,
       CASE WHEN enabled THEN 1 ELSE 0 END,
       EXTRACT(EPOCH FROM created_at)::bigint
FROM public.schedules
WHERE enabled = TRUE AND next_run_at IS NOT NULL AND next_run_at <= to_timestamp($1)
ORDER BY next_run_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1`, now.Unix())

	sch, err := scanRow(row)
	if err == sql.ErrNoRows {
		return nil, "", "", nil
	}
	if err != nil {
		return nil, "", "", err
	}

	execID := fmt.Sprintf("exec_%d_%s", now.UnixNano(), sch.ID)
	corrID := fmt.Sprintf("corr_%d_%s", now.UnixNano(), sch.ID)
	threadID := firstNonEmpty(strMap(sch.Origin, "thread_id"), strMap(sch.Origin, "chat_id"), strMap(sch.Context, "thread_id"))
	userID := firstNonEmpty(strMap(sch.Origin, "user_id"), strMap(sch.Origin, "sender_id"), strMap(sch.Context, "sender_id"))

	if _, err := tx.Exec(`
INSERT INTO public.schedule_executions
  (execution_id, schedule_id, correlation_id, thread_id, user_id, status, triggered_at, updated_at)
VALUES ($1,$2,$3,$4,NULLIF($5,''),'firing', NOW(), NOW())`,
		execID, sch.ID, corrID, threadID, userID); err != nil {
		return nil, "", "", err
	}

	park := now.Add(30 * time.Minute).Unix()
	if _, err := tx.Exec(`UPDATE public.schedules SET next_run_at=to_timestamp($1), updated_at=NOW() WHERE id=$2`, park, sch.ID); err != nil {
		return nil, "", "", err
	}
	if err := tx.Commit(); err != nil {
		return nil, "", "", err
	}
	return &sch, execID, corrID, nil
}

func finalizeExecutionPG(execID, status, detail, errorCode string, sch scheduleRow, now time.Time) {
	_, err := db.Exec(`
UPDATE public.schedule_executions SET
  status=$2,
  detail=$3,
  error_code=NULLIF($4,''),
  accepted_at = CASE WHEN $2 IN ('accepted','running','succeeded','failed') THEN COALESCE(accepted_at, NOW()) ELSE accepted_at END,
  started_at  = CASE WHEN $2 IN ('running','succeeded','failed') THEN COALESCE(started_at, NOW()) ELSE started_at END,
  completed_at= CASE WHEN $2='succeeded' THEN NOW() ELSE completed_at END,
  failed_at   = CASE WHEN $2='failed' THEN NOW() ELSE failed_at END,
  updated_at=NOW()
WHERE execution_id=$1`, execID, status, detail, errorCode)
	if err != nil {
		log.Printf("execution update %s: %v", execID, err)
	}
	if status == "succeeded" {
		if strings.EqualFold(sch.Cadence, "once") {
			_, _ = db.Exec(`DELETE FROM public.schedules WHERE id=$1`, sch.ID)
			return
		}
		nxt := nextDaily(sch.CronExpr, sch.Timezone, now.Add(time.Second), 0)
		if !nxt.After(now) {
			nxt = now.Add(24 * time.Hour)
		}
		_, _ = db.Exec(`UPDATE public.schedules SET last_fired_at=to_timestamp($1), next_run_at=to_timestamp($2), updated_at=NOW() WHERE id=$3`,
			now.Unix(), nxt.Unix(), sch.ID)
		return
	}
	_, _ = db.Exec(`UPDATE public.schedules SET next_run_at=to_timestamp($1), updated_at=NOW() WHERE id=$2`,
		now.Add(2*time.Minute).Unix(), sch.ID)
}

func upsertSchedulePG(req upsertReq) (scheduleRow, error) {
	id := strings.TrimSpace(req.ID)
	if id == "" {
		id = fmt.Sprintf("sch_%d", time.Now().UTC().UnixNano())
	}
	name := strings.TrimSpace(req.Name)
	cronExpr := strings.TrimSpace(req.CronExpr)
	if cronExpr == "" {
		return scheduleRow{}, fmt.Errorf("cron_expr required")
	}
	tz := strings.TrimSpace(req.Timezone)
	if tz == "" {
		tz = "Asia/Ho_Chi_Minh"
	}
	cadence := strings.TrimSpace(req.Cadence)
	if cadence == "" {
		cadence = "once"
	}
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}
	origin := req.Origin
	if origin == nil {
		origin = map[string]any{}
	}
	context := req.Context
	if context == nil {
		context = map[string]any{}
	}
	originJSON, _ := json.Marshal(origin)
	contextJSON, _ := json.Marshal(context)
	var next time.Time
	if strings.TrimSpace(req.NextRunAt) != "" {
		t, err := time.Parse(time.RFC3339, strings.TrimSpace(req.NextRunAt))
		if err != nil {
			return scheduleRow{}, fmt.Errorf("next_run_at: %w", err)
		}
		next = t.UTC()
	} else {
		next = nextDaily(cronExpr, tz, time.Now().UTC(), 0)
	}
	_, err := db.Exec(`
INSERT INTO public.schedules (
  id, name, cron_expr, timezone, cadence, text, fire_text,
  origin_json, context_json, next_run_at, enabled, created_at, updated_at
) VALUES (
  $1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,to_timestamp($10),$11,NOW(),NOW()
)
ON CONFLICT (id) DO UPDATE SET
  name=EXCLUDED.name,
  cron_expr=EXCLUDED.cron_expr,
  timezone=EXCLUDED.timezone,
  cadence=EXCLUDED.cadence,
  text=EXCLUDED.text,
  fire_text=EXCLUDED.fire_text,
  origin_json=EXCLUDED.origin_json,
  context_json=EXCLUDED.context_json,
  next_run_at=EXCLUDED.next_run_at,
  enabled=EXCLUDED.enabled,
  updated_at=NOW()`,
		id, name, cronExpr, tz, cadence, req.Text, req.FireText,
		string(originJSON), string(contextJSON), next.Unix(), enabled)
	if err != nil {
		return scheduleRow{}, err
	}
	return getSchedule(id)
}

func listSchedulesPG() ([]scheduleRow, error) {
	rows, err := db.Query(`
SELECT id, name, cron_expr, timezone, cadence, text, fire_text,
       origin_json::text, context_json::text,
       EXTRACT(EPOCH FROM next_run_at)::bigint,
       EXTRACT(EPOCH FROM last_fired_at)::bigint,
       CASE WHEN enabled THEN 1 ELSE 0 END,
       EXTRACT(EPOCH FROM created_at)::bigint
FROM public.schedules ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []scheduleRow{}
	for rows.Next() {
		row, err := scanRow(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func getSchedulePG(id string) (scheduleRow, error) {
	row := db.QueryRow(`
SELECT id, name, cron_expr, timezone, cadence, text, fire_text,
       origin_json::text, context_json::text,
       EXTRACT(EPOCH FROM next_run_at)::bigint,
       EXTRACT(EPOCH FROM last_fired_at)::bigint,
       CASE WHEN enabled THEN 1 ELSE 0 END,
       EXTRACT(EPOCH FROM created_at)::bigint
FROM public.schedules WHERE id=$1`, id)
	return scanRow(row)
}
