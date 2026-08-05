use std::io::Write;

use serde::Serialize;

use crate::config::SensorConfig;

pub const MODULE: &str = "tempstat";

#[allow(dead_code)]
#[derive(Serialize, Clone, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Float,
    Int,
    Bool,
    Str,
    Obj,
    Any,
}

#[allow(dead_code)]
#[derive(Serialize, Clone, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    State,
    Command,
    Availability,
}

#[derive(Serialize)]
pub struct Dimension {
    pub key: String,
    pub desc: String,
    pub subject: bool,
}

#[derive(Serialize)]
pub struct Measure {
    pub key: String,
    pub kind: Kind,
    pub unit: String,
    pub desc: String,
    pub persist: bool,
}

#[derive(Serialize)]
pub struct Relation {
    pub path: String,
    pub desc: String,
    pub cadence: String,
    pub entities: Vec<String>,
    pub dimensions: Vec<Dimension>,
    pub measures: Vec<Measure>,
}

#[derive(Serialize)]
pub struct Member {
    pub key: String,
    pub kind: Kind,
    #[serde(rename = "enum", skip_serializing_if = "Vec::is_empty")]
    pub enum_values: Vec<String>,
    #[serde(skip_serializing_if = "is_false")]
    pub dynamic: bool,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub members: Vec<Member>,
}

#[derive(Serialize)]
pub struct Payload {
    pub role: Role,
    #[serde(rename = "match", skip_serializing_if = "String::is_empty")]
    pub match_glob: String,
    pub desc: String,
    pub root: Member,
}

#[derive(Serialize)]
pub struct DatabaseSection {
    pub relations: Vec<Relation>,
}

#[derive(Serialize)]
pub struct BrokerSection {
    pub payloads: Vec<Payload>,
}

#[derive(Serialize)]
pub struct Document {
    pub module: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub database: Option<DatabaseSection>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub broker: Option<BrokerSection>,
}

pub trait DatabaseSchema {
    fn relations(&self) -> Vec<Relation>;
}

pub trait BrokerSchema {
    fn payloads(&self) -> Vec<Payload>;
}

pub fn reflect<W: Write>(
    writer: &mut W,
    module: &str,
    database: Option<&dyn DatabaseSchema>,
    broker: Option<&dyn BrokerSchema>,
) -> Result<(), String> {
    let document = Document {
        module: module.to_string(),
        database: database.map(|schema| DatabaseSection {
            relations: schema.relations(),
        }),
        broker: broker.map(|schema| BrokerSection {
            payloads: schema.payloads(),
        }),
    };
    let encoded =
        serde_json::to_string_pretty(&document).map_err(|err| format!("failed to encode schema [{module}] [{err}]"))?;
    writeln!(writer, "{encoded}").map_err(|err| format!("failed to write schema [{module}] [{err}]"))
}

pub struct TempStat {
    sensors: Vec<SensorConfig>,
    cadence: String,
}

impl TempStat {
    pub fn new(sensors: Vec<SensorConfig>, cadence: String) -> Self {
        Self { sensors, cadence }
    }
}

impl DatabaseSchema for TempStat {
    fn relations(&self) -> Vec<Relation> {
        vec![
            Relation {
                path: format!("{MODULE}/device"),
                desc: "the tempstat service itself, one row set per poll".to_string(),
                cadence: self.cadence.clone(),
                entities: vec![MODULE.to_string()],
                dimensions: vec![Dimension {
                    key: "device".to_string(),
                    desc: "the service instance".to_string(),
                    subject: true,
                }],
                measures: vec![
                    Measure {
                        key: "period_ms".to_string(),
                        kind: Kind::Int,
                        unit: "milliseconds".to_string(),
                        desc: "wall time taken to sample every sensor".to_string(),
                        persist: true,
                    },
                    Measure {
                        key: "sensors_failed".to_string(),
                        kind: Kind::Int,
                        unit: "count".to_string(),
                        desc: "sensors that did not return a reading this poll".to_string(),
                        persist: true,
                    },
                ],
            },
            Relation {
                path: format!("{MODULE}/sensor"),
                desc: "one DS18B20 probe on the one-wire bus".to_string(),
                cadence: self.cadence.clone(),
                entities: self.sensors.iter().map(|sensor| sensor.unique_id.clone()).collect(),
                dimensions: vec![Dimension {
                    key: "sensor".to_string(),
                    desc: "sensor unique_id from sensors.json".to_string(),
                    subject: true,
                }],
                measures: vec![Measure {
                    key: "temperature_celsius".to_string(),
                    kind: Kind::Float,
                    unit: "celsius".to_string(),
                    desc: "probe temperature, absent when the sensor fails".to_string(),
                    persist: true,
                }],
            },
        ]
    }
}

impl BrokerSchema for TempStat {
    fn payloads(&self) -> Vec<Payload> {
        vec![
            Payload {
                role: Role::State,
                match_glob: String::new(),
                desc: "one poll of every configured sensor".to_string(),
                root: Member {
                    key: String::new(),
                    kind: Kind::Obj,
                    enum_values: Vec::new(),
                    dynamic: false,
                    members: vec![
                        Member {
                            key: "timestamp".to_string(),
                            kind: Kind::Str,
                            enum_values: Vec::new(),
                            dynamic: false,
                            members: Vec::new(),
                        },
                        Member {
                            key: "period_ms".to_string(),
                            kind: Kind::Int,
                            enum_values: Vec::new(),
                            dynamic: false,
                            members: Vec::new(),
                        },
                        Member {
                            key: "samples".to_string(),
                            kind: Kind::Obj,
                            enum_values: Vec::new(),
                            dynamic: true,
                            members: self
                                .sensors
                                .iter()
                                .map(|sensor| Member {
                                    key: format!("{}_celsius", sensor.unique_id),
                                    kind: Kind::Float,
                                    enum_values: Vec::new(),
                                    dynamic: false,
                                    members: Vec::new(),
                                })
                                .collect(),
                        },
                    ],
                },
            },
            Payload {
                role: Role::Command,
                match_glob: String::new(),
                desc: "service lifecycle command".to_string(),
                root: Member {
                    key: String::new(),
                    kind: Kind::Str,
                    enum_values: vec!["start".to_string(), "stop".to_string(), "restart".to_string()],
                    dynamic: false,
                    members: Vec::new(),
                },
            },
            Payload {
                role: Role::Availability,
                match_glob: String::new(),
                desc: "retained service availability".to_string(),
                root: Member {
                    key: String::new(),
                    kind: Kind::Str,
                    enum_values: vec!["online".to_string(), "offline".to_string()],
                    dynamic: false,
                    members: Vec::new(),
                },
            },
        ]
    }
}

fn is_false(value: &bool) -> bool {
    !*value
}
