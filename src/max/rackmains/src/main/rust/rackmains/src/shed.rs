use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command as Process, ExitStatus, Stdio};
use std::sync::mpsc::Sender;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use chrono::Local;
use log::{info, warn};
use serde::Deserialize;

use crate::guard::{Call, Command, Host, HOST_SHED_LAST};
use crate::log_line;
use crate::outage;

pub const SSH_STATUS_UNREACHABLE: i32 = 255;
pub const SSH_STATUS_SPAWN: i32 = 127;
pub const SSH_STATUS_LIMIT: i32 = 124;
const LIMIT_POLL: Duration = Duration::from_millis(100);
const SSH_KEEPALIVE: Duration = Duration::from_secs(10);
const SSH_KEEPALIVE_COUNT: u32 = 3;
const RESULT_PREFIX: &str = "RESULT ";
const REMOTE_BIN_DIR: &str = "/usr/local/bin";
const CALL_LOG_PREFIX: &str = "rackmains_call_";
const CALL_LOG_SUFFIX: &str = ".log";
const CALL_LOG_KEEP: usize = 400;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Outcome {
    pub status: i32,
    pub reason: String,
    pub took: Duration,
}

pub trait Runner: Send + Sync {
    fn run(&self, host: &Host, command: Command) -> Outcome;
}

pub struct Ssh {
    pub key: PathBuf,
    pub known_hosts: PathBuf,
    pub timeout: Duration,
    pub limit: Duration,
    pub log_dir: PathBuf,
}

pub struct DryRun;

#[derive(Deserialize)]
struct HostEntry {
    name: String,
    address: String,
}

pub struct Finished {
    pub host: String,
    pub command: Command,
    pub outcome: Outcome,
}

pub fn load_hosts(path: &Path, local: &str) -> Result<Vec<Host>, String> {
    let bytes = fs::read(path).map_err(|err| format!("failed to read hosts [{}] [{err}]", path.display()))?;
    let entries: Vec<HostEntry> =
        serde_json::from_slice(&bytes).map_err(|err| format!("invalid hosts [{}] [{err}]", path.display()))?;
    if entries.is_empty() {
        return Err(format!("no hosts [{}]", path.display()));
    }
    let hosts: Vec<Host> = entries
        .into_iter()
        .map(|entry| Host {
            local: entry.name == local,
            name: entry.name,
            address: entry.address,
        })
        .collect();
    if !hosts.iter().any(|host| host.local) {
        return Err(format!("local host [{local}] not in hosts [{}]", path.display()));
    }
    Ok(hosts)
}

pub fn shed_order(hosts: &[Host]) -> Vec<String> {
    hosts
        .iter()
        .filter(|host| host.name != HOST_SHED_LAST)
        .chain(hosts.iter().filter(|host| host.name == HOST_SHED_LAST))
        .map(|host| host.name.clone())
        .collect()
}

pub fn spawn(runner: &Arc<dyn Runner>, hosts: &[Host], call: Call, results: &Sender<Finished>) {
    let Some(host) = hosts.iter().find(|host| host.name == call.host).cloned() else {
        warn!("{}", log_line("call for unknown host", &call.host));
        let _ = results.send(Finished {
            host: call.host,
            command: call.command,
            outcome: Outcome {
                status: SSH_STATUS_SPAWN,
                reason: "unknown host".to_string(),
                took: Duration::ZERO,
            },
        });
        return;
    };
    let runner = Arc::clone(runner);
    let results = results.clone();
    thread::spawn(move || {
        let outcome = runner.run(&host, call.command);
        let _ = results.send(Finished {
            host: call.host,
            command: call.command,
            outcome,
        });
    });
}

pub fn run_bounded(process: &mut Process, limit: Duration) -> std::io::Result<(Option<ExitStatus>, Vec<u8>, Vec<u8>)> {
    let mut child = process
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let drain = |pipe: Option<Box<dyn Read + Send>>| {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            if let Some(mut pipe) = pipe {
                let _ = pipe.read_to_end(&mut bytes);
            }
            bytes
        })
    };
    let stdout = drain(child.stdout.take().map(|pipe| Box::new(pipe) as Box<dyn Read + Send>));
    let stderr = drain(child.stderr.take().map(|pipe| Box::new(pipe) as Box<dyn Read + Send>));
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break Some(status);
        }
        if started.elapsed() >= limit {
            let _ = child.kill();
            let _ = child.wait();
            break None;
        }
        thread::sleep(LIMIT_POLL);
    };
    Ok((
        status,
        stdout.join().unwrap_or_default(),
        stderr.join().unwrap_or_default(),
    ))
}

pub fn parse_result(output: &str) -> String {
    output
        .lines()
        .rev()
        .find_map(|line| {
            line.strip_prefix(RESULT_PREFIX)
                .or_else(|| line.split_once(" RESULT ").map(|(_, rest)| rest))
        })
        .unwrap_or_default()
        .trim()
        .to_string()
}

impl Runner for Ssh {
    fn run(&self, host: &Host, command: Command) -> Outcome {
        let started = Instant::now();
        let output = run_bounded(
            Process::new("ssh")
                .arg("-i")
                .arg(&self.key)
                .args([
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "IdentitiesOnly=yes",
                    "-o",
                    "StrictHostKeyChecking=yes",
                ])
                .arg("-o")
                .arg(format!("UserKnownHostsFile={}", self.known_hosts.display()))
                .arg("-o")
                .arg(format!("ConnectTimeout={}", self.timeout.as_secs()))
                .arg("-o")
                .arg(format!("ServerAliveInterval={}", SSH_KEEPALIVE.as_secs()))
                .arg("-o")
                .arg(format!("ServerAliveCountMax={SSH_KEEPALIVE_COUNT}"))
                .arg(format!("root@{}", host.address))
                .arg(format!("{REMOTE_BIN_DIR}/{}", command.remote())),
            self.limit,
        );
        let took = started.elapsed();
        match output {
            Ok((exit, stdout, stderr)) => {
                let status = exit.map_or(SSH_STATUS_LIMIT, |exit| exit.code().unwrap_or(SSH_STATUS_UNREACHABLE));
                let mut reason = parse_result(&String::from_utf8_lossy(&stdout));
                if reason.is_empty() && status == SSH_STATUS_UNREACHABLE {
                    reason = "unreachable".to_string();
                }
                if reason.is_empty() && status == SSH_STATUS_LIMIT {
                    reason = "call limit reached".to_string();
                }
                let label = format!("ssh call {}", host.name);
                info!("{}", log_line(&label, command.remote()));
                info!("{}", log_line(&format!("{label} status"), &status.to_string()));
                info!("{}", log_line(&format!("{label} took"), &format!("{took:?}")));
                let record = || -> std::io::Result<()> {
                    let name = format!(
                        "{CALL_LOG_PREFIX}{}_{}_{}{CALL_LOG_SUFFIX}",
                        outage::stamp(Local::now()),
                        host.name,
                        command.remote().split(' ').next().unwrap_or_default()
                    );
                    fs::write(
                        self.log_dir.join(name),
                        format!(
                            "host [{}]\ncommand [{}]\nstatus [{status}]\ntook [{took:?}]\n--- stdout\n{}\n--- stderr\n{}\n",
                            host.name,
                            command.remote(),
                            String::from_utf8_lossy(&stdout),
                            String::from_utf8_lossy(&stderr)
                        ),
                    )?;
                    let mut logs: Vec<PathBuf> = fs::read_dir(&self.log_dir)?
                        .flatten()
                        .map(|entry| entry.path())
                        .filter(|path| {
                            path.file_name().and_then(|name| name.to_str()).is_some_and(|name| {
                                name.starts_with(CALL_LOG_PREFIX) && name.ends_with(CALL_LOG_SUFFIX)
                            })
                        })
                        .collect();
                    logs.sort();
                    for old in logs.iter().take(logs.len().saturating_sub(CALL_LOG_KEEP)) {
                        fs::remove_file(old)?;
                    }
                    Ok(())
                };
                if let Err(err) = record() {
                    warn!(
                        "{}",
                        log_line(&format!("ssh call {} log failed", host.name), &err.to_string())
                    );
                }
                Outcome { status, reason, took }
            }
            Err(err) => Outcome {
                status: SSH_STATUS_SPAWN,
                reason: format!("failed to run ssh [{err}]"),
                took,
            },
        }
    }
}

impl Runner for DryRun {
    fn run(&self, _host: &Host, _command: Command) -> Outcome {
        Outcome {
            status: 0,
            reason: "dry-run".to_string(),
            took: Duration::ZERO,
        }
    }
}

#[cfg(test)]
pub mod mock {
    use std::sync::Mutex;

    use super::*;

    #[derive(Default)]
    pub struct MockRunner {
        pub calls: Mutex<Vec<(String, Command)>>,
        pub status: i32,
    }

    impl Runner for MockRunner {
        fn run(&self, host: &Host, command: Command) -> Outcome {
            self.calls.lock().unwrap().push((host.name.clone(), command));
            Outcome {
                status: self.status,
                reason: String::new(),
                took: Duration::ZERO,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use super::*;

    fn write(name: &str, text: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("rackmains-hosts-{name}-{}.json", std::process::id()));
        fs::write(&path, text).unwrap();
        path
    }

    #[test]
    fn hosts_load_in_file_order_with_the_local_one_marked() {
        let path = write(
            "ok",
            r#"[{"name":"mad","address":"macmini-mad"},{"name":"max","address":"macmini-max"},{"name":"meg","address":"macmini-meg"}]"#,
        );
        let hosts = load_hosts(&path, "max").unwrap();
        assert_eq!(
            hosts.iter().map(|host| host.local).collect::<Vec<_>>(),
            vec![false, true, false]
        );
        assert_eq!(shed_order(&hosts), vec!["mad", "max", "meg"]);
    }

    #[test]
    fn meg_is_shed_last_wherever_it_is_listed() {
        let hosts: Vec<Host> = ["meg", "mad", "max"]
            .iter()
            .map(|name| Host {
                name: (*name).to_string(),
                address: String::new(),
                local: false,
            })
            .collect();
        assert_eq!(shed_order(&hosts), vec!["mad", "max", "meg"]);
    }

    #[test]
    fn a_bad_host_file_is_refused() {
        assert!(load_hosts(Path::new("/nonexistent"), "max").is_err());
        assert!(load_hosts(&write("garbled", "{"), "max").is_err());
        assert!(load_hosts(&write("empty", "[]"), "max").is_err());
        assert!(load_hosts(&write("nolocal", r#"[{"name":"mad","address":"a"}]"#), "max").is_err());
    }

    #[test]
    fn the_last_result_line_is_the_reason() {
        let output = "log line\nRESULT asleep status=0 reason=ok\nRESULT awake status=6 reason=unhealthy\n";
        assert_eq!(parse_result(output), "awake status=6 reason=unhealthy");
        let logged = "2026-11-13T09:43:57+0800 INFO  Log kept at [/run/asleep.log], took [3677] ms\n\
                      2026-11-13T09:43:57+0800 INFO  RESULT asleep status=0 reason=ok mode=shallow failed=0 warnings=1 timeouts=0\n\
                      2026-11-13T09:43:57+0800 DEBUG Exiting, exit code [0]\n";
        assert_eq!(
            parse_result(logged),
            "asleep status=0 reason=ok mode=shallow failed=0 warnings=1 timeouts=0"
        );
        assert_eq!(parse_result("nothing"), "");
    }

    #[test]
    fn a_spawned_call_reports_its_outcome_and_an_unknown_host_fails_without_a_thread() {
        let runner: Arc<dyn Runner> = Arc::new(mock::MockRunner {
            status: 4,
            ..mock::MockRunner::default()
        });
        let hosts = vec![Host {
            name: "mad".to_string(),
            address: "macmini-mad".to_string(),
            local: false,
        }];
        let (sender, receiver) = mpsc::channel();
        spawn(
            &runner,
            &hosts,
            Call {
                host: "mad".to_string(),
                command: Command::AsleepDeep,
            },
            &sender,
        );
        let finished = receiver.recv_timeout(Duration::from_secs(2)).unwrap();
        assert_eq!((finished.host.as_str(), finished.outcome.status), ("mad", 4));
        spawn(
            &runner,
            &hosts,
            Call {
                host: "zzz".to_string(),
                command: Command::Awake,
            },
            &sender,
        );
        assert_eq!(
            receiver.recv_timeout(Duration::from_secs(2)).unwrap().outcome.status,
            SSH_STATUS_SPAWN
        );
    }

    #[test]
    fn a_bounded_run_kills_a_call_past_the_limit_and_keeps_the_output_of_one_inside_it() {
        let (status, stdout, _) = run_bounded(Process::new("echo").arg("done"), Duration::from_secs(5)).unwrap();
        assert_eq!(status.and_then(|status| status.code()), Some(0));
        assert_eq!(String::from_utf8_lossy(&stdout).trim(), "done");
        let started = Instant::now();
        let (status, _, _) = run_bounded(Process::new("sleep").arg("30"), Duration::from_millis(300)).unwrap();
        assert!(status.is_none());
        assert!(started.elapsed() < Duration::from_secs(10));
    }

    #[test]
    fn a_dry_run_succeeds_without_running_anything() {
        let host = Host {
            name: "mad".to_string(),
            address: "x".to_string(),
            local: false,
        };
        assert_eq!(DryRun.run(&host, Command::Awake).status, 0);
    }
}
