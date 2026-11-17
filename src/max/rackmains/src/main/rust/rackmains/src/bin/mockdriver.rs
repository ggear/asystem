use std::path::Path;
use std::process::ExitCode;

use rackmains::DEFAULT_DEVICE;

fn main() -> ExitCode {
    let path = std::env::args().nth(1).unwrap_or_else(|| DEFAULT_DEVICE.to_string());
    if path.starts_with('-') {
        eprintln!(
            "{} {}",
            rackmains::log_prefix(log::Level::Error),
            rackmains::log_line("mockdriver usage", "mockdriver [SOCKET]")
        );
        return ExitCode::from(2);
    }
    match rackmains::mock::run(Path::new(&path)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!(
                "{} {}",
                rackmains::log_prefix(log::Level::Error),
                rackmains::log_line("mockdriver failed", &err)
            );
            ExitCode::FAILURE
        }
    }
}
