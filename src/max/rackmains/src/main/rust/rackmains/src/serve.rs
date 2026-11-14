use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicI32, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use chrono::{DateTime, Local, NaiveDateTime};
use log::{debug, info, warn};
use serde_json::{json, Map, Value};

use crate::broker::{MqttPublisher, Publisher};
use crate::cli::{init_serve_logging, ServeArgs};
use crate::drill::{Marker, Plug, Sampler, Tasmota};
use crate::guard::{Guard, Host, Output};
use crate::liveness::{
    abort_on_stall, boot_ms, watchdog, Effective, Liveness, Progress, FILE_LIVENESS, WATCHDOG_LIMIT, WATCHDOG_TICK,
};
use crate::metrics::{self, Frame, CLOCK, LAST_READ, MODEL_STATE, READ_FAILURES, STATUS};
use crate::model::battery::Request;
use crate::nut::{describe, Flags, Flow, Nut, Reading, Source, SAMPLES};
use crate::outage::{
    self, Stats, Writer, WriterCommand, DIR_OUTAGE, DIR_STATE, END_ABORTED, END_RESTORED, EVENT_COMMAND, EVENT_END,
    EVENT_NOTE, EVENT_START, EVENT_STATUS,
};
use crate::policy::{self, load_model, Loaded, Policy};
use crate::schema::{AVAILABILITY_ONLINE, KEY_PERIOD_MS, KEY_TIMESTAMP};
use crate::shed::{self, load_hosts, DryRun, Finished, Runner, Ssh};
use crate::{check, drill, log_change, log_line, parse_duration, STATE_TOPIC, STATUS_TOPIC};

static STOP_SIGNAL: AtomicI32 = AtomicI32::new(0);
const REPORT_PERIOD: Duration = Duration::from_secs(60);
const REPORT_PERIOD_BATTERY: Duration = Duration::from_secs(1);
const SSH_TIMEOUT_SECONDS: u64 = 30;
const SSH_LIMIT_SECONDS: u64 = 600;

pub struct Settings {
    pub period: Duration,
    pub mains_publish_period: Duration,
    pub data_dir: PathBuf,
    pub run_dir: PathBuf,
    pub outage_keep: usize,
    pub live: bool,
    pub version: String,
    pub battery_installed: String,
    pub ssh_timeout: Duration,
}

pub struct Parts {
    pub source: Box<dyn Source + Send>,
    pub publisher: Box<dyn Publisher + Send>,
    pub runner: Arc<dyn Runner>,
    pub plug: Option<Arc<dyn Plug>>,
    pub loaded: Loaded,
    pub policy: Policy,
    pub hosts: Vec<Host>,
    pub progress: Progress,
}

struct Session {
    started: NaiveDateTime,
    stats: Stats,
    drill: Option<String>,
    on_battery_seen: bool,
    hosts_shed: usize,
}

pub struct Poller {
    settings: Settings,
    source: Box<dyn Source + Send>,
    publisher: Box<dyn Publisher + Send>,
    runner: Arc<dyn Runner>,
    plug: Option<Arc<dyn Plug>>,
    loaded: Loaded,
    hosts: Vec<Host>,
    guard: Guard,
    policy: Policy,
    progress: Progress,
    writer: Writer,
    results: Receiver<Finished>,
    results_sender: Sender<Finished>,
    sampler: Option<Sampler>,
    session: Option<Session>,
    last: Frame,
    last_outage: Frame,
    battery_state: Option<Vec<f64>>,
    state_names: Vec<String>,
    previous: Option<String>,
    flow: Flow,
    published_key: Option<(Option<String>, u32)>,
    since_publish: Duration,
    failures: u32,
    last_read_boot_ms: u64,
    warned: HashSet<String>,
    rejected: Option<String>,
    acked: Option<String>,
    interrupted: Option<String>,
    first: bool,
    publish_failing: bool,
    model_failures: u32,
    read_failures_total: u64,
    report_since: Duration,
}

impl Poller {
    pub fn new(settings: Settings, parts: Parts, now: NaiveDateTime) -> Result<Poller, String> {
        let outage_dir = settings.data_dir.join(DIR_OUTAGE);
        let state_dir = settings.data_dir.join(DIR_STATE);
        for directory in [&outage_dir, &state_dir, &settings.run_dir] {
            fs::create_dir_all(directory)
                .map_err(|err| format!("failed to create [{}] [{err}]", directory.display()))?;
        }
        if !settings.battery_installed.is_empty() {
            metrics::battery_age_days(&settings.battery_installed, Local::now().date_naive())?;
        }
        let mut guard = Guard::new(parts.policy.clone(), settings.live, parts.hosts.clone());
        let open = outage::open_file(&outage_dir);
        let interrupted = open.as_ref().map(|(file, _)| {
            file.path
                .file_name()
                .map_or_else(String::new, |name| name.to_string_lossy().to_string())
        });
        if let Some((clock_battery, clock_mains, shed)) = open.and_then(|(_, table)| outage::clocks(&table, now)) {
            info!(
                "{}",
                log_line(
                    "guard resumed from an unfinished outage file",
                    &format!("{clock_battery:?}")
                )
            );
            guard.resume(clock_battery, clock_mains, shed);
        }
        outage::recover(&outage_dir);
        let last_outage = outage::last_outage(&outage_dir);
        let state_names = parts.loaded.state_names();
        let battery_state = outage::last_model_state(&outage_dir, &parts.loaded.info().content_sha256)
            .and_then(|object| policy::object_to_state(&state_names, &object));
        if battery_state.is_some() {
            info!(
                "{}",
                log_line(
                    "model state seeded from the last outage",
                    &parts.loaded.info().content_sha256
                )
            );
        }
        let writer = Writer::start(outage_dir, settings.outage_keep);
        let (results_sender, results) = mpsc::channel();
        Ok(Poller {
            writer,
            guard,
            policy: parts.policy,
            source: parts.source,
            publisher: parts.publisher,
            runner: parts.runner,
            plug: parts.plug,
            loaded: parts.loaded,
            hosts: parts.hosts,
            progress: parts.progress,
            results,
            results_sender,
            sampler: None,
            session: None,
            last: Frame::default(),
            last_outage,
            battery_state,
            state_names,
            previous: None,
            flow: Flow::default(),
            published_key: None,
            since_publish: Duration::ZERO,
            failures: 0,
            last_read_boot_ms: 0,
            warned: HashSet::new(),
            rejected: None,
            acked: None,
            interrupted,
            first: true,
            publish_failing: false,
            model_failures: 0,
            read_failures_total: 0,
            report_since: Duration::ZERO,
            settings,
        })
    }

    pub fn failures(&self) -> u32 {
        self.failures
    }

    pub fn stop(mut self) {
        self.writer.stop();
        if let Err(err) = self.publisher.close() {
            warn!("{}", log_line("publisher close failed", &err.to_string()));
        }
    }

    // Poller tick flow, one pass per poll
    //     1. Collect Calls: finished shed and wake calls into the guard
    //     2. Read UPS: the driver socket, a failed read only counted
    //     3. Build Frame: samples, flags and status changes
    //     4. Open Session: the first raw OB opens the outage file
    //     5. Match Drill Marker: ack a live marker, reject one mid-outage
    //     6. Step Guard: flags and elapsed time in, calls and rows out
    //     7. Observe Session: hosts shed and the outage statistics
    //     8. End Drill: a marker gone or overrun before the cut, then the last outage summary
    //     9. Call Model: the guard's policy and estimates from the battery model
    //    10. Log Outage Start: one INFO line when a session opens
    //    11. Publish: the retained payload, on battery every poll
    //    12. Record Rows: the CSV rows for the writer thread
    //    13. Finish: close the session, send rows, liveness and progress
    pub fn tick(&mut self, dt: Duration, wall: DateTime<Local>) -> Result<(), String> {
        let stamp = outage::stamp(wall);
        let naive = wall.naive_local();
        let epoch = SystemTime::from(wall)
            .duration_since(SystemTime::UNIX_EPOCH)
            .map_or(0.0, |elapsed| elapsed.as_secs_f64());
        // 1. Collect Calls
        let mut rows: Vec<(&'static str, String)> = Vec::new();
        let mut ended = false;
        while let Ok(finished) = self.results.try_recv() {
            rows.push((
                EVENT_COMMAND,
                format!(
                    "host [{}] command [{}] status [{}] reason [{}] took_ms [{}]",
                    finished.host,
                    finished.command.remote(),
                    finished.outcome.status,
                    finished.outcome.reason,
                    finished.outcome.took.as_millis()
                ),
            ));
            let out = self
                .guard
                .complete(&finished.host, finished.command, finished.outcome.status);
            ended |= self.apply(out, &mut rows);
        }
        // 2. Read UPS
        let reading = match self.source.read() {
            Ok(reading) => {
                if self.failures > 0 {
                    info!(
                        "{}",
                        log_line("ups read recovered after failed reads", &self.failures.to_string())
                    );
                }
                self.failures = 0;
                self.last_read_boot_ms = boot_ms();
                Some(reading)
            }
            Err(err) => {
                self.failures += 1;
                self.read_failures_total += 1;
                warn!(
                    "{}",
                    log_line("ups read failed", &format!("{err} failures {}", self.failures))
                );
                None
            }
        };
        let reading = reading.map(|mut reading| {
            let charge = reading
                .samples
                .iter()
                .find(|(key, _)| *key == metrics::BATTERY_CHARGE_PCT)
                .map(|(_, value)| *value);
            reading.status = reading.status.map(|status| self.flow.settle(&status, charge, dt));
            reading
        });
        // 3. Build Frame
        let mut frame = Frame::default();
        frame.set_number(CLOCK, epoch);
        frame.set_int(READ_FAILURES, i64::from(self.failures));
        let mut flags = None;
        let mut status_change = None;
        let mut pollfreq = None;
        if let Some(reading) = &reading {
            frame.set_number(LAST_READ, epoch);
            self.tick_frame(&mut frame, reading);
            pollfreq.clone_from(&reading.pollfreq);
            if let Some(status) = &reading.status {
                let (parsed, unknown) = Flags::parse(status);
                for token in unknown {
                    if self.warned.insert(token.clone()) {
                        warn!("{}", log_line("unknown ups status token", &token));
                    }
                }
                status_change = self.tick_changes(status);
                flags = Some(parsed);
            }
        }
        // 4. Open Session
        let mut start_detail = None;
        if flags.is_some_and(|flags| flags.raw_on_battery) {
            if self.session.is_none() {
                start_detail = Some(self.open_session(&stamp, naive, None, pollfreq.as_deref()));
            }
            if let Some(session) = &mut self.session {
                session.on_battery_seen = true;
            }
        }
        // 5. Match Drill Marker
        let pending = Marker::read(&self.settings.data_dir.join(DIR_STATE).join(drill::FILE_MARKER)).filter(|marker| {
            marker.live(naive)
                && self.acked.as_deref() != Some(marker.id.as_str())
                && self.rejected.as_deref() != Some(marker.id.as_str())
        });
        if let Some(marker) = pending {
            if self.session.is_none() && !self.guard.in_outage() {
                start_detail = Some(self.open_session(&stamp, naive, Some(&marker), pollfreq.as_deref()));
                self.acked = Some(marker.id);
            } else if self.rejected.as_deref() != Some(marker.id.as_str()) {
                rows.push((
                    EVENT_NOTE,
                    format!("drill [{}] rejected, outage in progress", marker.id),
                ));
                self.rejected = Some(marker.id);
            }
        }
        // 6. Step Guard
        let out = self.guard.step(flags, dt);
        ended |= self.apply(out, &mut rows);
        self.guard.metrics(&mut frame);
        frame.set_int(metrics::GUARD_SHED_BATTERY, self.policy.shed_battery.as_secs() as i64);
        frame.set_int(metrics::GUARD_RESTORE_MAINS, self.policy.restore_mains.as_secs() as i64);
        if let Some(runtime) = self.policy.shed_runtime {
            frame.set_int(metrics::GUARD_SHED_RUNTIME, runtime.as_secs() as i64);
        }
        // 7. Observe Session
        if let Some(session) = &mut self.session {
            session.hosts_shed = session.hosts_shed.max(self.guard.hosts_shed());
            if let Some(flags) = flags {
                session.stats.observe(&frame, flags, &stamp, dt);
            }
        }
        // 8. End Drill
        self.tick_drill_end(naive, &mut ended, &mut rows);
        if let Some(session) = self.session.as_ref().filter(|session| ended && session.on_battery_seen) {
            let mut summary = Frame::default();
            summary.set_int(metrics::LAST_OUTAGE_SECONDS, session.stats.seconds() as i64);
            if let Some(min) = session.stats.min_volts() {
                summary.set_number(metrics::LAST_OUTAGE_MIN_VOLTS, min);
            }
            summary.set_number(metrics::LAST_OUTAGE_END, epoch);
            self.last_outage = summary;
        }
        // 9. Call Model
        let mut published = frame.clone();
        if !self.settings.battery_installed.is_empty() {
            let days = metrics::battery_age_days(&self.settings.battery_installed, wall.date_naive())?;
            published.set_battery_age(days);
        }
        published.merge(&self.last_outage);
        self.last.merge_sticky(&published);
        let battery_state_in = self.battery_state.clone();
        self.tick_model(&mut published, flags.is_some(), epoch, &mut rows);
        self.last.merge_sticky(&published);
        // 10. Log Outage Start
        if start_detail.is_some() {
            let value = |name: &str| {
                published
                    .get(name)
                    .map_or_else(|| "unknown".to_string(), ToString::to_string)
            };
            let status = published.text(STATUS).map_or_else(|| "unknown".to_string(), describe);
            info!(
                "{}",
                log_line(
                    "outage started",
                    &format!(
                        "{status}, load {}%, battery {}V {}%",
                        value(metrics::UTILISATION),
                        value(metrics::BATTERY_VOLTS),
                        value(metrics::BATTERY_CHARGE_PCT)
                    )
                )
            );
            if let Some(id) = self.session.as_ref().and_then(|session| session.drill.as_ref()) {
                info!("{}", log_line("outage drill", id));
            }
        }
        // 11. Publish
        let forced = ended || status_change.is_some();
        self.tick_publish(&published, dt, flags.is_some_and(|flags| flags.raw_on_battery), forced)?;
        // 12. Record Rows
        let mut commands = Vec::new();
        if let Some(session) = &self.session {
            let elapsed = (naive - session.started).num_seconds().max(0) as u64;
            let mut sample = self.last.clone();
            if let Some(sampler) = &self.sampler {
                sampler.fill(&mut sample);
            }
            let (event, detail) = match (&start_detail, &status_change) {
                (Some(detail), _) => {
                    sample_state(&mut sample, &self.state_names, battery_state_in.as_ref());
                    (EVENT_START, detail.clone())
                }
                (None, Some(change)) => (EVENT_STATUS, change.clone()),
                (None, None) => ("", String::new()),
            };
            let sample_row = WriterCommand::Row(outage::row(&stamp, elapsed, event, &detail, &sample));
            let event_rows = rows
                .into_iter()
                .map(|(event, detail)| WriterCommand::Row(outage::row(&stamp, elapsed, event, &detail, &self.last)));
            if start_detail.is_some() {
                commands.push(sample_row);
                commands.extend(event_rows);
            } else {
                commands.extend(event_rows);
                commands.push(sample_row);
            }
            if ended {
                let reason = if session.on_battery_seen {
                    END_RESTORED
                } else {
                    END_ABORTED
                };
                let mut end = self.last.clone();
                sample_state(&mut end, &self.state_names, self.battery_state.as_ref());
                let detail = session.stats.detail(reason, session.hosts_shed);
                info!("{}", log_line("outage ended", &detail));
                commands.push(WriterCommand::Row(outage::row(
                    &stamp, elapsed, EVENT_END, &detail, &end,
                )));
                commands.push(WriterCommand::Close);
            }
        }
        // 13. Finish
        if ended {
            self.session = None;
            self.sampler = None;
        }
        for command in commands {
            self.writer.send(command);
        }
        self.tick_liveness();
        self.progress.tick();
        self.first = false;
        Ok(())
    }

    fn tick_frame(&self, frame: &mut Frame, reading: &Reading) {
        for sample in &SAMPLES {
            if let Some((_, value)) = reading.samples.iter().find(|(key, _)| *key == sample.key) {
                frame.set_number(sample.key, *value);
            }
        }
        if let Some(status) = &reading.status {
            frame.set_text(STATUS, status);
            let flags = Flags::parse(status).0;
            frame.set_bool(metrics::MAINS_PRESENT, !flags.on_battery);
            frame.set_bool(metrics::BATTERY_LOW, flags.low);
            frame.set_bool(metrics::BATTERY_REPLACE, flags.replace);
            frame.set_bool(metrics::BATTERY_CHARGING, flags.charging);
            frame.set_bool(metrics::UPS_PROBLEM, flags.problem);
            frame.set_bool(metrics::UPS_CALIBRATING, flags.calibrating);
            frame.set_bool(metrics::UPS_BOOST, flags.boost);
            frame.set_bool(metrics::UPS_TRIM, flags.trim);
        }
    }

    fn tick_changes(&mut self, status: &str) -> Option<String> {
        let before = self.previous.replace(status.to_string());
        if self.first && before.is_none() {
            info!("{}", log_line("ups status", &describe(status)));
        }
        let before = before.filter(|before| before != status)?;
        let (was, now) = (describe(&before), describe(status));
        info!("{}", log_change("ups status changed", &was, &now));
        Some(format!("from [{was}] to [{now}]"))
    }

    fn apply(&mut self, out: Output, rows: &mut Vec<(&'static str, String)>) -> bool {
        for row in out.rows {
            info!("{}", log_line(&format!("guard {}", row.event), &row.detail));
            rows.push((row.event, row.detail));
        }
        for call in out.calls {
            info!(
                "{}",
                log_line("guard call", &format!("{} {}", call.host, call.command.remote()))
            );
            shed::spawn(&self.runner, &self.hosts, call, &self.results_sender);
        }
        out.ended
    }

    fn open_session(
        &mut self,
        stamp: &str,
        naive: NaiveDateTime,
        marker: Option<&Marker>,
        pollfreq: Option<&str>,
    ) -> String {
        let info = self.loaded.info();
        let mut detail = format!(
            "version [{}] model [{} {}] guard_live [{}] pollfreq [{}]",
            self.settings.version,
            info.name,
            info.content_sha256,
            u8::from(self.settings.live),
            pollfreq.unwrap_or_default()
        );
        let mut extra = Vec::new();
        if let Some(previous) = self.interrupted.take() {
            info!("{}", log_line("outage file closed as interrupted", &previous));
            extra.push(format!("interrupted [{previous}]"));
        }
        if let Some(marker) = marker {
            extra.push(format!("drill [{}] mode [{}]", marker.id, marker.mode));
        }
        if !extra.is_empty() {
            detail = format!("{detail} {}", extra.join(" "));
        }
        self.writer.send(WriterCommand::Open(stamp.to_string()));
        self.session = Some(Session {
            started: naive,
            stats: Stats::default(),
            drill: marker.map(|marker| marker.id.clone()),
            on_battery_seen: false,
            hosts_shed: 0,
        });
        if marker.is_some() {
            if let Some(plug) = &self.plug {
                self.sampler = Some(Sampler::start(Arc::clone(plug)));
            }
        }
        detail
    }

    fn tick_drill_end(&mut self, naive: NaiveDateTime, ended: &mut bool, rows: &mut Vec<(&'static str, String)>) {
        let Some(session) = &self.session else { return };
        let Some(id) = &session.drill else { return };
        if session.on_battery_seen || *ended {
            return;
        }
        let marker = Marker::read(&self.settings.data_dir.join(DIR_STATE).join(drill::FILE_MARKER));
        let gone = marker
            .as_ref()
            .is_none_or(|marker| marker.id != *id || !marker.live(naive));
        let runtime = (naive - session.started).to_std().unwrap_or_default() >= self.policy.restore_mains;
        if gone || runtime {
            rows.push((EVENT_NOTE, format!("drill [{id}] ended before the cut")));
            *ended = true;
        }
    }

    fn tick_model(&mut self, frame: &mut Frame, read_ok: bool, epoch: f64, rows: &mut Vec<(&'static str, String)>) {
        let request = {
            let last = &self.last;
            let Some(utilisation) = last.number(metrics::UTILISATION) else {
                return;
            };
            let known = |name: &str| last.get(name).map(|_| i64::from(last.flag(name)));
            Request {
                clock_epoch_seconds: epoch,
                rackmains_output_load_pct: utilisation as i64,
                rackmains_mains_present: last.get(metrics::MAINS_PRESENT).and_then(Value::as_i64).unwrap_or(1),
                rackmains_ups_calibrating: known(metrics::UPS_CALIBRATING),
                rackmains_battery_low: known(metrics::BATTERY_LOW),
                rackmains_battery_volts: last.number(metrics::BATTERY_VOLTS),
                rackmains_battery_replace_due: known(metrics::BATTERY_REPLACE),
                rackmains_battery_age_days: last.number(metrics::BATTERY_AGE_DAYS).map(|days| days as i64),
                rackmains_read_failures: Some(i64::from(self.failures)),
                rackmains_battery_state_in: self.battery_state.clone(),
            }
        };
        match self.loaded.call(request) {
            Ok(answer) => {
                if self.model_failures > 0 {
                    info!(
                        "{}",
                        log_line(
                            "model call recovered after failed calls",
                            &self.model_failures.to_string()
                        )
                    );
                    self.model_failures = 0;
                }
                if answer.policy != self.policy {
                    for ((name, was), (_, now)) in self.policy.fields().into_iter().zip(answer.policy.fields()) {
                        if was != now {
                            info!("{}", log_change(&format!("guard policy {name} changed"), &was, &now));
                        }
                    }
                    self.guard.set_policy(answer.policy.clone());
                    self.policy = answer.policy;
                }
                self.guard.set_runtime_remaining(answer.estimate.runtime_remaining);
                let response = answer.response;
                if read_ok {
                    if let Some(value) = answer.estimate.energy_remaining_pct {
                        frame.set_int(metrics::BATTERY_ENERGY_REMAINING_PCT, value);
                    }
                    if let Some(value) = answer.estimate.runtime_remaining {
                        frame.set_int(metrics::BATTERY_RUNTIME_REMAINING_SECONDS, value.as_secs() as i64);
                    }
                    if let Some(value) = response.rackmains_battery_energy_used_wh {
                        frame.set_number(metrics::BATTERY_ENERGY_USED_WH, value);
                    }
                    if let Some(value) = response.rackmains_model_refit_due {
                        if value == 1 && !self.last.flag(metrics::MODEL_REFIT_DUE) {
                            warn!("{}", log_line("model refit due", "1"));
                        }
                        frame.set_int(metrics::MODEL_REFIT_DUE, value);
                    }
                    if let Some(value) = response.rackmains_model_refit_reason_code {
                        frame.set_int(metrics::MODEL_REFIT_REASON_CODE, value);
                    }
                }
                if response.rackmains_battery_state_out.is_some() {
                    self.battery_state = response.rackmains_battery_state_out;
                }
            }
            Err(err) => {
                self.guard.set_runtime_remaining(None);
                self.model_failures += 1;
                if self.model_failures == 1 {
                    warn!("{}", log_line("model call failed, keeping last answer", &err));
                } else {
                    debug!("{}", log_line("model call still failing", &err));
                }
                rows.push((EVENT_NOTE, format!("model call failed [{err}]")));
            }
        }
    }

    fn tick_publish(&mut self, frame: &Frame, dt: Duration, on_battery: bool, forced: bool) -> Result<(), String> {
        self.since_publish += dt;
        self.report_since += dt;
        if self.report_since
            >= if on_battery {
                REPORT_PERIOD_BATTERY
            } else {
                REPORT_PERIOD
            }
        {
            self.report_since = Duration::ZERO;
            let shown = |name: &str| {
                self.last.get(name).map_or_else(
                    || "unknown".to_string(),
                    |value| value.as_str().map_or_else(|| value.to_string(), str::to_string),
                )
            };
            let state = self
                .last
                .text(STATUS)
                .filter(|status| !status.is_empty())
                .map_or_else(|| "unknown".to_string(), describe);
            for (label, value) in [
                ("ups read failures", self.read_failures_total.to_string()),
                ("ups state", state),
                ("mains input volts", shown(metrics::MAINS_INPUT_VOLTS)),
                ("output load pct", shown(metrics::UTILISATION)),
                ("battery volts", shown(metrics::BATTERY_VOLTS)),
                ("battery charge pct", shown(metrics::BATTERY_CHARGE_PCT)),
                (
                    "battery remaining",
                    self.last
                        .number(metrics::BATTERY_RUNTIME_REMAINING_SECONDS)
                        .map_or_else(|| "unknown".to_string(), |seconds| format!("{}s", seconds as i64)),
                ),
                ("guard state", shown(metrics::GUARD_STATE)),
            ] {
                info!("{}", log_line(&format!("progress {label}"), &value));
            }
        }
        let key = (frame.text(STATUS).map(str::to_string), self.failures);
        let changed = self.published_key.as_ref() != Some(&key);
        let due = on_battery
            || self.session.is_some()
            || changed
            || forced
            || self.first
            || self.since_publish >= self.settings.mains_publish_period;
        if !due {
            return Ok(());
        }
        self.since_publish = Duration::ZERO;
        self.published_key = Some(key);
        if self.first {
            if let Err(err) = self.publisher.publish(STATUS_TOPIC, AVAILABILITY_ONLINE.as_bytes()) {
                warn!(
                    "{}",
                    log_line("status publish failed", &format!("{STATUS_TOPIC} {err}"))
                );
            }
        }
        let mut payload: Map<String, Value> = Map::new();
        payload.insert(
            KEY_TIMESTAMP.to_string(),
            json!(humantime::format_rfc3339_seconds(SystemTime::now()).to_string()),
        );
        payload.insert(KEY_PERIOD_MS.to_string(), json!(dt.as_millis() as u64));
        payload.extend(frame.payload());
        let bytes = serde_json::to_vec(&payload).map_err(|err| format!("failed to serialize payload [{err}]"))?;
        match self.publisher.publish(STATE_TOPIC, &bytes) {
            Err(err) if !self.publish_failing => {
                self.publish_failing = true;
                if self.session.is_some() {
                    info!(
                        "{}",
                        log_line("publish lost during an outage", &format!("{STATE_TOPIC} {err}"))
                    );
                } else {
                    warn!("{}", log_line("publish lost", &format!("{STATE_TOPIC} {err}")));
                }
            }
            Err(err) => debug!("{}", log_line("publish still lost", &format!("{STATE_TOPIC} {err}"))),
            Ok(()) if self.publish_failing => {
                self.publish_failing = false;
                info!("{}", log_line("publish restored", STATE_TOPIC));
            }
            Ok(()) => {}
        }
        Ok(())
    }

    fn tick_liveness(&self) {
        let liveness = Liveness {
            boot_ms: boot_ms(),
            last_read_boot_ms: self.last_read_boot_ms,
            guard_boot_ms: boot_ms(),
            ups_problem: self.last.flag(metrics::UPS_PROBLEM),
            effective: self.effective(),
        };
        if let Err(err) = liveness.write(&self.settings.run_dir.join(FILE_LIVENESS)) {
            warn!("{}", log_line("liveness write failed", &err));
        }
    }

    fn effective(&self) -> Effective {
        let info = self.loaded.info();
        Effective {
            guard_live: self.settings.live,
            model_name: info.name.clone(),
            model_version: info.release_version.clone().unwrap_or_else(|| "unreleased".to_string()),
            model_hash: info.content_sha256.clone(),
            guard_shed_battery_seconds: self.policy.shed_battery.as_secs(),
            guard_restore_mains_seconds: self.policy.restore_mains.as_secs(),
            poll_s: self.settings.period.as_secs(),
            ssh_timeout_s: self.settings.ssh_timeout.as_secs(),
            shed_order: shed::shed_order(&self.hosts),
        }
    }
}

fn sample_state(frame: &mut Frame, names: &[String], state: Option<&Vec<f64>>) {
    if let Some(state) = state {
        frame.set_text(MODEL_STATE, &policy::state_to_object(names, state).to_string());
    }
}

fn install_signal_handlers() {
    extern "C" fn handler(signal: libc::c_int) {
        STOP_SIGNAL.store(signal, Ordering::SeqCst);
    }
    for signal in [libc::SIGINT, libc::SIGTERM] {
        unsafe {
            libc::signal(signal, handler as extern "C" fn(libc::c_int) as libc::sighandler_t);
        }
    }
}

pub fn run(args: &ServeArgs, data_dir: &Path) -> Result<(), String> {
    let period = parse_duration(&args.poll_period)?;
    init_serve_logging(args, period);
    let common = &args.common;
    let timeout = parse_duration(&common.timeout)?;
    let version = std::env::var("SERVICE_VERSION_ABSOLUTE").unwrap_or_else(|_| "unknown".to_string());
    info!("{}", log_line("version", &version));
    info!("{}", log_line("poll period", &args.poll_period));
    info!("{}", log_line("mains publish period", &args.mains_publish_period));
    info!("{}", log_line("reading device", &common.device));
    if args.battery_installed.is_empty() {
        info!("{}", log_line("battery installed", "none"));
    } else {
        let age = metrics::battery_age_days(&args.battery_installed, Local::now().date_naive())?;
        info!("{}", log_line("battery installed", &args.battery_installed));
        info!("{}", log_line("battery age days", &age.to_string()));
    }
    let (loaded, policy) = load_model(Path::new(&common.model_dir))?;
    let model = loaded.info();
    info!("{}", log_line("model name", &model.name));
    info!("{}", log_line("model flavour", &model.flavour));
    info!(
        "{}",
        log_line(
            "model version",
            model.release_version.as_deref().unwrap_or("unreleased")
        )
    );
    info!("{}", log_line("model hash", &model.content_sha256));
    for (name, value) in policy.fields() {
        info!("{}", log_line(&format!("guard policy {name}"), &value));
    }
    let hosts = load_hosts(Path::new(&common.hosts_file), &common.local_host)?;
    let ssh_timeout = Duration::from_secs(SSH_TIMEOUT_SECONDS);
    if args.live {
        let outcomes = check::run(&check::Target {
            model_dir: Path::new(&common.model_dir),
            hosts_file: Path::new(&common.hosts_file),
            local_host: &common.local_host,
            ssh_key: Path::new(&common.ssh_key),
            known_hosts: Path::new(&common.known_hosts),
            data_dir,
            device: Path::new(&common.device),
            timeout,
        });
        for outcome in &outcomes {
            if let Ok(detail) = &outcome.result {
                info!("{}", log_line(&format!("check {}", outcome.name), detail));
            }
        }
        let failed = check::failed(&outcomes);
        if !failed.is_empty() {
            return Err(format!("live mode refused, check failed [{}]", failed.join(",")));
        }
    }
    let runner: Arc<dyn Runner> = if args.live {
        info!("{}", log_line("guard mode", "live"));
        Arc::new(Ssh {
            key: PathBuf::from(&common.ssh_key),
            known_hosts: PathBuf::from(&common.known_hosts),
            timeout: ssh_timeout,
            limit: Duration::from_secs(SSH_LIMIT_SECONDS),
            log_dir: data_dir.join(DIR_OUTAGE),
        })
    } else {
        info!("{}", log_line("guard mode", "dry-run"));
        Arc::new(DryRun)
    };
    let publisher = MqttPublisher::new(&args.broker_host, args.broker_port, &args.broker_token, STATUS_TOPIC)
        .map_err(|err| err.to_string())?;
    if period.is_zero() {
        publisher
            .wait_connected(Duration::from_secs(30))
            .map_err(|err| err.to_string())?;
    }
    let progress = Progress::default();
    let settings = Settings {
        period,
        mains_publish_period: parse_duration(&args.mains_publish_period)?,
        data_dir: data_dir.to_path_buf(),
        run_dir: PathBuf::from(&common.run_dir),
        outage_keep: args.outage_keep,
        live: args.live,
        version,
        battery_installed: args.battery_installed.clone(),
        ssh_timeout,
    };
    let plug: Option<Arc<dyn Plug>> = (!common.plug_host.is_empty()).then(|| {
        Arc::new(Tasmota {
            host: common.plug_host.clone(),
        }) as Arc<dyn Plug>
    });
    let mut poller = Poller::new(
        settings,
        Parts {
            source: Box::new(Nut::new(PathBuf::from(&common.device), timeout)),
            publisher: Box::new(publisher),
            runner,
            plug,
            loaded,
            policy,
            hosts,
            progress: progress.clone(),
        },
        Local::now().naive_local(),
    )?;
    if !period.is_zero() {
        watchdog("poller", progress, WATCHDOG_LIMIT, WATCHDOG_TICK, abort_on_stall);
    }
    install_signal_handlers();
    let mut last = Instant::now();
    let mut next = last;
    loop {
        let signal = STOP_SIGNAL.load(Ordering::SeqCst);
        if signal != 0 {
            let name = if signal == libc::SIGINT {
                "interrupt"
            } else {
                "terminate"
            };
            info!("{}", log_line("stopping on signal", name));
            poller.stop();
            info!("{}", log_line("stopped", "publisher closed, outage writer flushed"));
            return Ok(());
        }
        let now = Instant::now();
        let dt = if period.is_zero() { Duration::ZERO } else { now - last };
        last = now;
        poller.tick(dt, Local::now())?;
        if period.is_zero() {
            let failed = poller.failures() > 0;
            poller.stop();
            return if failed {
                Err("failed to read device".to_string())
            } else {
                Ok(())
            };
        }
        next += period;
        let after = Instant::now();
        if next <= after {
            warn!(
                "{}",
                log_line("poll overran its period", &format!("{:?}", after - next))
            );
            next = after;
        } else {
            thread::sleep(next - after);
        }
    }
}

#[cfg(test)]
mod tests {
    use std::collections::VecDeque;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Mutex;

    use chrono::TimeZone;

    use super::*;
    use crate::broker;
    use crate::drill::STATE_ARMED;
    use crate::liveness::Effective;
    use crate::nut::{self, Reading};
    use crate::outage::{Table, END_INTERRUPTED};
    use crate::shed::mock::MockRunner;

    type Readings = Arc<Mutex<VecDeque<nut::Result<Reading>>>>;
    type Messages = Arc<Mutex<Vec<(String, Vec<u8>)>>>;

    struct QueueSource(Readings);

    impl Source for QueueSource {
        fn read(&mut self) -> nut::Result<Reading> {
            self.0
                .lock()
                .unwrap()
                .pop_front()
                .unwrap_or_else(|| Err(nut::Error::Read("nothing queued".to_string())))
        }
    }

    struct RecordingPublisher {
        messages: Messages,
        down: Arc<AtomicBool>,
    }

    impl Publisher for RecordingPublisher {
        fn publish(&mut self, topic: &str, payload: &[u8]) -> broker::Result<()> {
            if self.down.load(Ordering::SeqCst) {
                return Err(broker::Error::Mqtt("down".to_string()));
            }
            self.messages
                .lock()
                .unwrap()
                .push((topic.to_string(), payload.to_vec()));
            Ok(())
        }
    }

    struct Rig {
        poller: Poller,
        readings: Readings,
        messages: Messages,
        down: Arc<AtomicBool>,
        runner: Arc<MockRunner>,
        data_dir: PathBuf,
        second: i64,
    }

    fn scratch(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("rackmains-serve-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn reading(status: &str, volts: &str) -> Reading {
        Reading::from_variables([
            ("battery.charge", "100"),
            ("battery.voltage", volts),
            ("input.voltage", "241.4"),
            ("output.voltage", "241.4"),
            ("output.frequency", "50.1"),
            ("ups.load", "13"),
            ("ups.status", status),
            ("driver.parameter.pollfreq", "4"),
        ])
    }

    impl Rig {
        fn new(name: &str) -> Rig {
            Rig::at(&scratch(name), 0)
        }

        fn at(data_dir: &Path, second: i64) -> Rig {
            let model = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../build/resources/model/battery");
            let (loaded, policy) = load_model(&model).unwrap();
            let hosts = ["mad", "max", "may", "meg"]
                .iter()
                .map(|name| Host {
                    name: (*name).to_string(),
                    address: format!("macmini-{name}"),
                    local: *name == "max",
                })
                .collect();
            let readings = Readings::default();
            let messages = Messages::default();
            let down = Arc::new(AtomicBool::new(false));
            let runner = Arc::new(MockRunner::default());
            let poller = Poller::new(
                Settings {
                    period: Duration::from_secs(1),
                    mains_publish_period: Duration::from_secs(5),
                    data_dir: data_dir.to_path_buf(),
                    run_dir: data_dir.join("run"),
                    outage_keep: 100,
                    live: true,
                    version: "test".to_string(),
                    battery_installed: "2024-11-12".to_string(),
                    ssh_timeout: Duration::from_secs(30),
                },
                Parts {
                    source: Box::new(QueueSource(Arc::clone(&readings))),
                    publisher: Box::new(RecordingPublisher {
                        messages: Arc::clone(&messages),
                        down: Arc::clone(&down),
                    }),
                    runner: runner.clone(),
                    plug: None,
                    loaded,
                    policy,
                    hosts,
                    progress: Progress::default(),
                },
                (Local.with_ymd_and_hms(2026, 11, 12, 14, 0, 0).unwrap() + chrono::Duration::seconds(second))
                    .naive_local(),
            )
            .unwrap();
            Rig {
                poller,
                readings,
                messages,
                down,
                runner,
                data_dir: data_dir.to_path_buf(),
                second,
            }
        }

        fn tick(&mut self, status: &str) {
            self.readings.lock().unwrap().push_back(Ok(reading(status, "13.4")));
            self.step();
        }

        fn fail(&mut self) {
            self.readings
                .lock()
                .unwrap()
                .push_back(Err(nut::Error::Read("refused".to_string())));
            self.step();
        }

        fn step(&mut self) {
            let wall = Local.with_ymd_and_hms(2026, 11, 12, 14, 0, 0).unwrap() + chrono::Duration::seconds(self.second);
            self.second += 1;
            self.poller.tick(Duration::from_secs(1), wall).unwrap();
        }

        fn run(&mut self, status: &str, seconds: u32) {
            for _ in 0..seconds {
                self.tick(status);
            }
        }

        fn payloads(&self) -> Vec<Value> {
            self.messages
                .lock()
                .unwrap()
                .iter()
                .filter(|(topic, _)| topic == STATE_TOPIC)
                .map(|(_, payload)| serde_json::from_slice(payload).unwrap())
                .collect()
        }

        fn tables(&self) -> Vec<Table> {
            self.poller.writer.sync();
            outage::files(&self.data_dir.join(DIR_OUTAGE))
                .into_iter()
                .map(|file| Table::read(&file.path).unwrap())
                .collect()
        }

        fn events(&self) -> Vec<(String, String)> {
            self.tables()
                .iter()
                .flat_map(|table| {
                    table
                        .rows
                        .iter()
                        .map(|row| {
                            (
                                table.cell(row, "event").to_string(),
                                table.cell(row, "detail").to_string(),
                            )
                        })
                        .collect::<Vec<_>>()
                })
                .collect()
        }

        fn calls(&self) -> Vec<(String, crate::guard::Command)> {
            let mut seen = self.runner.calls.lock().unwrap().len();
            let mut quiet = Instant::now();
            let waiting = Instant::now();
            while quiet.elapsed() < Duration::from_millis(150) && waiting.elapsed() < Duration::from_secs(10) {
                thread::sleep(Duration::from_millis(10));
                let now = self.runner.calls.lock().unwrap().len();
                if now != seen {
                    seen = now;
                    quiet = Instant::now();
                }
            }
            self.runner.calls.lock().unwrap().clone()
        }
    }

    #[test]
    fn mains_publishes_the_flat_payload_at_once_then_every_period() {
        let mut rig = Rig::new("cadence");
        rig.run("OL", 1);
        let payload = &rig.payloads()[0];
        assert_eq!(payload["rackmains_battery_volts"], 13.4);
        assert_eq!(payload["rackmains_output_load_pct"], 13);
        assert_eq!(payload["rackmains_ups_status"], "OL");
        assert_eq!(payload["rackmains_mains_present"], 1);
        assert!(payload.get("samples").is_none());
        assert!(payload["rackmains_battery_age_days"].as_i64().unwrap() > 0);
        rig.run("OL", 4);
        assert_eq!(rig.payloads().len(), 1);
        rig.run("OL", 1);
        assert_eq!(rig.payloads().len(), 2);
        rig.run("OB DISCHRG", 1);
        assert_eq!(rig.payloads().len(), 3);
        assert_eq!(rig.payloads()[2]["rackmains_mains_present"], 0);
    }

    #[test]
    fn a_failed_read_publishes_the_failure_count_alone_and_opens_no_file() {
        let mut rig = Rig::new("failed");
        rig.run("OL", 1);
        rig.fail();
        let payloads = rig.payloads();
        assert_eq!(payloads[1][READ_FAILURES], 1);
        assert!(payloads[1].get("rackmains_battery_volts").is_none());
        assert!(payloads[1].get("rackmains_mains_present").is_none());
        rig.run("OL", 1);
        assert_eq!(rig.payloads()[2][READ_FAILURES], 0);
        assert!(rig.tables().is_empty());
    }

    #[test]
    fn the_poll_and_the_csv_carry_on_with_the_broker_down() {
        let mut rig = Rig::new("broker-down");
        rig.down.store(true, Ordering::SeqCst);
        rig.run("OB DISCHRG", 3);
        assert!(rig.payloads().is_empty());
        assert_eq!(rig.tables()[0].rows.len(), 3);
        rig.down.store(false, Ordering::SeqCst);
        rig.run("OB DISCHRG", 1);
        assert_eq!(rig.payloads().len(), 1);
    }

    #[test]
    fn an_outage_is_recorded_shed_at_the_shed_time_and_restored_after_stable_mains() {
        let mut rig = Rig::new("outage");
        rig.run("OL", 3);
        rig.run("OB DISCHRG", 119);
        assert!(rig.calls().is_empty());
        rig.run("OB DISCHRG", 3);
        assert_eq!(rig.calls().len(), 4);
        rig.run("OL", 305);
        let calls = rig.calls();
        assert_eq!(calls.len(), 8);
        assert!(calls[4..]
            .iter()
            .all(|(_, command)| *command == crate::guard::Command::Awake));
        let events = rig.events();
        let events: Vec<&str> = events.iter().map(|(event, _)| event.as_str()).collect();
        assert_eq!(events.first(), Some(&"start"));
        assert_eq!(events.last(), Some(&"end"));
        assert_eq!(events.iter().filter(|event| **event == "command").count(), 8);
        assert!(events.contains(&"decision"));
        let tables = rig.tables();
        let table = &tables[0];
        let end = table.rows.last().unwrap();
        assert!(table.cell(end, "detail").contains("reason [restored]"));
        assert!(table.cell(end, "detail").contains("hosts_shed [4]"));
        assert_eq!(table.cell(end, "rackmains_outage_last_duration_seconds"), "122");
        let payloads = rig.payloads();
        assert_eq!(payloads.last().unwrap()["rackmains_outage_last_duration_seconds"], 122);
        assert_eq!(payloads.last().unwrap()["rackmains_guard_state"], "idle");
    }

    #[test]
    fn a_short_dip_records_a_file_without_a_shed() {
        let mut rig = Rig::new("dip");
        rig.run("OB DISCHRG", 5);
        rig.run("OL", 305);
        assert!(rig.calls().is_empty());
        let events = rig.events();
        assert_eq!(events.first().map(|(event, _)| event.as_str()), Some("start"));
        assert_eq!(events.last().map(|(event, _)| event.as_str()), Some("end"));
    }

    #[test]
    fn a_restart_mid_outage_closes_the_file_interrupted_and_names_it_in_the_next() {
        let data_dir = scratch("restart");
        let mut first = Rig::at(&data_dir, 0);
        first.run("OB DISCHRG", 30);
        first.poller.stop();
        let mut second = Rig::at(&data_dir, 31);
        second.run("OB DISCHRG", 2);
        let tables = second.tables();
        assert_eq!(tables.len(), 2);
        let ended = tables[0].rows.last().unwrap();
        assert_eq!(tables[0].cell(ended, "detail"), END_INTERRUPTED);
        let start = &tables[1].rows[0];
        assert!(tables[1]
            .cell(start, "detail")
            .contains("interrupted [rackmains_outage_"));
    }

    #[test]
    fn a_restart_after_a_shed_does_not_shed_again_and_still_wakes_the_hosts() {
        let data_dir = scratch("restart-shed");
        let mut first = Rig::at(&data_dir, 0);
        first.run("OB DISCHRG", 200);
        first.poller.stop();
        let mut second = Rig::at(&data_dir, 201);
        second.run("OB DISCHRG", 1);
        assert!(second.calls().is_empty());
        second.run("OL", 305);
        assert!(second
            .calls()
            .iter()
            .any(|(_, command)| *command == crate::guard::Command::Awake));
    }

    #[test]
    fn the_start_row_is_first_even_when_a_decision_is_made_on_first_sight() {
        let mut rig = Rig::new("start-first");
        rig.run("OB DISCHRG LB", 1);
        let events = rig.events();
        assert_eq!(events[0].0, "start");
        assert!(events.iter().any(|(event, _)| event == "decision"));
    }

    #[test]
    fn a_bouncing_discharge_flag_is_one_status_change_not_a_row_per_bounce() {
        let mut rig = Rig::new("bounce");
        rig.run("OB", 1);
        for _ in 0..5 {
            rig.run("OB DISCHRG", 1);
            rig.run("OB", 1);
        }
        let events = rig.events();
        assert_eq!(events.iter().filter(|(event, _)| event == EVENT_STATUS).count(), 0);
        let payloads = rig.payloads();
        assert!(payloads
            .iter()
            .skip(1)
            .all(|payload| payload["rackmains_ups_status"] == "OB DISCHRG"));
    }

    #[test]
    fn a_status_change_is_a_status_row_and_forces_a_publish() {
        let mut rig = Rig::new("status");
        rig.run("OB DISCHRG", 1);
        rig.run("OB DISCHRG LB", 1);
        let events = rig.events();
        assert!(events.iter().any(|(event, _)| event == EVENT_STATUS));
        assert_eq!(rig.payloads().len(), 2);
    }

    #[test]
    fn liveness_moves_the_read_stamp_only_on_a_good_read() {
        let mut rig = Rig::new("liveness");
        rig.run("OL", 1);
        let path = rig.data_dir.join("run").join(FILE_LIVENESS);
        let first = Liveness::read(&path).unwrap();
        thread::sleep(Duration::from_millis(30));
        rig.fail();
        let after = Liveness::read(&path).unwrap();
        assert_eq!(after.last_read_boot_ms, first.last_read_boot_ms);
        assert!(after.guard_boot_ms >= first.guard_boot_ms);
        thread::sleep(Duration::from_millis(30));
        rig.run("OL", 1);
        assert!(Liveness::read(&path).unwrap().last_read_boot_ms > first.last_read_boot_ms);
        assert_eq!(after.effective.guard_shed_battery_seconds, 120);
        assert_eq!(after.effective.shed_order, vec!["mad", "max", "may", "meg"]);
    }

    fn marker(rig: &Rig, id: &str, state: &str) {
        let now = Local.with_ymd_and_hms(2026, 11, 12, 14, 0, 0).unwrap().naive_local();
        Marker {
            id: id.to_string(),
            mode: drill::MODE_HOLD.to_string(),
            hold_seconds: 240,
            planned_cut: String::new(),
            expires: (now + chrono::Duration::hours(2))
                .format("%Y-%m-%d_%H-%M-%S")
                .to_string(),
            state: state.to_string(),
        }
        .write(&rig.data_dir.join(DIR_STATE).join(drill::FILE_MARKER))
        .unwrap();
    }

    #[test]
    fn a_marker_is_acked_by_opening_a_file_whose_start_row_carries_its_id() {
        let mut rig = Rig::new("marker-ack");
        rig.run("OL", 1);
        marker(&rig, "abc", STATE_ARMED);
        rig.run("OL", 3);
        let events = rig.events();
        assert_eq!(events[0].0, "start");
        assert!(events[0].1.contains("drill [abc] mode [hold]"));
        assert_eq!(events.len(), 3);
    }

    #[test]
    fn a_marker_deleted_before_the_cut_closes_the_file_aborted() {
        let mut rig = Rig::new("marker-abort");
        marker(&rig, "abc", STATE_ARMED);
        rig.run("OL", 3);
        fs::remove_file(rig.data_dir.join(DIR_STATE).join(drill::FILE_MARKER)).unwrap();
        rig.run("OL", 2);
        let events = rig.events();
        assert_eq!(events.last().unwrap().0, "end");
        let tables = rig.tables();
        assert!(tables[0]
            .cell(tables[0].rows.last().unwrap(), "detail")
            .contains("reason [aborted]"));
        assert!(rig
            .payloads()
            .iter()
            .all(|payload| payload.get("rackmains_outage_last_duration_seconds").is_none()));
    }

    #[test]
    fn a_marker_arriving_during_an_outage_is_rejected_with_a_note_and_marks_nothing() {
        let mut rig = Rig::new("marker-late");
        rig.run("OB DISCHRG", 3);
        marker(&rig, "late", STATE_ARMED);
        rig.run("OB DISCHRG", 3);
        let events = rig.events();
        assert!(events
            .iter()
            .any(|(event, detail)| event == EVENT_NOTE && detail.contains("late")));
        assert!(!events[0].1.contains("drill ["));
    }

    #[test]
    fn a_marker_that_is_aborted_or_expired_marks_nothing() {
        let mut rig = Rig::new("marker-dead");
        marker(&rig, "gone", drill::STATE_ABORTED);
        rig.run("OL", 3);
        assert!(rig.tables().is_empty());
    }

    #[test]
    fn a_surviving_marker_is_acked_again_after_a_restart() {
        let data_dir = scratch("marker-restart");
        let mut first = Rig::at(&data_dir, 0);
        marker(&first, "keep", STATE_ARMED);
        first.run("OL", 3);
        first.poller.stop();
        let mut second = Rig::at(&data_dir, 4);
        second.run("OL", 2);
        let tables = second.tables();
        assert_eq!(tables.len(), 2);
        let start = &tables[1].rows[0];
        assert!(tables[1].cell(start, "detail").contains("drill [keep]"));
        assert!(tables[1].cell(start, "detail").contains("interrupted ["));
    }

    struct RigPlug {
        on: Arc<AtomicBool>,
        sent: Mutex<Vec<String>>,
        rule: Mutex<String>,
        refuse: Mutex<Option<&'static str>>,
        panic_on: Mutex<Option<&'static str>>,
    }

    impl Plug for RigPlug {
        fn command(&self, command: &str, _timeout: Duration) -> Result<Value, String> {
            self.sent.lock().unwrap().push(command.to_string());
            if *self.refuse.lock().unwrap() == Some(command) {
                return Err("refused".to_string());
            }
            let mut panic_on = self.panic_on.lock().unwrap();
            if *panic_on == Some(command) {
                panic_on.take();
                drop(panic_on);
                panic!("plug panicked");
            }
            drop(panic_on);
            match command {
                "Power Off" => {
                    self.on.store(false, Ordering::SeqCst);
                    Ok(json!({"POWER": "OFF"}))
                }
                "Power On" => {
                    self.on.store(true, Ordering::SeqCst);
                    Ok(json!({"POWER": "ON"}))
                }
                "Power" => Ok(json!({"POWER": if self.on.load(Ordering::SeqCst) { "ON" } else { "OFF" }})),
                "Rule1" => Ok(json!({"Rule1": {"State": "ON", "Rules": self.rule.lock().unwrap().clone()}})),
                other if other.starts_with("Rule1 ON") => {
                    *self.rule.lock().unwrap() = other.to_string();
                    Ok(json!({}))
                }
                _ => Ok(json!({})),
            }
        }

        fn status(&self, _timeout: Duration) -> Result<drill::PlugReading, String> {
            let on = self.on.load(Ordering::SeqCst);
            Ok(drill::PlugReading {
                power: if on { "ON" } else { "OFF" }.to_string(),
                watts: if on { 90 } else { 0 },
                volts: 241,
                amps: 0.37,
                energy_today_wh: 100,
            })
        }
    }

    struct PlugSource {
        on: Arc<AtomicBool>,
        status: &'static str,
    }

    impl Source for PlugSource {
        fn read(&mut self) -> nut::Result<Reading> {
            Ok(reading(
                if self.on.load(Ordering::SeqCst) {
                    self.status
                } else {
                    "OB DISCHRG"
                },
                "13.4",
            ))
        }
    }

    struct Live {
        env: drill::Env,
        plug: Arc<RigPlug>,
        runner: Arc<MockRunner>,
        stop: Arc<AtomicBool>,
        handle: Option<thread::JoinHandle<()>>,
        dir: PathBuf,
    }

    impl Live {
        fn new(name: &str, status: &'static str, run_poller: bool) -> Live {
            let dir = scratch(name);
            let on = Arc::new(AtomicBool::new(true));
            let plug = Arc::new(RigPlug {
                on: Arc::clone(&on),
                sent: Mutex::new(Vec::new()),
                rule: Mutex::new(String::new()),
                refuse: Mutex::new(None),
                panic_on: Mutex::new(None),
            });
            fs::write(dir.join("hosts.json"), r#"[{"name":"max","address":"macmini-max"}]"#).unwrap();
            let model = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../build/resources/model/battery");
            let (loaded, policy) = load_model(&model).unwrap();
            let runner = Arc::new(MockRunner::default());
            let stop = Arc::new(AtomicBool::new(false));
            let handle = run_poller.then(|| {
                let mut poller = Poller::new(
                    Settings {
                        period: Duration::from_secs(1),
                        mains_publish_period: Duration::from_secs(5),
                        data_dir: dir.clone(),
                        run_dir: dir.join("run"),
                        outage_keep: 100,
                        live: true,
                        version: "test".to_string(),
                        battery_installed: String::new(),
                        ssh_timeout: Duration::from_secs(30),
                    },
                    Parts {
                        source: Box::new(PlugSource {
                            on: Arc::clone(&on),
                            status,
                        }),
                        publisher: Box::new(RecordingPublisher {
                            messages: Messages::default(),
                            down: Arc::new(AtomicBool::new(false)),
                        }),
                        runner: runner.clone(),
                        plug: Some(plug.clone()),
                        loaded,
                        policy,
                        hosts: vec![Host {
                            name: "max".to_string(),
                            address: "macmini-max".to_string(),
                            local: true,
                        }],
                        progress: Progress::default(),
                    },
                    Local::now().naive_local(),
                )
                .unwrap();
                let flag = Arc::clone(&stop);
                thread::spawn(move || {
                    while !flag.load(Ordering::SeqCst) {
                        poller.tick(Duration::from_secs(100), Local::now()).unwrap();
                        thread::sleep(Duration::from_millis(80));
                    }
                    poller.stop();
                })
            });
            let env = drill::Env {
                data_dir: dir.clone(),
                run_dir: dir.join("run"),
                hosts_file: dir.join("hosts.json"),
                local_host: "max".to_string(),
                plug: plug.clone(),
                plug_host: "plug".to_string(),
                timing: drill::Timing {
                    lead_in: Duration::from_secs(1),
                    ack_timeout: Duration::from_secs(10),
                    poll: Duration::from_millis(50),
                    cut_to_battery: Duration::from_secs(30),
                    restore_verify: Duration::from_secs(30),
                    after_cap: Duration::from_secs(60),
                    guard_stale_ms: 120_000,
                },
                clock: || Local::now().naive_local(),
                refuse_in_backup_window: false,
            };
            if run_poller {
                let liveness = dir.join("run").join(FILE_LIVENESS);
                let waiting = std::time::Instant::now();
                while Liveness::read(&liveness).is_err() && waiting.elapsed() < Duration::from_secs(20) {
                    thread::sleep(Duration::from_millis(20));
                }
            }
            Live {
                env,
                plug,
                runner,
                stop,
                handle,
                dir,
            }
        }

        fn sent(&self) -> Vec<String> {
            self.plug.sent.lock().unwrap().clone()
        }

        fn finish(mut self) -> Vec<Table> {
            self.stop.store(true, Ordering::SeqCst);
            if let Some(handle) = self.handle.take() {
                handle.join().unwrap();
            }
            outage::files(&self.dir.join(DIR_OUTAGE))
                .into_iter()
                .map(|file| Table::read(&file.path).unwrap())
                .collect()
        }
    }

    #[test]
    fn a_drill_runs_end_to_end_cut_shed_restore_and_end_row() {
        let live = Live::new("drill-flow", "OL", true);
        drill::run_drill(&live.env, Some("1s"), true).unwrap();
        let sent = live.sent();
        let off = sent.iter().position(|sent| sent == "Power Off").unwrap();
        let arm = sent.iter().position(|sent| sent.starts_with("Rule1 ON")).unwrap();
        assert!(arm < off, "the deadman is armed before the cut");
        assert!(sent[arm].contains("RuleTimer1 301 "));
        assert_eq!(sent[arm + 1], "Rule1 1");
        assert!(sent.iter().rposition(|sent| sent == "Power On").unwrap() > off);
        assert_eq!(sent.last().map(String::as_str), Some("Rule1 0"));
        assert!(live.plug.on.load(Ordering::SeqCst));
        assert!(!live.dir.join(DIR_STATE).join(drill::FILE_MARKER).exists());
        let calls = live.runner.calls.lock().unwrap().clone();
        assert!(calls
            .iter()
            .any(|(_, command)| *command == crate::guard::Command::AsleepShallow));
        assert!(calls
            .iter()
            .any(|(_, command)| *command == crate::guard::Command::Awake));
        let tables = live.finish();
        assert_eq!(tables.len(), 1);
        let table = &tables[0];
        assert!(table.cell(&table.rows[0], "detail").contains("drill ["));
        assert!(table
            .rows
            .iter()
            .any(|row| !table.cell(row, "rackmains_plug_watts").is_empty()));
        assert_eq!(table.cell(table.rows.last().unwrap(), "event"), "end");
        assert!(table
            .cell(table.rows.last().unwrap(), "detail")
            .contains("reason [restored]"));
    }

    #[test]
    fn a_drill_with_no_acknowledgement_cuts_nothing_and_exits_with_the_timeout_code() {
        let mut live = Live::new("drill-noack", "OL", false);
        live.env.timing.ack_timeout = Duration::from_millis(500);
        for name in ["run", DIR_STATE, DIR_OUTAGE] {
            fs::create_dir_all(live.dir.join(name)).unwrap();
        }
        Liveness {
            guard_boot_ms: boot_ms(),
            effective: Effective {
                guard_live: true,
                guard_shed_battery_seconds: 120,
                guard_restore_mains_seconds: 300,
                ..Effective::default()
            },
            ..Liveness::default()
        }
        .write(&live.dir.join("run").join(FILE_LIVENESS))
        .unwrap();
        let error = drill::run_drill(&live.env, Some("1s"), true).unwrap_err();
        assert_eq!(error.code, drill::EXIT_TIMEOUT);
        assert!(!live.sent().iter().any(|sent| sent == "Power Off"));
        assert!(!live.dir.join(DIR_STATE).join(drill::FILE_MARKER).exists());
    }

    #[test]
    fn a_lead_in_that_is_not_ol_refuses_to_cut() {
        let live = Live::new("drill-runtime", "OL OVER", true);
        let error = drill::run_drill(&live.env, Some("1s"), true).unwrap_err();
        assert_eq!(error.code, 1);
        assert!(!live.sent().iter().any(|sent| sent == "Power Off"));
        assert!(!live.sent().iter().any(|sent| sent.starts_with("Rule1 ON")));
        let tables = live.finish();
        assert_eq!(tables.len(), 1);
    }

    #[test]
    fn a_deadman_that_cannot_be_set_is_disarmed_and_nothing_is_cut() {
        let live = Live::new("drill-deadman", "OL", true);
        *live.plug.refuse.lock().unwrap() = Some("Rule1 1");
        let error = drill::run_drill(&live.env, Some("1s"), true).unwrap_err();
        assert_eq!(error.code, 1);
        let sent = live.sent();
        assert!(!sent.iter().any(|sent| sent == "Power Off"));
        assert_eq!(sent.last().map(String::as_str), Some("Rule1 0"));
        live.finish();
    }

    #[test]
    fn a_panic_after_the_cut_still_restores_the_plug() {
        let live = Live::new("drill-panic", "OL", true);
        *live.plug.panic_on.lock().unwrap() = Some("Power Off");
        let error = drill::run_drill(&live.env, Some("1s"), true).unwrap_err();
        assert_eq!(error.code, 1);
        assert!(live.plug.on.load(Ordering::SeqCst));
        assert_eq!(live.sent().last().map(String::as_str), Some("Rule1 0"));
        live.finish();
    }

    #[test]
    fn a_plan_without_force_cuts_nothing() {
        let live = Live::new("drill-plan", "OL", true);
        drill::run_drill(&live.env, None, false).unwrap();
        assert!(live.sent().iter().all(|sent| sent == "Status 0"));
        assert!(live.finish().is_empty());
    }
}
