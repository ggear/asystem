use std::fmt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::Arc;
use std::thread;
use std::thread::JoinHandle;
use std::time::Duration;

use log::{debug, info, warn};
use rumqttc::{Client, Event, LastWill, MqttOptions, Outgoing, Packet, QoS};

use crate::log_line;

const CHANNEL_CAPACITY: usize = 10;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(30);
const RECONNECT_DELAY: Duration = Duration::from_secs(5);

#[derive(Debug)]
pub enum Error {
    Mqtt(String),
    Timeout,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Mqtt(msg) => write!(f, "mqtt error: {msg}"),
            Error::Timeout => write!(f, "timed out connecting to broker"),
        }
    }
}

pub type Result<T> = std::result::Result<T, Error>;

pub trait Publisher {
    fn publish(&mut self, topic: &str, payload: &[u8]) -> Result<()>;
}

pub struct MqttPublisher {
    client: Client,
    shutdown: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl MqttPublisher {
    pub fn new(host: &str, port: u16, token: &str, status_topic: &str) -> Result<Self> {
        let mut options = MqttOptions::new("tempstat", host, port);
        let has_token = !token.is_empty();
        if has_token {
            options.set_credentials("tempstat", token);
        }
        options.set_last_will(LastWill::new(status_topic, "offline", QoS::AtLeastOnce, true));
        let (client, mut connection) = Client::new(options, CHANNEL_CAPACITY);
        let shutdown = Arc::new(AtomicBool::new(false));
        let (ready_sender, ready_receiver) = mpsc::channel();
        let thread_shutdown = Arc::clone(&shutdown);
        let thread_client = client.clone();
        let thread_status_topic = status_topic.to_string();
        let address = format!("{}:{}", host, port);
        let handle = thread::spawn(move || {
            let mut ready_sender = Some(ready_sender);
            for event in connection.iter() {
                match event {
                    Ok(Event::Incoming(Packet::ConnAck(_))) => {
                        if let Some(sender) = ready_sender.take() {
                            info!("{}", log_line("connected to broker", &address));
                            let _ = sender.send(());
                        } else {
                            info!("broker reconnected [{}]", address);
                        }
                        if let Err(err) =
                            thread_client.try_publish(&thread_status_topic, QoS::AtLeastOnce, true, "online")
                        {
                            warn!("broker status publish failed [{address}]: {err}");
                        }
                    }
                    Ok(Event::Incoming(Packet::PubAck(ack))) => {
                        debug!("broker ack pkid [{}]", ack.pkid);
                    }
                    Ok(Event::Outgoing(Outgoing::Publish(pkid))) => {
                        debug!("broker publish pkid [{pkid}]");
                    }
                    Ok(Event::Outgoing(Outgoing::Disconnect)) => {
                        debug!("broker disconnect sent");
                    }
                    Ok(_) => {}
                    Err(err) => {
                        if thread_shutdown.load(Ordering::SeqCst) {
                            break;
                        }
                        warn!("broker error [{address}]: {err}");
                        info!("broker reconnecting [{}] in {:?}", address, RECONNECT_DELAY);
                        thread::sleep(RECONNECT_DELAY);
                    }
                }
            }
            debug!("broker event loop stopped");
        });
        match ready_receiver.recv_timeout(CONNECT_TIMEOUT) {
            Ok(()) => Ok(MqttPublisher {
                client,
                shutdown,
                handle: Some(handle),
            }),
            Err(err) => {
                shutdown.store(true, Ordering::SeqCst);
                let _ = client.try_disconnect();
                handle.join().ok();
                Err(match err {
                    RecvTimeoutError::Timeout => Error::Timeout,
                    RecvTimeoutError::Disconnected => {
                        Error::Mqtt("broker event loop exited before connecting".to_string())
                    }
                })
            }
        }
    }

    pub fn close(&mut self, status_topic: &str) -> Result<()> {
        let published = self.publish(status_topic, b"offline");
        self.shutdown.store(true, Ordering::SeqCst);
        let disconnected = self.client.disconnect().map_err(|err| Error::Mqtt(err.to_string()));
        if let Some(handle) = self.handle.take() {
            handle.join().ok();
        }
        info!("broker disconnected");
        published.and(disconnected)
    }
}

impl Publisher for MqttPublisher {
    fn publish(&mut self, topic: &str, payload: &[u8]) -> Result<()> {
        match std::str::from_utf8(payload) {
            Ok(text) => debug!("publish [{topic}] -> {text}"),
            Err(_) => debug!("publish [{topic}] -> ({} bytes)", payload.len()),
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
