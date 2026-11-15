use std::fs;
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use chrono::{NaiveDateTime, NaiveTime};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::cli::ExitError;
use crate::liveness::{boot_ms, Effective, Liveness, FILE_LIVENESS};
use crate::metrics::{
    self, Frame, COLUMN_DETAIL, COLUMN_ELAPSED, COLUMN_EVENT, COLUMN_TIME, PLUG_AMPS, PLUG_ENERGY, PLUG_POWER_STATE,
    PLUG_VOLTS, PLUG_WATTS,
};
use crate::nut::{TOKEN_OB, TOKEN_OL};
use crate::outage::{
    self, parse_stamp, write_atomic, OutageFile, Table, DIR_OUTAGE, DIR_STATE, EVENT_COMMAND, EVENT_END, EVENT_START,
};
use crate::report;
use crate::shed::load_hosts;
use crate::{log_change, log_line, say};
use log::Level;

pub const FILE_MARKER: &str = "drill.json";
pub const STATE_ARMED: &str = "armed";
pub const STATE_ABORTED: &str = "aborted";
pub const MODE_BLIP: &str = "blip-watch";
pub const MODE_BROWNOUT: &str = "brownout-shed-wake";
pub const MODE_BLACKOUT: &str = "blackout-shed";
pub const PLUG_PORT: u16 = 80;
pub const PLUG_SAMPLE_TIMEOUT: Duration = Duration::from_millis(500);
pub const PLUG_COMMAND_TIMEOUT: Duration = Duration::from_secs(5);
pub const PLUG_SAMPLE_MAX_AGE: Duration = Duration::from_secs(2);
const PLUG_SAMPLE_PERIOD: Duration = Duration::from_secs(1);
const HTTP_LIMIT_BYTES: u64 = 65_536;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct Marker {
    pub id: String,
    pub mode: String,
    pub hold_seconds: u64,
    pub planned_cut: String,
    pub expires: String,
    pub state: String,
}

impl Marker {
    pub fn read(path: &Path) -> Option<Marker> {
        serde_json::from_slice(&fs::read(path).ok()?).ok()
    }

    pub fn write(&self, path: &Path) -> Result<(), String> {
        let bytes = serde_json::to_vec_pretty(self).map_err(|err| format!("failed to encode marker [{err}]"))?;
        write_atomic(path, &bytes)
    }

    pub fn expired(&self, now: NaiveDateTime) -> bool {
        parse_stamp(&self.expires).is_none_or(|expires| now >= expires)
    }

    pub fn live(&self, now: NaiveDateTime) -> bool {
        self.state == STATE_ARMED && !self.expired(now)
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct PlugReading {
    pub power: String,
    pub watts: i64,
    pub volts: i64,
    pub amps: f64,
    pub energy_today_wh: i64,
}

impl PlugReading {
    pub fn parse(body: &str) -> Option<PlugReading> {
        let value: Value = serde_json::from_str(body).ok()?;
        let energy = &value["StatusSNS"]["ENERGY"];
        Some(PlugReading {
            power: value["StatusSTS"]["POWER"].as_str()?.to_string(),
            watts: energy["Power"].as_f64()?.round() as i64,
            volts: energy["Voltage"].as_f64()?.round() as i64,
            amps: energy["Current"].as_f64()?,
            energy_today_wh: (energy["Today"].as_f64()? * 1000.0).round() as i64,
        })
    }
}

pub trait Plug: Send + Sync {
    fn command(&self, command: &str, timeout: Duration) -> Result<Value, String>;

    fn status(&self, timeout: Duration) -> Result<PlugReading, String> {
        let body = self.command("Status 0", timeout)?;
        PlugReading::parse(&body.to_string()).ok_or_else(|| "plug status not understood".to_string())
    }
}

pub struct Tasmota {
    pub host: String,
}

impl Plug for Tasmota {
    fn command(&self, command: &str, timeout: Duration) -> Result<Value, String> {
        let failed =
            |action: &str, err: &dyn std::fmt::Display| format!("failed to {action} plug [{}] [{err}]", self.host);
        let address = (self.host.as_str(), PLUG_PORT)
            .to_socket_addrs()
            .map_err(|err| failed("resolve", &err))?
            .next()
            .ok_or_else(|| failed("resolve", &"no address"))?;
        let mut stream = TcpStream::connect_timeout(&address, timeout).map_err(|err| failed("connect", &err))?;
        stream
            .set_read_timeout(Some(timeout))
            .map_err(|err| failed("set timeout", &err))?;
        stream
            .set_write_timeout(Some(timeout))
            .map_err(|err| failed("set timeout", &err))?;
        let request = format!(
            "GET /cm?cmnd={} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n",
            command.replace(' ', "%20").replace(';', "%3B"),
            self.host
        );
        stream
            .write_all(request.as_bytes())
            .map_err(|err| failed("write", &err))?;
        let mut response = String::new();
        stream
            .take(HTTP_LIMIT_BYTES)
            .read_to_string(&mut response)
            .map_err(|err| failed("read", &err))?;
        let (head, body) = response
            .split_once("\r\n\r\n")
            .ok_or_else(|| failed("read", &"no body"))?;
        let status_line = head.lines().next().unwrap_or_default();
        if !status_line.starts_with("HTTP/1.") || status_line.split_whitespace().nth(1) != Some("200") {
            return Err(failed("command", &head.lines().next().unwrap_or_default()));
        }
        serde_json::from_str(body).map_err(|err| failed("parse", &err))
    }
}

pub struct Sampler {
    latest: Arc<Mutex<Option<(Instant, PlugReading)>>>,
    stop: Arc<AtomicBool>,
}

impl Sampler {
    pub fn start(plug: Arc<dyn Plug>) -> Sampler {
        let latest = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        {
            let (latest, stop) = (Arc::clone(&latest), Arc::clone(&stop));
            thread::spawn(move || {
                while !stop.load(Ordering::SeqCst) {
                    let started = Instant::now();
                    if let Ok(reading) = plug.status(PLUG_SAMPLE_TIMEOUT) {
                        if let Ok(mut slot) = latest.lock() {
                            *slot = Some((Instant::now(), reading));
                        }
                    }
                    thread::sleep(PLUG_SAMPLE_PERIOD.saturating_sub(started.elapsed()));
                }
            });
        }
        Sampler { latest, stop }
    }

    pub fn fill(&self, frame: &mut Frame) {
        let reading = self.latest.lock().ok().and_then(|slot| {
            slot.as_ref()
                .filter(|(at, _)| at.elapsed() <= PLUG_SAMPLE_MAX_AGE)
                .map(|(_, reading)| reading.clone())
        });
        if let Some(reading) = reading {
            frame.set_text(PLUG_POWER_STATE, &reading.power);
            frame.set_int(PLUG_WATTS, reading.watts);
            frame.set_int(PLUG_VOLTS, reading.volts);
            frame.set_number(PLUG_AMPS, reading.amps);
            frame.set_int(PLUG_ENERGY, reading.energy_today_wh);
        }
    }
}

impl Drop for Sampler {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
    }
}

pub const EXIT_ABORTED: u8 = 7;
pub const EXIT_TIMEOUT: u8 = 4;
pub const LEAD_IN: Duration = Duration::from_secs(60);
pub const LEAD_IN_WATTS_WARN: i64 = 20;
const ABORT_MARGIN_VOLTS: f64 = 0.5;
pub const ACK_TIMEOUT: Duration = Duration::from_secs(10);
pub const GUARD_STALE_MS: u64 = 3000;
pub const AFTER_RESTORE_CAP: Duration = Duration::from_mins(30);
pub const MARKER_MARGIN: Duration = Duration::from_mins(5);
pub const DEADMAN_MARGIN: Duration = Duration::from_mins(5);
pub const DEADMAN_BLACKOUT: Duration = Duration::from_hours(3);
pub const HOLD_PAST_SHED: Duration = Duration::from_secs(120);
pub const HOLD_CEILING: Duration = Duration::from_mins(30);
pub const RECOVER_BEFORE_SHED: u64 = 30;
pub const CUT_TO_BATTERY: Duration = Duration::from_secs(10);
pub const RESTORE_VERIFY: Duration = Duration::from_secs(60);
pub const RECHARGE_WARNING: Duration = Duration::from_hours(6);
const CONNECT_PROBE: Duration = Duration::from_secs(2);
const BACKUP_WINDOW: (u32, u32, u32, u32) = (0, 45, 1, 45);

static SIGNALLED: AtomicBool = AtomicBool::new(false);

#[derive(Clone, Copy, Debug, PartialEq, Eq, clap::ValueEnum)]
pub enum Test {
    #[value(name = "blip-watch", help = "restore before the shed, the guard only watches")]
    Blip,
    #[value(
        name = "brownout-shed-wake",
        help = "hold past the shed, then restore, the guard sheds and wakes"
    )]
    Brownout,
    #[value(
        name = "blackout-shed",
        help = "run to the UPS cutoff and end there, the plug's deadman brings mains back"
    )]
    Blackout,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Target {
    Blip(Duration),
    Brownout(Duration),
    Blackout,
}

pub struct Timing {
    pub lead_in: Duration,
    pub ack_timeout: Duration,
    pub poll: Duration,
    pub cut_to_battery: Duration,
    pub restore_verify: Duration,
    pub after_cap: Duration,
    pub guard_stale_ms: u64,
}

impl Default for Timing {
    fn default() -> Self {
        Timing {
            lead_in: LEAD_IN,
            ack_timeout: ACK_TIMEOUT,
            poll: Duration::from_millis(500),
            cut_to_battery: CUT_TO_BATTERY,
            restore_verify: RESTORE_VERIFY,
            after_cap: AFTER_RESTORE_CAP,
            guard_stale_ms: GUARD_STALE_MS,
        }
    }
}

pub struct Env {
    pub data_dir: PathBuf,
    pub run_dir: PathBuf,
    pub hosts_file: PathBuf,
    pub local_host: String,
    pub plug: Arc<dyn Plug>,
    pub plug_host: String,
    pub timing: Timing,
    pub clock: fn() -> NaiveDateTime,
    pub refuse_in_backup_window: bool,
}

#[derive(Default, Debug, PartialEq, Eq)]
pub struct Preflight {
    pub refusals: Vec<String>,
    pub warnings: Vec<String>,
}

pub struct Assessment {
    pub guard_age_ms: Option<u64>,
    pub guard_stale_ms: u64,
    pub outage_open: bool,
    pub marker_run_open: bool,
    pub plug_reachable: bool,
    pub unreachable_hosts: Vec<String>,
    pub now: NaiveDateTime,
    pub last_outage_end: Option<NaiveDateTime>,
    pub battery_pct: Option<i64>,
    pub guard_live: bool,
    pub refuse_in_backup_window: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum LeadIn {
    Wait,
    Ready,
    Refuse(String),
}

pub fn parse_target(test: Test, hold: Option<&str>, effective: &Effective) -> Result<Target, String> {
    let shed = effective.guard_shed_battery_seconds;
    let parsed = hold
        .map(|raw| {
            crate::parse_duration(raw)
                .map(|hold| hold.as_secs())
                .and_then(|seconds| {
                    if seconds == 0 {
                        Err("hold must be over zero".to_string())
                    } else {
                        Ok(seconds)
                    }
                })
        })
        .transpose()?;
    if let Some(seconds) = parsed.filter(|seconds| *seconds > HOLD_CEILING.as_secs()) {
        return Err(format!(
            "hold [{seconds}s] is over the ceiling [{}s]",
            HOLD_CEILING.as_secs()
        ));
    }
    match test {
        Test::Blackout if parsed.is_some() => Err("blackout-shed runs to the UPS cutoff and takes no hold".to_string()),
        Test::Blackout => Ok(Target::Blackout),
        Test::Blip => {
            let seconds = parsed.unwrap_or(if shed > RECOVER_BEFORE_SHED {
                shed - RECOVER_BEFORE_SHED
            } else {
                shed / 2
            });
            if seconds >= shed {
                return Err(format!(
                    "blip-watch hold [{seconds}s] must be under the shed point [{shed}s]"
                ));
            }
            Ok(Target::Blip(Duration::from_secs(seconds)))
        }
        Test::Brownout => {
            let seconds = parsed.unwrap_or(shed + HOLD_PAST_SHED.as_secs());
            if seconds < shed {
                return Err(format!(
                    "brownout-shed-wake hold [{seconds}s] must be at or over the shed point [{shed}s]"
                ));
            }
            Ok(Target::Brownout(Duration::from_secs(seconds)))
        }
    }
}

fn target_mode(target: &Target) -> &'static str {
    match target {
        Target::Blip(_) => MODE_BLIP,
        Target::Brownout(_) => MODE_BROWNOUT,
        Target::Blackout => MODE_BLACKOUT,
    }
}

fn target_hold(target: &Target) -> Duration {
    match target {
        Target::Blip(hold) | Target::Brownout(hold) => *hold,
        Target::Blackout => Duration::ZERO,
    }
}

pub fn deadman_seconds(target: &Target) -> u64 {
    match target {
        Target::Blip(hold) | Target::Brownout(hold) => (*hold + DEADMAN_MARGIN).as_secs(),
        Target::Blackout => DEADMAN_BLACKOUT.as_secs(),
    }
}

pub fn deadman_command(seconds: u64) -> String {
    format!("Rule1 ON Power1#State=0 DO RuleTimer1 {seconds} ENDON ON Rules#Timer=1 DO Backlog Power1 1; Rule1 0 ENDON")
}

pub fn deadman_armed(reply: &Value, seconds: u64) -> bool {
    let rule = &reply["Rule1"];
    rule["State"].as_str() == Some("ON")
        && rule["Rules"]
            .as_str()
            .is_some_and(|text| text.contains(&format!("RuleTimer1 {seconds} ")))
}

pub fn in_backup_window(now: NaiveDateTime) -> bool {
    let (from_hour, from_minute, to_hour, to_minute) = BACKUP_WINDOW;
    match (
        NaiveTime::from_hms_opt(from_hour, from_minute, 0),
        NaiveTime::from_hms_opt(to_hour, to_minute, 0),
    ) {
        (Some(from), Some(to)) => (from..=to).contains(&now.time()),
        _ => false,
    }
}

pub fn assess(inputs: &Assessment) -> Preflight {
    let mut result = Preflight::default();
    match inputs.guard_age_ms {
        Some(age) if age <= inputs.guard_stale_ms => {}
        Some(age) => result.refusals.push(format!("guard stamp is stale [{age}ms]")),
        None => result.refusals.push("guard liveness is unreadable".to_string()),
    }
    if inputs.outage_open {
        result.refusals.push("an outage is in progress".to_string());
    }
    if inputs.marker_run_open {
        result
            .refusals
            .push("an existing drill marker has a run still open".to_string());
    }
    if !inputs.plug_reachable {
        result.refusals.push("the plug does not answer".to_string());
    }
    if !inputs.unreachable_hosts.is_empty() {
        result
            .refusals
            .push(format!("hosts unreachable [{}]", inputs.unreachable_hosts.join(",")));
    }
    if inputs.refuse_in_backup_window && in_backup_window(inputs.now) {
        result
            .refusals
            .push("inside the 00:45 to 01:45 backup window".to_string());
    }
    if let Some(end) = inputs.last_outage_end {
        if (inputs.now - end).to_std().is_ok_and(|since| since < RECHARGE_WARNING) {
            result
                .warnings
                .push("the last outage ended under 6 hours ago, the battery may not be recharged".to_string());
        }
    }
    if inputs.battery_pct.is_some_and(|pct| pct < 100) {
        result.warnings.push("the battery is not at 100 percent".to_string());
    }
    if !inputs.guard_live {
        result
            .warnings
            .push("the guard is in dry-run, this run proves nothing about the shed".to_string());
    }
    result
}

pub fn plan_lines(
    effective: &Effective,
    target: &Target,
    follow: Option<Duration>,
    assessment: &Preflight,
    plug_host: &str,
) -> Vec<(Level, String)> {
    let hold = target_hold(target).as_secs();
    let shed = effective.guard_shed_battery_seconds;
    let mut lines = vec![
        log_line("drill test", target_mode(target)),
        log_line(
            "drill test goal",
            match target {
                Target::Blip(_) => "restore before the shed, the guard only watches",
                Target::Brownout(_) => "the shed, then restore and awake",
                Target::Blackout => "the shed, then the UPS cutoff, the plug's deadman brings mains back",
            },
        ),
    ];
    if *target != Target::Blackout {
        lines.push(log_line("drill hold", &format!("{hold}s")));
        lines.push(log_line(
            "drill follow",
            &follow.map_or_else(|| "end".to_string(), |follow| format!("{}s", follow.as_secs())),
        ));
    }
    lines.extend([
        log_line(
            "drill restore period",
            &format!("{}s", effective.guard_restore_mains_seconds),
        ),
        log_line("drill deadman", &format!("{}s", deadman_seconds(target))),
        log_line("drill plug host", plug_host),
        log_line("guard live", &u8::from(effective.guard_live).to_string()),
        log_line(
            "guard model",
            &format!("{} {}", effective.model_name, effective.model_version),
        ),
        log_line("guard shed battery seconds", &shed.to_string()),
        log_line(
            "guard restore mains seconds",
            &effective.guard_restore_mains_seconds.to_string(),
        ),
        log_line(
            "guard abort battery volts",
            &effective.guard_abort_battery_volts.to_string(),
        ),
        log_line("guard shed order", &effective.shed_order.join(",")),
        log_line("drill timeline lead-in", &format!("T-{}s", LEAD_IN.as_secs())),
        log_line("drill timeline plug off", "T+0s"),
    ]);
    if matches!(target, Target::Brownout(_) | Target::Blackout) {
        lines.push(log_line("drill timeline shed", &format!("T+{shed}s")));
    }
    match target {
        Target::Blip(hold) | Target::Brownout(hold) => {
            lines.push(log_line("drill timeline plug on", &format!("T+{}s", hold.as_secs())));
            lines.push(log_line(
                "drill timeline awake",
                &format!("T+{}s", hold.as_secs() + effective.guard_restore_mains_seconds),
            ));
        }
        Target::Blackout => lines.push(log_line(
            "drill timeline plug on",
            "after the UPS cutoff, by the deadman",
        )),
    }
    let mut lines: Vec<(Level, String)> = lines.into_iter().map(|line| (Level::Info, line)).collect();
    if !effective.guard_live {
        lines.push((
            Level::Warn,
            log_line(
                "drill warning",
                "the guard is in dry-run, the test proves nothing about the shed",
            ),
        ));
    }
    lines.extend(
        assessment
            .refusals
            .iter()
            .map(|refusal| (Level::Error, log_line("drill refused", refusal))),
    );
    lines.extend(
        assessment
            .warnings
            .iter()
            .map(|warning| (Level::Warn, log_line("drill warning", warning))),
    );
    lines
}

pub fn find_ack(dir: &Path, id: &str) -> Option<(OutageFile, Table)> {
    outage::files(dir).into_iter().rev().find_map(|file| {
        let table = Table::read(&file.path).ok()?;
        let first = table.rows.first()?;
        (table.cell(first, COLUMN_EVENT) == EVENT_START
            && report::field(table.cell(first, COLUMN_DETAIL), "drill") == id)
            .then_some((file, table))
    })
}

#[derive(Debug, PartialEq, Eq)]
pub struct LeadInWindow {
    pub span: u64,
    pub low: i64,
    pub high: i64,
    pub median: i64,
    pub last: i64,
}

pub fn lead_in_window(table: &Table, lead: Duration) -> Option<LeadInWindow> {
    let points: Vec<(f64, i64)> = table
        .rows
        .iter()
        .filter_map(|row| {
            let seconds = table
                .cell(row, metrics::CLOCK)
                .parse::<f64>()
                .or_else(|_| table.cell(row, COLUMN_ELAPSED).parse::<f64>())
                .ok()?;
            Some((seconds, table.cell(row, "rackmains_plug_watts").parse::<i64>().ok()?))
        })
        .collect();
    let (&(start, _), &(end, last)) = (points.first()?, points.last()?);
    let mut recent: Vec<i64> = points
        .iter()
        .filter(|(seconds, _)| end - seconds <= lead.as_secs_f64())
        .map(|(_, watts)| *watts)
        .collect();
    recent.sort_unstable();
    Some(LeadInWindow {
        span: (end - start).floor() as u64,
        low: *recent.first()?,
        high: *recent.last()?,
        median: recent[recent.len() / 2],
        last,
    })
}

pub fn lead_in_verdict(table: &Table, lead: Duration) -> LeadIn {
    let Some(window) = lead_in_window(table, lead) else {
        return LeadIn::Wait;
    };
    let first = table
        .rows
        .iter()
        .position(|row| table.cell(row, "rackmains_plug_watts").parse::<i64>().is_ok())
        .unwrap_or(0);
    let unsteady = |row: &&Vec<String>| {
        let status = table.cell(row, crate::metrics::STATUS);
        let (flags, _) = crate::nut::Flags::parse(status);
        !status.split_whitespace().any(|token| token == TOKEN_OL) || flags.problem
    };
    if let Some(row) = table.rows[first..].iter().find(unsteady) {
        return LeadIn::Refuse(format!(
            "lead-in status [{}] is not steady mains",
            crate::nut::describe(table.cell(row, crate::metrics::STATUS))
        ));
    }
    if window.span >= lead.as_secs() {
        LeadIn::Ready
    } else {
        LeadIn::Wait
    }
}

pub fn held_seconds(table: &Table) -> Option<u64> {
    let seconds = |row: &[String]| table.cell(row, COLUMN_ELAPSED).parse::<u64>().ok();
    let first = table.rows.iter().find(|row| {
        table
            .cell(row, crate::metrics::STATUS)
            .split_whitespace()
            .any(|token| token == TOKEN_OB)
    })?;
    Some(seconds(table.rows.last()?)?.saturating_sub(seconds(first)?))
}

pub fn on_battery_seen(table: &Table) -> bool {
    held_seconds(table).is_some()
}

pub fn battery_volts(table: &Table) -> Option<f64> {
    table
        .rows
        .iter()
        .rev()
        .find_map(|row| table.cell(row, metrics::BATTERY_VOLTS).parse::<f64>().ok())
}

pub fn volts_aborted(table: &Table, abort_volts: f64) -> bool {
    battery_volts(table).is_some_and(|volts| volts <= abort_volts)
}

pub fn low_raised(table: &Table) -> bool {
    table
        .rows
        .iter()
        .any(|row| table.cell(row, metrics::BATTERY_LOW) == "1")
}

pub fn run_drill(env: &Env, test: Test, hold: Option<&str>, follow: Option<&str>, cut: bool) -> Result<(), ExitError> {
    let liveness = Liveness::read(&env.run_dir.join(FILE_LIVENESS))?;
    let target = parse_target(test, hold, &liveness.effective)?;
    let follow = follow
        .map(|raw| {
            crate::parse_duration(raw).and_then(|follow| {
                if follow.is_zero() {
                    Err("follow must be over zero".to_string())
                } else {
                    Ok(follow)
                }
            })
        })
        .transpose()?;
    let outage_dir = env.data_dir.join(DIR_OUTAGE);
    let marker_path = env.data_dir.join(DIR_STATE).join(FILE_MARKER);
    let preflight = assess(&gather(env, &liveness, &outage_dir, &marker_path));
    for (level, line) in plan_lines(&liveness.effective, &target, follow, &preflight, &env.plug_host) {
        say(level, &line);
    }
    if !cut {
        say(
            Level::Info,
            &log_line("drill plan only", "nothing was cut, run start to cut"),
        );
        return Ok(());
    }
    if !preflight.refusals.is_empty() {
        return Err(ExitError::new(1, "preflight refused, nothing was cut"));
    }
    if target == Target::Blackout
        && !confirm_typed(
            "blackout-shed keeps mains off until the UPS cuts its own output and max is cut while running",
            "blackout",
        )?
    {
        return Err(ExitError::new(1, "blackout-shed was not confirmed, nothing was cut"));
    }
    install_signal_handlers();
    let hold = target_hold(&target);
    let now = (env.clock)();
    let marker = Marker {
        id: format!("{}-{}", now.format("%Y%m%d%H%M%S"), std::process::id()),
        mode: target_mode(&target).to_string(),
        hold_seconds: hold.as_secs(),
        planned_cut: now.format("%Y-%m-%d_%H-%M-%S").to_string(),
        expires: (now
            + chrono::Duration::from_std(env.timing.lead_in + hold + env.timing.after_cap + MARKER_MARGIN)
                .unwrap_or_default())
        .format("%Y-%m-%d_%H-%M-%S")
        .to_string(),
        state: STATE_ARMED.to_string(),
    };
    marker.write(&marker_path)?;
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        drive(
            env,
            &target,
            follow,
            liveness.effective.guard_abort_battery_volts,
            &marker,
            &marker_path,
            &outage_dir,
        )
    }))
    .unwrap_or_else(|_| {
        Err(match restore_plug(env.plug.as_ref(), env.timing.poll) {
            Ok(()) => ExitError::new(1, "the drill panicked, mains restored"),
            Err(err) => ExitError::new(1, &err),
        })
    });
    let _ = fs::remove_file(&marker_path);
    result
}

fn stop_state(env: &Env) -> (PathBuf, Option<Marker>, Option<String>) {
    let marker_path = env.data_dir.join(DIR_STATE).join(FILE_MARKER);
    let marker = Marker::read(&marker_path);
    let power = env
        .plug
        .command("Power", PLUG_COMMAND_TIMEOUT)
        .ok()
        .and_then(|reply| reply["POWER"].as_str().map(str::to_string));
    say(
        Level::Info,
        &log_line(
            "drill marker",
            marker.as_ref().map_or("none", |marker| marker.state.as_str()),
        ),
    );
    say(
        Level::Info,
        &log_line("drill plug", power.as_deref().unwrap_or("unreachable")),
    );
    (marker_path, marker, power)
}

fn restore_drill(env: &Env, marker_path: &Path, marker: Option<Marker>) -> Result<(), ExitError> {
    restore_plug(env.plug.as_ref(), env.timing.poll)?;
    if let Some(mut marker) = marker {
        marker.state = STATE_ABORTED.to_string();
        marker.write(marker_path)?;
        let _ = fs::remove_file(marker_path);
    }
    say(Level::Info, &log_change("drill plug", "off", "on"));
    say(
        Level::Info,
        &log_line(
            "drill awake",
            "the main program runs it after the restore period of mains",
        ),
    );
    Ok(())
}

pub fn run_stop(env: &Env, confirm: impl FnOnce(&str, &str) -> Result<bool, String>) -> Result<(), ExitError> {
    let (marker_path, marker, power) = stop_state(env);
    if marker.is_none() {
        match power.as_deref() {
            Some("OFF") => {
                if !confirm("the plug is OFF with no drill running", "on")? {
                    return Err(ExitError::new(
                        1,
                        "turning the plug on was not confirmed, nothing changed",
                    ));
                }
            }
            Some(_) => {
                say(
                    Level::Info,
                    &log_line("drill stop", "no drill is running and the plug is on, nothing changed"),
                );
                return Ok(());
            }
            None => {
                return Err(ExitError::new(
                    1,
                    "no drill is running and the plug is unreachable, nothing changed",
                ))
            }
        }
    }
    restore_drill(env, &marker_path, marker)
}

pub fn restore_plug(plug: &dyn Plug, retry: Duration) -> Result<(), String> {
    let mut last = String::from("not tried");
    for _ in 0..3 {
        match plug.command("Power On", PLUG_COMMAND_TIMEOUT) {
            Ok(_) => match plug.command("Power", PLUG_COMMAND_TIMEOUT) {
                Ok(reply) if reply["POWER"].as_str() == Some("ON") => {
                    let _ = plug.command("Rule1 0", PLUG_COMMAND_TIMEOUT);
                    return Ok(());
                }
                Ok(reply) => last = format!("plug reads [{reply}]"),
                Err(err) => last = err,
            },
            Err(err) => last = err,
        }
        thread::sleep(retry);
    }
    Err(format!(
        "PLUG NOT CONFIRMED ON [{last}], run `rackmains guard drill stop` or curl the plug's Power On and Rule1 0"
    ))
}

fn drive(
    env: &Env,
    target: &Target,
    follow: Option<Duration>,
    abort_volts: f64,
    marker: &Marker,
    marker_path: &Path,
    outage_dir: &Path,
) -> Result<(), ExitError> {
    let timing = &env.timing;
    let (file, _) = wait_for_ack(outage_dir, &marker.id, timing).ok_or_else(|| {
        ExitError::new(
            EXIT_TIMEOUT,
            "the main program did not acknowledge the marker, nothing was cut",
        )
    })?;
    let stem = file.stem.clone();
    let reload = || -> Table { follow_run(outage_dir, &stem) };
    say(
        Level::Info,
        &log_line(
            "drill acknowledged",
            &file
                .path
                .file_name()
                .map_or_else(String::new, |name| name.to_string_lossy().to_string()),
        ),
    );
    let waiting = Instant::now();
    let mut last_span = u64::MAX;
    loop {
        if SIGNALLED.load(Ordering::SeqCst) {
            return Err(abort(env, marker, marker_path, outage_dir, &stem, false));
        }
        let table = reload();
        let window = lead_in_window(&table, timing.lead_in);
        if table.ended() || waiting.elapsed() > timing.lead_in * 3 + timing.ack_timeout {
            let detail = window.as_ref().map_or_else(String::new, |window| {
                format!(" [{}s] of [{}s]", window.span, timing.lead_in.as_secs())
            });
            return Err(ExitError::new(
                EXIT_TIMEOUT,
                &format!("the lead-in never completed{detail}, nothing was cut"),
            ));
        }
        match lead_in_verdict(&table, timing.lead_in) {
            LeadIn::Ready => {
                if let Some(window) = window {
                    say(
                        Level::Info,
                        &log_line("drill lead-in plug watts median", &format!("{}W", window.median)),
                    );
                    say(
                        Level::Info,
                        &log_line(
                            "drill lead-in plug watts range",
                            &format!("{}W to {}W", window.low, window.high),
                        ),
                    );
                    if window.high - window.low > LEAD_IN_WATTS_WARN {
                        say(
                            Level::Warn,
                            &log_line(
                                "drill warning",
                                &format!(
                                    "plug watts moved {}W over {LEAD_IN_WATTS_WARN}W in the last {}s, the baseline is not settled, the cut goes ahead",
                                    window.high - window.low,
                                    timing.lead_in.as_secs()
                                ),
                            ),
                        );
                    }
                }
                break;
            }
            LeadIn::Wait => {
                if let Some(window) = window.filter(|window| window.span != last_span) {
                    last_span = window.span;
                    say(
                        Level::Info,
                        &log_line(
                            "drill lead-in",
                            &format!("{}s of {}s", window.span, timing.lead_in.as_secs()),
                        ),
                    );
                }
            }
            LeadIn::Refuse(reason) => return Err(ExitError::new(1, &format!("{reason}, nothing was cut"))),
        }
        if stale(env) {
            return Err(ExitError::new(
                1,
                "guard stamp went stale during the lead-in, nothing was cut",
            ));
        }
        thread::sleep(timing.poll);
    }
    let seconds = deadman_seconds(target);
    let armed = env
        .plug
        .command(&deadman_command(seconds), PLUG_COMMAND_TIMEOUT)
        .and_then(|_| env.plug.command("Rule1 1", PLUG_COMMAND_TIMEOUT))
        .and_then(|_| env.plug.command("Rule1", PLUG_COMMAND_TIMEOUT));
    let problem = match &armed {
        Ok(reply) if deadman_armed(reply, seconds) => None,
        Ok(_) => Some("the deadman did not read back armed".to_string()),
        Err(err) => Some(format!("the deadman could not be set [{err}]")),
    };
    if let Some(problem) = problem {
        let _ = env.plug.command("Rule1 0", PLUG_COMMAND_TIMEOUT);
        return Err(ExitError::new(1, &format!("{problem}, nothing was cut")));
    }
    say(Level::Info, &log_line("drill deadman armed", &format!("{seconds}s")));
    let off = env.plug.command("Power Off", PLUG_COMMAND_TIMEOUT);
    if off
        .as_ref()
        .map_or(true, |reply| reply["POWER"].as_str() != Some("OFF"))
    {
        restore_plug(env.plug.as_ref(), env.timing.poll)?;
        return Err(ExitError::new(1, "the plug did not read OFF, mains restored"));
    }
    say(Level::Info, &log_change("drill plug", "on", "off"));
    let cut_at = Instant::now();
    let mut printed = reload().rows.len();
    let mut progress = report::Progress::default();
    let mut restored: Option<Instant> = None;
    loop {
        let table = reload();
        for row in table
            .rows
            .iter()
            .skip(printed)
            .filter(|row| table.cell(row, COLUMN_EVENT) != EVENT_END)
        {
            for line in report::row_lines(&table, row, &mut progress) {
                say(Level::Info, &line);
            }
        }
        printed = table.rows.len();
        if SIGNALLED.load(Ordering::SeqCst) {
            return Err(abort(env, marker, marker_path, outage_dir, &stem, true));
        }
        if !on_battery_seen(&table) && cut_at.elapsed() >= timing.cut_to_battery {
            restore_plug(env.plug.as_ref(), env.timing.poll)?;
            return Err(ExitError::new(
                1,
                "no OB within the bound after the cut, mains restored",
            ));
        }
        if table.ended() {
            break;
        }
        if let Target::Blip(hold) | Target::Brownout(hold) = target {
            let volts_low = volts_aborted(&table, abort_volts);
            if restored.is_none()
                && (held_seconds(&table).is_some_and(|held| held >= hold.as_secs()) || low_raised(&table) || volts_low)
            {
                if volts_low {
                    say(
                        Level::Warn,
                        &log_line(
                            "drill abort battery volts",
                            &format!(
                                "{:.1}V at or under {abort_volts:.1}V, restoring mains",
                                battery_volts(&table).unwrap_or_default()
                            ),
                        ),
                    );
                }
                restore_plug(env.plug.as_ref(), env.timing.poll)?;
                say(Level::Info, &log_change("drill plug", "off", "on"));
                restored = Some(Instant::now());
                verify_restored(env, outage_dir, &stem)?;
            }
        }
        if follow_over(restored, follow) {
            say(
                Level::Info,
                &log_line(
                    "drill follow over",
                    &format!("{}s", follow.map_or(0, |follow| follow.as_secs())),
                ),
            );
            say(
                Level::Warn,
                &log_line(
                    "drill run open",
                    &end_row_in(&table).map_or_else(
                        || "the guard writes the end row after the restore period of mains".to_string(),
                        |seconds| format!("the guard writes the end row in about {seconds}s"),
                    ),
                ),
            );
            say(
                Level::Info,
                &log_line("drill run done when", "guard outage list shows the run as restored"),
            );
            break;
        }
        if restored.is_some_and(|at| at.elapsed() > timing.after_cap) {
            return Err(ExitError::new(
                EXIT_TIMEOUT,
                "no end row within the cap after the restore, mains is on",
            ));
        }
        thread::sleep(timing.poll);
    }
    for (level, line) in run_summary(&reload(), target, abort_volts, follow.is_some()) {
        say(level, &line);
    }
    Ok(())
}

pub fn end_row_in(table: &Table) -> Option<u64> {
    let row = table.rows.last()?;
    let restore = table.cell(row, metrics::GUARD_RESTORE_MAINS).parse::<u64>().ok()?;
    let mains = table.cell(row, metrics::GUARD_MAINS_SECONDS).parse::<u64>().ok()?;
    Some(restore.saturating_sub(mains))
}

fn follow_over(restored: Option<Instant>, follow: Option<Duration>) -> bool {
    matches!((restored, follow), (Some(at), Some(limit)) if at.elapsed() >= limit)
}

fn run_detail(table: &Table) -> String {
    if let Some(row) = table.rows.iter().find(|row| table.cell(row, COLUMN_EVENT) == EVENT_END) {
        return table.cell(row, COLUMN_DETAIL).to_string();
    }
    let mut stats = outage::Stats::default();
    for row in &table.rows {
        let mut frame = Frame::default();
        for name in [
            metrics::BATTERY_VOLTS,
            metrics::UTILISATION,
            metrics::BATTERY_CHARGE_PCT,
        ] {
            if let Ok(value) = table.cell(row, name).parse::<f64>() {
                frame.set_number(name, value);
            }
        }
        let (flags, _) = crate::nut::Flags::parse(table.cell(row, metrics::STATUS));
        stats.observe(&frame, flags, table.cell(row, COLUMN_TIME), Duration::from_secs(1));
    }
    let mut shed: Vec<&str> = table
        .rows
        .iter()
        .filter(|row| table.cell(row, COLUMN_EVENT) == EVENT_COMMAND)
        .map(|row| table.cell(row, COLUMN_DETAIL))
        .filter(|command| {
            report::field(command, "command").starts_with("asleep") && report::field(command, "status") == "0"
        })
        .map(|command| report::field(command, "host"))
        .collect();
    shed.sort_unstable();
    shed.dedup();
    stats.detail("open", shed.len())
}

pub fn run_issues(table: &Table, target: &Target, abort_volts: f64, followed: bool) -> Vec<(&'static str, String)> {
    let end = table.rows.iter().find(|row| table.cell(row, COLUMN_EVENT) == EVENT_END);
    let detail = run_detail(table);
    let field = |name: &str| report::field(&detail, name);
    let mut issues = Vec::new();
    match end {
        None if !followed => issues.push(("run open", "the main program finishes it".to_string())),
        Some(_) if field("reason") != "restored" => issues.push(("run ended", format!("reason {}", field("reason")))),
        _ => {}
    }
    let shed = field("hosts_shed").parse::<u64>().unwrap_or(0);
    if shed > 0 && matches!(target, Target::Blip(_)) {
        issues.push(("hosts shed", format!("{shed} during a blip-watch")));
    }
    if let Ok(minimum) = field("battery_min_volts").parse::<f64>() {
        if minimum - abort_volts < ABORT_MARGIN_VOLTS {
            issues.push((
                "volts margin",
                format!(
                    "{:.1}V under the {ABORT_MARGIN_VOLTS:.1}V margin to the abort volts {abort_volts:.1}V",
                    minimum - abort_volts
                ),
            ));
        }
    }
    if field("battery_low") == "1" {
        issues.push(("low battery", "the UPS raised its flag".to_string()));
    }
    for row in table
        .rows
        .iter()
        .filter(|row| table.cell(row, COLUMN_EVENT) == EVENT_COMMAND)
    {
        let command = table.cell(row, COLUMN_DETAIL);
        if report::field(command, "status") != "0" {
            issues.push((
                "host command",
                format!(
                    "{} status {}",
                    report::field(command, "host"),
                    report::field(command, "status")
                ),
            ));
        }
    }
    let samples: Vec<&Vec<String>> = table
        .rows
        .iter()
        .filter(|row| table.cell(row, COLUMN_EVENT).is_empty())
        .collect();
    let missing = samples
        .iter()
        .filter(|row| table.cell(row, PLUG_WATTS).is_empty())
        .count();
    if missing * 100 > samples.len() {
        issues.push(("plug watts", format!("missing on {missing} of {} rows", samples.len())));
    }
    issues
}

pub fn run_summary(table: &Table, target: &Target, abort_volts: f64, followed: bool) -> Vec<(Level, String)> {
    let end = table.rows.iter().find(|row| table.cell(row, COLUMN_EVENT) == EVENT_END);
    let detail = run_detail(table);
    let field = |name: &str| report::field(&detail, name);
    let value = |name: &str, unit: &str| {
        let value = field(name);
        if value.is_empty() {
            "unknown".to_string()
        } else {
            format!("{value}{unit}")
        }
    };
    let mut lines = vec![
        log_line("drill result", if end.is_some() { field("reason") } else { "open" }),
        log_line("drill seconds on battery", &value("seconds_on_battery", "s")),
        log_line("drill battery volts min", &value("battery_min_volts", "V")),
        log_line("drill battery volts min at", &value("battery_min_at", "")),
        log_line("drill battery volts last", &value("battery_last_volts", "V")),
        log_line(
            "drill abort volts margin",
            &field("battery_min_volts").parse::<f64>().map_or_else(
                |_| "unknown".to_string(),
                |minimum| format!("{:.1}V", minimum - abort_volts),
            ),
        ),
        log_line("drill load peak", &value("utilisation_peak_pct", "%")),
        log_line("drill load mean", &value("utilisation_mean_pct", "%")),
        log_change(
            "drill charge",
            &value("charge_start_pct", "%"),
            &value("charge_end_pct", "%"),
        ),
        log_line("drill hosts shed", &value("hosts_shed", "")),
    ]
    .into_iter()
    .map(|line| (Level::Info, line))
    .collect::<Vec<_>>();
    let issues = run_issues(table, target, abort_volts, followed);
    if issues.is_empty() {
        lines.push((Level::Info, log_line("drill issues", "none")));
    }
    lines.extend(
        issues
            .iter()
            .map(|(tag, detail)| (Level::Warn, log_line(&format!("drill issue {tag}"), detail))),
    );
    lines
}

fn abort(env: &Env, marker: &Marker, marker_path: &Path, outage_dir: &Path, stem: &str, cut: bool) -> ExitError {
    say(Level::Warn, &log_line("drill signalled", "restoring mains first"));
    if cut || env.plug.command("Rule1", PLUG_COMMAND_TIMEOUT).is_ok() {
        if let Err(err) = restore_plug(env.plug.as_ref(), env.timing.poll) {
            return ExitError::new(1, &err);
        }
    }
    let mut aborted = marker.clone();
    aborted.state = STATE_ABORTED.to_string();
    let _ = aborted.write(marker_path);
    say(Level::Warn, &log_line("drill aborted", "mains restored"));
    say(
        Level::Info,
        &log_line(
            "drill awake",
            "the main program runs it after the restore period of mains, following until the end row",
        ),
    );
    let started = Instant::now();
    while started.elapsed() < env.timing.after_cap {
        if follow_run(outage_dir, stem).ended() {
            break;
        }
        thread::sleep(env.timing.poll);
    }
    ExitError::new(EXIT_ABORTED, "aborted, mains restored")
}

fn verify_restored(env: &Env, outage_dir: &Path, stem: &str) -> Result<(), ExitError> {
    let started = Instant::now();
    while started.elapsed() < env.timing.restore_verify {
        let table = follow_run(outage_dir, stem);
        if table.rows.last().is_some_and(|row| {
            table
                .cell(row, crate::metrics::STATUS)
                .split_whitespace()
                .all(|token| token != TOKEN_OB)
        }) {
            return Ok(());
        }
        thread::sleep(env.timing.poll);
    }
    let _ = restore_plug(env.plug.as_ref(), env.timing.poll);
    Err(ExitError::new(
        1,
        "OL was not seen after the restore, run `rackmains guard drill stop`",
    ))
}

fn wait_for_ack(outage_dir: &Path, id: &str, timing: &Timing) -> Option<(OutageFile, Table)> {
    let started = Instant::now();
    while started.elapsed() < timing.ack_timeout {
        if let Some(found) = find_ack(outage_dir, id) {
            return Some(found);
        }
        thread::sleep(timing.poll.min(Duration::from_millis(250)));
    }
    None
}

fn follow_run(outage_dir: &Path, stem: &str) -> Table {
    let mut merged = Table::default();
    for part in outage::files(outage_dir).into_iter().filter(|part| part.stem == stem) {
        if let Ok(table) = Table::read(&part.path) {
            merged.header = table.header;
            merged.rows.extend(table.rows);
        }
    }
    merged
}

fn stale(env: &Env) -> bool {
    Liveness::read(&env.run_dir.join(FILE_LIVENESS)).map_or(true, |liveness| {
        boot_ms().saturating_sub(liveness.guard_boot_ms) > env.timing.guard_stale_ms
    })
}

fn gather(env: &Env, liveness: &Liveness, outage_dir: &Path, marker_path: &Path) -> Assessment {
    let now = (env.clock)();
    let newest = outage::files(outage_dir)
        .into_iter()
        .last()
        .and_then(|file| Table::read(&file.path).ok());
    let last_end = outage::files(outage_dir).into_iter().rev().find_map(|file| {
        let table = Table::read(&file.path).ok()?;
        let last = table.rows.last().filter(|_| table.ended())?;
        parse_stamp(table.cell(last, COLUMN_TIME))
    });
    let marker_run_open = Marker::read(marker_path).is_some_and(|marker| {
        marker.live(now)
            && find_ack(outage_dir, &marker.id).is_some_and(|(file, _)| !follow_run(outage_dir, &file.stem).ended())
    });
    let unreachable_hosts = load_hosts(&env.hosts_file, &env.local_host).map_or_else(
        |_| vec!["hosts file".to_string()],
        |hosts| {
            hosts
                .into_iter()
                .filter(|host| !host.local)
                .filter(|host| {
                    (host.address.as_str(), 22u16)
                        .to_socket_addrs()
                        .ok()
                        .and_then(|mut addresses| addresses.next())
                        .is_none_or(|address| TcpStream::connect_timeout(&address, CONNECT_PROBE).is_err())
                })
                .map(|host| host.name)
                .collect()
        },
    );
    Assessment {
        guard_stale_ms: env.timing.guard_stale_ms,
        guard_age_ms: Liveness::read(&env.run_dir.join(FILE_LIVENESS))
            .ok()
            .map(|live| boot_ms().saturating_sub(live.guard_boot_ms)),
        outage_open: newest
            .as_ref()
            .is_some_and(|table| !table.ended() && on_battery_seen(table)),
        marker_run_open,
        plug_reachable: env.plug.status(PLUG_COMMAND_TIMEOUT).is_ok(),
        unreachable_hosts,
        now,
        last_outage_end: last_end,
        battery_pct: newest.as_ref().and_then(|table| {
            table
                .rows
                .last()
                .and_then(|row| table.cell(row, metrics::BATTERY_CHARGE_PCT).parse().ok())
        }),
        guard_live: liveness.effective.guard_live,
        refuse_in_backup_window: env.refuse_in_backup_window,
    }
}

pub fn confirm_typed(prompt: &str, word: &str) -> Result<bool, String> {
    say(
        Level::Warn,
        &log_line("drill confirm", &format!("{prompt}, type {word} to continue")),
    );
    let mut line = String::new();
    std::io::stdin()
        .read_line(&mut line)
        .map_err(|err| format!("failed to read confirmation [{err}]"))?;
    Ok(line.trim() == word)
}

fn install_signal_handlers() {
    extern "C" fn handler(_: libc::c_int) {
        SIGNALLED.store(true, Ordering::SeqCst);
    }
    for signal in [libc::SIGINT, libc::SIGTERM, libc::SIGHUP] {
        unsafe {
            libc::signal(signal, handler as extern "C" fn(libc::c_int) as libc::sighandler_t);
        }
    }
}

#[cfg(test)]
pub mod mock {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Mutex;

    use super::*;

    #[derive(Default)]
    pub struct MockPlug {
        pub reachable: bool,
        pub off: AtomicBool,
        pub sent: Mutex<Vec<String>>,
        pub reading: Option<PlugReading>,
    }

    impl Plug for MockPlug {
        fn command(&self, command: &str, _timeout: Duration) -> Result<Value, String> {
            if !self.reachable {
                return Err("unreachable".to_string());
            }
            self.sent.lock().unwrap().push(command.to_string());
            if command == "Power On" {
                self.off.store(false, Ordering::SeqCst);
            }
            Ok(serde_json::json!({"POWER": if self.off.load(Ordering::SeqCst) { "OFF" } else { "ON" }}))
        }

        fn status(&self, _timeout: Duration) -> Result<PlugReading, String> {
            self.reading
                .clone()
                .filter(|_| self.reachable)
                .ok_or_else(|| "unreachable".to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const STATUS: &str = r#"{"StatusSTS":{"POWER":"ON"},"StatusSNS":{"ENERGY":{"Today":0.512,"Voltage":241,"Current":0.371,"Power":89.6}}}"#;

    fn marker(expires: &str, state: &str) -> Marker {
        Marker {
            id: "a".to_string(),
            mode: MODE_BROWNOUT.to_string(),
            hold_seconds: 240,
            planned_cut: "2026-01-01_00-00-00".to_string(),
            expires: expires.to_string(),
            state: state.to_string(),
        }
    }

    fn effective() -> Effective {
        Effective {
            guard_live: true,
            guard_shed_battery_seconds: 120,
            guard_restore_mains_seconds: 300,
            guard_abort_battery_volts: 11.5,
            ..Effective::default()
        }
    }

    fn at(stamp: &str) -> NaiveDateTime {
        parse_stamp(stamp).unwrap()
    }

    fn assessment() -> Assessment {
        Assessment {
            guard_age_ms: Some(500),
            guard_stale_ms: GUARD_STALE_MS,
            outage_open: false,
            marker_run_open: false,
            plug_reachable: true,
            unreachable_hosts: Vec::new(),
            now: at("2026-01-01_12-00-00"),
            last_outage_end: None,
            battery_pct: Some(100),
            guard_live: true,
            refuse_in_backup_window: true,
        }
    }

    fn csv(rows: &[(&str, &str, &str, &str)]) -> Table {
        let mut text = outage::encode_row(&crate::metrics::header());
        text.push('\n');
        for (elapsed, status, watts, event) in rows {
            let mut frame = Frame::default();
            frame.set_text(crate::metrics::STATUS, status);
            if !watts.is_empty() {
                frame.set_int(PLUG_WATTS, watts.parse().unwrap());
            }
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_12-00-00",
                elapsed.parse().unwrap(),
                event,
                "",
                &frame,
            )));
            text.push('\n');
        }
        Table::parse(&text)
    }

    #[test]
    fn each_test_defaults_to_its_side_of_the_shed_point_and_refuses_the_other() {
        let target = |test, hold| parse_target(test, hold, &effective());
        assert_eq!(
            target(Test::Brownout, None),
            Ok(Target::Brownout(Duration::from_secs(240)))
        );
        assert_eq!(
            target(Test::Brownout, Some("120s")),
            Ok(Target::Brownout(Duration::from_secs(120)))
        );
        assert!(target(Test::Brownout, Some("119s")).is_err());
        assert_eq!(target(Test::Blip, None), Ok(Target::Blip(Duration::from_secs(90))));
        assert_eq!(
            target(Test::Blip, Some("119s")),
            Ok(Target::Blip(Duration::from_secs(119)))
        );
        assert!(target(Test::Blip, Some("120s")).is_err());
        assert_eq!(target(Test::Blackout, None), Ok(Target::Blackout));
        assert!(target(Test::Blackout, Some("5m")).is_err());
        assert!(target(Test::Brownout, Some("0")).is_err());
        assert!(target(Test::Brownout, Some("30m")).is_ok());
        assert!(target(Test::Brownout, Some("31m")).is_err());
        assert!(target(Test::Blip, Some("soon")).is_err());
    }

    #[test]
    fn the_deadman_outlasts_the_hold_and_a_blackout_gets_three_hours() {
        assert_eq!(deadman_seconds(&Target::Brownout(Duration::from_secs(240))), 540);
        assert_eq!(deadman_seconds(&Target::Blackout), 10_800);
        assert!(deadman_command(540).contains("RuleTimer1 540 ENDON"));
        assert!(deadman_command(540).contains("Power1 1; Rule1 0"));
    }

    #[test]
    fn the_deadman_reads_back_armed_only_with_the_rule_on_and_the_right_timer() {
        let reply = |state: &str, seconds: u64| serde_json::json!({"Rule1": {"State": state, "Rules": deadman_command(seconds)}});
        assert!(deadman_armed(&reply("ON", 540), 540));
        assert!(!deadman_armed(&reply("OFF", 540), 540));
        assert!(!deadman_armed(&reply("ON", 300), 540));
        assert!(!deadman_armed(&serde_json::json!({}), 540));
    }

    #[test]
    fn the_backup_window_is_a_fixed_hour() {
        for (stamp, inside) in [
            ("2026-01-01_00-44-59", false),
            ("2026-01-01_00-45-00", true),
            ("2026-01-01_01-00-00", true),
            ("2026-01-01_01-45-00", true),
            ("2026-01-01_01-45-01", false),
            ("2026-01-01_12-00-00", false),
        ] {
            assert_eq!(in_backup_window(at(stamp)), inside, "stamp [{stamp}]");
        }
    }

    #[test]
    fn preflight_refuses_on_each_hard_condition_and_only_warns_on_the_soft_ones() {
        assert_eq!(assess(&assessment()), Preflight::default());
        for (name, change) in [
            (
                "stale guard",
                Assessment {
                    guard_age_ms: Some(3001),
                    ..assessment()
                },
            ),
            (
                "no liveness",
                Assessment {
                    guard_age_ms: None,
                    ..assessment()
                },
            ),
            (
                "outage",
                Assessment {
                    outage_open: true,
                    ..assessment()
                },
            ),
            (
                "open marker",
                Assessment {
                    marker_run_open: true,
                    ..assessment()
                },
            ),
            (
                "plug",
                Assessment {
                    plug_reachable: false,
                    ..assessment()
                },
            ),
            (
                "host",
                Assessment {
                    unreachable_hosts: vec!["may".to_string()],
                    ..assessment()
                },
            ),
            (
                "backup",
                Assessment {
                    now: at("2026-01-01_01-00-00"),
                    ..assessment()
                },
            ),
        ] {
            let result = assess(&change);
            assert_eq!(result.refusals.len(), 1, "case [{name}]");
        }
        for (name, change) in [
            (
                "recent outage",
                Assessment {
                    last_outage_end: Some(at("2026-01-01_08-00-00")),
                    ..assessment()
                },
            ),
            (
                "battery",
                Assessment {
                    battery_pct: Some(80),
                    ..assessment()
                },
            ),
            (
                "dry-run",
                Assessment {
                    guard_live: false,
                    ..assessment()
                },
            ),
        ] {
            let result = assess(&change);
            assert!(result.refusals.is_empty(), "case [{name}]");
            assert_eq!(result.warnings.len(), 1, "case [{name}]");
        }
        let old = Assessment {
            last_outage_end: Some(at("2025-12-31_08-00-00")),
            ..assessment()
        };
        assert!(assess(&old).warnings.is_empty());
    }

    #[test]
    fn the_plan_names_its_test_and_warns_when_the_guard_is_dry() {
        let plan = |target: Target, live: bool| {
            let mut effective = effective();
            effective.guard_live = live;
            plan_lines(&effective, &target, None, &Preflight::default(), "plug")
                .into_iter()
                .map(|(level, line)| format!("{level} {line}"))
                .collect::<Vec<_>>()
                .join("\n")
        };
        let brownout = || Target::Brownout(Duration::from_secs(240));
        assert!(plan(brownout(), false).contains("WARN drill warning") && plan(brownout(), false).contains("dry-run"));
        assert!(!plan(brownout(), true).contains("dry-run"));
        assert!(plan(brownout(), true).contains("drill timeline shed ") && plan(brownout(), true).contains("[T+120s]"));
        assert!(plan(brownout(), true).contains("restore and awake"));
        assert!(plan(Target::Blip(Duration::from_secs(60)), true).contains("only watches"));
        assert!(!plan(Target::Blip(Duration::from_secs(60)), true).contains("timeline shed"));
        assert!(plan(Target::Blackout, true).contains("UPS cutoff"));
        assert!(!plan(Target::Blackout, true).contains("drill hold"));
        let refused = Preflight {
            refusals: vec!["why".to_string()],
            warnings: Vec::new(),
        };
        let lines = plan_lines(&effective(), &Target::Blackout, None, &refused, "plug");
        assert!(lines
            .iter()
            .any(|(level, line)| *level == Level::Error && line.contains("drill refused") && line.contains("[why]")));
    }

    #[test]
    fn the_lead_in_counts_exact_seconds_from_the_clock_when_the_elapsed_column_jitters() {
        let mut text = outage::encode_row(&crate::metrics::header());
        text.push('\n');
        for (elapsed, clock) in [
            (0u64, 1000.0),
            (1, 1001.0),
            (2, 1002.0),
            (2, 1003.0),
            (3, 1004.0),
            (4, 1005.0),
        ] {
            let mut frame = Frame::default();
            frame.set_number(crate::metrics::CLOCK, clock);
            frame.set_int(PLUG_WATTS, 90);
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_12-00-00",
                elapsed,
                "",
                "",
                &frame,
            )));
            text.push('\n');
        }
        let window = lead_in_window(&Table::parse(&text), Duration::from_secs(60)).unwrap();
        assert_eq!(window.span, 5);
    }

    #[test]
    fn the_lead_in_needs_a_minute_of_ol_and_only_reports_the_plug_watts() {
        let lead = Duration::from_secs(60);
        let series = |points: &[(u64, i64)], status: &str| {
            let rows: Vec<(String, String, String, String)> = points
                .iter()
                .map(|(seconds, watts)| {
                    (
                        seconds.to_string(),
                        status.to_string(),
                        watts.to_string(),
                        String::new(),
                    )
                })
                .collect();
            let borrowed: Vec<(&str, &str, &str, &str)> = rows
                .iter()
                .map(|(a, b, c, d)| (a.as_str(), b.as_str(), c.as_str(), d.as_str()))
                .collect();
            csv(&borrowed)
        };
        let table = |points: &[(u64, i64)]| series(points, "OL");
        assert_eq!(
            lead_in_verdict(&csv(&[("0", "OL", "", "start"), ("1", "OL", "", "")]), lead),
            LeadIn::Wait
        );
        assert_eq!(lead_in_verdict(&table(&[(1, 90), (30, 91)]), lead), LeadIn::Wait);
        assert_eq!(lead_in_verdict(&table(&[(1, 90), (61, 92)]), lead), LeadIn::Ready);
        assert_eq!(
            lead_in_verdict(&table(&[(1, 90), (30, 200), (61, 90)]), lead),
            LeadIn::Ready
        );
        assert_eq!(
            lead_in_window(&table(&[(1, 90), (5, 110), (6, 88), (30, 91)]), lead),
            Some(LeadInWindow {
                span: 29,
                low: 88,
                high: 110,
                median: 91,
                last: 91
            })
        );
        assert_eq!(
            lead_in_window(&table(&[(1, 300), (70, 90), (100, 92)]), lead),
            Some(LeadInWindow {
                span: 99,
                low: 90,
                high: 92,
                median: 92,
                last: 92
            })
        );
        assert!(matches!(
            lead_in_verdict(&series(&[(1, 90), (61, 90)], "OL OVER"), lead),
            LeadIn::Refuse(_)
        ));
        assert_eq!(
            lead_in_verdict(&series(&[(1, 90), (61, 90)], "OL CHRG BOOST"), lead),
            LeadIn::Ready
        );
        assert!(matches!(
            lead_in_verdict(&csv(&[("1", "OB", "90", "")]), lead),
            LeadIn::Refuse(_)
        ));
    }

    #[test]
    fn a_run_reports_what_went_wrong_and_nothing_when_it_went_well() {
        let table = |end: Option<&str>, commands: &[&str], samples: &[Option<i64>]| {
            let mut text = outage::encode_row(&crate::metrics::header());
            text.push('\n');
            let mut line = |event: &str, detail: &str, watts: Option<i64>| {
                let mut frame = Frame::default();
                if let Some(watts) = watts {
                    frame.set_int(PLUG_WATTS, watts);
                }
                text.push_str(&outage::encode_row(&outage::row(
                    "2026-01-01_12-00-00",
                    0,
                    event,
                    detail,
                    &frame,
                )));
                text.push('\n');
            };
            for watts in samples {
                line("", "", *watts);
            }
            for command in commands {
                line(EVENT_COMMAND, command, None);
            }
            if let Some(end) = end {
                line(EVENT_END, end, None);
            }
            Table::parse(&text)
        };
        let good = "reason [restored] seconds_on_battery [113] battery_min_volts [12.0] hosts_shed [0] battery_low [0]";
        let blip = Target::Blip(Duration::from_secs(110));
        let ok = [Some(90), Some(91)];
        assert!(run_issues(&table(Some(good), &[], &ok), &blip, 11.5, false).is_empty());
        assert_eq!(run_issues(&table(None, &[], &ok), &blip, 11.5, false).len(), 1);
        assert!(run_issues(&table(None, &[], &ok), &blip, 11.5, true).is_empty());
        let aborted = "reason [aborted] battery_min_volts [12.0] hosts_shed [0]";
        assert_eq!(run_issues(&table(Some(aborted), &[], &ok), &blip, 11.5, false).len(), 1);
        let shed = "reason [restored] battery_min_volts [12.0] hosts_shed [2]";
        assert_eq!(run_issues(&table(Some(shed), &[], &ok), &blip, 11.5, false).len(), 1);
        assert!(run_issues(
            &table(Some(shed), &[], &ok),
            &Target::Brownout(Duration::from_secs(240)),
            11.5,
            false
        )
        .is_empty());
        let close = "reason [restored] battery_min_volts [11.8] hosts_shed [0]";
        assert_eq!(run_issues(&table(Some(close), &[], &ok), &blip, 11.5, false).len(), 1);
        let edge = "reason [restored] battery_min_volts [12.0] hosts_shed [0]";
        assert!(run_issues(&table(Some(edge), &[], &ok), &blip, 11.5, false).is_empty());
        let low = "reason [restored] battery_min_volts [12.0] hosts_shed [0] battery_low [1]";
        assert_eq!(run_issues(&table(Some(low), &[], &ok), &blip, 11.5, false).len(), 1);
        let failed = [
            "host [max] command [asleep] status [5] reason []",
            "host [may] command [awake] status [0] reason []",
        ];
        assert_eq!(
            run_issues(&table(Some(good), &failed, &ok), &blip, 11.5, false).len(),
            1
        );
        assert_eq!(
            run_issues(&table(Some(good), &[], &[Some(90), None, Some(91)]), &blip, 11.5, false).len(),
            1
        );
        let mostly: Vec<Option<i64>> = std::iter::once(None).chain(std::iter::repeat_n(Some(90), 49)).collect();
        assert_eq!(
            run_issues(&table(Some(good), &[], &mostly), &blip, 11.5, false).len(),
            1
        );
        let rarely: Vec<Option<i64>> = std::iter::once(None)
            .chain(std::iter::repeat_n(Some(90), 120))
            .collect();
        assert!(run_issues(&table(Some(good), &[], &rarely), &blip, 11.5, false).is_empty());
        let summary = run_summary(&table(Some(good), &[], &ok), &blip, 11.5, false);
        assert!(summary.iter().any(|(_, line)| line.contains("drill issues")));
        assert!(!summary.iter().any(|(level, _)| *level == Level::Warn));
        assert!(run_summary(&table(None, &[], &ok), &blip, 11.5, true)
            .iter()
            .any(|(_, line)| line.contains("drill result") && line.contains("[open]")));
        let warned = run_summary(&table(Some(close), &[], &ok), &blip, 11.5, false);
        assert!(warned.iter().any(|(level, line)| *level == Level::Warn
            && line.contains("drill issue volts margin")
            && line.contains("[0.3V")));
    }

    #[test]
    fn a_run_still_open_is_summarised_from_its_rows() {
        let mut text = outage::encode_row(&crate::metrics::header());
        text.push('\n');
        for (status, volts, load, charge) in [
            ("OL", 13.3, 10.0, 100.0),
            ("OB DISCHRG", 12.0, 13.0, 62.0),
            ("OB DISCHRG", 11.8, 17.0, 58.0),
            ("OB DISCHRG", 12.0, 13.0, 62.0),
            ("OL CHRG", 12.5, 10.0, 81.0),
        ] {
            let mut frame = Frame::default();
            frame.set_text(crate::metrics::STATUS, status);
            frame.set_number(crate::metrics::BATTERY_VOLTS, volts);
            frame.set_number(crate::metrics::UTILISATION, load);
            frame.set_number(crate::metrics::BATTERY_CHARGE_PCT, charge);
            frame.set_int(PLUG_WATTS, 90);
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_12-00-00",
                0,
                "",
                "",
                &frame,
            )));
            text.push('\n');
        }
        let table = Table::parse(&text);
        let detail = run_detail(&table);
        for part in [
            "seconds_on_battery [3]",
            "battery_min_volts [11.8]",
            "battery_last_volts [12]",
            "utilisation_peak_pct [17]",
            "charge_start_pct [100]",
            "charge_end_pct [62]",
        ] {
            assert!(detail.contains(part), "missing [{part}] in [{detail}]");
        }
        let summary = run_summary(&table, &Target::Blip(Duration::from_secs(100)), 11.5, true);
        assert!(summary
            .iter()
            .any(|(_, line)| line.contains("drill battery volts min ") && line.contains("[11.8V]")));
        assert!(summary
            .iter()
            .any(|(_, line)| line.contains("drill issue volts margin")));
    }

    #[test]
    fn the_time_to_the_end_row_is_the_restore_period_less_the_mains_seconds_so_far() {
        let table = |restore: Option<i64>, mains: Option<i64>| {
            let mut frame = Frame::default();
            if let Some(restore) = restore {
                frame.set_int(crate::metrics::GUARD_RESTORE_MAINS, restore);
            }
            if let Some(mains) = mains {
                frame.set_int(crate::metrics::GUARD_MAINS_SECONDS, mains);
            }
            let mut text = outage::encode_row(&crate::metrics::header());
            text.push('\n');
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_12-00-00",
                0,
                "",
                "",
                &frame,
            )));
            Table::parse(&text)
        };
        assert_eq!(end_row_in(&table(Some(300), Some(40))), Some(260));
        assert_eq!(end_row_in(&table(Some(300), Some(400))), Some(0));
        assert_eq!(end_row_in(&table(Some(300), None)), None);
        assert_eq!(end_row_in(&table(None, Some(40))), None);
    }

    #[test]
    fn the_follow_is_over_only_once_the_plug_is_restored_and_the_time_has_passed() {
        let past = Instant::now().checked_sub(Duration::from_secs(40)).unwrap();
        let limit = Some(Duration::from_secs(30));
        assert!(!follow_over(None, limit));
        assert!(!follow_over(Some(past), None));
        assert!(!follow_over(Some(Instant::now()), limit));
        assert!(follow_over(Some(past), limit));
    }

    #[test]
    fn the_hold_counts_from_the_first_battery_row_and_low_battery_is_seen() {
        let table = csv(&[
            ("0", "OL", "90", "start"),
            ("70", "OL", "90", ""),
            ("71", "OB DISCHRG", "0", ""),
            ("200", "OB DISCHRG", "0", ""),
        ]);
        assert_eq!(held_seconds(&table), Some(129));
        assert!(on_battery_seen(&table));
        assert!(!on_battery_seen(&csv(&[("0", "OL", "90", "start")])));
        assert!(!low_raised(&table));
    }

    #[test]
    fn the_latest_battery_volts_at_or_under_the_abort_volts_aborts_and_a_blank_or_higher_reading_does_not() {
        let table = |readings: &[Option<f64>]| {
            let mut text = outage::encode_row(&crate::metrics::header());
            text.push('\n');
            for (elapsed, volts) in readings.iter().enumerate() {
                let mut frame = Frame::default();
                if let Some(volts) = volts {
                    frame.set_number(crate::metrics::BATTERY_VOLTS, *volts);
                }
                text.push_str(&outage::encode_row(&outage::row(
                    "2026-01-01_12-00-00",
                    elapsed as u64,
                    "",
                    "",
                    &frame,
                )));
                text.push('\n');
            }
            Table::parse(&text)
        };
        assert!(!volts_aborted(&table(&[]), 11.5));
        assert!(!volts_aborted(&table(&[None, None]), 11.5));
        assert!(!volts_aborted(&table(&[Some(12.8), Some(11.6)]), 11.5));
        assert!(volts_aborted(&table(&[Some(12.8), Some(11.5)]), 11.5));
        assert!(volts_aborted(&table(&[Some(11.4), None]), 11.5));
        assert!(!volts_aborted(&table(&[Some(11.4), Some(12.0)]), 11.5));
    }

    #[test]
    fn an_ack_is_a_start_row_carrying_the_markers_own_id() {
        let dir = std::env::temp_dir().join(format!("rackmains-ack-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let write = |stem: &str, detail: &str| {
            let mut text = outage::encode_row(&crate::metrics::header());
            text.push('\n');
            text.push_str(&outage::encode_row(&outage::row(
                stem,
                0,
                "start",
                detail,
                &Frame::default(),
            )));
            fs::write(dir.join(outage::file_name(stem, 1)), text).unwrap();
        };
        write("2026-01-01_00-00-00", "drill [other] mode [brownout-shed-wake]");
        assert!(find_ack(&dir, "mine").is_none());
        write(
            "2026-01-01_00-01-00",
            "version [x] drill [mine] mode [brownout-shed-wake]",
        );
        assert_eq!(find_ack(&dir, "mine").unwrap().0.stem, "2026-01-01_00-01-00");
    }

    #[test]
    fn restoring_the_plug_retries_and_fails_loudly_when_it_never_reads_on() {
        let plug = mock::MockPlug {
            reachable: true,
            ..mock::MockPlug::default()
        };
        assert!(restore_plug(&plug, Duration::from_millis(1)).is_ok());
        assert!(plug.sent.lock().unwrap().iter().any(|sent| sent == "Rule1 0"));
        let dead = mock::MockPlug::default();
        assert!(restore_plug(&dead, Duration::from_millis(1)).is_err());
    }

    #[test]
    fn a_signalled_run_restores_the_plug_first_marks_the_marker_aborted_and_exits_seven() {
        let dir = std::env::temp_dir().join(format!("rackmains-abort-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join(DIR_STATE)).unwrap();
        let plug = Arc::new(mock::MockPlug {
            reachable: true,
            ..mock::MockPlug::default()
        });
        let env = Env {
            data_dir: dir.clone(),
            run_dir: dir.clone(),
            hosts_file: dir.join("hosts.json"),
            local_host: "max".to_string(),
            plug: plug.clone(),
            plug_host: "plug".to_string(),
            timing: Timing {
                after_cap: Duration::from_millis(50),
                poll: Duration::from_millis(10),
                ..Timing::default()
            },
            clock: || at("2026-01-01_12-00-00"),
            refuse_in_backup_window: true,
        };
        let marker = marker("2026-01-01_14-00-00", STATE_ARMED);
        let path = dir.join(DIR_STATE).join(FILE_MARKER);
        let error = abort(&env, &marker, &path, &dir.join(DIR_OUTAGE), "stem", true);
        assert_eq!(error.code, EXIT_ABORTED);
        assert_eq!(plug.sent.lock().unwrap().first().map(String::as_str), Some("Power On"));
        assert_eq!(Marker::read(&path).unwrap().state, STATE_ABORTED);
    }

    #[test]
    fn stop_acts_on_a_drill_and_on_an_off_plug_only_when_confirmed() {
        let dir = std::env::temp_dir().join(format!("rackmains-stop-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join(DIR_STATE)).unwrap();
        let rig = |reachable: bool| {
            let plug = Arc::new(mock::MockPlug {
                reachable,
                ..mock::MockPlug::default()
            });
            let env = Env {
                data_dir: dir.clone(),
                run_dir: dir.clone(),
                hosts_file: dir.join("hosts.json"),
                local_host: "max".to_string(),
                plug: plug.clone(),
                plug_host: "plug".to_string(),
                timing: Timing::default(),
                clock: || at("2026-01-01_12-00-00"),
                refuse_in_backup_window: true,
            };
            (plug, env)
        };
        let powered_on = |plug: &mock::MockPlug| plug.sent.lock().unwrap().iter().any(|sent| sent == "Power On");
        let never = |_: &str, _: &str| -> Result<bool, String> { panic!("no confirmation expected") };
        let (plug, env) = rig(true);
        run_stop(&env, never).unwrap();
        assert!(!powered_on(&plug));
        plug.off.store(true, std::sync::atomic::Ordering::SeqCst);
        assert_eq!(run_stop(&env, |_, word| Ok(word != "on")).unwrap_err().code, 1);
        assert!(!powered_on(&plug));
        run_stop(&env, |_, word| Ok(word == "on")).unwrap();
        assert!(powered_on(&plug));
        let (plug, env) = rig(false);
        assert_eq!(run_stop(&env, never).unwrap_err().code, 1);
        assert!(!powered_on(&plug));
        let (plug, env) = rig(true);
        marker("2026-01-01_14-00-00", STATE_ARMED)
            .write(&dir.join(DIR_STATE).join(FILE_MARKER))
            .unwrap();
        run_stop(&env, never).unwrap();
        assert!(powered_on(&plug));
        assert!(Marker::read(&dir.join(DIR_STATE).join(FILE_MARKER)).is_none());
    }

    #[test]
    fn a_status_reply_parses_to_whole_watts_and_wh() {
        let reading = PlugReading::parse(STATUS).unwrap();
        assert_eq!(
            reading,
            PlugReading {
                power: "ON".to_string(),
                watts: 90,
                volts: 241,
                amps: 0.371,
                energy_today_wh: 512
            }
        );
        assert!(PlugReading::parse("{}").is_none());
        assert!(PlugReading::parse("junk").is_none());
    }

    #[test]
    fn a_marker_is_live_only_while_armed_and_unexpired() {
        let now = parse_stamp("2026-01-01_00-10-00").unwrap();
        assert!(marker("2026-01-01_00-20-00", STATE_ARMED).live(now));
        assert!(!marker("2026-01-01_00-10-00", STATE_ARMED).live(now));
        assert!(!marker("2026-01-01_00-20-00", STATE_ABORTED).live(now));
        assert!(!marker("garbled", STATE_ARMED).live(now));
    }

    #[test]
    fn a_marker_round_trips_and_a_garbled_one_reads_as_none() {
        let path = std::env::temp_dir().join(format!("rackmains-marker-{}.json", std::process::id()));
        let original = marker("2026-01-01_00-20-00", STATE_ARMED);
        original.write(&path).unwrap();
        assert_eq!(Marker::read(&path), Some(original));
        fs::write(&path, "{").unwrap();
        assert_eq!(Marker::read(&path), None);
        let _ = fs::remove_file(path);
        assert_eq!(Marker::read(Path::new("/nonexistent")), None);
    }

    #[test]
    fn the_sampler_fills_the_plug_columns_and_leaves_them_blank_when_unreachable() {
        let reachable = Arc::new(mock::MockPlug {
            reachable: true,
            reading: PlugReading::parse(STATUS),
            ..mock::MockPlug::default()
        });
        let sampler = Sampler::start(reachable);
        let mut frame = Frame::default();
        let waiting = Instant::now();
        while frame.number(PLUG_WATTS).is_none() && waiting.elapsed() < Duration::from_secs(10) {
            thread::sleep(Duration::from_millis(10));
            sampler.fill(&mut frame);
        }
        assert_eq!(frame.number(PLUG_WATTS), Some(90.0));
        let sampler = Sampler::start(Arc::new(mock::MockPlug::default()));
        thread::sleep(Duration::from_millis(300));
        let mut blank = Frame::default();
        sampler.fill(&mut blank);
        assert_eq!(blank, Frame::default());
    }
}
