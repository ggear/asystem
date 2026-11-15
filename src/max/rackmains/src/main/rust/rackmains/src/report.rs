use std::io::Write;
use std::path::Path;
use std::thread;
use std::time::Duration;

use log::Level;

use crate::metrics::{
    BATTERY_VOLTS, CLOCK, COLUMN_DETAIL, COLUMN_ELAPSED, COLUMN_EVENT, COLUMN_TIME, GUARD_BATTERY_SECONDS,
    GUARD_MAINS_SECONDS, GUARD_RESTORE_MAINS, GUARD_SHED_BATTERY, GUARD_STATE, PLUG_WATTS, STATUS, UTILISATION,
};
use crate::nut::describe;
use crate::outage::{
    self, OutageFile, Table, EVENT_COMMAND, EVENT_DECISION, EVENT_END, EVENT_NOTE, EVENT_START, EVENT_STATUS,
};
use crate::{log_change, log_line, log_prefix, log_prefix_at};

const TAIL_POLL: Duration = Duration::from_secs(1);
const PROGRESS_SECONDS: u64 = 10;

pub fn list(dir: &Path, limit: usize) -> Vec<String> {
    let mut stems: Vec<String> = outage::files(dir).into_iter().map(|file| file.stem).collect();
    stems.dedup();
    let skip = stems.len().saturating_sub(limit);
    let rows: Vec<Vec<String>> = stems
        .into_iter()
        .skip(skip)
        .rev()
        .map(|stem| {
            let parts: Vec<OutageFile> = outage::files(dir)
                .into_iter()
                .filter(|file| file.stem == stem)
                .collect();
            summarise(&stem, &parts)
        })
        .collect();
    let mut table = comfy_table::Table::new();
    table.load_style(
        comfy_table::presets::ASCII_FULL_CONDENSED.header_separator(comfy_table::LineStyle::new('+', '=', '+', '+')),
    );
    table.set_header([
        "STARTED (OUTAGE-ID)",
        "FINISHED",
        "DURATION",
        "BATTERY",
        "TRIGGER",
        "TEST",
        "ROWS",
        "MIN VOLTS",
        "SHED",
        "RESULT",
    ]);
    for column in [2, 3, 6, 7, 8] {
        if let Some(column) = table.column_mut(column) {
            column.set_cell_alignment(comfy_table::CellAlignment::Right);
        }
    }
    table.add_rows(rows);
    table.to_string().lines().map(str::to_string).collect()
}

pub fn field<'a>(detail: &'a str, name: &str) -> &'a str {
    detail
        .split_once(&format!("{name} ["))
        .and_then(|(_, rest)| rest.split_once(']'))
        .map_or("", |(value, _)| value)
}

pub fn pairs(detail: &str) -> Vec<(String, String)> {
    let mut found = Vec::new();
    let mut rest = detail;
    while let Some(open) = rest.find('[') {
        let Some(close) = rest[open..].find(']') else { break };
        found.push((
            rest[..open].trim().to_string(),
            rest[open + 1..open + close].to_string(),
        ));
        rest = &rest[open + close + 1..];
    }
    found
}

fn words(key: &str) -> String {
    key.replace('_', " ")
}

pub fn event_lines(event: &str, detail: &str) -> Vec<String> {
    match event {
        EVENT_STATUS => {
            let (from, to) = (field(detail, "from"), field(detail, "to"));
            vec![log_change("ups status changed", from, to)]
        }
        EVENT_DECISION => {
            let (head, counters) = detail.split_once(" guard_battery_seconds").unwrap_or((detail, ""));
            let mut lines = vec![log_line("guard decision", head)];
            lines.extend(
                pairs(&format!("guard_battery_seconds{counters}"))
                    .into_iter()
                    .filter(|(key, _)| key != "guard_live")
                    .map(|(key, value)| log_line(&words(&key), &value)),
            );
            lines
        }
        EVENT_COMMAND => pairs(detail)
            .into_iter()
            .filter(|(key, value)| (key != "reason" || !value.is_empty()) && (key != "took_ms" || value != "0"))
            .map(|(key, value)| {
                let label = if key == "command" {
                    "guard command".to_string()
                } else {
                    format!("guard command {}", words(&key))
                };
                log_line(&label, &value)
            })
            .collect(),
        EVENT_START => pairs(detail)
            .into_iter()
            .map(|(key, value)| {
                let value = if key == "model" {
                    value.split(' ').next().unwrap_or("").to_string()
                } else {
                    value
                };
                log_line(&format!("outage start {}", words(&key)), &value)
            })
            .collect(),
        EVENT_NOTE => vec![log_line("guard note", detail)],
        EVENT_END => pairs(detail)
            .into_iter()
            .map(|(key, value)| log_line(&format!("outage end {}", words(&key)), &value))
            .collect(),
        _ => Vec::new(),
    }
}

pub fn progress_lines(table: &Table, row: &[String]) -> Vec<String> {
    let shown = |name: &str, unit: &str| {
        let value = table.cell(row, name);
        if value.is_empty() {
            "unknown".to_string()
        } else {
            format!("{value}{unit}")
        }
    };
    let clock = |name: &str, limit: &str| {
        let value = table.cell(row, name);
        if value.is_empty() {
            "unknown".to_string()
        } else {
            format!("{value} of {limit}", limit = table.cell(row, limit))
        }
    };
    [
        ("ups state", describe(table.cell(row, STATUS))),
        ("output load pct", shown(UTILISATION, "")),
        ("battery volts", shown(BATTERY_VOLTS, "")),
        ("plug watts", shown(PLUG_WATTS, "")),
        ("guard state", shown(GUARD_STATE, "")),
        (
            "guard battery seconds",
            clock(GUARD_BATTERY_SECONDS, GUARD_SHED_BATTERY),
        ),
        ("guard mains seconds", clock(GUARD_MAINS_SECONDS, GUARD_RESTORE_MAINS)),
    ]
    .iter()
    .map(|(label, value)| log_line(&format!("progress {label}"), value))
    .collect()
}

#[derive(Debug, Default)]
pub struct Progress {
    next: u64,
    last: Vec<String>,
}

pub fn row_lines(table: &Table, row: &[String], progress: &mut Progress) -> Vec<String> {
    let event = table.cell(row, COLUMN_EVENT);
    if !event.is_empty() {
        return event_lines(event, table.cell(row, COLUMN_DETAIL));
    }
    let elapsed = table.cell(row, COLUMN_ELAPSED).parse::<u64>().unwrap_or(0);
    if elapsed < progress.next {
        return Vec::new();
    }
    progress.next = elapsed + PROGRESS_SECONDS;
    let lines = progress_lines(table, row);
    let changed = lines
        .iter()
        .enumerate()
        .filter(|(index, line)| progress.last.get(*index) != Some(line))
        .map(|(_, line)| line.clone())
        .collect();
    progress.last = lines;
    changed
}

pub fn tail(dir: &Path, file: Option<&Path>, follow: bool, out: &mut dyn Write) -> Result<(), String> {
    let mut printed = 0usize;
    let mut progress = Progress::default();
    let mut current: Option<String> = None;
    loop {
        let parts: Vec<OutageFile> = if let Some(path) = file {
            let parent = path
                .parent()
                .filter(|parent| !parent.as_os_str().is_empty())
                .unwrap_or(Path::new("."));
            outage::files(parent)
                .into_iter()
                .filter(|part| part.path.file_name() == path.file_name())
                .collect()
        } else {
            let all = outage::files(dir);
            let stem = all.last().map(|part| part.stem.clone());
            all.into_iter()
                .filter(|part| Some(&part.stem) == stem.as_ref())
                .collect()
        };
        let stem = parts.first().map(|part| part.stem.clone());
        if stem != current {
            current = stem;
            printed = 0;
            progress = Progress::default();
        }
        let mut seen = 0usize;
        let mut ended = false;
        for part in &parts {
            let table = Table::read(&part.path)?;
            for row in &table.rows {
                if seen >= printed {
                    let prefix = table
                        .cell(row, CLOCK)
                        .parse::<f64>()
                        .map_or_else(|_| log_prefix(Level::Info), |at| log_prefix_at(Level::Info, at));
                    for line in row_lines(&table, row, &mut progress) {
                        writeln!(out, "{prefix} {line}").map_err(|err| format!("failed to write [{err}]"))?;
                    }
                    printed += 1;
                }
                seen += 1;
            }
            ended = table.ended();
        }
        if !follow || (ended && !parts.is_empty()) {
            return if parts.is_empty() {
                Err(format!("no outage files [{}]", dir.display()))
            } else {
                Ok(())
            };
        }
        thread::sleep(TAIL_POLL);
    }
}

fn hms(seconds: u64) -> String {
    format!("{:02}h{:02}m{:02}s", seconds / 3600, seconds % 3600 / 60, seconds % 60)
}

fn summarise(stem: &str, parts: &[OutageFile]) -> Vec<String> {
    let mut rows = 0usize;
    let mut trigger = "outage";
    let mut test = String::new();
    let mut end: Option<(String, String)> = None;
    let mut elapsed = 0u64;
    for part in parts {
        let Ok(table) = Table::read(&part.path) else { continue };
        rows += table.rows.len();
        if let Some(first) = table
            .rows
            .first()
            .filter(|first| table.cell(first, COLUMN_EVENT) == EVENT_START)
        {
            let detail = table.cell(first, COLUMN_DETAIL);
            if detail.contains("drill [") {
                trigger = "drill";
                test = field(detail, "mode").to_string();
            }
        }
        if let Some(last) = table.rows.last() {
            elapsed = table.cell(last, COLUMN_ELAPSED).parse().unwrap_or(elapsed);
            if table.ended() {
                end = Some((
                    table.cell(last, COLUMN_TIME).to_string(),
                    table.cell(last, COLUMN_DETAIL).to_string(),
                ));
            }
        }
    }
    let dash = |value: String| if value.is_empty() { "-".to_string() } else { value };
    let detail = end.as_ref().map_or("", |(_, detail)| detail.as_str());
    let result = match &end {
        None => "open".to_string(),
        Some((_, detail)) if field(detail, "reason").is_empty() => detail.clone(),
        Some((_, detail)) => field(detail, "reason").to_string(),
    };
    let number = |name: &str, unit: &str| {
        let value = field(detail, name);
        if value.is_empty() {
            "-".to_string()
        } else {
            format!("{value}{unit}")
        }
    };
    vec![
        stem.to_string(),
        dash(end.as_ref().map_or_else(String::new, |(time, _)| time.clone())),
        hms(elapsed),
        field(detail, "seconds_on_battery")
            .parse::<u64>()
            .map_or_else(|_| "-".to_string(), hms),
        trigger.to_string(),
        dash(test),
        rows.to_string(),
        number("battery_min_volts", " V"),
        number("hosts_shed", ""),
        result,
    ]
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::*;
    use crate::metrics::{self, Frame};

    fn directory(name: &str) -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!("rackmains-report-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn write(dir: &Path, stem: &str, number: u32, rows: &[(&str, &str, &str)]) {
        let mut text = outage::encode_row(&metrics::header());
        text.push('\n');
        for (stamp, event, detail) in rows {
            text.push_str(&outage::encode_row(&outage::row(
                stamp,
                1,
                event,
                detail,
                &Frame::default(),
            )));
            text.push('\n');
        }
        fs::write(dir.join(outage::file_name(stem, number)), text).unwrap();
    }

    #[test]
    fn a_field_is_read_out_of_a_bracketed_detail() {
        let detail = "reason [restored] seconds_on_battery [90] hosts_shed [4]";
        assert_eq!(field(detail, "seconds_on_battery"), "90");
        assert_eq!(field(detail, "missing"), "");
    }

    #[test]
    fn list_shows_each_outage_newest_first_as_a_boxed_table_like_the_backups_list() {
        let dir = directory("list");
        write(
            &dir,
            "2026-01-01_00-00-00",
            1,
            &[
                ("2026-01-01_00-00-00", "start", "drill [a] mode [brownout-shed-wake]"),
                (
                    "2026-01-01_00-01-00",
                    outage::EVENT_END,
                    "reason [restored] seconds_on_battery [3725] battery_min_volts [11.8] hosts_shed [3]",
                ),
            ],
        );
        write(&dir, "2026-01-02_00-00-00", 1, &[("2026-01-02_00-00-00", "start", "")]);
        let lines = list(&dir, 10);
        assert_eq!(lines.len(), 6);
        assert!(lines[0].starts_with("+--") && lines[0].ends_with("--+") && lines[2].starts_with("+=="));
        assert!(lines[1].starts_with("| STARTED (OUTAGE-ID) |") && lines[1].contains("| RESULT"));
        assert!(lines[3].contains("2026-01-02_00-00-00") && lines[3].contains("open") && lines[3].contains("outage"));
        assert!(lines[4].contains("2026-01-01_00-00-00") && lines[4].contains("2026-01-01_00-01-00"));
        assert!(
            lines[4].contains("01h02m05s") && lines[4].contains("brownout-shed-wake") && lines[4].contains("11.8 V")
        );
        assert!(lines[4].trim_end().ends_with("restored |"));
        assert!(lines.iter().all(|line| line.len() == lines[0].len()));
        assert_eq!(list(&dir, 1).len(), 5);
        assert_eq!(list(&directory("list-empty"), 10).len(), 4);
    }

    #[test]
    fn tail_starts_with_the_start_row_and_stamps_each_line_with_its_own_time() {
        let dir = directory("tail-start");
        let mut text = outage::encode_row(&metrics::header());
        text.push('\n');
        for (clock, event, detail) in [
            (
                1_700_000_000.25,
                "start",
                "version [10.200.2070] model [rackmains_ups_battery c517] pollfreq [1] drill [d] mode [blip-watch]",
            ),
            (1_700_000_060.75, "note", "later"),
        ] {
            let mut frame = Frame::default();
            frame.set_number(metrics::CLOCK, clock);
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_00-00-00",
                1,
                event,
                detail,
                &frame,
            )));
            text.push('\n');
        }
        text.push_str(&outage::encode_row(&outage::row(
            "2026-01-01_00-02-00",
            2,
            outage::EVENT_END,
            "reason [restored]",
            &Frame::default(),
        )));
        text.push('\n');
        fs::write(dir.join(outage::file_name("2026-01-01_00-00-00", 1)), text).unwrap();
        let mut out = Vec::new();
        tail(&dir, None, true, &mut out).unwrap();
        let text = String::from_utf8(out).unwrap();
        let lines: Vec<&str> = text.lines().collect();
        assert!(
            lines[0].contains("outage start version")
                && lines[0].starts_with(&log_prefix_at(Level::Info, 1_700_000_000.25))
        );
        assert!(
            text.contains("outage start model ") && text.contains("[rackmains_ups_battery]") && !text.contains("c517")
        );
        assert!(text.contains("outage start mode") && text.contains("[blip-watch]"));
        let note = lines.iter().find(|line| line.contains("guard note")).unwrap();
        assert!(note.starts_with(&log_prefix_at(Level::Info, 1_700_000_060.75)));
        assert_ne!(lines[0][..32], note[..32]);
    }

    #[test]
    fn a_detail_is_split_into_its_bracketed_pairs() {
        assert_eq!(
            pairs("host [max] command [asleep --shallow] status [0] reason []"),
            vec![
                ("host".to_string(), "max".to_string()),
                ("command".to_string(), "asleep --shallow".to_string()),
                ("status".to_string(), "0".to_string()),
                ("reason".to_string(), String::new()),
            ]
        );
        assert!(pairs("no brackets").is_empty());
    }

    #[test]
    fn each_event_becomes_one_fact_per_line_and_a_sample_row_only_on_the_progress_period() {
        let status = event_lines(EVENT_STATUS, "from [on mains] to [on battery, discharging]");
        assert_eq!(status.len(), 1);
        assert!(
            status[0].starts_with("ups status changed")
                && status[0].ends_with("[on mains] to [on battery, discharging]")
        );
        let decision = event_lines(
            EVENT_DECISION,
            "shed shed time reached guard_battery_seconds [200] guard_mains_seconds [0] guard_live [1]",
        );
        assert_eq!(decision.len(), 3);
        assert!(decision.iter().all(|line| !line.contains("guard live")));
        let command = event_lines(
            EVENT_COMMAND,
            "host [max] command [awake] status [0] reason [] took_ms [4]",
        );
        assert_eq!(command.len(), 4);
        assert!(command
            .iter()
            .any(|line| line.starts_with("guard command .") && line.ends_with("[awake]")));
        assert!(event_lines("", "").is_empty());
        let mut text = outage::encode_row(&metrics::header());
        text.push('\n');
        for (elapsed, volts) in [(0u64, 13.3), (4, 13.3), (12, 13.3), (24, 12.1)] {
            let mut frame = Frame::default();
            frame.set_number(metrics::BATTERY_VOLTS, volts);
            frame.set_int(metrics::GUARD_BATTERY_SECONDS, elapsed as i64);
            frame.set_int(metrics::GUARD_SHED_BATTERY, 120);
            text.push_str(&outage::encode_row(&outage::row(
                "2026-01-01_00-00-00",
                elapsed,
                "",
                "",
                &frame,
            )));
            text.push('\n');
        }
        let table = Table::parse(&text);
        let mut progress = Progress::default();
        let counts: Vec<usize> = table
            .rows
            .iter()
            .map(|row| row_lines(&table, row, &mut progress).len())
            .collect();
        assert_eq!(counts, vec![7, 0, 1, 2]);
        let mut progress = Progress::default();
        let heartbeat: Vec<String> = table
            .rows
            .iter()
            .flat_map(|row| row_lines(&table, row, &mut progress))
            .collect();
        assert!(heartbeat
            .iter()
            .any(|line| line.contains("progress guard battery seconds") && line.ends_with("[12 of 120]")));
    }

    #[test]
    fn tail_prints_the_events_of_the_newest_outage_across_its_parts_once() {
        let dir = directory("tail");
        write(&dir, "2026-01-01_00-00-00", 1, &[("a", "start", "")]);
        write(
            &dir,
            "2026-01-02_00-00-00",
            1,
            &[("b", "start", ""), ("c", "note", "hello")],
        );
        write(
            &dir,
            "2026-01-02_00-00-00",
            2,
            &[("d", outage::EVENT_END, "reason [restored]")],
        );
        let mut out = Vec::new();
        tail(&dir, None, true, &mut out).unwrap();
        let text = String::from_utf8(out).unwrap();
        assert_eq!(text.lines().count(), 2);
        assert!(text.contains("guard note") && text.contains("outage end reason") && text.contains("INFO"));
    }

    #[test]
    fn tail_of_a_given_file_prints_that_file() {
        let dir = directory("tail-file");
        write(
            &dir,
            "2026-01-01_00-00-00",
            1,
            &[("a", "start", ""), ("b", outage::EVENT_END, "reason [restored]")],
        );
        write(&dir, "2026-01-02_00-00-00", 1, &[("c", "start", "")]);
        let path = dir.join(outage::file_name("2026-01-01_00-00-00", 1));
        let mut out = Vec::new();
        tail(&dir, Some(&path), false, &mut out).unwrap();
        assert_eq!(String::from_utf8(out).unwrap().lines().count(), 1);
    }

    #[test]
    fn tail_of_an_empty_directory_is_an_error() {
        assert!(tail(&directory("tail-empty"), None, false, &mut Vec::new()).is_err());
    }
}
