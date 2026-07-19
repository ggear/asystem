use std::io::{self, Read, Write};

use tempstat::driver::mock::Mock;

fn main() -> io::Result<()> {
    let mut mock = Mock::new();
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
