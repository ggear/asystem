use std::fmt;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use clap::builder::{PossibleValuesParser, TypedValueParser};
use clap::{Args, CommandFactory, Parser, Subcommand};
use clap_complete::Shell;
use log::LevelFilter;

use crate::drill::{self, Env, Tasmota, Test, Timing};
use crate::{check, init_logging, parse_duration, report, serve, DEFAULT_DEVICE, LEVEL_NAMES};

pub const DEFAULT_DATA_DIR: &str = "/asystem/mnt";
pub const DEFAULT_MODEL_DIR: &str = "/asystem/etc/model";
pub const DEFAULT_HOSTS_FILE: &str = "/asystem/etc/hosts.json";
pub const DEFAULT_SSH_KEY: &str = "/asystem/ssh/id_rsa";
pub const DEFAULT_KNOWN_HOSTS: &str = "/asystem/ssh/known_hosts";
pub const DEFAULT_RUN_DIR: &str = "/run/rackmains";
pub const DEFAULT_PLUG_HOST: &str = "10.0.4.102";
const LIST_LIMIT: usize = 20;

#[derive(Debug)]
pub struct ExitError {
    pub code: u8,
    pub message: String,
}

impl ExitError {
    pub fn new(code: u8, message: &str) -> Self {
        ExitError {
            code,
            message: message.to_string(),
        }
    }
}

impl fmt::Display for ExitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl From<String> for ExitError {
    fn from(message: String) -> Self {
        ExitError { code: 1, message }
    }
}

#[derive(Debug, Parser)]
#[command(
    name = "rackmains",
    about = "Read the rack UPS, publish it, record outages and guard the servers",
    version,
    arg_required_else_help = true
)]
pub struct Cli {
    #[arg(short = 'R', long = "data-dir", help = "directory holding the outage CSVs and the drill state", global = true, value_name = "DIR", env = "RACKMAINS_DATA_DIR", default_value = DEFAULT_DATA_DIR)]
    pub data_dir: String,
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    #[command(about = "run the reader, publisher and guard")]
    Serve(Box<ServeArgs>),
    #[command(about = "validate the model, hosts, ssh keys, data dir and driver socket, then exit")]
    Check(CommonArgs),
    #[command(about = "rehearse a power cut and read the outages", arg_required_else_help = true)]
    Guard {
        #[command(subcommand)]
        command: GuardCommands,
    },
    #[command(about = "print the tab completion script for a shell")]
    Completions {
        #[arg(value_enum, help = "shell to complete for")]
        shell: Shell,
    },
}

#[derive(Debug, Subcommand)]
pub enum GuardCommands {
    #[command(about = "rehearse a power cut", arg_required_else_help = true)]
    Drill {
        #[command(subcommand)]
        command: Box<DrillCommands>,
    },
    #[command(about = "read the recorded outages", arg_required_else_help = true)]
    Outage {
        #[command(subcommand)]
        command: OutageCommands,
    },
}

#[derive(Debug, Subcommand)]
pub enum DrillCommands {
    #[command(about = "print the plan and preflight of a test, cut nothing")]
    Plan(DrillTestArgs),
    #[command(about = "cut mains and run a test, blackout-shed asks for a typed confirmation")]
    Start(DrillTestArgs),
    #[command(
        about = "abort the running drill, mains on and deadman disarmed, or with none running ask to turn an OFF plug on"
    )]
    Stop {
        #[command(flatten)]
        common: CommonArgs,
    },
}

#[derive(Debug, Subcommand)]
pub enum OutageCommands {
    #[command(about = "follow the newest outage CSV, or the given file, as rows arrive")]
    Tail {
        #[arg(value_name = "FILE", help = "outage CSV to follow, default the newest")]
        file: Option<String>,
    },
    #[command(about = "show the recent outages and how each ended")]
    List,
    #[command(
        about = "delete every outage CSV, call log and stray temporary file and a stale drill marker, asks for a typed `clean`, refuses while an outage or drill is open"
    )]
    Clean,
}

#[derive(Debug, Args)]
pub struct DrillTestArgs {
    #[arg(value_enum, help = "test to run")]
    pub test: Test,
    #[arg(
        short = 'F',
        long,
        help = "time mains is held off, a blip under the shed point and a brownout at or over it",
        value_name = "DUR"
    )]
    pub hold: Option<String>,
    #[command(flatten)]
    pub common: CommonArgs,
}

#[derive(Debug, Args)]
pub struct CommonArgs {
    #[arg(short = 'D', long = "device", help = "NUT driver socket", value_name = "SOCKET", hide_short_help = true, default_value = DEFAULT_DEVICE)]
    pub device: String,
    #[arg(short = 'M', long = "model-dir", help = "directory of the released battery model", value_name = "DIR", hide_short_help = true, env = "RACKMAINS_MODEL_DIR", default_value = DEFAULT_MODEL_DIR)]
    pub model_dir: String,
    #[arg(
        short = 'T',
        long = "timeout",
        help = "timeout of one driver read",
        value_name = "PERIOD",
        hide_short_help = true,
        default_value = "1s"
    )]
    pub timeout: String,
    #[arg(short = 'H', long = "hosts-file", help = "JSON list of the servers the guard sheds and wakes", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_HOSTS_FILE", default_value = DEFAULT_HOSTS_FILE)]
    pub hosts_file: String,
    #[arg(
        short = 'C',
        long = "local-host",
        help = "this host, shed with asleep --shallow",
        value_name = "NAME",
        hide_short_help = true,
        env = "RACKMAINS_LOCAL_HOST",
        default_value = "max"
    )]
    pub local_host: String,
    #[arg(short = 'S', long = "ssh-key", help = "private key for the shed and wake calls", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_SSH_KEY", default_value = DEFAULT_SSH_KEY)]
    pub ssh_key: String,
    #[arg(short = 'N', long = "known-hosts", help = "pinned host keys for the shed and wake calls", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_KNOWN_HOSTS", default_value = DEFAULT_KNOWN_HOSTS)]
    pub known_hosts: String,
    #[arg(short = 'U', long = "run-dir", help = "directory of the liveness file", value_name = "DIR", hide_short_help = true, env = "RACKMAINS_RUN_DIR", default_value = DEFAULT_RUN_DIR)]
    pub run_dir: String,
    #[arg(short = 'G', long = "plug-host", help = "host of the rack plug", value_name = "HOST", hide_short_help = true, env = "RACKMAINS_PLUG_HOST", default_value = DEFAULT_PLUG_HOST)]
    pub plug_host: String,
}

#[derive(Debug, Args)]
pub struct ServeArgs {
    #[arg(
        short = 'P',
        long = "poll-period",
        help = "how often the driver is read",
        value_name = "PERIOD",
        default_value = "1s"
    )]
    pub poll_period: String,
    #[arg(
        short = 'A',
        long = "mains-publish-period",
        help = "how often mains is published, every poll on battery",
        value_name = "PERIOD",
        default_value = "5s"
    )]
    pub mains_publish_period: String,
    #[arg(
        short = 'B',
        long = "broker-host",
        help = "MQTT broker host",
        value_name = "HOST",
        env = "BROKER_HOST",
        default_value = "localhost"
    )]
    pub broker_host: String,
    #[arg(
        short = 'O',
        long = "broker-port",
        help = "MQTT broker port",
        value_name = "PORT",
        hide_short_help = true,
        env = "BROKER_PORT",
        default_value = "1883"
    )]
    pub broker_port: u16,
    #[arg(
        short = 'K',
        long = "broker-token",
        help = "MQTT broker token",
        value_name = "TOKEN",
        hide_short_help = true,
        env = "BROKER_TOKEN",
        default_value = ""
    )]
    pub broker_token: String,
    #[arg(
        short = 'E',
        long = "outage-keep",
        help = "number of outage CSVs kept",
        value_name = "COUNT",
        hide_short_help = true,
        env = "RACKMAINS_OUTAGE_LOG_KEEP",
        default_value = "100"
    )]
    pub outage_keep: usize,
    #[arg(
        short = 'I',
        long = "battery-installed",
        help = "date the battery was installed, YYYY-MM-DD, for its age",
        value_name = "DATE",
        hide_short_help = true,
        env = "RACKMAINS_BATTERY_INSTALLED",
        default_value = ""
    )]
    pub battery_installed: String,
    #[arg(
        long = "dry-run",
        help = "log the shed and wake calls instead of making them, implied by the mock"
    )]
    pub dry_run: bool,
    #[arg(
        short = 'L',
        long = "log-level", help = "log verbosity",
        value_name = "LEVEL",
        default_value = "info",
        env = "RACKMAINS_LOG_LEVEL",
        value_parser = PossibleValuesParser::new(LEVEL_NAMES.iter().map(|name| name.as_str()))
            .map(|name| name.parse::<LevelFilter>().unwrap())
    )]
    pub log_level: LevelFilter,
    #[command(flatten)]
    pub common: CommonArgs,
}

impl Cli {
    pub fn run(&self) -> Result<(), ExitError> {
        let data_dir = Path::new(&self.data_dir);
        match &self.command {
            Commands::Serve(args) => serve::run(args, data_dir).map_err(ExitError::from),
            Commands::Check(common) => run_check(common, data_dir),
            Commands::Completions { shell } => {
                clap_complete::generate(*shell, &mut Cli::command(), "rackmains", &mut std::io::stdout());
                Ok(())
            }
            Commands::Guard { command } => match command {
                GuardCommands::Drill { command } => match command.as_ref() {
                    DrillCommands::Plan(args) => drill::run_drill(
                        &drill_env(&args.common, data_dir),
                        args.test,
                        args.hold.as_deref(),
                        false,
                    ),
                    DrillCommands::Start(args) => drill::run_drill(
                        &drill_env(&args.common, data_dir),
                        args.test,
                        args.hold.as_deref(),
                        true,
                    ),
                    DrillCommands::Stop { common } => {
                        drill::run_stop(&drill_env(common, data_dir), drill::confirm_typed)
                    }
                },
                GuardCommands::Outage { command } => match command {
                    OutageCommands::Tail { file } => report::tail(
                        &data_dir.join(crate::outage::DIR_OUTAGE),
                        file.as_deref().map(Path::new),
                        true,
                        &mut std::io::stdout(),
                    )
                    .map_err(ExitError::from),
                    OutageCommands::List => {
                        for line in report::list(&data_dir.join(crate::outage::DIR_OUTAGE), LIST_LIMIT) {
                            println!("{line}");
                        }
                        Ok(())
                    }
                    OutageCommands::Clean => run_clean(data_dir, drill::confirm_typed),
                },
            },
        }
    }
}

pub fn run_clean(data_dir: &Path, confirm: impl FnOnce(&str, &str) -> Result<bool, String>) -> Result<(), ExitError> {
    let outage_dir = data_dir.join(crate::outage::DIR_OUTAGE);
    let marker_path = data_dir.join(crate::outage::DIR_STATE).join(drill::FILE_MARKER);
    if drill::Marker::read(&marker_path).is_some_and(|marker| marker.live(chrono::Local::now().naive_local())) {
        return Err(ExitError::new(1, "a drill is armed, nothing was deleted"));
    }
    if crate::outage::open_file(&outage_dir).is_some() {
        return Err(ExitError::new(
            1,
            "an outage is open and being written, nothing was deleted",
        ));
    }
    let mut paths = crate::outage::removable(&outage_dir);
    if marker_path.is_file() {
        paths.push(marker_path);
    }
    if paths.is_empty() {
        println!("nothing to delete under [{}]", data_dir.display());
        return Ok(());
    }
    let bytes: u64 = paths
        .iter()
        .filter_map(|path| std::fs::metadata(path).ok())
        .map(|metadata| metadata.len())
        .sum();
    let prompt = format!(
        "this deletes [{}] files [{bytes}] bytes under [{}], real outages included, and cannot be undone",
        paths.len(),
        data_dir.display()
    );
    if !confirm(&prompt, "clean")? {
        return Err(ExitError::new(1, "clean was not confirmed, nothing was deleted"));
    }
    for path in &paths {
        std::fs::remove_file(path).map_err(|err| format!("failed to delete [{}] [{err}]", path.display()))?;
    }
    println!(
        "deleted [{}] files, restart the container to clear the last outage values the main program still holds",
        paths.len()
    );
    let version = std::env::var("SERVICE_VERSION_ABSOLUTE").unwrap_or_else(|_| "unknown".to_string());
    println!(
        "the next backup will report a shrink and refuse the next install, accept it on the host from the running version with [/var/lib/asystem/install/rackmains/{version}/backup.sh --accept=<timestamp of the regressed backup>]"
    );
    Ok(())
}

pub fn run_check(common: &CommonArgs, data_dir: &Path) -> Result<(), ExitError> {
    let timeout = parse_duration(&common.timeout)?;
    let outcomes = check::run(&check::Target {
        model_dir: Path::new(&common.model_dir),
        hosts_file: Path::new(&common.hosts_file),
        local_host: &common.local_host,
        ssh_key: Path::new(&common.ssh_key),
        known_hosts: Path::new(&common.known_hosts),
        data_dir,
        device: Path::new(&common.device),
        timeout,
    });
    for outcome in &outcomes {
        match &outcome.result {
            Ok(detail) => println!("ok   {} {detail}", outcome.name),
            Err(err) => println!("FAIL {} {err}", outcome.name),
        }
    }
    let failed = check::failed(&outcomes);
    if failed.is_empty() {
        Ok(())
    } else {
        Err(ExitError::new(1, &format!("check failed [{}]", failed.join(","))))
    }
}

fn drill_env(common: &CommonArgs, data_dir: &Path) -> Env {
    Env {
        data_dir: data_dir.to_path_buf(),
        run_dir: PathBuf::from(&common.run_dir),
        hosts_file: PathBuf::from(&common.hosts_file),
        local_host: common.local_host.clone(),
        plug: Arc::new(Tasmota {
            host: common.plug_host.clone(),
        }),
        plug_host: common.plug_host.clone(),
        timing: Timing::default(),
        clock: || chrono::Local::now().naive_local(),
        refuse_in_backup_window: true,
    }
}

pub fn init_serve_logging(args: &ServeArgs, period: Duration) {
    init_logging(if period.is_zero() {
        args.log_level.max(LevelFilter::Debug)
    } else {
        args.log_level
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn serve(arguments: &[&str]) -> ServeArgs {
        let mut full = vec!["rackmains", "serve"];
        full.extend_from_slice(arguments);
        match Cli::parse_from(full).command {
            Commands::Serve(args) => *args,
            other => panic!("not serve [{other:?}]"),
        }
    }

    #[test]
    fn cli_parses_serve_poll_and_publish_periods() {
        assert_eq!(serve(&[]).poll_period, "1s");
        assert_eq!(serve(&["-P", "10s"]).poll_period, "10s");
        assert_eq!(serve(&["--poll-period", "2m"]).poll_period, "2m");
        assert_eq!(serve(&[]).mains_publish_period, "5s");
        assert_eq!(serve(&["--mains-publish-period", "30s"]).mains_publish_period, "30s");
    }

    #[test]
    fn cli_parses_serve_device_and_timeout_flags() {
        assert_eq!(serve(&[]).common.device, "/run/nut/nutdrv_qx-powershield");
        assert_eq!(serve(&["-D", "/tmp/other"]).common.device, "/tmp/other");
        assert_eq!(serve(&["--device", "/tmp/another"]).common.device, "/tmp/another");
        assert_eq!(serve(&[]).common.timeout, "1s");
        assert_eq!(serve(&["-T", "500ms"]).common.timeout, "500ms");
        assert_eq!(serve(&["--timeout", "2s"]).common.timeout, "2s");
    }

    #[test]
    fn cli_parses_serve_log_level_flags() {
        assert_eq!(serve(&[]).log_level, LevelFilter::Info);
        assert_eq!(serve(&["-L", "debug"]).log_level, LevelFilter::Debug);
        assert_eq!(serve(&["--log-level", "warn"]).log_level, LevelFilter::Warn);
        assert!(Cli::try_parse_from(["rackmains", "serve", "-L", "verbose"]).is_err());
    }

    #[test]
    fn cli_parses_serve_broker_flags() {
        let args = serve(&["-B", "mqtt.local", "--broker-port", "8883", "--broker-token", "secret"]);
        assert_eq!(
            (args.broker_host.as_str(), args.broker_port, args.broker_token.as_str()),
            ("mqtt.local", 8883, "secret")
        );
        let defaults = serve(&[]);
        assert_eq!(
            (defaults.broker_host.as_str(), defaults.broker_port),
            ("localhost", 1883)
        );
    }

    #[test]
    fn cli_parses_serve_guard_and_outage_flags() {
        assert!(!serve(&[]).dry_run);
        assert!(serve(&["--dry-run"]).dry_run);
        assert_eq!(serve(&[]).outage_keep, 100);
        assert_eq!(serve(&["--outage-keep", "7"]).outage_keep, 7);
        assert_eq!(
            serve(&["--battery-installed", "2024-11-12"]).battery_installed,
            "2024-11-12"
        );
        assert_eq!(serve(&["--local-host", "may"]).common.local_host, "may");
    }

    #[test]
    fn cli_parses_the_root_data_dir_before_or_after_the_subcommand() {
        assert_eq!(
            Cli::parse_from(["rackmains", "guard", "outage", "list"]).data_dir,
            "/asystem/mnt"
        );
        assert_eq!(
            Cli::parse_from(["rackmains", "--data-dir", "/x", "guard", "outage", "list"]).data_dir,
            "/x"
        );
        assert_eq!(
            Cli::parse_from(["rackmains", "guard", "outage", "list", "--data-dir", "/y"]).data_dir,
            "/y"
        );
    }

    #[test]
    fn cli_parses_the_guard_subcommands() {
        let guard = |arguments: &[&str]| {
            let mut full = vec!["rackmains", "guard"];
            full.extend_from_slice(arguments);
            match Cli::parse_from(full).command {
                Commands::Guard { command } => command,
                other => panic!("not guard [{other:?}]"),
            }
        };
        let drill = |arguments: &[&str]| match guard(&[&["drill"], arguments].concat()) {
            GuardCommands::Drill { command } => *command,
            other @ GuardCommands::Outage { .. } => panic!("not drill [{other:?}]"),
        };
        let outage = |arguments: &[&str]| match guard(&[&["outage"], arguments].concat()) {
            GuardCommands::Outage { command } => command,
            other @ GuardCommands::Drill { .. } => panic!("not outage [{other:?}]"),
        };
        assert!(Cli::try_parse_from(["rackmains", "guard", "drill"]).is_err());
        assert!(Cli::try_parse_from(["rackmains", "guard", "drill", "start"]).is_err());
        assert!(Cli::try_parse_from(["rackmains", "guard", "drill", "start", "soon"]).is_err());
        assert!(matches!(
            drill(&["plan", "brownout-shed-wake"]),
            DrillCommands::Plan(DrillTestArgs {
                test: Test::Brownout,
                hold: None,
                ..
            })
        ));
        assert!(
            matches!(drill(&["start", "blip-watch", "-F", "90s"]), DrillCommands::Start(DrillTestArgs { test: Test::Blip, hold: Some(ref hold), .. }) if hold == "90s")
        );
        assert!(matches!(
            drill(&["start", "blackout-shed"]),
            DrillCommands::Start(DrillTestArgs {
                test: Test::Blackout,
                hold: None,
                ..
            })
        ));
        assert!(matches!(drill(&["stop"]), DrillCommands::Stop { .. }));
        assert!(Cli::try_parse_from(["rackmains", "guard", "drill", "restore"]).is_err());
        assert!(Cli::try_parse_from(["rackmains", "guard", "drill", "stop", "--force"]).is_err());
        assert!(matches!(outage(&["tail"]), OutageCommands::Tail { file: None }));
        assert!(matches!(outage(&["tail", "x.csv"]), OutageCommands::Tail { file: Some(ref file) } if file == "x.csv"));
        assert!(matches!(outage(&["list"]), OutageCommands::List));
        assert!(matches!(outage(&["clean"]), OutageCommands::Clean));
        assert!(Cli::try_parse_from(["rackmains", "guard", "list"]).is_err());
    }

    #[test]
    fn cli_requires_a_subcommand_and_parses_check() {
        assert!(Cli::try_parse_from(["rackmains"]).is_err());
        assert!(matches!(
            Cli::parse_from(["rackmains", "check"]).command,
            Commands::Check(_)
        ));
    }

    #[test]
    fn an_exit_error_from_a_string_exits_one() {
        assert_eq!(ExitError::from("x".to_string()).code, 1);
    }

    #[test]
    fn every_command_and_option_is_described_and_named_alike() {
        fn walk(command: &clap::Command, path: &str, seen: &mut usize) {
            for arg in command
                .get_arguments()
                .filter(|arg| !matches!(arg.get_id().as_str(), "help" | "version"))
            {
                let name = format!("{path} {}", arg.get_id());
                assert!(arg.get_help().is_some(), "no help [{name}]");
                if let Some(short) = arg.get_short() {
                    assert_eq!(
                        arg.get_action().takes_values(),
                        short.is_ascii_uppercase(),
                        "short [{short}] case [{name}]"
                    );
                }
                if let Some(env) = arg.get_env() {
                    let env = env.to_string_lossy();
                    assert!(
                        env.starts_with("RACKMAINS_") || env.starts_with("BROKER_"),
                        "env [{env}] [{name}]"
                    );
                }
                *seen += 1;
            }
            for sub in command.get_subcommands() {
                let name = format!("{path} {}", sub.get_name());
                assert!(sub.get_about().is_some(), "no about [{name}]");
                walk(sub, &name, seen);
            }
        }
        let mut seen = 0;
        walk(&Cli::command(), "rackmains", &mut seen);
        assert!(seen > 20);
    }

    #[test]
    fn clean_deletes_outage_files_only_when_idle_and_confirmed() {
        use crate::drill::{Marker, FILE_MARKER, STATE_ABORTED, STATE_ARMED};
        use crate::metrics::{header, Frame};
        use crate::outage::{encode_row, file_name, row, DIR_OUTAGE, DIR_STATE};
        let dir = std::env::temp_dir().join(format!("rackmains-clean-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let (outage, state) = (dir.join(DIR_OUTAGE), dir.join(DIR_STATE));
        std::fs::create_dir_all(&outage).unwrap();
        std::fs::create_dir_all(&state).unwrap();
        let write = |stem: &str, ended: bool| {
            let mut text = encode_row(&header());
            text.push('\n');
            let mut events = vec!["start"];
            events.extend(ended.then_some("end"));
            for event in events {
                text.push_str(&encode_row(&row(stem, 0, event, "", &Frame::default())));
                text.push('\n');
            }
            std::fs::write(outage.join(file_name(stem, 1)), text).unwrap();
        };
        let marker = |state: &str| Marker {
            id: "a".to_string(),
            mode: "blip-watch".to_string(),
            hold_seconds: 90,
            planned_cut: "2999-01-01_00-00-00".to_string(),
            expires: "2999-01-01_00-10-00".to_string(),
            state: state.to_string(),
        };
        let never = |_: &str, _: &str| -> Result<bool, String> { panic!("no confirmation expected") };
        run_clean(&dir, never).unwrap();
        write("2026-01-01_00-00-00", true);
        std::fs::write(outage.join("rackmains_call_2026-01-01_00-00-00_max_asleep.log"), "log").unwrap();
        std::fs::write(outage.join("rackmains_outage_2026-01-01_00-00-00_2.csv.tmp"), "junk").unwrap();
        std::fs::write(outage.join("notes.txt"), "keep").unwrap();
        marker(STATE_ABORTED).write(&state.join(FILE_MARKER)).unwrap();
        assert_eq!(run_clean(&dir, |_, word| Ok(word != "clean")).unwrap_err().code, 1);
        assert_eq!(std::fs::read_dir(&outage).unwrap().count(), 4);
        marker(STATE_ARMED).write(&state.join(FILE_MARKER)).unwrap();
        assert_eq!(run_clean(&dir, never).unwrap_err().code, 1);
        marker(STATE_ABORTED).write(&state.join(FILE_MARKER)).unwrap();
        write("2026-01-02_00-00-00", false);
        assert_eq!(run_clean(&dir, never).unwrap_err().code, 1);
        assert!(outage.join(file_name("2026-01-02_00-00-00", 1)).exists());
        std::fs::remove_file(outage.join(file_name("2026-01-02_00-00-00", 1))).unwrap();
        run_clean(&dir, |_, word| Ok(word == "clean")).unwrap();
        assert_eq!(std::fs::read_dir(&outage).unwrap().count(), 1);
        assert!(outage.join("notes.txt").exists());
        assert!(!state.join(FILE_MARKER).exists());
    }
}
