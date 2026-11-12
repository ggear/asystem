use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::thread;

use crate::nut::COMMAND_DUMP;

pub const DUMP: &str = concat!(
    "SETINFO battery.charge \"100\"\n",
    "SETINFO battery.voltage \"13.4\"\n",
    "SETINFO device.type \"ups\"\n",
    "SETINFO input.voltage \"241.4\"\n",
    "SETINFO input.voltage.fault \"241.4\"\n",
    "SETINFO output.frequency \"50.1\"\n",
    "SETINFO output.voltage \"241.4\"\n",
    "SETINFO ups.load \"13\"\n",
    "SETINFO ups.status \"OL\"\n",
    "DATAOK\n",
    "DUMPDONE\n",
);

pub const STATUS_SUFFIX: &str = ".status";

pub fn run(path: &Path) -> Result<(), String> {
    let _ = fs::remove_file(path);
    let listener =
        UnixListener::bind(path).map_err(|err| format!("failed to bind socket [{}] [{err}]", path.display()))?;
    serve(&listener, &status_path(path))
}

pub fn status_path(socket: &Path) -> PathBuf {
    let mut name = socket.as_os_str().to_os_string();
    name.push(STATUS_SUFFIX);
    PathBuf::from(name)
}

pub fn serve(listener: &UnixListener, status: &Path) -> Result<(), String> {
    for stream in listener.incoming() {
        let stream = stream.map_err(|err| format!("failed to accept [{err}]"))?;
        let status = status.to_path_buf();
        thread::spawn(move || answer(stream, &status));
    }
    Ok(())
}

pub fn dump(status: &Path) -> String {
    match fs::read_to_string(status) {
        Ok(text) if !text.trim().is_empty() => DUMP.replace(
            "SETINFO ups.status \"OL\"",
            &format!("SETINFO ups.status \"{}\"", text.trim().replace('"', "")),
        ),
        _ => DUMP.to_string(),
    }
}

fn answer(stream: UnixStream, status: &Path) {
    let Ok(mut writer) = stream.try_clone() else {
        return;
    };
    for line in BufReader::new(stream).lines() {
        match line {
            Ok(line) if line == COMMAND_DUMP => {
                if writer.write_all(dump(status).as_bytes()).is_err() {
                    return;
                }
            }
            Ok(_) => {}
            Err(_) => return,
        }
    }
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;
    use std::time::Duration;

    use super::*;
    use crate::nut::{Nut, Source};

    fn socket(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("rm-{}-{name}", std::process::id()))
    }

    fn serving(path: &Path) {
        let _ = fs::remove_file(path);
        let listener = UnixListener::bind(path).unwrap();
        let status = status_path(path);
        thread::spawn(move || serve(&listener, &status));
    }

    #[test]
    fn nut_reads_a_full_reading_from_the_mock_driver() {
        let path = socket("full");
        serving(&path);
        let mut nut = Nut::new(path.clone(), Duration::from_secs(2));
        for _ in 0..2 {
            let reading = nut.read().unwrap();
            assert_eq!(reading.status.as_deref(), Some("OL"));
            assert_eq!(reading.samples.len(), crate::nut::SAMPLES.len());
            assert!(reading.samples.contains(&("rackmains_battery_charge_pct", 100.0)));
            assert!(reading.samples.contains(&("rackmains_mains_input_volts", 241.4)));
        }
        let _ = fs::remove_file(path);
    }

    #[test]
    fn nut_fails_when_no_driver_is_listening() {
        let mut nut = Nut::new(socket("absent"), Duration::from_secs(1));
        assert!(nut.read().is_err());
    }

    #[test]
    fn nut_fails_when_the_driver_hangs_up_mid_dump() {
        let path = socket("cut");
        let _ = fs::remove_file(&path);
        let listener = UnixListener::bind(&path).unwrap();
        thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let _ = stream.write_all(b"SETINFO ups.status \"OL\"\n");
            }
        });
        let mut nut = Nut::new(path.clone(), Duration::from_secs(2));
        assert!(nut.read().is_err());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn nut_fails_when_the_driver_never_answers() {
        let path = socket("mute");
        let _ = fs::remove_file(&path);
        let listener = UnixListener::bind(&path).unwrap();
        let held = thread::spawn(move || listener.accept().map(|(stream, _)| stream));
        let mut nut = Nut::new(path.clone(), Duration::from_millis(200));
        assert!(nut.read().is_err());
        drop(held);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn the_mock_driver_reports_the_status_written_beside_its_socket() {
        let path = socket("status");
        serving(&path);
        let status = status_path(&path);
        let mut nut = Nut::new(path.clone(), Duration::from_secs(2));
        assert_eq!(nut.read().unwrap().status.as_deref(), Some("OL"));
        fs::write(&status, "OB DISCHRG\n").unwrap();
        assert_eq!(nut.read().unwrap().status.as_deref(), Some("OB DISCHRG"));
        fs::write(&status, "\n").unwrap();
        assert_eq!(nut.read().unwrap().status.as_deref(), Some("OL"));
        let _ = fs::remove_file(status);
        let _ = fs::remove_file(path);
    }
}
