package probe

import (
	"encoding/json"
	"os"
	"time"

	"supervisor/internal/metric"
)

// backupSummary is every status document a backup run writes. The run directory is the topic namespace,
// so <run>/<path>.json publishes at supervisor/<host>/backup/<path>, four documents in all:
//
//	<run>/status.json                                  RUN        finishRun, on either trigger
//	<run>/stage/<stage>/status.json                    STAGE      runStage, rewritten by reapLocalStale
//	<run>/stage/primary/service/<service>/status.json  SERVICE    runOneService
//	<run>/stage/tertiary/scrub.json                    SCRUB      writeScrubSummary
//
// Every field is omitempty but [state] and [success_bool], so a zero reads as absent rather than as a
// measurement of zero. The shapes are declared in metric.Payloads(), one payload per document, and tests
// hold that declaration equal to what these writers emit:
//
//	{
//	    "run_id":                "<timestamp>", ALL               Run directory name, [YYYY-MM-DD_hh-mm-ss]
//	    "state":                 "<state>",     ALL               Enum differs per document, only STAGE and SCRUB carry all six
//	    "started_ts":            "<rfc3339>",   ALL
//	    "finished_ts":           "<rfc3339>",   ALL
//	    "duration_s":            <number>,      ALL
//	    "success_bool":          <true|false>,  ALL
//	    "trigger":               "<trigger>",   RUN STAGE         [system|manual], from the first stage carrying one
//	    "expires_ts":            "<rfc3339>",   STAGE SCRUB       Liveness, the reaper stops a run found past it
//	    "timeout_hours":         <number>,      STAGE             Read back rather than resolved by the reader
//	    "file_count":            <number>,      RUN STAGE SERVICE
//	    "size_mb":               <number>,      RUN STAGE SERVICE
//	    "disk_usage_perc":       <number>,      RUN STAGE         Backup volume, tertiary alone measures it
//	    "files_held":            <number>,      RUN STAGE
//	    "files_created":         <number>,      RUN STAGE         Files, never services, in every stage
//	    "files_deleted":         <number>,      RUN STAGE
//	    "size_held_mb":          <number>,      RUN STAGE
//	    "sent_mb":               <number>,      RUN STAGE
//	    "stages_run":            <number>,      RUN
//	    "stages_failed":         <number>,      RUN               Excludes a stop or a timeout
//	    "stages_halted":         <number>,      RUN               A stop or a timeout alone
//	    "disk_used_mb":          <number>,      STAGE
//	    "disk_total_mb":         <number>,      STAGE
//	    "disk_unclean_bool":     <true|false>,  STAGE             The mount replayed its log
//	    "total_mb":              <number>,      STAGE             Expected, against which size_mb is progress
//	    "backup_id":             "<timestamp>", SERVICE           Artefact the run points at, reused when skipped
//	    "kind":                  "<kind>",      SERVICE           [full|delta|unknown]
//	    "version":               "<text>",      SERVICE
//	    "resumed_bool":          <true|false>,  SCRUB             Resumed an unfinished pass rather than starting one
//	    "scrubbed_mb":           <number>,      SCRUB             Cumulative, carried across a resume
//	    "progress_perc":         <number>,      SCRUB
//	    "errors_found":          <number>,      SCRUB             Checksum, verify and super errors
//	    "errors_corrected":      <number>,      SCRUB
//	    "errors_uncorrectable":  <number>,      SCRUB
//	    "files_to_delete":       "<text>",      SCRUB             First 20, comma separated
//	    "files_to_delete_count": <number>,      SCRUB
//	    "device_errors":         <number>,      SCRUB             Since the last scrub, zeroed after reporting
//	    "chunks_relocated":      <number>       SCRUB             From the balance that follows a clean scrub
//	}
//
// Go owns the whole run tree, so every document above has exactly one writer, and the shapes belong to
// metric.Payloads() alone, with the [state] enums and topic templates coming from metric rather than
// being spelled here:
//
//	Go writes         every RUN, STAGE, SERVICE and SCRUB document, on the scheduled trigger and on a
//	                  hand [supervisor backup start] alike, and rewrites a STAGE when the reaper stops
//	                  a run found past its [expires_ts] [reapLocalStale]
//	Go reads          [state] [trigger] [expires_ts] for liveness, [success_bool] per SERVICE for
//	                  service/backup_status, [stages_*] and [disk_usage_perc] for the three host metrics
//	A module reads    nothing here, its own [backup.sh] is execed on an environment contract instead
//	The leader reads  every host's RUN [state] [started_ts] [success_bool] off the broker, never off
//	                  another host's tree, and publishes the cluster rollup [backupClusterSummary]
//
// This struct carries the whole STAGE shape even where Go reads none of a field, because reapLocalStale
// round-trips a stage document through it and anything missing is dropped from the reaped run.
type backupSummary struct {
	RunID           string  `json:"run_id"`
	State           string  `json:"state"`
	Trigger         string  `json:"trigger,omitempty"`
	StartedTS       string  `json:"started_ts,omitempty"`
	FinishedTS      string  `json:"finished_ts,omitempty"`
	ExpiresTS       string  `json:"expires_ts,omitempty"`
	TimeoutHours    int     `json:"timeout_hours,omitempty"`
	DurationS       int     `json:"duration_s,omitempty"`
	SuccessBool     bool    `json:"success_bool"`
	DiskUsagePerc   float64 `json:"disk_usage_perc,omitempty"`
	DiskUsedMB      int     `json:"disk_used_mb,omitempty"`
	DiskTotalMB     int     `json:"disk_total_mb,omitempty"`
	DiskUncleanBool bool    `json:"disk_unclean_bool,omitempty"`
	TotalMB         int     `json:"total_mb,omitempty"`
	FileCount       int     `json:"file_count,omitempty"`
	SizeMB          int     `json:"size_mb,omitempty"`
	FilesHeld       int     `json:"files_held,omitempty"`
	FilesCreated    int     `json:"files_created,omitempty"`
	FilesDeleted    int     `json:"files_deleted,omitempty"`
	SizeHeldMB      int     `json:"size_held_mb,omitempty"`
	SentMB          int     `json:"sent_mb,omitempty"`
	StagesRun       int     `json:"stages_run,omitempty"`
	StagesFailed    int     `json:"stages_failed,omitempty"`
	StagesHalted    int     `json:"stages_halted,omitempty"`
}

type scrubSummary struct {
	RunID               string  `json:"run_id"`
	State               string  `json:"state"`
	StartedTS           string  `json:"started_ts,omitempty"`
	FinishedTS          string  `json:"finished_ts,omitempty"`
	ExpiresTS           string  `json:"expires_ts,omitempty"`
	DurationS           int     `json:"duration_s,omitempty"`
	SuccessBool         bool    `json:"success_bool"`
	ResumedBool         bool    `json:"resumed_bool,omitempty"`
	ScrubbedMB          int     `json:"scrubbed_mb,omitempty"`
	ProgressPerc        float64 `json:"progress_perc,omitempty"`
	ErrorsFound         int     `json:"errors_found,omitempty"`
	ErrorsCorrected     int     `json:"errors_corrected,omitempty"`
	ErrorsUncorrectable int     `json:"errors_uncorrectable,omitempty"`
	FilesToDelete       string  `json:"files_to_delete,omitempty"`
	FilesToDeleteCount  int     `json:"files_to_delete_count,omitempty"`
	DeviceErrors        int     `json:"device_errors,omitempty"`
	ChunksRelocated     int     `json:"chunks_relocated,omitempty"`
}

type serviceSummary struct {
	RunID       string `json:"run_id"`
	BackupID    string `json:"backup_id,omitempty"`
	State       string `json:"state"`
	StartedTS   string `json:"started_ts,omitempty"`
	FinishedTS  string `json:"finished_ts,omitempty"`
	DurationS   int    `json:"duration_s,omitempty"`
	SuccessBool bool   `json:"success_bool"`
	Kind        string `json:"kind,omitempty"`
	Version     string `json:"version,omitempty"`
	FileCount   int    `json:"file_count,omitempty"`
	SizeMB      int    `json:"size_mb,omitempty"`
}

type backupClusterSummary struct {
	RunID         string `json:"run_id"`
	State         string `json:"state"`
	StartedTS     string `json:"started_ts"`
	FinishedTS    string `json:"finished_ts,omitempty"`
	DurationS     int    `json:"duration_s"`
	SuccessBool   bool   `json:"success_bool"`
	PowerBool     bool   `json:"power_bool"`
	HostsExpected int    `json:"hosts_expected"`
	HostsReported int    `json:"hosts_reported"`
	HostsFailed   int    `json:"hosts_failed"`
	LeaderHost    string `json:"leader_host"`
	LeaderEpoch   int64  `json:"leader_epoch"`
}

func finishRun(root, runID string, started time.Time) backupSummary {
	runPath := backupRunPath(root, runID)
	document := backupSummary{RunID: runID, StartedTS: started.Format(time.RFC3339)}
	states := map[metric.BackupStage]string{}
	for _, stage := range backupStages {
		staged := readBackupSummary(stageStatusPath(runPath, stage))
		if staged == nil {
			continue
		}
		document.StagesRun++
		states[stage] = staged.State
		if document.Trigger == "" {
			document.Trigger = staged.Trigger
		}
		switch staged.State {
		case metric.BackupStateSuccess, metric.BackupStateSkipped:
		case metric.BackupStateStopped, metric.BackupStateTimeout:
			document.StagesHalted++
		default:
			document.StagesFailed++
		}
		document.FileCount += staged.FileCount
		document.SizeMB += staged.SizeMB
		document.FilesCreated += staged.FilesCreated
		document.FilesDeleted += staged.FilesDeleted
		document.SentMB += staged.SentMB
		if stage == metric.BackupStageTertiary {
			document.DiskUsagePerc = staged.DiskUsagePerc
			document.FilesHeld = staged.FilesHeld
			document.SizeHeldMB = staged.SizeHeldMB
		}
	}
	scrubState := ""
	if scrubbed := readScrubSummary(scrubStatusPath(runPath)); scrubbed != nil {
		scrubState = scrubbed.State
	}
	state := resolvedState(states, scrubState)
	if document.StagesRun == 0 {
		state = metric.BackupStateFailure
	}
	document.State = state
	document.FinishedTS = time.Now().Format(time.RFC3339)
	document.DurationS = int(time.Since(started).Seconds())
	document.SuccessBool = state == metric.BackupStateSuccess
	_ = writeAtomic(statusPath(runPath), document)
	return document
}

func resolvedState(stages map[metric.BackupStage]string, scrub string) string {
	for _, stage := range backupStages {
		if stages[stage] == metric.BackupStateRunning {
			return metric.BackupStateRunning
		}
	}
	if scrub == metric.BackupStateRunning {
		return metric.BackupStateRunning
	}
	for _, stage := range backupStages {
		if state, ok := stages[stage]; ok && state != metric.BackupStateSuccess && state != metric.BackupStateSkipped {
			return state
		}
	}
	if scrub != "" && scrub != metric.BackupStateSuccess && scrub != metric.BackupStateSkipped {
		return scrub
	}
	return metric.BackupStateSuccess
}

func writeAtomic(path string, document any) error {
	data, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return err
	}
	temporary := path + ".tmp"
	if err := os.WriteFile(temporary, data, 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func readBackupSummary(path string) *backupSummary { return readSummary[backupSummary](path) }

func readScrubSummary(path string) *scrubSummary { return readSummary[scrubSummary](path) }

func readSummary[T any](path string) *T {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var document T
	if json.Unmarshal(data, &document) != nil {
		return nil
	}
	return &document
}

func backupTerminal(state string) bool {
	return state != "" && state != metric.BackupStateRunning
}

func runStarted(document backupSummary) (time.Time, bool) {
	if started, err := time.ParseInLocation(backupTimestampFormat, document.RunID, time.Local); err == nil {
		return started, true
	}
	started, err := time.Parse(time.RFC3339, document.StartedTS)
	return started, err == nil
}

func reportedForRun(document backupSummary, earliest time.Time) bool {
	started, err := time.Parse(time.RFC3339, document.StartedTS)
	return err == nil && !started.Before(earliest)
}
