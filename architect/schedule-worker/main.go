// Schedule worker: store + wait + send the inner message back to Hermes.
// No LLM, agent, MCP, search, OCR, ComfyUI, or workflow execution here.
package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "modernc.org/sqlite"
)

type scheduleRow struct {
	ID           string         `json:"id"`
	Name         string         `json:"name"`
	CronExpr     string         `json:"cron_expr"`
	Timezone     string         `json:"timezone"`
	Cadence      string         `json:"cadence"`
	Text         string         `json:"text"`
	FireText     string         `json:"fire_text"`
	Origin       map[string]any `json:"origin"`
	Context      map[string]any `json:"context"`
	NextRunAt    *time.Time     `json:"next_run_at"`
	LastFiredAt  *time.Time     `json:"last_fired_at"`
	Enabled      bool           `json:"enabled"`
	CreatedAt    time.Time      `json:"created_at"`
}

type upsertReq struct {
	ID         string         `json:"id"`
	Name       string         `json:"name"`
	CronExpr   string         `json:"cron_expr"`
	Timezone   string         `json:"timezone"`
	Cadence    string         `json:"cadence"`
	Text       string         `json:"text"`
	FireText   string         `json:"fire_text"`
	Origin     map[string]any `json:"origin"`
	Context    map[string]any `json:"context"`
	Enabled    *bool          `json:"enabled"`
	NextRunAt  string         `json:"next_run_at"`
}

var (
	db          *sql.DB
	mu          sync.Mutex
	listen      = env("LISTEN", ":8110")
	// Used only when DATABASE_URL is empty (local/migrate fallback). Compose does not set SQLITE_PATH.
	sqlitePath  = env("SQLITE_PATH", "/data/schedules.db")
	zaloInject  = env("ZALO_INJECT_URL", "http://zalo-proxy:8787/inject-event")
	zaloToken   = strings.TrimSpace(os.Getenv("ZALO_PLUGIN_TOKEN"))
	hermesURL   = env("HERMES_FIRE_URL", "http://hermes:8642/v1/chat/completions")
	hermesKey   = strings.TrimSpace(os.Getenv("HERMES_API_KEY"))
	tickEvery   = time.Duration(envInt("TICK_MS", 2000)) * time.Millisecond
	graceSec    = envInt("GRACE_S", 120)
	httpClient  = &http.Client{Timeout: 15 * time.Second}
)

func env(key, fallback string) string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v
}

func envInt(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func main() {
	var err error
	if dsn := strings.TrimSpace(os.Getenv("DATABASE_URL")); dsn != "" {
		db, err = openPostgres(dsn)
		if err != nil {
			log.Fatal(err)
		}
	} else {
		if err = os.MkdirAll(dirOf(sqlitePath), 0o755); err != nil {
			log.Fatal(err)
		}
		db, err = sql.Open("sqlite", sqlitePath)
		if err != nil {
			log.Fatal(err)
		}
		if _, err = db.Exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`); err != nil {
			log.Fatal(err)
		}
		if _, err = db.Exec(`
CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY,
  name TEXT,
  cron_expr TEXT NOT NULL,
  timezone TEXT,
  cadence TEXT,
  text TEXT,
  fire_text TEXT,
  origin_json TEXT,
  context_json TEXT,
  next_run_unix INTEGER,
  last_fired_unix INTEGER,
  enabled INTEGER DEFAULT 1,
  created_unix INTEGER
);`); err != nil {
			log.Fatal(err)
		}
		if _, err = db.Exec(`
CREATE TABLE IF NOT EXISTS schedule_fire_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  schedule_id TEXT NOT NULL,
  thread_id TEXT,
  status TEXT NOT NULL,
  detail TEXT,
  fired_unix INTEGER NOT NULL
);`); err != nil {
			log.Fatal(err)
		}
		_, _ = db.Exec(`CREATE INDEX IF NOT EXISTS idx_fire_log_sched ON schedule_fire_log(schedule_id, fired_unix DESC);`)
		_, _ = db.Exec(`CREATE INDEX IF NOT EXISTS idx_fire_log_thread ON schedule_fire_log(thread_id, fired_unix DESC);`)
	}
	defer db.Close()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		backend := "sqlite"
		if usingPostgres() {
			backend = "postgres"
		}
		writeJSON(w, 200, map[string]any{"ok": true, "service": "schedule-worker", "store": backend})
	})
	mux.HandleFunc("/v1/schedules", schedulesHandler)
	mux.HandleFunc("/v1/schedules/history", scheduleHistoryHandler)
	mux.HandleFunc("/v1/schedules/", scheduleItemHandler)
	mux.HandleFunc("/v1/schedules/tick", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		ids := fireDue(time.Now().UTC())
		writeJSON(w, 200, map[string]any{"ok": true, "fired": ids})
	})

	go func() {
		t := time.NewTicker(tickEvery)
		defer t.Stop()
		for range t.C {
			fireDue(time.Now().UTC())
		}
	}()

	if usingPostgres() {
		log.Printf("schedule-worker listen=%s store=postgres", listen)
	} else {
		log.Printf("schedule-worker listen=%s sqlite=%s", listen, sqlitePath)
	}
	log.Fatal(http.ListenAndServe(listen, mux))
}

func dirOf(path string) string {
	i := strings.LastIndex(path, "/")
	if i <= 0 {
		return "/data"
	}
	return path[:i]
}

func schedulesHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		rows, err := listSchedules()
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true, "schedules": rows})
	case http.MethodPost:
		var req upsertReq
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			http.Error(w, "invalid json", 400)
			return
		}
		row, err := upsert(req)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true, "schedule": row})
	default:
		http.Error(w, "method", http.StatusMethodNotAllowed)
	}
}

func scheduleItemHandler(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/v1/schedules/")
	id = strings.Trim(id, "/")
	if id == "" || id == "tick" || id == "history" {
		http.NotFound(w, r)
		return
	}
	if strings.HasSuffix(id, "/history") {
		sid := strings.TrimSuffix(id, "/history")
		sid = strings.Trim(sid, "/")
		rows, err := listFireLog(sid, "", 50)
		if err != nil {
			writeJSON(w, 500, map[string]any{"ok": false, "error": err.Error()})
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true, "schedule_id": sid, "history": rows})
		return
	}
	switch r.Method {
	case http.MethodGet:
		row, err := getSchedule(id)
		if err != nil {
			writeJSON(w, 404, map[string]any{"ok": false, "error": "not_found"})
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true, "schedule": row})
	case http.MethodDelete:
		var err error
		if usingPostgres() {
			_, err = db.Exec(`DELETE FROM public.schedules WHERE id=$1`, id)
		} else {
			_, err = db.Exec(`DELETE FROM schedules WHERE id=?`, id)
		}
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true, "deleted": id})
	default:
		http.Error(w, "method", http.StatusMethodNotAllowed)
	}
}

func scheduleHistoryHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	q := r.URL.Query()
	sid := strings.TrimSpace(q.Get("schedule_id"))
	thread := strings.TrimSpace(q.Get("thread_id"))
	limit := 50
	if n, err := strconv.Atoi(q.Get("limit")); err == nil && n > 0 && n <= 200 {
		limit = n
	}
	rows, err := listFireLog(sid, thread, limit)
	if err != nil {
		writeJSON(w, 500, map[string]any{"ok": false, "error": err.Error()})
		return
	}
	writeJSON(w, 200, map[string]any{"ok": true, "history": rows, "count": len(rows)})
}

func recordFire(sch scheduleRow, status, detail string) {
	threadID := firstNonEmpty(strMap(sch.Origin, "thread_id"), strMap(sch.Origin, "chat_id"), strMap(sch.Context, "thread_id"))
	_, err := db.Exec(
		`INSERT INTO schedule_fire_log (schedule_id, thread_id, status, detail, fired_unix) VALUES (?,?,?,?,?)`,
		sch.ID, threadID, status, detail, time.Now().UTC().Unix(),
	)
	if err != nil {
		log.Printf("fire_log %s %v", sch.ID, err)
	}
}

func listFireLog(scheduleID, threadID string, limit int) ([]map[string]any, error) {
	q := `SELECT id, schedule_id, thread_id, status, detail, fired_unix FROM schedule_fire_log WHERE 1=1`
	args := []any{}
	if scheduleID != "" {
		q += ` AND schedule_id=?`
		args = append(args, scheduleID)
	}
	if threadID != "" {
		q += ` AND thread_id=?`
		args = append(args, threadID)
	}
	q += ` ORDER BY fired_unix DESC LIMIT ?`
	args = append(args, limit)
	rows, err := db.Query(q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var id int64
		var sid, tid, status, detail string
		var fired int64
		if err := rows.Scan(&id, &sid, &tid, &status, &detail, &fired); err != nil {
			return nil, err
		}
		out = append(out, map[string]any{
			"id":          id,
			"schedule_id": sid,
			"thread_id":   tid,
			"status":      status,
			"detail":      detail,
			"fired_at":    time.Unix(fired, 0).UTC().Format(time.RFC3339),
		})
	}
	return out, rows.Err()
}

func upsert(req upsertReq) (scheduleRow, error) {
	if usingPostgres() {
		return upsertSchedulePG(req)
	}
	mu.Lock()
	defer mu.Unlock()
	cron := strings.TrimSpace(req.CronExpr)
	if validCron(cron) == "" {
		return scheduleRow{}, fmt.Errorf("cron_expr required")
	}
	fire := strings.TrimSpace(req.FireText)
	if fire == "" {
		fire = fireFromContext(req.Context)
	}
	if fire == "" {
		return scheduleRow{}, fmt.Errorf("fire_text required")
	}
	id := strings.TrimSpace(req.ID)
	if id == "" {
		id = "sch_" + strconv.FormatInt(time.Now().UnixNano(), 36)
	}
	tzName := strings.TrimSpace(req.Timezone)
	if tzName == "" {
		tzName = "Asia/Ho_Chi_Minh"
	}
	cadence := strings.ToLower(strings.TrimSpace(req.Cadence))
	if cadence == "" {
		cadence = "once"
	}
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}
	name := strings.TrimSpace(req.Name)
	if name == "" {
		name = firstLine(fire)
		if len(name) > 40 {
			name = name[:40]
		}
	}
	now := time.Now().UTC()
	nxt := parseTime(req.NextRunAt)
	if nxt == nil {
		t := nextDaily(cron, tzName, now, time.Duration(graceSec)*time.Second)
		nxt = &t
	}
	origin, _ := json.Marshal(req.Origin)
	if req.Origin == nil {
		origin = []byte("{}")
	}
	ctx, _ := json.Marshal(req.Context)
	if req.Context == nil {
		ctx = []byte("{}")
	}
	_, err := db.Exec(`
INSERT INTO schedules (id,name,cron_expr,timezone,cadence,text,fire_text,origin_json,context_json,next_run_unix,last_fired_unix,enabled,created_unix)
VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?,?)
ON CONFLICT(id) DO UPDATE SET
  name=excluded.name,
  cron_expr=excluded.cron_expr,
  timezone=excluded.timezone,
  cadence=excluded.cadence,
  text=excluded.text,
  fire_text=excluded.fire_text,
  origin_json=excluded.origin_json,
  context_json=excluded.context_json,
  next_run_unix=excluded.next_run_unix,
  enabled=excluded.enabled
`, id, name, cron, tzName, cadence, req.Text, fire, string(origin), string(ctx), nxt.Unix(), boolInt(enabled), now.Unix())
	if err != nil {
		return scheduleRow{}, err
	}
	return getSchedule(id)
}

func listSchedules() ([]scheduleRow, error) {
	if usingPostgres() {
		return listSchedulesPG()
	}
	rows, err := db.Query(`SELECT id,name,cron_expr,timezone,cadence,text,fire_text,origin_json,context_json,next_run_unix,last_fired_unix,enabled,created_unix FROM schedules ORDER BY next_run_unix`)
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

func getSchedule(id string) (scheduleRow, error) {
	if usingPostgres() {
		return getSchedulePG(id)
	}
	row := db.QueryRow(`SELECT id,name,cron_expr,timezone,cadence,text,fire_text,origin_json,context_json,next_run_unix,last_fired_unix,enabled,created_unix FROM schedules WHERE id=?`, id)
	return scanRow(row)
}

type scanner interface {
	Scan(dest ...any) error
}

func scanRow(s scanner) (scheduleRow, error) {
	var (
		row                         scheduleRow
		originJSON, contextJSON     string
		nextUnix, lastUnix, created sql.NullInt64
		enabled                     int
	)
	err := s.Scan(&row.ID, &row.Name, &row.CronExpr, &row.Timezone, &row.Cadence, &row.Text, &row.FireText, &originJSON, &contextJSON, &nextUnix, &lastUnix, &enabled, &created)
	if err != nil {
		return row, err
	}
	row.Enabled = enabled == 1
	_ = json.Unmarshal([]byte(originJSON), &row.Origin)
	_ = json.Unmarshal([]byte(contextJSON), &row.Context)
	if row.Origin == nil {
		row.Origin = map[string]any{}
	}
	if row.Context == nil {
		row.Context = map[string]any{}
	}
	if nextUnix.Valid {
		t := time.Unix(nextUnix.Int64, 0).UTC()
		row.NextRunAt = &t
	}
	if lastUnix.Valid {
		t := time.Unix(lastUnix.Int64, 0).UTC()
		row.LastFiredAt = &t
	}
	if created.Valid {
		row.CreatedAt = time.Unix(created.Int64, 0).UTC()
	}
	return row, nil
}

func fireDue(now time.Time) []string {
	if usingPostgres() {
		return fireDuePG(now)
	}
	rows, err := listSchedules()
	if err != nil {
		log.Printf("list err %v", err)
		return nil
	}
	fired := []string{}
	for _, sch := range rows {
		if !sch.Enabled || sch.NextRunAt == nil || sch.NextRunAt.After(now) {
			continue
		}
		if err := sendBack(sch); err != nil {
			log.Printf("fire %s err %v", sch.ID, err)
			recordFire(sch, "error", err.Error())
			continue
		}
		recordFire(sch, "ok", "")
		mu.Lock()
		if strings.EqualFold(sch.Cadence, "once") {
			if _, err := db.Exec(`DELETE FROM schedules WHERE id=?`, sch.ID); err != nil {
				log.Printf("delete once %s %v", sch.ID, err)
			}
		} else {
			nxt := nextDaily(sch.CronExpr, sch.Timezone, now.Add(time.Second), 0)
			if !nxt.After(now) {
				nxt = now.Add(24 * time.Hour)
			}
			if _, err := db.Exec(`UPDATE schedules SET last_fired_unix=?, next_run_unix=? WHERE id=?`, now.Unix(), nxt.Unix(), sch.ID); err != nil {
				log.Printf("update next %s %v", sch.ID, err)
			}
		}
		mu.Unlock()
		fired = append(fired, sch.ID)
	}
	return fired
}

func fireDuePG(now time.Time) []string {
	fired := []string{}
	for {
		sch, execID, corrID, err := claimDueSchedulePG(now)
		if err != nil {
			log.Printf("claim due pg: %v", err)
			return fired
		}
		if sch == nil {
			return fired
		}
		// Propagate correlation into origin for downstream inject headers/metadata.
		if sch.Origin == nil {
			sch.Origin = map[string]any{}
		}
		sch.Origin["execution_id"] = execID
		sch.Origin["correlation_id"] = corrID
		if err := sendBack(*sch); err != nil {
			log.Printf("fire %s err %v", sch.ID, err)
			finalizeExecutionPG(execID, "failed", err.Error(), "fire_error", *sch, now)
			continue
		}
		finalizeExecutionPG(execID, "succeeded", "handoff_accepted", "", *sch, now)
		fired = append(fired, sch.ID+"/"+execID)
	}
}

func sendBack(sch scheduleRow) error {
	text := strings.TrimSpace(sch.FireText)
	if text == "" {
		return fmt.Errorf("empty fire_text")
	}
	platform := strings.ToLower(strMap(sch.Origin, "platform"))
	if platform == "zalo" || strMap(sch.Origin, "thread_id") != "" || strMap(sch.Context, "thread_id") != "" {
		return injectZalo(sch, text)
	}
	return fireHermes(text)
}

func injectZalo(sch scheduleRow, text string) error {
	threadID := firstNonEmpty(strMap(sch.Origin, "thread_id"), strMap(sch.Origin, "chat_id"), strMap(sch.Context, "thread_id"))
	senderID := firstNonEmpty(strMap(sch.Origin, "user_id"), strMap(sch.Origin, "sender_id"), strMap(sch.Context, "sender_id"), threadID)
	senderName := firstNonEmpty(strMap(sch.Context, "sender_name"), strMap(sch.Origin, "chat_name"), "user")
	threadType := firstNonEmpty(strMap(sch.Context, "thread_type"), "user")
	if threadID == "" {
		return fmt.Errorf("missing zalo thread")
	}
	body, _ := json.Marshal(map[string]any{
		"type": "message",
		"payload": map[string]any{
			"threadId":       threadID,
			"threadType":     threadType,
			"senderId":       senderID,
			"senderName":     senderName,
			"text":           text,
			"isSelf":         false,
			"scheduleFire":   true,
			"scheduleId":     sch.ID,
			"executionId":    strMap(sch.Origin, "execution_id"),
			"correlationId":  strMap(sch.Origin, "correlation_id"),
		},
	})
	req, err := http.NewRequest(http.MethodPost, zaloInject, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	if corr := strMap(sch.Origin, "correlation_id"); corr != "" {
		req.Header.Set("X-Correlation-ID", corr)
	}
	if execID := strMap(sch.Origin, "execution_id"); execID != "" {
		req.Header.Set("X-Execution-ID", execID)
	}
	if sch.ID != "" {
		req.Header.Set("X-Schedule-ID", sch.ID)
	}
	if zaloToken != "" {
		req.Header.Set("Authorization", "Bearer "+zaloToken)
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("inject %d %s", resp.StatusCode, string(raw))
	}
	log.Printf("fired zalo id=%s thread=%s", sch.ID, threadID)
	return nil
}

func fireHermes(text string) error {
	body, _ := json.Marshal(map[string]any{
		"model":    "hermes",
		"messages": []map[string]string{{"role": "user", "content": text}},
	})
	req, err := http.NewRequest(http.MethodPost, hermesURL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	if hermesKey != "" {
		req.Header.Set("Authorization", "Bearer "+hermesKey)
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("hermes %d %s", resp.StatusCode, string(raw))
	}
	return nil
}

func fireFromContext(ctx map[string]any) string {
	if ctx == nil {
		return ""
	}
	plan, _ := ctx["plan"].(map[string]any)
	if plan == nil {
		return ""
	}
	if raw, ok := plan["instructions"].([]any); ok {
		parts := make([]string, 0, len(raw))
		for _, item := range raw {
			s := strings.TrimSpace(strAny(item))
			if s != "" {
				parts = append(parts, s)
			}
		}
		if len(parts) > 0 {
			return strings.Join(parts, "\n")
		}
	}
	return strings.TrimSpace(strAny(plan["message"]))
}

func nextDaily(expr, tzName string, now time.Time, grace time.Duration) time.Time {
	parts := strings.Fields(expr)
	minute, hour := 0, 0
	if len(parts) >= 2 {
		minute, _ = strconv.Atoi(parts[0])
		hour, _ = strconv.Atoi(parts[1])
	}
	loc, err := time.LoadLocation(tzName)
	if err != nil {
		loc = time.FixedZone("ICT", 7*3600)
	}
	local := now.In(loc)
	cand := time.Date(local.Year(), local.Month(), local.Day(), hour, minute, 0, 0, loc)
	if cand.After(local) {
		return cand.UTC()
	}
	if grace > 0 && local.Sub(cand) >= 0 && local.Sub(cand) <= grace {
		return cand.UTC()
	}
	return cand.Add(24 * time.Hour).UTC()
}

func validCron(expr string) string {
	parts := strings.Fields(expr)
	if len(parts) != 5 {
		return ""
	}
	ok := "0123456789*,/-"
	for _, p := range parts {
		if p == "" {
			return ""
		}
		for _, ch := range p {
			if !strings.ContainsRune(ok, ch) {
				return ""
			}
		}
	}
	return strings.Join(parts, " ")
}

func parseTime(raw string) *time.Time {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	t, err := time.Parse(time.RFC3339, strings.ReplaceAll(raw, "Z", "+00:00"))
	if err != nil {
		t, err = time.Parse(time.RFC3339Nano, raw)
	}
	if err != nil {
		return nil
	}
	u := t.UTC()
	return &u
}

func strMap(m map[string]any, key string) string {
	if m == nil {
		return ""
	}
	return strings.TrimSpace(strAny(m[key]))
}

func strAny(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case float64:
		return strconv.FormatInt(int64(t), 10)
	default:
		return ""
	}
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

func boolInt(v bool) int {
	if v {
		return 1
	}
	return 0
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
