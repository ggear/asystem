use std::fmt;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use clap::builder::{BoolishValueParser, PossibleValuesParser, TypedValueParser};
use clap::{Args, Parser, Subcommand};
use log::LevelFilter;

use crate::drill::{self, Env, Tasmota, Timing};
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
    #[arg(long = "data-dir", global = true, value_name = "DIR", env = "RACKMAINS_DATA_DIR", default_value = DEFAULT_DATA_DIR)]
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
    #[command(about = "operate on the guard", arg_required_else_help = true)]
    Guard {
        #[command(subcommand)]
        command: GuardCommands,
    },
}

#[derive(Debug, Subcommand)]
pub enum GuardCommands {
    #[command(about = "rehearse a power cut, print the plan without --force")]
    Drill {
        #[arg(value_name = "DUR|drain")]
        target: Option<String>,
        #[arg(long, help = "cut mains")]
        force: bool,
        #[command(flatten)]
        common: CommonArgs,
    },
    #[command(about = "abort the active drill, mains on and deadman disarmed")]
    Stop {
        #[arg(long, help = "restore the plug even with no drill running")]
        force: bool,
        #[command(flatten)]
        common: CommonArgs,
    },
    #[command(about = "follow the newest outage CSV, or the given file, as rows arrive")]
    Tail { file: Option<String> },
    #[command(about = "show the recent outages and how each ended")]
    List,
}

#[derive(Debug, Args)]
pub struct CommonArgs {
    #[arg(short = 'D', long = "device", value_name = "SOCKET", hide_short_help = true, default_value = DEFAULT_DEVICE)]
    pub device: String,
    #[arg(short = 'M', long = "model-dir", value_name = "DIR", hide_short_help = true, env = "RACKMAINS_MODEL_DIR", default_value = DEFAULT_MODEL_DIR)]
    pub model_dir: String,
    #[arg(
        short = 'T',
        long = "timeout",
        value_name = "PERIOD",
        hide_short_help = true,
        default_value = "1s"
    )]
    pub timeout: String,
    #[arg(long = "hosts-file", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_HOSTS_FILE", default_value = DEFAULT_HOSTS_FILE)]
    pub hosts_file: String,
    #[arg(
        long = "local-host",
        value_name = "NAME",
        hide_short_help = true,
        env = "RACKMAINS_LOCAL_HOST",
        default_value = "max"
    )]
    pub local_host: String,
    #[arg(long = "ssh-key", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_SSH_KEY", default_value = DEFAULT_SSH_KEY)]
    pub ssh_key: String,
    #[arg(long = "known-hosts", value_name = "FILE", hide_short_help = true, env = "RACKMAINS_KNOWN_HOSTS", default_value = DEFAULT_KNOWN_HOSTS)]
    pub known_hosts: String,
    #[arg(long = "run-dir", value_name = "DIR", hide_short_help = true, env = "RACKMAINS_RUN_DIR", default_value = DEFAULT_RUN_DIR)]
    pub run_dir: String,
    #[arg(long = "plug-host", value_name = "HOST", hide_short_help = true, env = "RACKMAINS_PLUG_HOST", default_value = DEFAULT_PLUG_HOST)]
    pub plug_host: String,
}

#[derive(Debug, Args)]
pub struct ServeArgs {
    #[arg(short = 'P', long = "poll-period", value_name = "PERIOD", default_value = "1s")]
    pub poll_period: String,
    #[arg(long = "mains-publish-period", value_name = "PERIOD", default_value = "5s")]
    pub mains_publish_period: String,
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
        hide_short_help = true,
        env = "BROKER_PORT",
        default_value = "1883"
    )]
    pub broker_port: u16,
    #[arg(
        long = "broker-token",
        value_name = "TOKEN",
        hide_short_help = true,
        env = "BROKER_TOKEN",
        default_value = ""
    )]
    pub broker_token: String,
    #[arg(
        long = "outage-keep",
        value_name = "COUNT",
        hide_short_help = true,
        env = "RACKMAINS_OUTAGE_LOG_KEEP",
        default_value = "100"
    )]
    pub outage_keep: usize,
    #[arg(
        long = "battery-installed",
        value_name = "DATE",
        hide_short_help = true,
        env = "RACKMAINS_BATTERY_INSTALLED",
        default_value = ""
    )]
    pub battery_installed: String,
    #[arg(
        long,
        help = "the guard sheds for real, otherwise dry-run",
        env = "RACKMAINS_GUARD_LIVE",
        value_parser = BoolishValueParser::new(),
        num_args = 0..=1,
        default_missing_value = "true",
        default_value = "false"
    )]
    pub live: bool,
    #[arg(
        short = 'L',
        long = "log-level",
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
            Commands::Guard { command } => match command {
                GuardCommands::Drill { target, force, common } => {
                    drill::run_drill(&drill_env(common, data_dir), target.as_deref(), *force)
                }
                GuardCommands::Stop { force, common } => drill::run_stop(&drill_env(common, data_dir), *force),
                GuardCommands::Tail { file } => report::tail(
                    &data_dir.join(crate::outage::DIR_OUTAGE),
                    file.as_deref().map(Path::new),
                    true,
                    &mut std::io::stdout(),
                )
                .map_err(ExitError::from),
                GuardCommands::List => {
                    for line in report::list(&data_dir.join(crate::outage::DIR_OUTAGE), LIST_LIMIT) {
                        println!("{line}");
                    }
                    Ok(())
                }
            },
        }
    }
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
        assert!(!serve(&[]).live);
        assert!(serve(&["--live"]).live);
        assert!(serve(&["--live=1"]).live);
        assert!(!serve(&["--live=0"]).live);
        assert!(serve(&["--live", "true"]).live);
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
        assert_eq!(Cli::parse_from(["rackmains", "guard", "list"]).data_dir, "/asystem/mnt");
        assert_eq!(
            Cli::parse_from(["rackmains", "--data-dir", "/x", "guard", "list"]).data_dir,
            "/x"
        );
        assert_eq!(
            Cli::parse_from(["rackmains", "guard", "list", "--data-dir", "/y"]).data_dir,
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
        assert!(matches!(
            guard(&["drill"]),
            GuardCommands::Drill {
                target: None,
                force: false,
                ..
            }
        ));
        assert!(
            matches!(guard(&["drill", "4m", "--force"]), GuardCommands::Drill { target: Some(ref target), force: true, .. } if target == "4m")
        );
        assert!(
            matches!(guard(&["drill", "drain"]), GuardCommands::Drill { target: Some(ref target), force: false, .. } if target == "drain")
        );
        assert!(matches!(guard(&["stop"]), GuardCommands::Stop { force: false, .. }));
        assert!(matches!(
            guard(&["stop", "--force"]),
            GuardCommands::Stop { force: true, .. }
        ));
        assert!(matches!(guard(&["tail"]), GuardCommands::Tail { file: None }));
        assert!(matches!(guard(&["tail", "x.csv"]), GuardCommands::Tail { file: Some(ref file) } if file == "x.csv"));
        assert!(matches!(guard(&["list"]), GuardCommands::List));
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
}
