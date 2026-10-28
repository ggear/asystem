use std::io;
use std::process;

use rackmains::schema::{reflect, RackMains, MODULE};

fn main() {
    let mut stdout = io::stdout().lock();
    if let Err(err) = reflect(&mut stdout, MODULE, Some(&RackMains)) {
        eprintln!("{err}");
        process::exit(1);
    }
}
