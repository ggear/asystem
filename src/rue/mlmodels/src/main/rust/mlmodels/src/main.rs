use std::path::Path;
use std::process::ExitCode;
use std::time::Instant;

use consumer::runtime::loader::{read_json, read_project, replay, Kind, Model, ModelError, Tensors};
use consumer::runtime::served::load_served;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    if arguments.is_empty() || arguments.len() == 2 || arguments.len() > 3 {
        eprintln!("ERROR usage consumer <project dir> [<server> <name>]");
        return ExitCode::from(2);
    }
    let served = (arguments.len() == 3).then(|| (arguments[1].clone(), arguments[2].clone()));
    match run(Path::new(&arguments[0]), served) {
        Ok(findings) => {
            for (rule, message) in &findings {
                eprintln!("ERROR {rule} [{message}]");
            }
            if findings.is_empty() {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            }
        }
        Err(error) => {
            eprintln!("ERROR [{error}]");
            ExitCode::FAILURE
        }
    }
}

fn run(dir: &Path, served: Option<(String, String)>) -> Result<Vec<(String, String)>, ModelError> {
    let started = Instant::now();
    let project = read_project(dir)?;
    report(
        "verify",
        &format!(
            "{} files",
            project.manifest["files"].as_object().map_or(0, serde_json::Map::len) + 1
        ),
        started,
    );
    let started = Instant::now();
    let model = Model::build(dir, &project)?;
    let remote = served
        .map(|(host, name)| {
            load_served(&format!("{host}/v2/models/{name}/infer"), &project.signature_json).map_err(|cause| {
                ModelError {
                    kind: Kind::Load,
                    gate: "served".to_string(),
                    cause,
                }
            })
        })
        .transpose()?;
    report(
        "load",
        if remote.is_some() {
            "served"
        } else {
            &model.info().flavour
        },
        started,
    );
    let started = Instant::now();
    let golden = read_json(&dir.join("golden.json"))?;
    let steps: usize = golden["sequences"]
        .as_array()
        .into_iter()
        .flatten()
        .map(|sequence| sequence["steps"].as_array().map_or(0, Vec::len))
        .sum();
    let local = |inputs: &Tensors| model.predict(inputs).map_err(|error| error.to_string());
    let findings = match &remote {
        Some(predict) => replay(dir, model.signature(), predict.as_ref())?,
        None => replay(dir, model.signature(), &local)?,
    };
    report("replay", &format!("{steps} steps"), started);
    Ok(findings)
}

fn report(stage: &str, detail: &str, started: Instant) {
    println!(
        "    {stage:<12} ... done [{detail}] ({:.2}s)",
        started.elapsed().as_secs_f64()
    );
}
