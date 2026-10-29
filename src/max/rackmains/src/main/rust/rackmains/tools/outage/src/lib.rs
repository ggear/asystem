use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use clap::builder::{PossibleValuesParser, TypedValueParser};
use clap::Parser;
use log::{info, warn, LevelFilter};
use rackmains::nut::SAMPLES;
use rackmains::schema::{KEY_SAMPLES, KEY_STATUS, KEY_TIMESTAMP};
use rackmains::{log_line, parse_duration, LEVEL_NAMES, STATE_TOPIC};
use rumqttc::{Client, Event, MqttOptions, Packet, QoS};
use serde_json::{json, Value};

const DEFAULT_PLUG_HOST: &str = "10.0.4.102";
const DEFAULT_HOSTS: &str = "macmini-mad,macmini-max,macmini-may,macmini-meg";
const FLAG_ON_BATTERY: &str = "OB";
const FLAG_ON_LINE: &str = "OL";
const FLAG_LOW_BATTERY: &str = "LB";
const VARIABLE_BATTERY_VOLTAGE: &str = "battery.voltage";
const HOST_PORT: u16 = 22;
const PLUG_PORT: u16 = 80;
const HOST_CHECK_EVERY: Duration = Duration::from_secs(15);
const STALE_AFTER: Duration = Duration::from_secs(30);
const MAX_STALE_POLLS: u32 = 3;
const RESTORE_GRACE: Duration = Duration::from_secs(15);
const RECOVER_TIMEOUT: Duration = Duration::from_secs(120);
const CONNECT_TIMEOUT: Duration = Duration::from_secs(30);
const PLUG_DELAY_MAX_DECISECONDS: u64 = 3600;
const PLUG_DELAY_MIN_DECISECONDS: u64 = 2;
const CUT_MIN: Duration = Duration::from_secs(5);

#[derive(Debug, Parser)]
#[command(
    name = "outage",
    about = "Cut the rack's mains through its smart plug, watch the battery and restore, from a host that is not on the UPS",
    version
)]
pub struct Cli {
    #[arg(short = 'C', long = "cut", value_name = "PERIOD", default_value = "60s")]
    pub cut: String,
    #[arg(short = 'F', long = "floor-volts", value_name = "VOLTS", default_value = "11.5")]
    pub floor_volts: f64,
    #[arg(short = 'U', long = "plug-host", value_name = "HOST", default_value = DEFAULT_PLUG_HOST)]
    pub plug_host: String,
    #[arg(short = 'H', long = "hosts", value_name = "HOSTS", default_value = DEFAULT_HOSTS)]
    pub hosts: String,
    #[arg(short = 'E', long = "events", value_name = "FILE", default_value = "")]
    pub events: String,
    #[arg(short = 'n', long = "dry-run")]
    pub dry_run: bool,
    #[arg(short = 'P', long = "poll-period", value_name = "PERIOD", default_value = "2s")]
    pub poll_period: String,
    #[arg(short = 'T', long = "timeout", value_name = "PERIOD", default_value = "5s")]
    pub timeout: String,
    #[arg(
        short = 'B',
        long = "broker-host",
        value_name = "HOST",
        env = "BROKER_HOST",
        default_value = "localhost"
    )]
    pub broker_host: String,
    #[arg(
        long = "broker-port",
        value_name = "PORT",
        env = "BROKER_PORT",
        default_value = "1883"
    )]
    pub broker_port: u16,
    #[arg(
        long = "broker-token",
        value_name = "TOKEN",
        env = "BROKER_TOKEN",
        default_value = ""
    )]
    pub broker_token: String,
    #[arg(
        short = 'L',
        long = "log-level",
        value_name = "LEVEL",
        default_value = "info",
        value_parser = PossibleValuesParser::new(LEVEL_NAMES.iter().map(|name| name.as_str()))
            .map(|name| name.parse::<LevelFilter>().unwrap())
    )]
    pub log_level: LevelFilter,
}

impl Cli {
    pub fn run(&self) -> Result<(), String> {
        let _ = env_logger::Builder::new()
            .filter_level(self.log_level)
            .format(|buf, record| {
                writeln!(
                    buf,
                    "[{} {:<5}] {}",
                    chrono::Local::now().format("%Y-%m-%dT%H:%M:%S%.3f%:z"),
                    record.level(),
                    record.args()
                )
            })
            .try_init();
        let cut = parse_duration(&self.cut)?;
        let period = parse_duration(&self.poll_period)?;
        let timeout = parse_duration(&self.timeout)?;
        if cut < CUT_MIN || period.is_zero() || timeout.is_zero() {
            return Err(format!(
                "cut [{cut:?}] must be at least [{CUT_MIN:?}] and the poll period [{period:?}] and timeout [{timeout:?}] above zero"
            ));
        }
        let hosts: Vec<String> = self
            .hosts
            .split(',')
            .map(str::trim)
            .filter(|host| !host.is_empty())
            .map(str::to_string)
            .collect();
        let plug = Plug {
            host: self.plug_host.clone(),
            timeout,
        };
        let mut events = Events::open(&self.events)?;
        let feed = Feed::connect(&self.broker_host, self.broker_port, &self.broker_token)?;
        info!("{}", log_line("cutting the plug", &self.plug_host));
        info!("{}", log_line("cut for", &format!("{}s", cut.as_secs())));
        info!("{}", log_line("voltage floor", &format!("{}V", self.floor_volts)));
        let outage = Outage {
            cut,
            period,
            timeout,
            floor: self.floor_volts,
            hosts,
            plug,
            feed,
        };
        outage.execute(&mut events, self.dry_run)
    }
}

struct Outage {
    cut: Duration,
    period: Duration,
    timeout: Duration,
    floor: f64,
    hosts: Vec<String>,
    plug: Plug,
    feed: Feed,
}

impl Outage {
    fn execute(&self, events: &mut Events, dry_run: bool) -> Result<(), String> {
        self.preflight(events)?;
        let command = cut_command(self.cut);
        events.record(
            "plan",
            json!({"command": command, "cut_seconds": self.cut.as_secs(), "floor_volts": self.floor, "hosts": self.hosts, "dry_run": dry_run}),
        );
        if dry_run {
            info!("{}", log_line("dry run, would send", &command));
            return Ok(());
        }
        let sent = self.plug.command(&command)?;
        let started = Instant::now();
        events.record("cut", json!({"plug": sent}));
        let aborted = self.hold(events, started);
        let restored = self.restore(events, started, aborted.is_some());
        let recovered = self.recover(events, started);
        let down = self.hosts_down();
        events.record("finish", json!({"aborted": aborted, "device_timer_fired": restored.as_ref().ok(), "recovered": recovered.as_ref().ok(), "hosts_down": down}));
        if let Some(reason) = aborted {
            return Err(format!("aborted [{reason}]"));
        }
        restored?;
        recovered?;
        if !down.is_empty() {
            return Err(format!("hosts down after the restore [{}]", down.join(",")));
        }
        Ok(())
    }

    fn preflight(&self, events: &mut Events) -> Result<(), String> {
        let snapshot = self.feed.wait_fresh(CONNECT_TIMEOUT)?;
        let status = snapshot.status.clone().unwrap_or_default();
        if !has_flag(&status, FLAG_ON_LINE) || has_flag(&status, FLAG_ON_BATTERY) {
            return Err(format!("mains status [{status}] is not on line"));
        }
        if let Some(reason) = abort_reason(&snapshot, self.floor) {
            return Err(format!("not safe to start [{reason}]"));
        }
        let power = self.plug.command("Power")?;
        if !power.contains("\"ON\"") {
            return Err(format!("plug is not on [{power}]"));
        }
        let down = self.hosts_down();
        if !down.is_empty() {
            return Err(format!("hosts unreachable before the cut [{}]", down.join(",")));
        }
        events.record(
            "preflight",
            json!({"status": status, "battery_volts": snapshot.voltage, "plug": power}),
        );
        Ok(())
    }

    fn hold(&self, events: &mut Events, started: Instant) -> Option<String> {
        let mut stale: u32 = 0;
        let mut last_hosts = Instant::now();
        while started.elapsed() < self.cut {
            thread::sleep(self.period);
            let elapsed = started.elapsed();
            let snapshot = match self.feed.latest() {
                Some(snapshot) if snapshot.seen.elapsed() <= STALE_AFTER => {
                    stale = 0;
                    snapshot
                }
                _ => {
                    stale += 1;
                    warn!("no fresh reading [{stale}]");
                    if stale >= MAX_STALE_POLLS {
                        return Some(self.abort(events, elapsed, "readings stale".to_string()));
                    }
                    continue;
                }
            };
            events.record("sample", sample_fields(elapsed, &snapshot));
            info!(
                "{}",
                log_line(
                    &format!("+{}s", elapsed.as_secs()),
                    &format!(
                        "{} {}V",
                        snapshot.status.as_deref().unwrap_or("unknown"),
                        snapshot
                            .voltage
                            .map_or("unknown".to_string(), |volts| volts.to_string())
                    )
                )
            );
            if let Some(reason) = abort_reason(&snapshot, self.floor) {
                return Some(self.abort(events, elapsed, reason));
            }
            if last_hosts.elapsed() >= HOST_CHECK_EVERY {
                last_hosts = Instant::now();
                let down = self.hosts_down();
                events.record("hosts", json!({"elapsed": elapsed.as_secs(), "down": down}));
                if !down.is_empty() {
                    return Some(self.abort(events, elapsed, format!("hosts unreachable {}", down.join(","))));
                }
            }
        }
        None
    }

    fn abort(&self, events: &mut Events, elapsed: Duration, reason: String) -> String {
        warn!("aborting [{reason}] at [{}s]", elapsed.as_secs());
        events.record("abort", json!({"elapsed": elapsed.as_secs(), "reason": reason}));
        reason
    }

    fn restore(&self, events: &mut Events, started: Instant, aborted: bool) -> Result<(), String> {
        if !aborted {
            while started.elapsed() < self.cut + RESTORE_GRACE {
                thread::sleep(self.period);
                if started.elapsed() < self.cut {
                    continue;
                }
                if let Ok(power) = self.plug.command("Power") {
                    if power.contains("\"ON\"") {
                        events.record(
                            "restore",
                            json!({"elapsed": started.elapsed().as_secs_f64(), "by": "device timer", "plug": power}),
                        );
                        return Ok(());
                    }
                }
            }
        }
        let sent = self.plug.command("Power On");
        events.record(
            "restore",
            json!({"elapsed": started.elapsed().as_secs_f64(), "by": "explicit", "plug": sent.as_ref().ok()}),
        );
        match sent {
            Ok(power) if power.contains("\"ON\"") && aborted => Ok(()),
            Ok(power) if power.contains("\"ON\"") => {
                Err("device timer did not restore the plug, restored explicitly".to_string())
            }
            Ok(power) => Err(format!("plug did not report on after the restore [{power}]")),
            Err(err) => Err(format!("plug restore failed [{err}]")),
        }
    }

    fn recover(&self, events: &mut Events, started: Instant) -> Result<f64, String> {
        let begun = Instant::now();
        while begun.elapsed() < RECOVER_TIMEOUT {
            thread::sleep(self.period);
            if let Some(snapshot) = self.feed.latest() {
                let status = snapshot.status.clone().unwrap_or_default();
                if snapshot.seen.elapsed() <= STALE_AFTER
                    && has_flag(&status, FLAG_ON_LINE)
                    && !has_flag(&status, FLAG_ON_BATTERY)
                {
                    let taken = begun.elapsed().as_secs_f64();
                    events.record(
                        "recovered",
                        json!({"elapsed": started.elapsed().as_secs_f64(), "after_restore_seconds": taken, "status": status, "battery_volts": snapshot.voltage}),
                    );
                    return Ok(taken);
                }
            }
        }
        events.record(
            "recovered",
            json!({"elapsed": started.elapsed().as_secs_f64(), "failed": true}),
        );
        Err(format!(
            "mains status did not return to on line within [{RECOVER_TIMEOUT:?}]"
        ))
    }

    fn hosts_down(&self) -> Vec<String> {
        self.hosts
            .iter()
            .filter(|host| !reachable(host, HOST_PORT, self.timeout))
            .cloned()
            .collect()
    }
}

pub fn cut_command(cut: Duration) -> String {
    let mut remaining = cut.as_secs() * 10;
    let mut delays: Vec<u64> = Vec::new();
    while remaining > 0 {
        let mut chunk = remaining.min(PLUG_DELAY_MAX_DECISECONDS);
        if remaining - chunk > 0 && remaining - chunk < PLUG_DELAY_MIN_DECISECONDS {
            chunk -= PLUG_DELAY_MIN_DECISECONDS;
        }
        delays.push(chunk);
        remaining -= chunk;
    }
    let delays: Vec<String> = delays.iter().map(|delay| format!("Delay {delay}")).collect();
    format!("Backlog Power Off; {}; Power On", delays.join("; "))
}

pub fn abort_reason(snapshot: &Snapshot, floor: f64) -> Option<String> {
    let status = snapshot.status.as_deref().unwrap_or_default();
    if has_flag(status, FLAG_LOW_BATTERY) {
        return Some(format!("low battery flag in [{status}]"));
    }
    match snapshot.voltage {
        Some(volts) if volts < floor => Some(format!("battery voltage [{volts}] below floor [{floor}]")),
        _ => None,
    }
}

pub fn has_flag(status: &str, flag: &str) -> bool {
    status.split_whitespace().any(|token| token == flag)
}

pub fn url_encode(raw: &str) -> String {
    raw.bytes()
        .map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' => (byte as char).to_string(),
            _ => format!("%{byte:02X}"),
        })
        .collect()
}

#[derive(Clone, Debug)]
pub struct Snapshot {
    pub timestamp: String,
    pub status: Option<String>,
    pub voltage: Option<f64>,
    pub payload: Value,
    pub seen: Instant,
}

impl Snapshot {
    pub fn parse(payload: &[u8], seen: Instant) -> Option<Snapshot> {
        let payload: Value = serde_json::from_slice(payload).ok()?;
        let timestamp = payload.get(KEY_TIMESTAMP)?.as_str()?.to_string();
        let status = payload.get(KEY_STATUS).and_then(Value::as_str).map(str::to_string);
        let key = SAMPLES
            .iter()
            .find(|sample| sample.variable == VARIABLE_BATTERY_VOLTAGE)?
            .key;
        let voltage = payload
            .get(KEY_SAMPLES)
            .and_then(|samples| samples.get(key))
            .and_then(Value::as_f64);
        Some(Snapshot {
            timestamp,
            status,
            voltage,
            payload,
            seen,
        })
    }
}

struct Feed {
    latest: Arc<Mutex<Option<Snapshot>>>,
}

impl Feed {
    fn connect(host: &str, port: u16, token: &str) -> Result<Feed, String> {
        let mut options = MqttOptions::new("rackmains-outage", host, port);
        if !token.is_empty() {
            options.set_credentials("rackmains", token);
        }
        let (client, mut connection) = Client::new(options, 10);
        let latest: Arc<Mutex<Option<Snapshot>>> = Arc::new(Mutex::new(None));
        let (ready_sender, ready_receiver) = mpsc::channel();
        let shared = Arc::clone(&latest);
        let address = format!("{host}:{port}");
        thread::spawn(move || {
            let mut ready_sender = Some(ready_sender);
            for event in connection.iter() {
                match event {
                    Ok(Event::Incoming(Packet::ConnAck(_))) => {
                        if let Err(err) = client.try_subscribe(STATE_TOPIC, QoS::AtLeastOnce) {
                            warn!("subscribe failed [{STATE_TOPIC}] [{err}]");
                        }
                        if let Some(sender) = ready_sender.take() {
                            info!("{}", log_line("connected to broker", &address));
                            let _ = sender.send(());
                        }
                    }
                    Ok(Event::Incoming(Packet::Publish(publish))) if publish.topic == STATE_TOPIC => {
                        if let Some(mut snapshot) = Snapshot::parse(&publish.payload, Instant::now()) {
                            if let Ok(mut held) = shared.lock() {
                                if let Some(previous) = held.as_ref() {
                                    if previous.timestamp == snapshot.timestamp {
                                        snapshot.seen = previous.seen;
                                    }
                                }
                                *held = Some(snapshot);
                            }
                        }
                    }
                    Ok(_) => {}
                    Err(err) => {
                        warn!("broker error [{address}] [{err}]");
                        thread::sleep(Duration::from_secs(2));
                    }
                }
            }
        });
        match ready_receiver.recv_timeout(CONNECT_TIMEOUT) {
            Ok(()) => Ok(Feed { latest }),
            Err(RecvTimeoutError::Timeout) => Err(format!("timed out connecting to broker [{host}:{port}]")),
            Err(RecvTimeoutError::Disconnected) => Err("broker event loop exited before connecting".to_string()),
        }
    }

    fn latest(&self) -> Option<Snapshot> {
        self.latest.lock().ok().and_then(|held| held.clone())
    }

    fn wait_fresh(&self, wait: Duration) -> Result<Snapshot, String> {
        let begun = Instant::now();
        while begun.elapsed() < wait {
            if let Some(snapshot) = self.latest() {
                if timestamp_age(&snapshot.timestamp).is_some_and(|age| age <= STALE_AFTER) {
                    return Ok(snapshot);
                }
            }
            thread::sleep(Duration::from_millis(250));
        }
        Err(format!("no fresh reading on [{STATE_TOPIC}] within [{wait:?}]"))
    }
}

struct Plug {
    host: String,
    timeout: Duration,
}

impl Plug {
    fn command(&self, command: &str) -> Result<String, String> {
        self.command_on(PLUG_PORT, command)
    }

    fn command_on(&self, port: u16, command: &str) -> Result<String, String> {
        let failed = |action: &str, err: std::io::Error| format!("failed to {action} plug [{}] [{err}]", self.host);
        let address = (self.host.as_str(), port)
            .to_socket_addrs()
            .map_err(|err| failed("resolve", err))?
            .next()
            .ok_or_else(|| format!("no address for plug [{}]", self.host))?;
        let mut stream = TcpStream::connect_timeout(&address, self.timeout).map_err(|err| failed("connect", err))?;
        stream
            .set_read_timeout(Some(self.timeout))
            .and_then(|()| stream.set_write_timeout(Some(self.timeout)))
            .map_err(|err| failed("set timeout", err))?;
        write!(
            stream,
            "GET /cm?cmnd={} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n",
            url_encode(command),
            self.host
        )
        .map_err(|err| failed("write", err))?;
        let mut response = String::new();
        stream
            .read_to_string(&mut response)
            .map_err(|err| failed("read", err))?;
        let (head, body) = response
            .split_once("\r\n\r\n")
            .ok_or_else(|| format!("malformed response from plug [{}]", self.host))?;
        if !head.starts_with("HTTP/1.0 200") && !head.starts_with("HTTP/1.1 200") {
            return Err(format!(
                "plug [{}] answered [{}]",
                self.host,
                head.lines().next().unwrap_or_default()
            ));
        }
        Ok(body.trim().to_string())
    }
}

struct Events {
    file: Option<File>,
}

impl Events {
    fn open(path: &str) -> Result<Events, String> {
        if path.is_empty() {
            return Ok(Events { file: None });
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|err| format!("failed to open events [{path}] [{err}]"))?;
        Ok(Events { file: Some(file) })
    }

    fn record(&mut self, event: &str, fields: Value) {
        let mut line =
            json!({"t": chrono::Local::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, false), "event": event});
        if let (Some(line), Value::Object(fields)) = (line.as_object_mut(), fields) {
            line.extend(fields);
        }
        if let Some(file) = self.file.as_mut() {
            if let Err(err) = writeln!(file, "{line}").and_then(|()| file.sync_all()) {
                warn!("events write failed [{err}]");
            }
        }
    }
}

fn sample_fields(elapsed: Duration, snapshot: &Snapshot) -> Value {
    json!({"elapsed": elapsed.as_secs_f64(), "status": snapshot.status, "battery_volts": snapshot.voltage, "payload": snapshot.payload})
}

fn timestamp_age(timestamp: &str) -> Option<Duration> {
    let at = humantime::parse_rfc3339(timestamp).ok()?;
    Some(SystemTime::now().duration_since(at).unwrap_or(Duration::ZERO))
}

fn reachable(host: &str, port: u16, timeout: Duration) -> bool {
    (host, port)
        .to_socket_addrs()
        .ok()
        .and_then(|mut addresses| addresses.next())
        .is_some_and(|address| TcpStream::connect_timeout(&address, timeout).is_ok())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};
    use std::net::TcpListener;

    fn snapshot(status: Option<&str>, voltage: Option<f64>) -> Snapshot {
        Snapshot {
            timestamp: "2026-10-28T10:00:00Z".to_string(),
            status: status.map(str::to_string),
            voltage,
            payload: Value::Null,
            seen: Instant::now(),
        }
    }

    #[test]
    fn cut_command_chains_delays_within_the_device_limit() {
        for (seconds, want) in [
            (60, "Backlog Power Off; Delay 600; Power On"),
            (360, "Backlog Power Off; Delay 3600; Power On"),
            (600, "Backlog Power Off; Delay 3600; Delay 2400; Power On"),
            (721, "Backlog Power Off; Delay 3600; Delay 3600; Delay 10; Power On"),
        ] {
            assert_eq!(cut_command(Duration::from_secs(seconds)), want, "cut {seconds}s");
        }
    }

    #[test]
    fn url_encode_escapes_everything_but_unreserved() {
        assert_eq!(
            url_encode("Backlog Power Off; Delay 600"),
            "Backlog%20Power%20Off%3B%20Delay%20600"
        );
        assert_eq!(url_encode("Power"), "Power");
    }

    #[test]
    fn abort_reason_fires_on_low_battery_flag_or_floor_volts() {
        assert_eq!(abort_reason(&snapshot(Some("OB DISCHRG"), Some(12.0)), 11.5), None);
        assert!(abort_reason(&snapshot(Some("OB LB"), Some(12.0)), 11.5).is_some());
        assert!(abort_reason(&snapshot(Some("OB"), Some(11.4)), 11.5).is_some());
        assert_eq!(abort_reason(&snapshot(Some("OB"), None), 11.5), None);
        assert_eq!(abort_reason(&snapshot(None, Some(13.3)), 11.5), None);
    }

    #[test]
    fn has_flag_matches_whole_tokens_only() {
        assert!(has_flag("OL CHRG", "OL"));
        assert!(!has_flag("OLD", "OL"));
        assert!(!has_flag("", "OL"));
    }

    #[test]
    fn snapshot_parses_the_published_payload() {
        let key = SAMPLES
            .iter()
            .find(|sample| sample.variable == VARIABLE_BATTERY_VOLTAGE)
            .unwrap()
            .key;
        let payload = json!({"timestamp": "2026-10-28T10:00:00Z", "mains_status": "OB", "samples": {key: 12.4}});
        let parsed = Snapshot::parse(payload.to_string().as_bytes(), Instant::now()).unwrap();
        assert_eq!(parsed.status.as_deref(), Some("OB"));
        assert_eq!(parsed.voltage, Some(12.4));
        assert!(Snapshot::parse(b"not json", Instant::now()).is_none());
    }

    #[test]
    fn plug_sends_the_encoded_command_and_returns_the_body() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = String::new();
            BufReader::new(stream.try_clone().unwrap())
                .read_line(&mut request)
                .unwrap();
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"POWER\":\"ON\"}")
                .unwrap();
            request
        });
        let plug = Plug {
            host: "127.0.0.1".to_string(),
            timeout: Duration::from_secs(2),
        };
        assert!(plug
            .command_on(port, "Backlog Power Off; Delay 600")
            .unwrap()
            .contains("\"POWER\":\"ON\""));
        assert_eq!(
            server.join().unwrap().trim(),
            "GET /cm?cmnd=Backlog%20Power%20Off%3B%20Delay%20600 HTTP/1.0"
        );
    }

    #[test]
    fn cli_parses_the_shared_and_own_flags() {
        let cli = Cli::parse_from(["outage"]);
        assert_eq!(
            (cli.cut.as_str(), cli.poll_period.as_str(), cli.timeout.as_str()),
            ("60s", "2s", "5s")
        );
        assert_eq!(
            (cli.broker_host.as_str(), cli.broker_port, cli.log_level),
            ("localhost", 1883, LevelFilter::Info)
        );
        assert!(!cli.dry_run);
        let cli = Cli::parse_from([
            "outage", "-C", "10m", "-F", "11.6", "-U", "plug", "-H", "a,b", "-E", "/tmp/e", "-n", "-P", "1s", "-T",
            "2s", "-B", "mqtt", "-L", "debug",
        ]);
        assert_eq!(
            (
                cli.cut.as_str(),
                cli.floor_volts,
                cli.plug_host.as_str(),
                cli.hosts.as_str()
            ),
            ("10m", 11.6, "plug", "a,b")
        );
        assert!(cli.dry_run);
        assert_eq!(
            (cli.events.as_str(), cli.broker_host.as_str(), cli.log_level),
            ("/tmp/e", "mqtt", LevelFilter::Debug)
        );
        assert!(Cli::try_parse_from(["outage", "-L", "verbose"]).is_err());
    }
}
