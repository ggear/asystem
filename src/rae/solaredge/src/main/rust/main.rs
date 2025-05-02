extern crate chrono;

use chrono::{DateTime, Utc};

fn main() {
    let now: DateTime<Utc> = Utc::now();
    println!("Gateway started at [{}]", now.to_rfc3339());
}

