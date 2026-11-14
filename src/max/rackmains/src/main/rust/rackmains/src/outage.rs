use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use chrono::{Local, NaiveDateTime};
use log::{info, warn};
use serde_json::Value;

use crate::log_line;
use crate::metrics::{
    self, Frame, COLUMN_DETAIL, COLUMN_ELAPSED, COLUMN_EVENT, COLUMN_TIME, LAST_OUTAGE_END, LAST_OUTAGE_MIN_VOLTS,
    LAST_OUTAGE_SECONDS, STATUS,
};
use crate::nut::{Flags, TOKEN_OB};

pub const DIR_OUTAGE: &str = "outage";
pub const DIR_STATE: &str = "state";
pub const FILE_LIMIT_BYTES: usize = 1_000_000;
pub const EVENT_START: &str = "start";
pub const EVENT_STATUS: &str = "status";
pub const EVENT_DECISION: &str = "decision";
pub const EVENT_COMMAND: &str = "command";
pub const EVENT_NOTE: &str = "note";
pub const EVENT_END: &str = "end";
pub const DECISION_SHED: &str = "shed";
pub const END_INTERRUPTED: &str = "interrupted";
pub const END_ABORTED: &str = "aborted";
pub const END_RESTORED: &str = "restored";
const STAMP_FORMAT: &str = "%Y-%m-%d_%H-%M-%S";
const FILE_PREFIX: &str = "rackmains_outage_";
const FILE_SUFFIX: &str = ".csv";
const FLUSH_RETRY: Duration = Duration::from_secs(1);

#[derive(Debug, Default, PartialEq)]
pub struct Table {
    pub header: Vec<String>,
    pub rows: Vec<Vec<String>>,
}

impl Table {
    pub fn read(path: &Path) -> Result<Table, String> {
        let text = fs::read_to_string(path).map_err(|err| format!("failed to read [{}] [{err}]", path.display()))?;
        Ok(Table::parse(&text))
    }

    pub fn parse(text: &str) -> Table {
        let mut lines = text.lines().map(decode_row);
        let header = lines.next().unwrap_or_default();
        Table {
            header,
            rows: lines.collect(),
        }
    }

    pub fn column(&self, name: &str) -> Option<usize> {
        self.header.iter().position(|header| header == name)
    }

    pub fn cell<'a>(&self, row: &'a [String], name: &str) -> &'a str {
        self.column(name)
            .and_then(|index| row.get(index))
            .map_or("", String::as_str)
    }

    pub fn ended(&self) -> bool {
        self.rows
            .last()
            .is_some_and(|row| self.cell(row, COLUMN_EVENT) == EVENT_END)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct OutageFile {
    pub stem: String,
    pub number: u32,
    pub path: PathBuf,
}

#[derive(Debug, Default)]
pub struct Stats {
    seconds_on_battery: Duration,
    min_volts: Option<(f64, String)>,
    peak_utilisation: i64,
    utilisation_sum: i64,
    utilisation_count: i64,
    charge_start: Option<i64>,
    charge_end: Option<i64>,
    low_raised: bool,
    last_volts: Option<f64>,
}

impl Stats {
    pub fn observe(&mut self, frame: &Frame, flags: Flags, stamp: &str, dt: Duration) {
        if !flags.raw_on_battery {
            return;
        }
        self.seconds_on_battery += dt;
        self.low_raised |= flags.low;
        if let Some(volts) = frame.number(metrics::BATTERY_VOLTS) {
            self.last_volts = Some(volts);
            if self.min_volts.as_ref().is_none_or(|(min, _)| volts < *min) {
                self.min_volts = Some((volts, stamp.to_string()));
            }
        }
        if let Some(utilisation) = frame.number(metrics::UTILISATION) {
            let utilisation = utilisation as i64;
            self.peak_utilisation = self.peak_utilisation.max(utilisation);
            self.utilisation_sum += utilisation;
            self.utilisation_count += 1;
        }
        if let Some(charge) = frame.number(metrics::BATTERY_CHARGE_PCT) {
            self.charge_start.get_or_insert(charge as i64);
            self.charge_end = Some(charge as i64);
        }
    }

    pub fn seconds(&self) -> u64 {
        self.seconds_on_battery.as_secs()
    }

    pub fn min_volts(&self) -> Option<f64> {
        self.min_volts.as_ref().map(|(volts, _)| *volts)
    }

    pub fn detail(&self, reason: &str, hosts_shed: usize) -> String {
        let (min_volts, min_at) = self
            .min_volts
            .as_ref()
            .map_or((String::new(), String::new()), |(volts, at)| {
                (volts.to_string(), at.clone())
            });
        let mean = if self.utilisation_count == 0 {
            String::new()
        } else {
            (self.utilisation_sum / self.utilisation_count).to_string()
        };
        let text = |value: Option<i64>| value.map(|value| value.to_string()).unwrap_or_default();
        format!(
            "reason [{reason}] seconds_on_battery [{}] battery_min_volts [{min_volts}] battery_min_at [{min_at}] battery_last_volts [{}] \
             utilisation_peak_pct [{}] utilisation_mean_pct [{mean}] charge_start_pct [{}] charge_end_pct [{}] battery_low [{}] hosts_shed [{hosts_shed}]",
            self.seconds_on_battery.as_secs(),
            self.last_volts.map(|volts| volts.to_string()).unwrap_or_default(),
            self.peak_utilisation,
            text(self.charge_start),
            text(self.charge_end),
            u8::from(self.low_raised),
        )
    }
}

pub enum WriterCommand {
    Open(String),
    Row(Vec<String>),
    Close,
    Sync(Sender<()>),
    Stop,
}

pub struct Writer {
    sender: Sender<WriterCommand>,
    handle: Option<JoinHandle<()>>,
}

impl Writer {
    pub fn start(dir: PathBuf, keep: usize) -> Writer {
        let (sender, receiver) = mpsc::channel();
        let handle = thread::spawn(move || {
            let mut spool = Spool::new(dir, keep);
            loop {
                match receiver.recv_timeout(FLUSH_RETRY) {
                    Ok(WriterCommand::Stop) | Err(RecvTimeoutError::Disconnected) => break,
                    Ok(command) => {
                        let mut acks = Vec::new();
                        let mut stopped = false;
                        let mut next = Some(command);
                        while let Some(command) = next.take() {
                            match command {
                                WriterCommand::Stop => {
                                    stopped = true;
                                    break;
                                }
                                WriterCommand::Sync(ack) => acks.push(ack),
                                other => spool.apply(other),
                            }
                            next = receiver.try_recv().ok();
                        }
                        spool.flush();
                        for ack in acks {
                            let _ = ack.send(());
                        }
                        if stopped {
                            break;
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => spool.flush(),
                }
            }
            spool.flush();
        });
        Writer {
            sender,
            handle: Some(handle),
        }
    }

    pub fn send(&self, command: WriterCommand) {
        if self.sender.send(command).is_err() {
            warn!("outage writer stopped, row dropped");
        }
    }

    pub fn sync(&self) {
        let (ack, done) = mpsc::channel();
        if self.sender.send(WriterCommand::Sync(ack)).is_ok() {
            let _ = done.recv_timeout(Duration::from_secs(10));
        }
    }

    pub fn stop(mut self) {
        let _ = self.sender.send(WriterCommand::Stop);
        if let Some(handle) = self.handle.take() {
            let _ = handle.join();
        }
    }
}

struct Part {
    path: PathBuf,
    text: String,
    written: bool,
}

struct Spool {
    dir: PathBuf,
    keep: usize,
    stem: String,
    number: u32,
    parts: Vec<Part>,
    current: Option<usize>,
    failing: bool,
}

impl Spool {
    fn new(dir: PathBuf, keep: usize) -> Spool {
        Spool {
            dir,
            keep,
            stem: String::new(),
            number: 0,
            parts: Vec::new(),
            current: None,
            failing: false,
        }
    }

    fn apply(&mut self, command: WriterCommand) {
        match command {
            WriterCommand::Open(stem) => {
                self.stem = stem;
                self.number = 0;
                self.next_part();
            }
            WriterCommand::Row(cells) => {
                let Some(index) = self.current else {
                    warn!("outage row dropped, no file open");
                    return;
                };
                let part = &mut self.parts[index];
                part.text.push_str(&encode_row(&cells));
                part.text.push('\n');
                part.written = false;
                if part.text.len() >= FILE_LIMIT_BYTES {
                    self.next_part();
                }
            }
            WriterCommand::Close => {
                if let Some(index) = self.current {
                    info!(
                        "{}",
                        log_line("outage file closed", &self.parts[index].path.display().to_string())
                    );
                }
                self.current = None;
            }
            WriterCommand::Sync(_) | WriterCommand::Stop => {}
        }
    }

    fn next_part(&mut self) {
        self.number += 1;
        let mut text = encode_row(&metrics::header());
        text.push('\n');
        self.parts.push(Part {
            path: self.dir.join(file_name(&self.stem, self.number)),
            text,
            written: false,
        });
        self.current = Some(self.parts.len() - 1);
        let label = if self.number == 1 {
            "outage file opened"
        } else {
            "outage file continued"
        };
        info!(
            "{}",
            log_line(label, &self.parts[self.parts.len() - 1].path.display().to_string())
        );
    }

    fn flush(&mut self) {
        let mut created = false;
        let mut failed = false;
        let mut attempted = false;
        for part in self.parts.iter_mut().filter(|part| !part.written) {
            attempted = true;
            let fresh = !part.path.exists();
            match write_atomic(&part.path, part.text.as_bytes()) {
                Ok(()) => {
                    part.written = true;
                    created |= fresh;
                }
                Err(err) => {
                    failed = true;
                    warn!("outage write failed, rows kept in memory [{err}]");
                }
            }
        }
        if failed {
            self.failing = true;
        } else if attempted && self.failing {
            self.failing = false;
            info!("{}", log_line("outage writer recovered", "rows written"));
        }
        if created {
            prune(&self.dir, self.keep, &self.stem);
        }
        let current = self.current.map(|index| self.parts[index].path.clone());
        self.parts
            .retain(|part| !part.written || current.as_ref() == Some(&part.path));
        self.current = current.and_then(|path| self.parts.iter().position(|part| part.path == path));
    }
}

pub fn stamp(now: chrono::DateTime<Local>) -> String {
    now.format(STAMP_FORMAT).to_string()
}

pub fn file_name(stem: &str, number: u32) -> String {
    format!("{FILE_PREFIX}{stem}_{number}{FILE_SUFFIX}")
}

pub fn parse_stamp(text: &str) -> Option<NaiveDateTime> {
    NaiveDateTime::parse_from_str(text, STAMP_FORMAT).ok()
}

pub fn row(stamp: &str, elapsed_seconds: u64, event: &str, detail: &str, frame: &Frame) -> Vec<String> {
    [
        stamp.to_string(),
        elapsed_seconds.to_string(),
        event.to_string(),
        detail.to_string(),
    ]
    .into_iter()
    .chain(frame.cells())
    .collect()
}

pub fn encode_row(cells: &[String]) -> String {
    cells
        .iter()
        .map(|cell| {
            if cell.contains([',', '"', '\n', '\r']) {
                format!("\"{}\"", cell.replace('"', "\"\"").replace(['\n', '\r'], " "))
            } else {
                cell.clone()
            }
        })
        .collect::<Vec<_>>()
        .join(",")
}

pub fn decode_row(line: &str) -> Vec<String> {
    let mut cells = Vec::new();
    let mut cell = String::new();
    let mut quoted = false;
    let mut chars = line.chars().peekable();
    while let Some(character) = chars.next() {
        match (character, quoted) {
            ('"', true) if chars.peek() == Some(&'"') => {
                cell.push('"');
                chars.next();
            }
            ('"', _) => quoted = !quoted,
            (',', false) => cells.push(std::mem::take(&mut cell)),
            (other, _) => cell.push(other),
        }
    }
    cells.push(cell);
    cells
}

pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    write_replace(path, bytes, true)
}

pub fn write_replace(path: &Path, bytes: &[u8], durable: bool) -> Result<(), String> {
    let failed = |action: &str, err: std::io::Error| format!("failed to {action} [{}] [{err}]", path.display());
    let temporary = path.with_extension(match path.extension().and_then(|extension| extension.to_str()) {
        Some(extension) => format!("{extension}.tmp"),
        None => "tmp".to_string(),
    });
    let mut file = File::create(&temporary).map_err(|err| failed("create", err))?;
    file.write_all(bytes).map_err(|err| failed("write", err))?;
    if durable {
        file.sync_all().map_err(|err| failed("sync", err))?;
    }
    drop(file);
    fs::rename(&temporary, path).map_err(|err| failed("rename", err))?;
    if !durable {
        return Ok(());
    }
    let directory = path
        .parent()
        .ok_or_else(|| format!("no parent directory [{}]", path.display()))?;
    File::open(directory)
        .and_then(|directory| directory.sync_all())
        .map_err(|err| failed("sync directory", err))
}

pub fn files(dir: &Path) -> Vec<OutageFile> {
    let mut found: Vec<OutageFile> = fs::read_dir(dir)
        .into_iter()
        .flatten()
        .flatten()
        .filter_map(|entry| {
            let name = entry.file_name().to_string_lossy().to_string();
            let body = name.strip_prefix(FILE_PREFIX)?.strip_suffix(FILE_SUFFIX)?;
            let (stem, number) = body.rsplit_once('_')?;
            Some(OutageFile {
                stem: stem.to_string(),
                number: number.parse().ok()?,
                path: entry.path(),
            })
        })
        .collect();
    found.sort();
    found
}

pub fn prune(dir: &Path, keep: usize, current_stem: &str) {
    let all = files(dir);
    let excess = all.len().saturating_sub(keep.max(1));
    for file in all.iter().take(excess).filter(|file| file.stem != current_stem) {
        match fs::remove_file(&file.path) {
            Ok(()) => info!("outage file pruned [{}]", file.path.display()),
            Err(err) => warn!("outage file prune failed [{}] [{err}]", file.path.display()),
        }
    }
}

pub fn recover(dir: &Path) -> Vec<PathBuf> {
    for entry in fs::read_dir(dir).into_iter().flatten().flatten() {
        if entry.path().extension().is_some_and(|extension| extension == "tmp") {
            let _ = fs::remove_file(entry.path());
        }
    }
    let all = files(dir);
    let mut closed = Vec::new();
    for file in all.iter().filter(|file| {
        all.iter()
            .filter(|other| other.stem == file.stem)
            .map(|other| other.number)
            .max()
            == Some(file.number)
    }) {
        let Ok(table) = Table::read(&file.path) else { continue };
        if table.ended() || table.rows.is_empty() {
            continue;
        }
        let Some(last) = table.rows.last() else { continue };
        let mut end = last.clone();
        for (name, value) in [(COLUMN_EVENT, EVENT_END), (COLUMN_DETAIL, END_INTERRUPTED)] {
            if let Some(index) = table.column(name) {
                end[index] = value.to_string();
            }
        }
        let mut text = fs::read_to_string(&file.path).unwrap_or_default();
        text.push_str(&encode_row(&end));
        text.push('\n');
        match write_atomic(&file.path, text.as_bytes()) {
            Ok(()) => {
                warn!("outage file closed [{END_INTERRUPTED}] [{}]", file.path.display());
                closed.push(file.path.clone());
            }
            Err(err) => warn!("{err}"),
        }
    }
    closed
}

pub fn open_file(dir: &Path) -> Option<(OutageFile, Table)> {
    let all = files(dir);
    let newest = all.last()?;
    let table = Table::read(&newest.path).ok()?;
    (!table.ended() && !table.rows.is_empty()).then(|| (newest.clone(), table))
}

pub fn last_outage(dir: &Path) -> Frame {
    let mut frame = Frame::default();
    for file in files(dir).iter().rev() {
        let Ok(table) = Table::read(&file.path) else { continue };
        let Some(end) = table.rows.last().filter(|_| table.ended()) else {
            continue;
        };
        let seconds = table.cell(end, LAST_OUTAGE_SECONDS);
        if seconds.is_empty() {
            continue;
        }
        if let Ok(seconds) = seconds.parse::<i64>() {
            frame.set_int(LAST_OUTAGE_SECONDS, seconds);
        }
        for name in [LAST_OUTAGE_MIN_VOLTS, LAST_OUTAGE_END] {
            if let Ok(value) = table.cell(end, name).parse::<f64>() {
                frame.set_number(name, value);
            }
        }
        break;
    }
    frame
}

pub fn last_model_state(dir: &Path, model_hash: &str) -> Option<Value> {
    let all = files(dir);
    for file in all.iter().rev() {
        let Ok(table) = Table::read(&file.path) else { continue };
        let Some(end) = table.rows.last().filter(|_| table.ended()) else {
            continue;
        };
        let state = table.cell(end, metrics::MODEL_STATE);
        if state.is_empty() {
            continue;
        }
        let first = all.iter().find(|part| part.stem == file.stem)?;
        let head = Table::read(&first.path).ok()?;
        let start = head.rows.first()?;
        return head
            .cell(start, COLUMN_DETAIL)
            .contains(model_hash)
            .then(|| serde_json::from_str(state).ok())
            .flatten();
    }
    None
}

pub fn clocks(table: &Table, now: NaiveDateTime) -> Option<(Duration, Duration, bool)> {
    let on_battery = |row: &Vec<String>| {
        table
            .cell(row, STATUS)
            .split_whitespace()
            .any(|token| token == TOKEN_OB)
    };
    let seconds = |row: &Vec<String>| table.cell(row, COLUMN_ELAPSED).parse::<u64>().unwrap_or(0);
    let stamp_of = |row: &Vec<String>| parse_stamp(table.cell(row, COLUMN_TIME));
    let last_battery_row = table.rows.iter().rev().find(|row| on_battery(row))?;
    let last_row = table.rows.last()?;
    let since = |from: NaiveDateTime| (now - from).to_std().unwrap_or_default();
    let mut battery: u64 = table
        .rows
        .windows(2)
        .filter(|pair| on_battery(&pair[0]))
        .map(|pair| seconds(&pair[1]).saturating_sub(seconds(&pair[0])))
        .sum();
    battery = battery.max(1);
    let mut battery = Duration::from_secs(battery);
    let mains = if on_battery(last_row) {
        battery += since(stamp_of(last_row)?);
        Duration::ZERO
    } else {
        since(stamp_of(last_battery_row)?)
    };
    let shed = table.rows.iter().any(|row| {
        table.cell(row, COLUMN_EVENT) == EVENT_DECISION && table.cell(row, COLUMN_DETAIL).starts_with(DECISION_SHED)
    });
    Some((battery, mains, shed))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn directory(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("rackmains-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn cells(stamp: &str, event: &str, detail: &str) -> Vec<String> {
        row(stamp, 0, event, detail, &Frame::default())
    }

    fn settle() {
        thread::sleep(Duration::from_millis(300));
    }

    #[test]
    fn rows_round_trip_through_the_encoding() {
        for original in [
            vec!["a".to_string(), "b,c".to_string(), "d\"e".to_string(), String::new()],
            vec!["one".to_string()],
            vec![String::new(), String::new()],
        ] {
            assert_eq!(decode_row(&encode_row(&original)), original);
        }
        assert_eq!(decode_row(&encode_row(&["x\ny".to_string()])), vec!["x y".to_string()]);
    }

    #[test]
    fn files_order_by_stem_then_number_as_a_number() {
        let dir = directory("order");
        for name in [
            file_name("2026-01-02_00-00-00", 10),
            file_name("2026-01-02_00-00-00", 2),
            file_name("2026-01-01_00-00-00", 1),
        ] {
            fs::write(dir.join(name), "").unwrap();
        }
        let order: Vec<(String, u32)> = files(&dir).into_iter().map(|file| (file.stem, file.number)).collect();
        assert_eq!(
            order,
            vec![
                ("2026-01-01_00-00-00".to_string(), 1),
                ("2026-01-02_00-00-00".to_string(), 2),
                ("2026-01-02_00-00-00".to_string(), 10),
            ]
        );
    }

    #[test]
    fn the_writer_leaves_a_whole_file_and_no_temporary() {
        let dir = directory("writer");
        let writer = Writer::start(dir.clone(), 100);
        writer.send(WriterCommand::Open("2026-01-01_00-00-00".to_string()));
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-00", "start", "x")));
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-01", "", "")));
        writer.stop();
        let table = Table::read(&dir.join(file_name("2026-01-01_00-00-00", 1))).unwrap();
        assert_eq!(table.rows.len(), 2);
        assert_eq!(table.header, metrics::header());
        assert!(fs::read_dir(&dir)
            .unwrap()
            .flatten()
            .all(|entry| entry.path().extension().unwrap() == "csv"));
    }

    #[test]
    fn a_failed_write_does_not_lose_rows_and_the_next_holds_them_all() {
        let dir = directory("failed");
        let gone = dir.join("later");
        let writer = Writer::start(gone.clone(), 100);
        writer.send(WriterCommand::Open("2026-01-01_00-00-00".to_string()));
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-00", "start", "")));
        settle();
        assert!(!gone.exists());
        fs::create_dir_all(&gone).unwrap();
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-01", "", "")));
        writer.stop();
        let table = Table::read(&gone.join(file_name("2026-01-01_00-00-00", 1))).unwrap();
        assert_eq!(table.rows.len(), 2);
    }

    #[test]
    fn a_file_over_the_limit_continues_in_the_next_numbered_file() {
        let dir = directory("rotate");
        let writer = Writer::start(dir.clone(), 100);
        writer.send(WriterCommand::Open("2026-01-01_00-00-00".to_string()));
        let big = "x".repeat(FILE_LIMIT_BYTES);
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-00", "start", &big)));
        writer.send(WriterCommand::Row(cells("2026-01-01_00-00-01", "", "")));
        writer.stop();
        let found = files(&dir);
        assert_eq!(found.iter().map(|file| file.number).collect::<Vec<_>>(), vec![1, 2]);
        assert_eq!(Table::read(&found[1].path).unwrap().rows.len(), 1);
    }

    #[test]
    fn pruning_keeps_the_newest_and_never_the_current_stem() {
        let dir = directory("prune");
        for stem in ["2026-01-01_00-00-00", "2026-01-02_00-00-00", "2026-01-03_00-00-00"] {
            fs::write(dir.join(file_name(stem, 1)), "").unwrap();
        }
        prune(&dir, 1, "2026-01-01_00-00-00");
        let stems: Vec<String> = files(&dir).into_iter().map(|file| file.stem).collect();
        assert_eq!(
            stems,
            vec!["2026-01-01_00-00-00".to_string(), "2026-01-03_00-00-00".to_string()]
        );
    }

    #[test]
    fn recovery_closes_an_unfinished_file_and_deletes_a_stray_temporary() {
        let dir = directory("recover");
        let path = dir.join(file_name("2026-01-01_00-00-00", 1));
        let mut text = encode_row(&metrics::header());
        text.push('\n');
        text.push_str(&encode_row(&cells("2026-01-01_00-00-05", "start", "")));
        text.push('\n');
        fs::write(&path, text).unwrap();
        fs::write(dir.join("rackmains_outage_x_1.csv.tmp"), "junk").unwrap();
        assert_eq!(recover(&dir), vec![path.clone()]);
        let table = Table::read(&path).unwrap();
        let last = table.rows.last().unwrap();
        assert_eq!(
            (table.cell(last, "event"), table.cell(last, "detail")),
            (EVENT_END, END_INTERRUPTED)
        );
        assert_eq!(table.cell(last, "time"), "2026-01-01_00-00-05");
        assert!(!dir.join("rackmains_outage_x_1.csv.tmp").exists());
        assert!(recover(&dir).is_empty());
    }

    #[test]
    fn recovery_leaves_a_rotated_earlier_part_and_a_finished_file_alone() {
        let dir = directory("recover-parts");
        let header = encode_row(&metrics::header());
        let body = |event: &str| format!("{header}\n{}\n", encode_row(&cells("2026-01-01_00-00-05", event, "")));
        fs::write(dir.join(file_name("2026-01-01_00-00-00", 1)), body("")).unwrap();
        fs::write(dir.join(file_name("2026-01-01_00-00-00", 2)), body(EVENT_END)).unwrap();
        assert!(recover(&dir).is_empty());
    }

    #[test]
    fn the_stats_summary_derives_from_a_sequence_of_samples() {
        let mut stats = Stats::default();
        let on_battery = Flags {
            raw_on_battery: true,
            on_battery: true,
            ..Flags::default()
        };
        for (volts, load, charge, stamp) in [
            (13.0, 10.0, 100.0, "a"),
            (12.0, 20.0, 80.0, "b"),
            (12.4, 15.0, 60.0, "c"),
        ] {
            let mut frame = Frame::default();
            frame.set_number(metrics::BATTERY_VOLTS, volts);
            frame.set_number(metrics::UTILISATION, load);
            frame.set_number("rackmains_battery_charge_pct", charge);
            stats.observe(&frame, on_battery, stamp, Duration::from_secs(1));
        }
        stats.observe(&Frame::default(), Flags::default(), "d", Duration::from_secs(1));
        assert_eq!(stats.seconds(), 3);
        assert_eq!(stats.min_volts(), Some(12.0));
        let detail = stats.detail(END_RESTORED, 4);
        for part in [
            "seconds_on_battery [3]",
            "battery_min_volts [12]",
            "battery_min_at [b]",
            "battery_last_volts [12.4]",
            "utilisation_peak_pct [20]",
            "utilisation_mean_pct [15]",
            "charge_start_pct [100]",
            "charge_end_pct [60]",
            "battery_low [0]",
            "hosts_shed [4]",
        ] {
            assert!(detail.contains(part), "missing [{part}] in [{detail}]");
        }
    }

    #[test]
    fn the_battery_time_adds_the_poll_period_not_one_per_tick() {
        let mut stats = Stats::default();
        let flags = Flags {
            raw_on_battery: true,
            ..Flags::default()
        };
        for _ in 0..3 {
            stats.observe(&Frame::default(), flags, "a", Duration::from_secs(10));
        }
        assert_eq!(stats.seconds(), 30);
    }

    #[test]
    fn the_last_outage_is_read_from_the_newest_end_row_with_a_duration() {
        let dir = directory("last");
        let header = encode_row(&metrics::header());
        let mut ended = Frame::default();
        ended.set_int(LAST_OUTAGE_SECONDS, 42);
        ended.set_number(LAST_OUTAGE_MIN_VOLTS, 11.9);
        ended.set_number(LAST_OUTAGE_END, 1000.5);
        let finished = row("2026-01-01_00-10-00", 600, EVENT_END, END_RESTORED, &ended);
        fs::write(
            dir.join(file_name("2026-01-01_00-00-00", 1)),
            format!("{header}\n{}\n", encode_row(&finished)),
        )
        .unwrap();
        let interrupted = row(
            "2026-01-02_00-10-00",
            600,
            EVENT_END,
            END_INTERRUPTED,
            &Frame::default(),
        );
        fs::write(
            dir.join(file_name("2026-01-02_00-00-00", 1)),
            format!("{header}\n{}\n", encode_row(&interrupted)),
        )
        .unwrap();
        let frame = last_outage(&dir);
        assert_eq!(frame.number(LAST_OUTAGE_SECONDS), Some(42.0));
        assert_eq!(frame.number(LAST_OUTAGE_MIN_VOLTS), Some(11.9));
        assert_eq!(frame.number(LAST_OUTAGE_END), Some(1000.5));
        assert_eq!(last_outage(&directory("last-empty")), Frame::default());
    }

    #[test]
    fn the_last_model_state_is_read_from_the_newest_clean_end_row_of_the_same_project() {
        let dir = directory("state");
        let header = encode_row(&metrics::header());
        let mut start = Frame::default();
        start.set_text(metrics::MODEL_STATE, "{\"a\":1.0}");
        let mut end = Frame::default();
        end.set_text(metrics::MODEL_STATE, "{\"a\":2.5}");
        let stem = "2026-01-01_00-00-00";
        fs::write(
            dir.join(file_name(stem, 1)),
            format!(
                "{header}\n{}\n{}\n",
                encode_row(&row(stem, 0, "start", "model [x abc123]", &start)),
                encode_row(&row("2026-01-01_00-10-00", 600, EVENT_END, END_RESTORED, &end)),
            ),
        )
        .unwrap();
        assert_eq!(last_model_state(&dir, "abc123"), Some(serde_json::json!({"a": 2.5})));
        assert_eq!(last_model_state(&dir, "different"), None);
        let interrupted = row(
            "2026-01-02_00-10-00",
            600,
            EVENT_END,
            END_INTERRUPTED,
            &Frame::default(),
        );
        fs::write(
            dir.join(file_name("2026-01-02_00-00-00", 1)),
            format!("{header}\n{}\n", encode_row(&interrupted)),
        )
        .unwrap();
        assert_eq!(last_model_state(&dir, "abc123"), Some(serde_json::json!({"a": 2.5})));
        assert_eq!(last_model_state(&directory("state-empty"), "abc123"), None);
    }

    #[test]
    fn clocks_are_none_for_a_file_that_never_saw_the_battery() {
        let mut off = Frame::default();
        off.set_text(STATUS, "OL");
        let text = format!(
            "{}\n{}\n",
            encode_row(&metrics::header()),
            encode_row(&row("2026-01-01_00-00-00", 0, "start", "", &off))
        );
        assert_eq!(
            clocks(&Table::parse(&text), parse_stamp("2026-01-01_00-05-00").unwrap()),
            None
        );
    }

    #[test]
    fn clocks_count_only_the_time_spent_on_battery() {
        let mut on = Frame::default();
        on.set_text(STATUS, "OB DISCHRG");
        let mut off = Frame::default();
        off.set_text(STATUS, "OL");
        let text = format!(
            "{}\n{}\n{}\n{}\n",
            encode_row(&metrics::header()),
            encode_row(&row("2026-01-01_00-00-00", 0, "start", "", &on)),
            encode_row(&row("2026-01-01_00-01-00", 60, "", "", &on)),
            encode_row(&row("2026-01-01_00-02-00", 120, "", "", &off)),
        );
        let table = Table::parse(&text);
        let now = parse_stamp("2026-01-01_00-05-00").unwrap();
        assert_eq!(
            clocks(&table, now),
            Some((Duration::from_secs(120), Duration::from_secs(240), false))
        );
        assert_eq!(clocks(&Table::default(), now), None);
        let flapping = format!(
            "{}\n{}\n{}\n{}\n{}\n{}\n",
            encode_row(&metrics::header()),
            encode_row(&row("2026-01-01_00-00-00", 0, "start", "", &on)),
            encode_row(&row("2026-01-01_00-00-30", 30, "", "", &on)),
            encode_row(&row("2026-01-01_00-00-31", 31, "", "", &off)),
            encode_row(&row("2026-01-01_00-02-10", 130, "", "", &off)),
            encode_row(&row("2026-01-01_00-02-11", 131, "", "", &on)),
        );
        let later = parse_stamp("2026-01-01_00-02-21").unwrap();
        assert_eq!(
            clocks(&Table::parse(&flapping), later),
            Some((Duration::from_secs(41), Duration::ZERO, false))
        );
    }

    #[test]
    fn clocks_report_a_shed_decision_already_on_record() {
        let mut on = Frame::default();
        on.set_text(STATUS, "OB");
        let text = format!(
            "{}\n{}\n{}\n",
            encode_row(&metrics::header()),
            encode_row(&row("2026-01-01_00-00-00", 0, "start", "", &on)),
            encode_row(&row(
                "2026-01-01_00-02-00",
                120,
                "decision",
                "shed shed time reached",
                &on
            )),
        );
        let (_, _, shed) = clocks(&Table::parse(&text), parse_stamp("2026-01-01_00-05-00").unwrap()).unwrap();
        assert!(shed);
    }

    #[test]
    fn the_file_name_and_stamp_agree() {
        assert_eq!(
            file_name("2026-11-12_14-03-27", 1),
            "rackmains_outage_2026-11-12_14-03-27_1.csv"
        );
        assert!(parse_stamp("2026-11-12_14-03-27").is_some());
    }
}
