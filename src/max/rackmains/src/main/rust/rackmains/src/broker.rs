use std::collections::HashMap;
use std::fmt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use log::{debug, info, warn};
use rumqttc::{Client, Event, LastWill, MqttOptions, Outgoing, Packet, QoS};

use crate::log_line;
use crate::schema::{AVAILABILITY_OFFLINE, AVAILABILITY_ONLINE};

const CHANNEL_CAPACITY: usize = 10;
const RECONNECT_DELAY: Duration = Duration::from_secs(5);
const RECONNECT_POLL: Duration = Duration::from_millis(100);

#[derive(Debug)]
pub enum Error {
    Mqtt(String),
    Timeout,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Mqtt(msg) => write!(f, "mqtt error [{msg}]"),
            Error::Timeout => write!(f, "timed out connecting to broker"),
        }
    }
}

pub type Result<T> = std::result::Result<T, Error>;

pub trait Publisher {
    fn publish(&mut self, topic: &str, payload: &[u8]) -> Result<()>;

    fn close(&mut self) -> Result<()> {
        Ok(())
    }
}

pub struct MqttPublisher {
    client: Client,
    shutdown: Arc<AtomicBool>,
    connected: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
    status_topic: String,
    retained: Arc<Mutex<HashMap<String, Vec<u8>>>>,
}

impl MqttPublisher {
    pub fn new(host: &str, port: u16, token: &str, status_topic: &str) -> Result<Self> {
        let mut options = MqttOptions::new("rackmains", host, port);
        let has_token = !token.is_empty();
        if has_token {
            options.set_credentials("rackmains", token);
        }
        options.set_last_will(LastWill::new(
            status_topic,
            AVAILABILITY_OFFLINE,
            QoS::AtLeastOnce,
            true,
        ));
        let (client, mut connection) = Client::new(options, CHANNEL_CAPACITY);
        let shutdown = Arc::new(AtomicBool::new(false));
        let connected = Arc::new(AtomicBool::new(false));
        let retained: Arc<Mutex<HashMap<String, Vec<u8>>>> = Arc::new(Mutex::new(HashMap::new()));
        let thread_shutdown = Arc::clone(&shutdown);
        let thread_connected = Arc::clone(&connected);
        let thread_retained = Arc::clone(&retained);
        let thread_client = client.clone();
        let thread_status_topic = status_topic.to_string();
        let address = format!("{host}:{port}");
        let handle = thread::spawn(move || {
            let mut seen = false;
            let mut failing = false;
            for event in connection.iter() {
                match event {
                    Ok(Event::Incoming(Packet::ConnAck(_))) => {
                        thread_connected.store(true, Ordering::SeqCst);
                        failing = false;
                        if seen {
                            info!("{}", log_line("broker reconnected", &address));
                        } else {
                            info!("{}", log_line("connected to broker", &address));
                            seen = true;
                        }
                        if let Err(err) =
                            thread_client.try_publish(&thread_status_topic, QoS::AtLeastOnce, true, AVAILABILITY_ONLINE)
                        {
                            warn!("{}", log_line("broker status publish failed", &err.to_string()));
                        }
                        let replay: Vec<(String, Vec<u8>)> = match thread_retained.lock() {
                            Ok(cache) => cache
                                .iter()
                                .map(|(topic, payload)| (topic.clone(), payload.clone()))
                                .collect(),
                            Err(err) => {
                                warn!("{}", log_line("broker retained cache unreadable", &err.to_string()));
                                Vec::new()
                            }
                        };
                        if !replay.is_empty() {
                            for (topic, payload) in &replay {
                                if let Err(err) =
                                    thread_client.try_publish(topic, QoS::AtLeastOnce, true, payload.clone())
                                {
                                    warn!("{}", log_line("broker retained republish failed", topic));
                                    warn!("{}", log_line("broker retained republish error", &err.to_string()));
                                }
                            }
                            info!(
                                "{}",
                                log_line("broker republished retained topics", &replay.len().to_string())
                            );
                        }
                    }
                    Ok(Event::Incoming(Packet::PubAck(ack))) => {
                        debug!("{}", log_line("broker ack", &ack.pkid.to_string()));
                    }
                    Ok(Event::Outgoing(Outgoing::Publish(pkid))) => {
                        debug!("{}", log_line("broker publish", &pkid.to_string()));
                    }
                    Ok(Event::Outgoing(Outgoing::Disconnect)) => {
                        debug!("{}", log_line("broker disconnect", "sent"));
                    }
                    Ok(_) => {}
                    Err(err) => {
                        if thread_shutdown.load(Ordering::SeqCst) {
                            break;
                        }
                        thread_connected.store(false, Ordering::SeqCst);
                        if failing {
                            debug!("{}", log_line("broker still down", &err.to_string()));
                        } else {
                            failing = true;
                            warn!("{}", log_line("broker error", &err.to_string()));
                            warn!("{}", log_line("broker retry period", &format!("{RECONNECT_DELAY:?}")));
                        }
                        let waiting = Instant::now();
                        while waiting.elapsed() < RECONNECT_DELAY && !thread_shutdown.load(Ordering::SeqCst) {
                            thread::sleep(RECONNECT_POLL);
                        }
                    }
                }
            }
            debug!("{}", log_line("broker event loop", "stopped"));
        });
        Ok(MqttPublisher {
            client,
            shutdown,
            connected,
            handle: Some(handle),
            status_topic: status_topic.to_string(),
            retained,
        })
    }

    pub fn wait_connected(&self, timeout: Duration) -> Result<()> {
        let started = Instant::now();
        while !self.connected.load(Ordering::SeqCst) {
            if started.elapsed() >= timeout {
                return Err(Error::Timeout);
            }
            thread::sleep(Duration::from_millis(50));
        }
        Ok(())
    }
}

impl Publisher for MqttPublisher {
    fn close(&mut self) -> Result<()> {
        let status_topic = self.status_topic.clone();
        let published = self.publish(&status_topic, AVAILABILITY_OFFLINE.as_bytes());
        self.shutdown.store(true, Ordering::SeqCst);
        let disconnected = self.client.try_disconnect().map_err(|err| Error::Mqtt(err.to_string()));
        if let Some(handle) = self.handle.take() {
            handle.join().ok();
        }
        info!("{}", log_line("broker disconnected", "closing connection"));
        published.and(disconnected)
    }

    fn publish(&mut self, topic: &str, payload: &[u8]) -> Result<()> {
        debug!("{}", log_line("publish topic", topic));
        match std::str::from_utf8(payload) {
            Ok(text) => debug!("{}", log_line("publish payload", text)),
            Err(_) => debug!("{}", log_line("publish payload bytes", &payload.len().to_string())),
        }
        if topic != self.status_topic {
            match self.retained.lock() {
                Ok(mut cache) => {
                    cache.insert(topic.to_string(), payload.to_vec());
                }
                Err(err) => {
                    warn!("{}", log_line("broker retained cache unwritable", topic));
                    warn!("{}", log_line("broker retained cache error", &err.to_string()));
                }
            }
        }
        self.client
            .try_publish(topic, QoS::AtLeastOnce, true, payload.to_vec())
            .map_err(|err| Error::Mqtt(err.to_string()))
    }
}

#[cfg(test)]
pub mod mock {
    use super::{Publisher, Result};

    #[derive(Default)]
    pub struct MockPublisher {
        pub messages: Vec<(String, Vec<u8>)>,
    }

    impl MockPublisher {
        pub fn new() -> Self {
            MockPublisher { messages: Vec::new() }
        }
    }

    impl Publisher for MockPublisher {
        fn publish(&mut self, topic: &str, payload: &[u8]) -> Result<()> {
            self.messages.push((topic.to_string(), payload.to_vec()));
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn closing_against_a_dead_broker_returns_well_inside_the_reconnect_delay() {
        let mut publisher = MqttPublisher::new("127.0.0.1", 1, "", "rackmains/status").unwrap();
        thread::sleep(Duration::from_millis(500));
        let started = Instant::now();
        let _ = publisher.close();
        assert!(
            started.elapsed() < Duration::from_secs(2),
            "close took [{:?}]",
            started.elapsed()
        );
    }
}
