use std::io::{self, Read, Write};

use tempstat::driver::mock::{Emulator, MockDs2480b, MockDs9097};

fn main() -> io::Result<()> {
    let mut mock: Box<dyn Emulator> = match std::env::var("TEMPSTAT_MOCK_ADAPTER").as_deref() {
        Ok("ds2480b") => Box::new(MockDs2480b::new()),
        _ => Box::new(MockDs9097::new()),
    };
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    let mut byte = [0u8; 1];
    let mut out = Vec::new();
    loop {
        if input.read(&mut byte)? == 0 {
            return Ok(());
        }
        out.clear();
        mock.feed(byte[0], &mut out);
        if !out.is_empty() {
            output.write_all(&out)?;
            output.flush()?;
        }
    }
}
