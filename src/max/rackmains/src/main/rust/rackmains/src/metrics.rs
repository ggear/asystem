use std::collections::HashMap;

use chrono::NaiveDate;
use serde_json::{json, Map, Value};

pub const BATTERY_AGE_DUE_DAYS: i64 = 1095;

pub const COLUMN_TIME: &str = "time";
pub const COLUMN_ELAPSED: &str = "elapsed_seconds";
pub const COLUMN_EVENT: &str = "event";
pub const COLUMN_DETAIL: &str = "detail";

pub const MAINS_INPUT_VOLTS: &str = "rackmains_mains_input_volts";
pub const BATTERY_LOW: &str = "rackmains_battery_low";
pub const BATTERY_CHARGE_PCT: &str = "rackmains_battery_charge_pct";
pub const BATTERY_REPLACE: &str = "rackmains_battery_replace_due";
pub const BATTERY_CHARGING: &str = "rackmains_battery_charging";
pub const UPS_PROBLEM: &str = "rackmains_ups_problem";
pub const UPS_CALIBRATING: &str = "rackmains_ups_calibrating";
pub const UPS_BOOST: &str = "rackmains_ups_boost";
pub const UPS_TRIM: &str = "rackmains_ups_trim";
pub const CLOCK: &str = "clock_epoch_seconds";
pub const READ_FAILURES: &str = "rackmains_read_failures";
pub const LAST_READ: &str = "rackmains_read_last_epoch_seconds";
pub const BATTERY_AGE_DAYS: &str = "rackmains_battery_age_days";
pub const BATTERY_AGE_DUE: &str = "rackmains_battery_age_due";
pub const BATTERY_VOLTS: &str = "rackmains_battery_volts";
pub const UTILISATION: &str = "rackmains_output_load_pct";
pub const STATUS: &str = "rackmains_ups_status";
pub const MAINS_PRESENT: &str = "rackmains_mains_present";
pub const LAST_OUTAGE_SECONDS: &str = "rackmains_outage_last_duration_seconds";
pub const LAST_OUTAGE_MIN_VOLTS: &str = "rackmains_outage_last_battery_min_volts";
pub const LAST_OUTAGE_END: &str = "rackmains_outage_last_end_epoch_seconds";
pub const GUARD_STATE: &str = "rackmains_guard_state";
pub const GUARD_LIVE: &str = "rackmains_guard_live";
pub const GUARD_MAINS_SECONDS: &str = "rackmains_guard_mains_seconds";
pub const GUARD_BATTERY_SECONDS: &str = "rackmains_guard_battery_seconds";
pub const GUARD_FAILED_HOSTS: &str = "rackmains_guard_failed_hosts";
pub const GUARD_LAST_ACTION: &str = "rackmains_guard_last_action_result";
pub const GUARD_SHED_BATTERY: &str = "rackmains_guard_shed_battery_seconds";
pub const GUARD_RESTORE_MAINS: &str = "rackmains_guard_restore_mains_seconds";
pub const GUARD_SHED_RUNTIME: &str = "rackmains_guard_shed_runtime_seconds";
pub const BATTERY_ENERGY_REMAINING_PCT: &str = "rackmains_battery_energy_remaining_pct";
pub const BATTERY_RUNTIME_REMAINING_SECONDS: &str = "rackmains_battery_runtime_remaining_seconds";
pub const BATTERY_ENERGY_USED_WH: &str = "rackmains_battery_energy_used_wh";
pub const MODEL_REFIT_DUE: &str = "rackmains_model_refit_due";
pub const MODEL_REFIT_REASON_CODE: &str = "rackmains_model_refit_reason_code";
pub const MODEL_STATE: &str = "rackmains_battery_state";
pub const PLUG_POWER_STATE: &str = "rackmains_plug_power_state";
pub const PLUG_WATTS: &str = "rackmains_plug_watts";
pub const PLUG_VOLTS: &str = "rackmains_plug_volts";
pub const PLUG_AMPS: &str = "rackmains_plug_amps";
pub const PLUG_ENERGY: &str = "rackmains_plug_energy_today_wh";

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Float,
    Int,
    Text,
}

pub struct Column {
    pub name: &'static str,
    pub kind: Kind,
    pub mqtt: bool,
    pub declared: bool,
}

const fn column(name: &'static str, kind: Kind) -> Column {
    Column {
        name,
        kind,
        mqtt: true,
        declared: true,
    }
}

const fn later(name: &'static str, kind: Kind) -> Column {
    Column {
        name,
        kind,
        mqtt: true,
        declared: false,
    }
}

const fn recorded(name: &'static str, kind: Kind) -> Column {
    Column {
        name,
        kind,
        mqtt: false,
        declared: false,
    }
}

pub const COLUMNS: &[Column] = &[
    column(CLOCK, Kind::Float),
    column(READ_FAILURES, Kind::Int),
    column(LAST_READ, Kind::Float),
    column("rackmains_mains_input_volts", Kind::Float),
    column("rackmains_mains_input_fault_volts", Kind::Float),
    column("rackmains_output_volts", Kind::Float),
    column("rackmains_output_hertz", Kind::Float),
    column(UTILISATION, Kind::Int),
    column(BATTERY_VOLTS, Kind::Float),
    column(BATTERY_CHARGE_PCT, Kind::Int),
    column(BATTERY_CHARGING, Kind::Int),
    column(BATTERY_LOW, Kind::Int),
    column(BATTERY_REPLACE, Kind::Int),
    column(BATTERY_AGE_DAYS, Kind::Int),
    column(BATTERY_AGE_DUE, Kind::Int),
    later(BATTERY_ENERGY_REMAINING_PCT, Kind::Int),
    later(BATTERY_RUNTIME_REMAINING_SECONDS, Kind::Int),
    column(STATUS, Kind::Text),
    column(MAINS_PRESENT, Kind::Int),
    column(UPS_PROBLEM, Kind::Int),
    column(UPS_CALIBRATING, Kind::Int),
    column(UPS_BOOST, Kind::Int),
    column(UPS_TRIM, Kind::Int),
    column(LAST_OUTAGE_SECONDS, Kind::Int),
    column(LAST_OUTAGE_MIN_VOLTS, Kind::Float),
    column(LAST_OUTAGE_END, Kind::Float),
    column(GUARD_STATE, Kind::Text),
    column(GUARD_LIVE, Kind::Int),
    column(GUARD_MAINS_SECONDS, Kind::Int),
    column(GUARD_BATTERY_SECONDS, Kind::Int),
    column(GUARD_FAILED_HOSTS, Kind::Text),
    column(GUARD_LAST_ACTION, Kind::Text),
    later(BATTERY_ENERGY_USED_WH, Kind::Float),
    later(MODEL_REFIT_DUE, Kind::Int),
    later(MODEL_REFIT_REASON_CODE, Kind::Int),
    recorded(GUARD_SHED_BATTERY, Kind::Int),
    recorded(GUARD_RESTORE_MAINS, Kind::Int),
    recorded(GUARD_SHED_RUNTIME, Kind::Int),
    recorded(MODEL_STATE, Kind::Text),
    recorded(PLUG_POWER_STATE, Kind::Text),
    recorded(PLUG_WATTS, Kind::Int),
    recorded(PLUG_VOLTS, Kind::Int),
    recorded(PLUG_AMPS, Kind::Float),
    recorded(PLUG_ENERGY, Kind::Int),
];

#[derive(Clone, Default, Debug, PartialEq)]
pub struct Frame {
    values: HashMap<&'static str, Value>,
}

impl Frame {
    pub fn set_number(&mut self, name: &'static str, value: f64) {
        match kind(name) {
            Some(Kind::Int) => self.set(name, json!(value.round() as i64)),
            _ => self.set(name, json!(value)),
        }
    }

    pub fn set_int(&mut self, name: &'static str, value: i64) {
        self.set(name, json!(value));
    }

    pub fn set_bool(&mut self, name: &'static str, value: bool) {
        self.set(name, json!(i64::from(value)));
    }

    pub fn set_text(&mut self, name: &'static str, value: &str) {
        self.set(name, json!(value));
    }

    pub fn set_battery_age(&mut self, days: i64) {
        self.set_int(BATTERY_AGE_DAYS, days);
        self.set_bool(BATTERY_AGE_DUE, days >= BATTERY_AGE_DUE_DAYS);
    }

    pub fn get(&self, name: &str) -> Option<&Value> {
        self.values.get(name)
    }

    pub fn number(&self, name: &str) -> Option<f64> {
        self.get(name).and_then(Value::as_f64)
    }

    pub fn flag(&self, name: &str) -> bool {
        self.get(name).and_then(Value::as_i64) == Some(1)
    }

    pub fn text(&self, name: &str) -> Option<&str> {
        self.get(name).and_then(Value::as_str)
    }

    pub fn payload(&self) -> Map<String, Value> {
        COLUMNS
            .iter()
            .filter(|column| column.mqtt)
            .filter_map(|column| Some((column.name.to_string(), self.values.get(column.name)?.clone())))
            .collect()
    }

    pub fn merge(&mut self, other: &Frame) {
        for (name, value) in &other.values {
            self.values.insert(name, value.clone());
        }
    }

    pub fn merge_sticky(&mut self, other: &Frame) {
        for (name, value) in &other.values {
            if sticky(name) {
                self.values.insert(name, value.clone());
            }
        }
    }

    pub fn cells(&self) -> Vec<String> {
        COLUMNS
            .iter()
            .map(|column| self.values.get(column.name).map(cell).unwrap_or_default())
            .collect()
    }

    fn set(&mut self, name: &'static str, value: Value) {
        self.values.insert(name, value);
    }
}

pub fn header() -> Vec<String> {
    [COLUMN_TIME, COLUMN_ELAPSED, COLUMN_EVENT, COLUMN_DETAIL]
        .into_iter()
        .map(str::to_string)
        .chain(COLUMNS.iter().map(|column| column.name.to_string()))
        .collect()
}

pub fn battery_age_days(installed: &str, today: NaiveDate) -> Result<i64, String> {
    NaiveDate::parse_from_str(installed, "%Y-%m-%d")
        .map(|date| (today - date).num_days())
        .map_err(|err| format!("invalid battery install date [{installed}] [{err}]"))
}

pub fn cell(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        other => other.to_string(),
    }
}

fn kind(name: &str) -> Option<Kind> {
    COLUMNS
        .iter()
        .find(|column| column.name == name)
        .map(|column| column.kind)
}

fn sticky(name: &str) -> bool {
    name != MODEL_STATE && !name.starts_with("rackmains_plug_")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{BrokerSchema, RackMains};

    #[test]
    fn column_names_are_unique() {
        let mut names: Vec<&str> = COLUMNS.iter().map(|column| column.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), COLUMNS.len());
    }

    #[test]
    fn a_whole_number_metric_is_an_integer_and_a_float_stays_one() {
        let mut frame = Frame::default();
        frame.set_number(UTILISATION, 12.6);
        frame.set_number(BATTERY_VOLTS, 13.0);
        assert_eq!(frame.get(UTILISATION), Some(&json!(13)));
        assert_eq!(cell(frame.get(BATTERY_VOLTS).unwrap()), "13.0");
    }

    #[test]
    fn bools_are_integers_in_payload_and_cells() {
        let mut frame = Frame::default();
        frame.set_bool(MAINS_PRESENT, true);
        frame.set_bool(UPS_BOOST, false);
        assert_eq!(frame.payload()[MAINS_PRESENT], json!(1));
        assert_eq!(frame.payload()[UPS_BOOST], json!(0));
    }

    #[test]
    fn the_payload_omits_what_is_absent_and_what_is_only_recorded() {
        let mut frame = Frame::default();
        frame.set_text(STATUS, "OL");
        frame.set_text(MODEL_STATE, "{}");
        frame.set_int(PLUG_WATTS, 90);
        let payload = frame.payload();
        assert_eq!(payload.keys().collect::<Vec<_>>(), vec![STATUS]);
    }

    #[test]
    fn the_payload_follows_the_column_order() {
        let mut frame = Frame::default();
        frame.set_text(STATUS, "OL");
        frame.set_number(CLOCK, 1.5);
        frame.set_int(READ_FAILURES, 0);
        assert_eq!(
            frame.payload().keys().map(String::as_str).collect::<Vec<_>>(),
            vec![CLOCK, READ_FAILURES, STATUS]
        );
    }

    #[test]
    fn cells_are_blank_until_reported_and_repeat_after() {
        let mut last = Frame::default();
        let mut first = Frame::default();
        first.set_number(BATTERY_VOLTS, 13.4);
        last.merge_sticky(&first);
        last.merge_sticky(&Frame::default());
        let cells = last.cells();
        let index = COLUMNS.iter().position(|column| column.name == BATTERY_VOLTS).unwrap();
        assert_eq!(cells[index], "13.4");
        assert_eq!(cells.iter().filter(|cell| !cell.is_empty()).count(), 1);
    }

    #[test]
    fn plug_and_model_state_columns_do_not_carry_over() {
        let mut last = Frame::default();
        let mut row = Frame::default();
        row.set_int(PLUG_WATTS, 90);
        row.set_text(MODEL_STATE, "{}");
        row.set_bool(MAINS_PRESENT, true);
        last.merge_sticky(&row);
        assert!(last.get(PLUG_WATTS).is_none());
        assert!(last.get(MODEL_STATE).is_none());
        assert!(last.get(MAINS_PRESENT).is_some());
    }

    #[test]
    fn every_declared_column_is_in_the_schema_and_nothing_else() {
        let mut declared: Vec<String> = COLUMNS
            .iter()
            .filter(|column| column.declared)
            .map(|column| column.name.to_string())
            .collect();
        declared.sort();
        let payloads = RackMains.payloads();
        let mut reflected: Vec<String> = payloads[0]
            .root
            .members
            .iter()
            .map(|member| member.key.clone())
            .filter(|key| key != crate::schema::KEY_TIMESTAMP && key != crate::schema::KEY_PERIOD_MS)
            .collect();
        reflected.sort();
        assert_eq!(declared, reflected);
    }

    #[test]
    fn every_nut_sample_key_is_a_published_column() {
        for sample in &crate::nut::SAMPLES {
            assert!(
                COLUMNS.iter().any(|column| column.name == sample.key && column.mqtt),
                "sample [{}]",
                sample.key
            );
        }
    }

    #[test]
    fn the_header_leads_with_the_envelope() {
        let header = header();
        assert_eq!(&header[..4], ["time", "elapsed_seconds", "event", "detail"]);
        assert_eq!(header.len(), 4 + COLUMNS.len());
    }

    #[test]
    fn battery_age_counts_whole_days_and_rejects_a_bad_date() {
        let today = NaiveDate::from_ymd_opt(2026, 11, 12).unwrap();
        assert_eq!(battery_age_days("2024-11-12", today).unwrap(), 730);
        assert!(battery_age_days("12/11/2024", today).is_err());
        let mut frame = Frame::default();
        frame.set_battery_age(BATTERY_AGE_DUE_DAYS - 1);
        assert!(!frame.flag(BATTERY_AGE_DUE));
        frame.set_battery_age(BATTERY_AGE_DUE_DAYS);
        assert!(frame.flag(BATTERY_AGE_DUE));
    }

    #[test]
    fn the_discovery_entities_and_the_declared_columns_name_the_same_keys() {
        fn collect(dir: &std::path::Path, found: &mut Vec<Value>) {
            for entry in std::fs::read_dir(dir).unwrap().flatten() {
                let path = entry.path();
                if path.is_dir() {
                    collect(&path, found);
                } else if path.extension().is_some_and(|extension| extension == "json") {
                    found.push(serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap());
                }
            }
        }
        let mut entities = Vec::new();
        collect(
            &std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../resources/image/broker/homeassistant"),
            &mut entities,
        );
        assert!(!entities.is_empty(), "no discovery entities found");
        let declared: std::collections::BTreeSet<&str> = COLUMNS
            .iter()
            .filter(|column| column.mqtt && column.declared)
            .map(|column| column.name)
            .collect();
        let mut entity_keys = std::collections::BTreeSet::new();
        for entity in &entities {
            entity_keys.insert(entity["unique_id"].as_str().unwrap().to_string());
            let template = entity["value_template"].as_str().unwrap();
            for key in template.split("value_json['").skip(1) {
                entity_keys.insert(key.split('\'').next().unwrap().to_string());
            }
        }
        let entity_keys: std::collections::BTreeSet<&str> = entity_keys.iter().map(String::as_str).collect();
        let unpublished: Vec<_> = entity_keys.difference(&declared).collect();
        let unexposed: Vec<_> = declared
            .difference(&entity_keys)
            .filter(|name| **name != CLOCK)
            .collect();
        assert!(
            unpublished.is_empty(),
            "entities with no declared column {unpublished:?}"
        );
        assert!(unexposed.is_empty(), "declared columns with no entity {unexposed:?}");
    }
}
