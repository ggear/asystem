use std::process::ExitCode;

use clap::{CommandFactory, FromArgMatches};

use tempstat::Cli;

fn main() -> ExitCode {
    let version: &'static str = Box::leak(
        std::env::var("SERVICE_VERSION_ABSOLUTE")
            .unwrap_or_else(|_| "unknown".to_string())
            .into_boxed_str(),
    );
    let matches = Cli::command().version(version).get_matches();
    let cli = match Cli::from_arg_matches(&matches) {
        Ok(c) => c,
        Err(err) => err.exit(),
    };
    match cli.run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("tempstat: {err}");
            ExitCode::FAILURE
        }
    }
}
