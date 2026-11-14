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
use crate::outage::{self, parse_stamp, write_atomic, OutageFile, Table, DIR_OUTAGE, DIR_STATE, EVENT_START};
use crate::report;
use crate::shed::load_hosts;

pub const FILE_MARKER: &str = "drill.json";
pub const STATE_ARMED: &str = "armed";
pub const STATE_ABORTED: &str = "aborted";
pub const MODE_HOLD: &str = "hold";
pub const MODE_DRAIN: &str = "drain";
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
pub const LEAD_IN_WATTS_SPREAD: i64 = 3;
pub const ACK_TIMEOUT: Duration = Duration::from_secs(10);
pub const GUARD_STALE_MS: u64 = 3000;
pub const AFTER_RESTORE_CAP: Duration = Duration::from_mins(30);
pub const MARKER_MARGIN: Duration = Duration::from_mins(5);
pub const DEADMAN_MARGIN: Duration = Duration::from_mins(5);
pub const DEADMAN_DRAIN: Duration = Duration::from_hours(3);
pub const HOLD_PAST_SHED: Duration = Duration::from_secs(120);
pub const CUT_TO_BATTERY: Duration = Duration::from_secs(10);
pub const RESTORE_VERIFY: Duration = Duration::from_secs(60);
pub const RECHARGE_WARNING: Duration = Duration::from_hours(6);
const CONNECT_PROBE: Duration = Duration::from_secs(2);
const BACKUP_WINDOW: (u32, u32, u32, u32) = (0, 45, 1, 45);

static SIGNALLED: AtomicBool = AtomicBool::new(false);

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Target {
    Hold(Duration),
    Drain,
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

pub fn parse_target(raw: Option<&str>, effective: &Effective) -> Result<Target, String> {
    match raw {
        None => Ok(Target::Hold(
            Duration::from_secs(effective.guard_shed_battery_seconds) + HOLD_PAST_SHED,
        )),
        Some("drain") => Ok(Target::Drain),
        Some(raw) => crate::parse_duration(raw).and_then(|hold| {
            if hold.is_zero() {
                Err("hold must be over zero".to_string())
            } else {
                Ok(Target::Hold(hold))
            }
        }),
    }
}

pub fn deadman_seconds(target: &Target) -> u64 {
    match target {
        Target::Hold(hold) => (*hold + DEADMAN_MARGIN).as_secs(),
        Target::Drain => DEADMAN_DRAIN.as_secs(),
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

pub fn plan_text(effective: &Effective, target: &Target, assessment: &Preflight, plug_host: &str) -> String {
    let (mode, hold) = match target {
        Target::Hold(hold) => (MODE_HOLD, hold.as_secs()),
        Target::Drain => (MODE_DRAIN, 0),
    };
    let shed = effective.guard_shed_battery_seconds;
    let restore_mains = effective.guard_restore_mains_seconds;
    let mut lines = vec![
        "tool".to_string(),
        format!(
            "  mode [{mode}] hold [{hold}s] after [{restore_mains}s] deadman [{}s] plug [{plug_host}]",
            deadman_seconds(target)
        ),
        "main program".to_string(),
        format!(
            "  guard_live [{}] model [{} {}] rackmains_guard_shed_battery_seconds [{shed}] rackmains_guard_restore_mains_seconds [{restore_mains}] poll [{}s] ssh_timeout [{}s] shed_order [{}]",
            u8::from(effective.guard_live),
            effective.model_name,
            effective.model_hash,
            effective.poll_s,
            effective.ssh_timeout_s,
            effective.shed_order.join(",")
        ),
        "timeline".to_string(),
    ];
    let ending = match target {
        Target::Hold(hold) => format!(
            "T+{} plug on, T+{} awake, end",
            hold.as_secs(),
            hold.as_secs() + restore_mains
        ),
        Target::Drain => "runs to the UPS cutoff, the deadman restores mains".to_string(),
    };
    lines.push(format!(
        "  T-{}s lead-in starts, T+0 plug off, about T+2 OB, T+{shed} shed, {ending}",
        LEAD_IN.as_secs()
    ));
    if let Target::Hold(hold) = target {
        if hold.as_secs() < shed {
            lines.push(format!(
                "WARNING hold [{}s] is under the shed point [{shed}s], the guard will not shed",
                hold.as_secs()
            ));
        }
    }
    if !effective.guard_live {
        lines.push("WARNING the guard is in dry-run, the test proves nothing about the shed".to_string());
    }
    lines.extend(assessment.refusals.iter().map(|refusal| format!("REFUSED {refusal}")));
    lines.extend(assessment.warnings.iter().map(|warning| format!("WARNING {warning}")));
    lines.join("\n") + "\n"
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

pub fn lead_in_verdict(table: &Table, lead: Duration) -> LeadIn {
    let seconds = |row: &[String]| table.cell(row, COLUMN_ELAPSED).parse::<u64>().unwrap_or(0);
    let watts = |row: &[String]| table.cell(row, "rackmains_plug_watts").parse::<i64>().ok();
    let Some(first) = table.rows.iter().position(|row| watts(row).is_some()) else {
        return LeadIn::Wait;
    };
    let window = &table.rows[first..];
    let unsteady = |row: &&Vec<String>| {
        let status = table.cell(row, crate::metrics::STATUS);
        let (flags, _) = crate::nut::Flags::parse(status);
        !status.split_whitespace().any(|token| token == TOKEN_OL) || flags.problem
    };
    if let Some(row) = window.iter().find(unsteady) {
        return LeadIn::Refuse(format!(
            "lead-in status [{}] is not steady mains",
            table.cell(row, crate::metrics::STATUS)
        ));
    }
    let readings: Vec<i64> = window.iter().filter_map(|row| watts(row)).collect();
    let spread = readings.iter().max().unwrap_or(&0) - readings.iter().min().unwrap_or(&0);
    if spread > LEAD_IN_WATTS_SPREAD {
        return LeadIn::Refuse(format!(
            "lead-in plug watts moved [{spread}] over [{LEAD_IN_WATTS_SPREAD}]"
        ));
    }
    match (window.first(), window.last()) {
        (Some(start), Some(end)) if seconds(end).saturating_sub(seconds(start)) >= lead.as_secs() => LeadIn::Ready,
        _ => LeadIn::Wait,
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

pub fn low_raised(table: &Table) -> bool {
    table
        .rows
        .iter()
        .any(|row| table.cell(row, metrics::BATTERY_LOW) == "1")
}

pub fn run_drill(env: &Env, raw_target: Option<&str>, force: bool) -> Result<(), ExitError> {
    let liveness = Liveness::read(&env.run_dir.join(FILE_LIVENESS))?;
    let target = parse_target(raw_target, &liveness.effective)?;
    let outage_dir = env.data_dir.join(DIR_OUTAGE);
    let marker_path = env.data_dir.join(DIR_STATE).join(FILE_MARKER);
    let preflight = assess(&gather(env, &liveness, &outage_dir, &marker_path));
    print!(
        "{}",
        plan_text(&liveness.effective, &target, &preflight, &env.plug_host)
    );
    if !force {
        println!("plan only, nothing was cut, add --force to cut");
        return Ok(());
    }
    if !preflight.refusals.is_empty() {
        return Err(ExitError::new(1, "preflight refused, nothing was cut"));
    }
    if target == Target::Drain && !confirmed_drain()? {
        return Err(ExitError::new(1, "drain was not confirmed, nothing was cut"));
    }
    install_signal_handlers();
    let hold = match &target {
        Target::Hold(hold) => *hold,
        Target::Drain => Duration::ZERO,
    };
    let now = (env.clock)();
    let marker = Marker {
        id: format!("{}-{}", now.format("%Y%m%d%H%M%S"), std::process::id()),
        mode: if target == Target::Drain { MODE_DRAIN } else { MODE_HOLD }.to_string(),
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
        drive(env, &target, &marker, &marker_path, &outage_dir)
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

pub fn run_stop(env: &Env, force: bool) -> Result<(), ExitError> {
    let marker_path = env.data_dir.join(DIR_STATE).join(FILE_MARKER);
    let marker = Marker::read(&marker_path);
    let power = env
        .plug
        .command("Power", PLUG_COMMAND_TIMEOUT)
        .ok()
        .and_then(|reply| reply["POWER"].as_str().map(str::to_string));
    println!(
        "marker [{}] plug [{}]",
        marker.as_ref().map_or("none", |marker| marker.state.as_str()),
        power.as_deref().unwrap_or("unreachable")
    );
    if marker.is_none() && !force {
        println!("no drill is running, nothing changed, use --force to restore the plug regardless");
        return Ok(());
    }
    restore_plug(env.plug.as_ref(), env.timing.poll)?;
    if let Some(mut marker) = marker {
        marker.state = STATE_ABORTED.to_string();
        marker.write(&marker_path)?;
        let _ = fs::remove_file(&marker_path);
    }
    println!("mains restored, the main program runs awake after the restore period of mains");
    Ok(())
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
        "PLUG NOT CONFIRMED ON [{last}], run `rackmains guard stop --force` or curl the plug's Power On and Rule1 0"
    ))
}

fn drive(env: &Env, target: &Target, marker: &Marker, marker_path: &Path, outage_dir: &Path) -> Result<(), ExitError> {
    let timing = &env.timing;
    let (file, _) = wait_for_ack(outage_dir, &marker.id, timing).ok_or_else(|| {
        ExitError::new(
            EXIT_TIMEOUT,
            "the main program did not acknowledge the marker, nothing was cut",
        )
    })?;
    println!("acknowledged [{}]", file.path.display());
    let stem = file.stem.clone();
    let reload = || -> Table { follow_run(outage_dir, &stem) };
    let waiting = Instant::now();
    loop {
        if SIGNALLED.load(Ordering::SeqCst) {
            return Err(abort(env, marker, marker_path, outage_dir, &stem, false));
        }
        let table = reload();
        if table.ended() || waiting.elapsed() > timing.lead_in * 3 + timing.ack_timeout {
            return Err(ExitError::new(
                EXIT_TIMEOUT,
                "the lead-in never completed, nothing was cut",
            ));
        }
        match lead_in_verdict(&table, timing.lead_in) {
            LeadIn::Ready => break,
            LeadIn::Wait => {}
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
    println!("deadman armed [{seconds}s]");
    let off = env.plug.command("Power Off", PLUG_COMMAND_TIMEOUT);
    if off
        .as_ref()
        .map_or(true, |reply| reply["POWER"].as_str() != Some("OFF"))
    {
        restore_plug(env.plug.as_ref(), env.timing.poll)?;
        return Err(ExitError::new(1, "the plug did not read OFF, mains restored"));
    }
    println!("mains cut");
    let cut_at = Instant::now();
    let mut printed = reload().rows.len();
    let mut restored: Option<Instant> = None;
    loop {
        let table = reload();
        for row in table.rows.iter().skip(printed) {
            println!("{}", report::format_row(&table, row));
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
        if let Target::Hold(hold) = target {
            if restored.is_none()
                && (held_seconds(&table).is_some_and(|held| held >= hold.as_secs()) || low_raised(&table))
            {
                restore_plug(env.plug.as_ref(), env.timing.poll)?;
                println!("mains restored");
                restored = Some(Instant::now());
                verify_restored(env, outage_dir, &stem)?;
            }
        }
        if restored.is_some_and(|at| at.elapsed() > timing.after_cap) {
            return Err(ExitError::new(
                EXIT_TIMEOUT,
                "no end row within the cap after the restore, mains is on",
            ));
        }
        thread::sleep(timing.poll);
    }
    Ok(())
}

fn abort(env: &Env, marker: &Marker, marker_path: &Path, outage_dir: &Path, stem: &str, cut: bool) -> ExitError {
    println!("signalled, restoring mains first");
    if cut || env.plug.command("Rule1", PLUG_COMMAND_TIMEOUT).is_ok() {
        if let Err(err) = restore_plug(env.plug.as_ref(), env.timing.poll) {
            return ExitError::new(1, &err);
        }
    }
    let mut aborted = marker.clone();
    aborted.state = STATE_ABORTED.to_string();
    let _ = aborted.write(marker_path);
    println!("aborted, the main program runs awake after the restore period of mains, following until the end row");
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
        "OL was not seen after the restore, run `rackmains guard stop --force`",
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

fn confirmed_drain() -> Result<bool, String> {
    println!("drain keeps mains off until the UPS cuts its own output and max is cut while running, type [drain] to continue");
    let mut line = String::new();
    std::io::stdin()
        .read_line(&mut line)
        .map_err(|err| format!("failed to read confirmation [{err}]"))?;
    Ok(line.trim() == "drain")
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
    use std::sync::Mutex;

    use super::*;

    #[derive(Default)]
    pub struct MockPlug {
        pub reachable: bool,
        pub sent: Mutex<Vec<String>>,
        pub reading: Option<PlugReading>,
    }

    impl Plug for MockPlug {
        fn command(&self, command: &str, _timeout: Duration) -> Result<Value, String> {
            if !self.reachable {
                return Err("unreachable".to_string());
            }
            self.sent.lock().unwrap().push(command.to_string());
            Ok(serde_json::json!({"POWER": "ON"}))
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
            mode: MODE_HOLD.to_string(),
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
    fn the_default_hold_is_the_shed_point_plus_two_minutes_and_drain_is_a_word() {
        assert_eq!(
            parse_target(None, &effective()),
            Ok(Target::Hold(Duration::from_secs(240)))
        );
        assert_eq!(
            parse_target(Some("90s"), &effective()),
            Ok(Target::Hold(Duration::from_secs(90)))
        );
        assert_eq!(parse_target(Some("drain"), &effective()), Ok(Target::Drain));
        assert!(parse_target(Some("0"), &effective()).is_err());
        assert!(parse_target(Some("soon"), &effective()).is_err());
    }

    #[test]
    fn the_deadman_outlasts_the_hold_and_a_drain_gets_three_hours() {
        assert_eq!(deadman_seconds(&Target::Hold(Duration::from_secs(240))), 540);
        assert_eq!(deadman_seconds(&Target::Drain), 10_800);
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
    fn the_plan_warns_when_the_hold_is_under_the_shed_point_or_the_guard_is_dry() {
        let plan = |hold: u64, live: bool| {
            let mut effective = effective();
            effective.guard_live = live;
            plan_text(
                &effective,
                &Target::Hold(Duration::from_secs(hold)),
                &Preflight::default(),
                "plug",
            )
        };
        assert!(plan(60, true).contains("will not shed"));
        assert!(!plan(240, true).contains("will not shed"));
        assert!(plan(240, false).contains("dry-run"));
        assert!(plan(240, true).contains("T+120 shed"));
        assert!(plan_text(&effective(), &Target::Drain, &Preflight::default(), "plug").contains("UPS cutoff"));
        let refused = Preflight {
            refusals: vec!["why".to_string()],
            warnings: Vec::new(),
        };
        assert!(plan_text(&effective(), &Target::Drain, &refused, "plug").contains("REFUSED why"));
    }

    #[test]
    fn the_lead_in_needs_a_minute_of_ol_with_steady_plug_watts() {
        let lead = Duration::from_secs(60);
        assert_eq!(
            lead_in_verdict(&csv(&[("0", "OL", "", "start"), ("1", "OL", "", "")]), lead),
            LeadIn::Wait
        );
        assert_eq!(
            lead_in_verdict(&csv(&[("1", "OL", "90", ""), ("30", "OL", "91", "")]), lead),
            LeadIn::Wait
        );
        assert_eq!(
            lead_in_verdict(&csv(&[("1", "OL", "90", ""), ("61", "OL", "92", "")]), lead),
            LeadIn::Ready
        );
        assert!(matches!(
            lead_in_verdict(&csv(&[("1", "OL", "90", ""), ("61", "OL OVER", "90", "")]), lead),
            LeadIn::Refuse(_)
        ));
        assert!(matches!(
            lead_in_verdict(&csv(&[("1", "OL", "90", ""), ("61", "OL", "94", "")]), lead),
            LeadIn::Refuse(_)
        ));
        assert_eq!(
            lead_in_verdict(
                &csv(&[("1", "OL CHRG", "90", ""), ("61", "OL CHRG BOOST", "90", "")]),
                lead
            ),
            LeadIn::Ready
        );
        assert!(matches!(
            lead_in_verdict(&csv(&[("1", "OB", "90", "")]), lead),
            LeadIn::Refuse(_)
        ));
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
        write("2026-01-01_00-00-00", "drill [other] mode [hold]");
        assert!(find_ack(&dir, "mine").is_none());
        write("2026-01-01_00-01-00", "version [x] drill [mine] mode [hold]");
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
    fn stop_with_no_drill_changes_nothing_and_force_restores() {
        let dir = std::env::temp_dir().join(format!("rackmains-stop-{}", std::process::id()));
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
            timing: Timing::default(),
            clock: || at("2026-01-01_12-00-00"),
            refuse_in_backup_window: true,
        };
        run_stop(&env, false).unwrap();
        assert!(!plug.sent.lock().unwrap().iter().any(|sent| sent == "Power On"));
        run_stop(&env, true).unwrap();
        assert!(plug.sent.lock().unwrap().iter().any(|sent| sent == "Power On"));
        marker("2026-01-01_14-00-00", STATE_ARMED)
            .write(&dir.join(DIR_STATE).join(FILE_MARKER))
            .unwrap();
        run_stop(&env, false).unwrap();
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
