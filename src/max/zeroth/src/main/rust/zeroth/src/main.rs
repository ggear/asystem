use std::process::ExitCode;

use clap::Parser;
use zeroth::Cli;

fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("zeroth: {err}");
            ExitCode::FAILURE
        }
    }
}
