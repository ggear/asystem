use std::io::Write;
use std::path::Path;
use std::thread;
use std::time::Duration;

use crate::metrics::{
    BATTERY_VOLTS, COLUMN_DETAIL, COLUMN_ELAPSED, COLUMN_EVENT, GUARD_STATE, PLUG_WATTS, STATUS, UTILISATION,
};
use crate::nut::describe;
use crate::outage::{self, OutageFile, Table, EVENT_START};

const TAIL_POLL: Duration = Duration::from_secs(1);

pub fn list(dir: &Path, limit: usize) -> Vec<String> {
    let mut stems: Vec<String> = outage::files(dir).into_iter().map(|file| file.stem).collect();
    stems.dedup();
    let skip = stems.len().saturating_sub(limit);
    stems
        .into_iter()
        .skip(skip)
        .map(|stem| {
            let parts: Vec<OutageFile> = outage::files(dir)
                .into_iter()
                .filter(|file| file.stem == stem)
                .collect();
            summarise(&stem, &parts)
        })
        .collect()
}

pub fn field<'a>(detail: &'a str, name: &str) -> &'a str {
    detail
        .split_once(&format!("{name} ["))
        .and_then(|(_, rest)| rest.split_once(']'))
        .map_or("", |(value, _)| value)
}

pub fn format_row(table: &Table, row: &[String]) -> String {
    let cell = |name: &str| table.cell(row, name);
    format!(
        "{:>6}s {:<30} {:>6}V {:>3}% {:<10} {:>5}W {} {}",
        cell(COLUMN_ELAPSED),
        describe(cell(STATUS)),
        cell(BATTERY_VOLTS),
        cell(UTILISATION),
        cell(GUARD_STATE),
        cell(PLUG_WATTS),
        cell(COLUMN_EVENT),
        cell(COLUMN_DETAIL),
    )
}

pub fn tail(dir: &Path, file: Option<&Path>, follow: bool, out: &mut dyn Write) -> Result<(), String> {
    let mut printed = 0usize;
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
        }
        let mut seen = 0usize;
        let mut ended = false;
        for part in &parts {
            let table = Table::read(&part.path)?;
            for row in &table.rows {
                if seen >= printed {
                    writeln!(out, "{}", format_row(&table, row)).map_err(|err| format!("failed to write [{err}]"))?;
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

fn summarise(stem: &str, parts: &[OutageFile]) -> String {
    let mut rows = 0usize;
    let mut kind = "outage";
    let mut end = String::from("open");
    for part in parts {
        let Ok(table) = Table::read(&part.path) else { continue };
        rows += table.rows.len();
        if let Some(first) = table
            .rows
            .first()
            .filter(|first| table.cell(first, COLUMN_EVENT) == EVENT_START)
        {
            if table.cell(first, COLUMN_DETAIL).contains("drill [") {
                kind = "drill";
            }
        }
        if let Some(last) = table.rows.last().filter(|_| table.ended()) {
            let detail = table.cell(last, COLUMN_DETAIL);
            end = format!(
                "{} seconds [{}] min_volts [{}] hosts_shed [{}]",
                field(detail, "reason"),
                field(detail, "seconds_on_battery"),
                field(detail, "battery_min_volts"),
                field(detail, "hosts_shed"),
            );
            if detail == outage::END_INTERRUPTED || detail == outage::END_ABORTED {
                end = detail.to_string();
            }
        }
    }
    format!("{stem} {kind} rows [{rows}] ended [{end}]")
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
    fn list_shows_each_outage_its_kind_and_how_it_ended() {
        let dir = directory("list");
        write(
            &dir,
            "2026-01-01_00-00-00",
            1,
            &[
                ("2026-01-01_00-00-00", "start", "drill [a] mode [hold]"),
                (
                    "2026-01-01_00-01-00",
                    outage::EVENT_END,
                    "reason [restored] seconds_on_battery [60] battery_min_volts [12] hosts_shed [3]",
                ),
            ],
        );
        write(&dir, "2026-01-02_00-00-00", 1, &[("2026-01-02_00-00-00", "start", "")]);
        let lines = list(&dir, 10);
        assert_eq!(lines.len(), 2);
        assert!(lines[0].contains("drill") && lines[0].contains("restored seconds [60] min_volts [12] hosts_shed [3]"));
        assert!(lines[1].contains("outage") && lines[1].contains("ended [open]"));
        assert_eq!(list(&dir, 1).len(), 1);
    }

    #[test]
    fn tail_prints_every_row_of_the_newest_outage_across_its_parts_once() {
        let dir = directory("tail");
        write(&dir, "2026-01-01_00-00-00", 1, &[("a", "start", "")]);
        write(&dir, "2026-01-02_00-00-00", 1, &[("b", "start", ""), ("c", "", "")]);
        write(
            &dir,
            "2026-01-02_00-00-00",
            2,
            &[("d", outage::EVENT_END, "reason [restored]")],
        );
        let mut out = Vec::new();
        tail(&dir, None, true, &mut out).unwrap();
        let text = String::from_utf8(out).unwrap();
        assert_eq!(text.lines().count(), 3);
        assert!(text.contains("start") && text.contains("end"));
    }

    #[test]
    fn tail_of_a_given_file_prints_that_file() {
        let dir = directory("tail-file");
        write(
            &dir,
            "2026-01-01_00-00-00",
            1,
            &[("a", "start", ""), ("b", outage::EVENT_END, "")],
        );
        write(&dir, "2026-01-02_00-00-00", 1, &[("c", "start", "")]);
        let path = dir.join(outage::file_name("2026-01-01_00-00-00", 1));
        let mut out = Vec::new();
        tail(&dir, Some(&path), false, &mut out).unwrap();
        assert_eq!(String::from_utf8(out).unwrap().lines().count(), 2);
    }

    #[test]
    fn tail_of_an_empty_directory_is_an_error() {
        assert!(tail(&directory("tail-empty"), None, false, &mut Vec::new()).is_err());
    }
}
