use std::collections::HashMap;
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;

use log::{info, warn};

use crate::guard::{Call, Command, Host, AWAKE_UNHEALTHY};
use crate::log_line;
use crate::shed::{self, Finished, Runner};

pub fn state_topic(host: &str) -> String {
    format!("rackmains/host/{host}/state")
}

pub struct HostSwitch {
    commands: Option<Receiver<(String, Vec<u8>)>>,
    results: Receiver<Finished>,
    sender: Sender<Finished>,
    running: bool,
    state: HashMap<String, bool>,
}

impl HostSwitch {
    pub fn new(commands: Option<Receiver<(String, Vec<u8>)>>) -> HostSwitch {
        let (sender, results) = mpsc::channel();
        HostSwitch {
            commands,
            results,
            sender,
            running: false,
            state: HashMap::new(),
        }
    }

    pub fn tick(&mut self, idle: bool, runner: &Arc<dyn Runner>, hosts: &[Host]) -> Vec<(String, Vec<u8>)> {
        let mut published = Vec::new();
        while let Ok(finished) = self.results.try_recv() {
            self.running = false;
            published.extend(self.observe(&finished.host, finished.command, finished.outcome.status));
        }
        let Some(commands) = self.commands.take() else {
            return published;
        };
        while let Ok((topic, payload)) = commands.try_recv() {
            match parse_command(&topic, &payload) {
                Err(reason) => warn!("{}", log_line("host switch command refused", &reason)),
                Ok((host, _)) if !hosts.iter().any(|known| known.name == host) => {
                    warn!("{}", log_line("host switch command for unknown host", &host));
                }
                Ok((host, _)) if !idle => {
                    warn!("{}", log_line("host switch command refused guard busy", &host));
                }
                Ok((host, _)) if self.running => {
                    warn!("{}", log_line("host switch command refused call in flight", &host));
                }
                Ok((host, on)) if self.state.get(&host) == Some(&on) => {
                    info!(
                        "{}",
                        log_line(
                            "host switch command skipped already in state",
                            &format!("{host} {}", payload_of(on))
                        )
                    );
                    published.push((state_topic(&host), payload_of(on).as_bytes().to_vec()));
                }
                Ok((host, on)) => {
                    let command = if on { Command::Awake } else { Command::Asleep };
                    info!(
                        "{}",
                        log_line("host switch command accepted", &format!("{host} {}", payload_of(on)))
                    );
                    self.running = true;
                    shed::spawn(runner, hosts, Call { host, command }, &self.sender);
                }
            }
        }
        self.commands = Some(commands);
        published
    }

    pub fn observe(&mut self, host: &str, command: Command, status: i32) -> Vec<(String, Vec<u8>)> {
        let reached = match command {
            Command::Awake if status == 0 || status == AWAKE_UNHEALTHY => Some(true),
            Command::Asleep if status == 0 => Some(false),
            _ => None,
        };
        let Some(on) = reached else {
            return Vec::new();
        };
        self.state.insert(host.to_string(), on);
        vec![(state_topic(host), payload_of(on).as_bytes().to_vec())]
    }
}

pub fn parse_command(topic: &str, payload: &[u8]) -> Result<(String, bool), String> {
    let tokens: Vec<&str> = topic.split('/').collect();
    if tokens.len() != 5
        || tokens[0] != "supervisor"
        || tokens[2] != "command"
        || tokens[3] != "host"
        || tokens[4].is_empty()
    {
        return Err(format!("topic [{topic}] is not a host command"));
    }
    match String::from_utf8_lossy(payload).trim().to_uppercase().as_str() {
        COMMAND_ON => Ok((tokens[4].to_string(), true)),
        COMMAND_OFF => Ok((tokens[4].to_string(), false)),
        other => Err(format!("payload [{other}] is neither ON nor OFF")),
    }
}

fn payload_of(on: bool) -> &'static str {
    if on {
        COMMAND_ON
    } else {
        COMMAND_OFF
    }
}

pub const COMMAND_FILTER: &str = "supervisor/+/command/host/+";
// Owner is supervisor's metric_schema.go CommandOn and CommandOff, mirrored here with the COMMAND_ prefix.
pub const COMMAND_ON: &str = "ON";
pub const COMMAND_OFF: &str = "OFF";

#[cfg(test)]
mod tests {
    use std::thread;
    use std::time::{Duration, Instant};

    use super::*;
    use crate::shed::mock::MockRunner;

    fn hosts() -> Vec<Host> {
        ["mad", "max"]
            .iter()
            .map(|name| Host {
                name: (*name).to_string(),
                address: format!("macmini-{name}"),
            })
            .collect()
    }

    struct Rig {
        switch: HostSwitch,
        sender: Sender<(String, Vec<u8>)>,
        runner: Arc<MockRunner>,
        as_runner: Arc<dyn Runner>,
    }

    fn rig(status: i32) -> Rig {
        let (sender, commands) = mpsc::channel();
        let runner = Arc::new(MockRunner {
            status,
            ..MockRunner::default()
        });
        let as_runner: Arc<dyn Runner> = runner.clone();
        Rig {
            switch: HostSwitch::new(Some(commands)),
            sender,
            runner,
            as_runner,
        }
    }

    impl Rig {
        fn send(&self, host: &str, payload: &str) {
            self.sender
                .send((
                    format!("supervisor/macmini-{host}/command/host/{host}"),
                    payload.as_bytes().to_vec(),
                ))
                .unwrap();
        }

        fn tick(&mut self, idle: bool) -> Vec<(String, Vec<u8>)> {
            self.switch.tick(idle, &self.as_runner, &hosts())
        }

        fn settle(&mut self) -> Vec<(String, Vec<u8>)> {
            let started = Instant::now();
            let mut published = Vec::new();
            while started.elapsed() < Duration::from_secs(5) {
                published.extend(self.tick(true));
                if !self.switch.running {
                    break;
                }
                thread::sleep(Duration::from_millis(10));
            }
            published
        }

        fn calls(&self) -> Vec<(String, Command)> {
            self.runner.calls.lock().unwrap().clone()
        }
    }

    fn published(state: &str, host: &str) -> (String, Vec<u8>) {
        (format!("rackmains/host/{host}/state"), state.as_bytes().to_vec())
    }

    #[test]
    fn a_command_is_parsed_from_its_topic_and_payload() {
        let tests = [
            (
                "supervisor/macmini-mad/command/host/mad",
                "ON",
                Ok(("mad".to_string(), true)),
            ),
            (
                "supervisor/macmini-mad/command/host/mad",
                " off\n",
                Ok(("mad".to_string(), false)),
            ),
            ("supervisor/macmini-mad/command/service/mad", "ON", Err(())),
            ("supervisor/macmini-mad/command/host/", "ON", Err(())),
            ("supervisor/all/command/cluster", "ON", Err(())),
            ("supervisor/macmini-mad/command/host/mad", "SLEEP", Err(())),
            ("supervisor/macmini-mad/command/host/mad", "", Err(())),
        ];
        for (topic, payload, expected) in tests {
            assert_eq!(
                parse_command(topic, payload.as_bytes()).map_err(|_| ()),
                expected,
                "{topic} {payload}"
            );
        }
    }

    #[test]
    fn off_asleeps_the_host_and_on_awakes_it_and_each_reports_its_state_once_it_has_succeeded() {
        let mut rig = rig(0);
        rig.send("mad", "OFF");
        rig.tick(true);
        assert_eq!(rig.settle(), vec![published("OFF", "mad")]);
        rig.send("mad", "ON");
        rig.tick(true);
        assert_eq!(rig.settle(), vec![published("ON", "mad")]);
        assert_eq!(
            rig.calls(),
            vec![
                ("mad".to_string(), Command::Asleep),
                ("mad".to_string(), Command::Awake)
            ]
        );
    }

    #[test]
    fn a_failed_call_reports_nothing_so_the_switch_stays_where_it_was() {
        let mut rig = rig(1);
        rig.send("mad", "OFF");
        rig.tick(true);
        assert!(rig.settle().is_empty());
        assert_eq!(rig.calls().len(), 1);
    }

    #[test]
    fn an_unhealthy_awake_still_counts_as_awake() {
        let mut rig = rig(AWAKE_UNHEALTHY);
        rig.send("mad", "ON");
        rig.tick(true);
        assert_eq!(rig.settle(), vec![published("ON", "mad")]);
    }

    #[test]
    fn nothing_is_commanded_while_the_guard_is_busy_and_the_command_is_not_kept() {
        let mut rig = rig(0);
        rig.send("mad", "OFF");
        assert!(rig.tick(false).is_empty());
        assert!(rig.settle().is_empty());
        assert!(rig.calls().is_empty());
    }

    struct Blocking {
        calls: std::sync::Mutex<Vec<(String, Command)>>,
        release: std::sync::Mutex<Receiver<()>>,
    }

    impl Runner for Blocking {
        fn run(&self, host: &Host, command: Command) -> crate::shed::Outcome {
            self.calls.lock().unwrap().push((host.name.clone(), command));
            let _ = self.release.lock().unwrap().recv();
            crate::shed::Outcome {
                status: 0,
                reason: String::new(),
                took: Duration::ZERO,
            }
        }
    }

    #[test]
    fn a_second_command_while_one_is_in_flight_is_refused_and_not_kept() {
        let (release, wait) = mpsc::channel();
        let blocking = Arc::new(Blocking {
            calls: std::sync::Mutex::new(Vec::new()),
            release: std::sync::Mutex::new(wait),
        });
        let runner: Arc<dyn Runner> = blocking.clone();
        let (sender, commands) = mpsc::channel();
        let mut switch = HostSwitch::new(Some(commands));
        sender
            .send(("supervisor/macmini-mad/command/host/mad".to_string(), b"OFF".to_vec()))
            .unwrap();
        sender
            .send(("supervisor/macmini-max/command/host/max".to_string(), b"OFF".to_vec()))
            .unwrap();
        switch.tick(true, &runner, &hosts());
        sender
            .send(("supervisor/macmini-max/command/host/max".to_string(), b"OFF".to_vec()))
            .unwrap();
        switch.tick(true, &runner, &hosts());
        release.send(()).unwrap();
        let started = Instant::now();
        while switch.running && started.elapsed() < Duration::from_secs(5) {
            switch.tick(true, &runner, &hosts());
            thread::sleep(Duration::from_millis(10));
        }
        thread::sleep(Duration::from_millis(50));
        assert_eq!(
            *blocking.calls.lock().unwrap(),
            vec![("mad".to_string(), Command::Asleep)]
        );
    }

    #[test]
    fn a_command_for_the_state_the_host_already_has_is_skipped_and_the_state_republished() {
        let mut rig = rig(0);
        rig.send("mad", "OFF");
        rig.tick(true);
        rig.settle();
        rig.send("mad", "OFF");
        assert_eq!(rig.tick(true), vec![published("OFF", "mad")]);
        assert_eq!(rig.calls().len(), 1);
    }

    #[test]
    fn an_unknown_host_and_a_bad_payload_do_nothing_and_leave_nothing_in_flight() {
        let mut rig = rig(0);
        rig.send("nobody", "OFF");
        rig.send("mad", "RESTART");
        assert!(rig.tick(true).is_empty());
        assert!(!rig.switch.running);
        assert!(rig.settle().is_empty());
        assert!(rig.calls().is_empty());
    }

    #[test]
    fn a_wake_or_shed_the_guard_made_is_reported_too() {
        let mut switch = HostSwitch::new(None);
        assert_eq!(switch.observe("meg", Command::Asleep, 0), vec![published("OFF", "meg")]);
        assert_eq!(switch.observe("meg", Command::Awake, 0), vec![published("ON", "meg")]);
        assert!(switch.observe("meg", Command::Asleep, 1).is_empty());
    }

    #[test]
    fn command_words_equal_the_owner_in_supervisor() {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../../../../all/supervisor/src/main/go/supervisor/internal/metric/metric_schema.go");
        let source = std::fs::read_to_string(&path)
            .unwrap_or_else(|err| panic!("owner unreadable [{}] [{err}]", path.display()));
        let word = |name: &str| {
            source
                .lines()
                .find_map(|line| {
                    let mut parts = line.split('=');
                    (parts.next()?.trim() == name)
                        .then(|| parts.next().map(|value| value.trim().trim_matches('"').to_string()))?
                })
                .unwrap_or_else(|| panic!("owner has no [{name}]"))
        };
        assert_eq!(word("CommandOn"), COMMAND_ON);
        assert_eq!(word("CommandOff"), COMMAND_OFF);
    }
}
