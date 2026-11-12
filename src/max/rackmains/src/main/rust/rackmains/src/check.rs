use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::time::Duration;

use crate::nut::{Nut, Source};
use crate::outage::{DIR_OUTAGE, DIR_STATE};
use crate::policy::load_model;
use crate::shed::load_hosts;

pub struct Target<'a> {
    pub model_dir: &'a Path,
    pub hosts_file: &'a Path,
    pub local_host: &'a str,
    pub ssh_key: &'a Path,
    pub known_hosts: &'a Path,
    pub data_dir: &'a Path,
    pub device: &'a Path,
    pub timeout: Duration,
}

pub struct Outcome {
    pub name: &'static str,
    pub result: Result<String, String>,
}

pub fn run(target: &Target) -> Vec<Outcome> {
    vec![
        Outcome {
            name: "model",
            result: load_model(target.model_dir).map(|(loaded, policy)| {
                format!(
                    "project [{}] hash [{}] shed_max [{}s] mains_stable [{}s]",
                    loaded.info().name,
                    loaded.info().content_sha256,
                    policy.shed_max.as_secs(),
                    policy.mains_stable.as_secs()
                )
            }),
        },
        Outcome {
            name: "hosts",
            result: load_hosts(target.hosts_file, target.local_host).map(|hosts| format!("[{}] host(s)", hosts.len())),
        },
        Outcome {
            name: "ssh key",
            result: private_file(target.ssh_key),
        },
        Outcome {
            name: "known hosts",
            result: fs::metadata(target.known_hosts)
                .map(|_| format!("present [{}]", target.known_hosts.display()))
                .map_err(|err| format!("failed to read [{}] [{err}]", target.known_hosts.display())),
        },
        Outcome {
            name: "data dir",
            result: writable(target.data_dir),
        },
        Outcome {
            name: "driver socket",
            result: Nut::new(target.device.to_path_buf(), target.timeout)
                .read()
                .map(|_| format!("reading [{}]", target.device.display()))
                .map_err(|err| err.to_string()),
        },
    ]
}

pub fn failed(outcomes: &[Outcome]) -> Vec<&'static str> {
    outcomes
        .iter()
        .filter(|outcome| outcome.result.is_err())
        .map(|outcome| outcome.name)
        .collect()
}

fn private_file(path: &Path) -> Result<String, String> {
    let mode = fs::metadata(path)
        .map_err(|err| format!("failed to read [{}] [{err}]", path.display()))?
        .permissions()
        .mode();
    if mode & 0o077 != 0 {
        return Err(format!(
            "mode [{:o}] is open to group or others [{}]",
            mode & 0o777,
            path.display()
        ));
    }
    Ok(format!("present [{}]", path.display()))
}

fn writable(data_dir: &Path) -> Result<String, String> {
    for name in [DIR_OUTAGE, DIR_STATE] {
        let directory = data_dir.join(name);
        fs::create_dir_all(&directory).map_err(|err| format!("failed to create [{}] [{err}]", directory.display()))?;
        let probe = directory.join(".probe");
        fs::write(&probe, b"").map_err(|err| format!("failed to write [{}] [{err}]", probe.display()))?;
        let _ = fs::remove_file(probe);
    }
    Ok(format!("writable [{}]", data_dir.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!("rackmains-check-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn a_key_open_to_others_is_refused_and_a_private_one_passes() {
        let dir = scratch("key");
        let key = dir.join("id");
        fs::write(&key, "k").unwrap();
        fs::set_permissions(&key, fs::Permissions::from_mode(0o644)).unwrap();
        assert!(private_file(&key).is_err());
        fs::set_permissions(&key, fs::Permissions::from_mode(0o600)).unwrap();
        assert!(private_file(&key).is_ok());
        assert!(private_file(&dir.join("absent")).is_err());
    }

    #[test]
    fn a_data_dir_gets_both_subdirectories_and_an_unwritable_one_fails() {
        let dir = scratch("data");
        assert!(writable(&dir).is_ok());
        assert!(dir.join(DIR_OUTAGE).is_dir() && dir.join(DIR_STATE).is_dir());
        assert!(writable(Path::new("/proc/rackmains")).is_err());
    }

    #[test]
    fn every_failing_check_is_named() {
        let dir = scratch("all");
        let model = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../build/resources/model/battery");
        let outcomes = run(&Target {
            model_dir: &model,
            hosts_file: &dir.join("hosts.json"),
            local_host: "max",
            ssh_key: &dir.join("id"),
            known_hosts: &dir.join("known_hosts"),
            data_dir: &dir,
            device: &dir.join("socket"),
            timeout: Duration::from_millis(200),
        });
        assert_eq!(
            failed(&outcomes),
            vec!["hosts", "ssh key", "known hosts", "driver socket"]
        );
    }
}
