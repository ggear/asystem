use std::path::Path;
use std::process::ExitCode;

use rackmains::DEFAULT_DEVICE;

fn main() -> ExitCode {
    let path = std::env::args().nth(1).unwrap_or_else(|| DEFAULT_DEVICE.to_string());
    match rackmains::mock::run(Path::new(&path)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("mockdriver failed [{err}]");
            ExitCode::FAILURE
        }
    }
}
