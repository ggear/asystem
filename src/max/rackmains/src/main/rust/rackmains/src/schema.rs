use std::io::Write;

use serde::Serialize;

use crate::nut::SAMPLES;

pub const MODULE: &str = "rackmains";
pub const KEY_TIMESTAMP: &str = "timestamp";
pub const KEY_PERIOD_MS: &str = "period_ms";
pub const KEY_STATUS: &str = "mains_status";
pub const KEY_SAMPLES: &str = "samples";
pub const AVAILABILITY_ONLINE: &str = "online";
pub const AVAILABILITY_OFFLINE: &str = "offline";

#[derive(Serialize, Clone, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Float,
    Int,
    Bool,
    Str,
}

#[derive(Serialize, Clone, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    State,
    Command,
    Availability,
}

#[derive(Serialize)]
pub struct Member {
    #[serde(skip_serializing_if = "String::is_empty")]
    pub key: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind: Option<Kind>,
    #[serde(rename = "enum", skip_serializing_if = "Vec::is_empty")]
    pub enum_values: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub members: Vec<Member>,
}

#[derive(Serialize)]
pub struct Payload {
    pub role: Role,
    #[serde(rename = "match", skip_serializing_if = "String::is_empty")]
    pub match_glob: String,
    pub root: Member,
}

#[derive(Serialize)]
pub struct BrokerSection {
    pub payloads: Vec<Payload>,
}

#[derive(Serialize)]
pub struct Document {
    pub module: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub broker: Option<BrokerSection>,
}

pub trait BrokerSchema {
    fn payloads(&self) -> Vec<Payload>;
}

pub fn reflect<W: Write>(writer: &mut W, module: &str, broker: Option<&dyn BrokerSchema>) -> Result<(), String> {
    let document = Document {
        module: module.to_string(),
        broker: broker.map(|schema| BrokerSection {
            payloads: schema.payloads(),
        }),
    };
    let encoded =
        serde_json::to_string_pretty(&document).map_err(|err| format!("failed to encode schema [{module}] [{err}]"))?;
    writeln!(writer, "{encoded}").map_err(|err| format!("failed to write schema [{module}] [{err}]"))
}

pub struct RackMains;

impl BrokerSchema for RackMains {
    fn payloads(&self) -> Vec<Payload> {
        vec![
            Payload {
                role: Role::State,
                match_glob: String::new(),
                root: Member::object(
                    "",
                    vec![
                        Member::scalar(KEY_TIMESTAMP, Kind::Str),
                        Member::scalar(KEY_PERIOD_MS, Kind::Int),
                        Member::scalar(KEY_STATUS, Kind::Str),
                        Member::object(
                            KEY_SAMPLES,
                            SAMPLES
                                .iter()
                                .map(|sample| Member::scalar(sample.key, Kind::Float))
                                .collect(),
                        ),
                    ],
                ),
            },
            Payload {
                role: Role::Command,
                match_glob: String::new(),
                root: Member::scalar("", Kind::Str),
            },
            Payload {
                role: Role::Availability,
                match_glob: String::new(),
                root: Member::options(&[AVAILABILITY_ONLINE, AVAILABILITY_OFFLINE]),
            },
        ]
    }
}

impl Member {
    fn scalar(key: &str, kind: Kind) -> Self {
        Member {
            key: key.to_string(),
            kind: Some(kind),
            enum_values: Vec::new(),
            members: Vec::new(),
        }
    }

    fn object(key: &str, members: Vec<Member>) -> Self {
        Member {
            key: key.to_string(),
            kind: None,
            enum_values: Vec::new(),
            members,
        }
    }

    fn options(values: &[&str]) -> Self {
        Member {
            key: String::new(),
            kind: None,
            enum_values: values.iter().map(std::string::ToString::to_string).collect(),
            members: Vec::new(),
        }
    }
}
