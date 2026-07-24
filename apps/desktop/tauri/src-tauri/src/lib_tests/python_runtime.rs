use super::*;
use sha2::{Digest, Sha256};
use std::{
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};

fn python_runtime_fixture(name: &str, payload: &[u8]) -> (PathBuf, PathBuf, PathBuf) {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time")
        .as_nanos();
    let project_root = std::env::temp_dir().join(format!(
        "mediapipeline-tauri-python-runtime-{name}-{}-{unique}",
        std::process::id()
    ));
    let desktop_root = project_root.join("apps").join("desktop");
    let python = desktop_root
        .join("runtime")
        .join("Python")
        .join("python.exe");
    std::fs::create_dir_all(python.parent().expect("python parent")).expect("create runtime");
    std::fs::write(&python, payload).expect("write python fixture");
    (project_root, desktop_root, python)
}

fn write_python_release_manifest(project_root: &Path, payload: &[u8], hash: &str) {
    let manifest = serde_json::json!({
        "schema_version": "mediapipeline_release_manifest.v1",
        "integrity": {
            "algorithm": "sha256",
            "files": [{
                "path": "apps\\desktop\\runtime\\Python\\python.exe",
                "sha256": hash,
                "bytes": payload.len(),
            }],
        },
    });
    std::fs::write(
        project_root.join("release_manifest.json"),
        serde_json::to_vec(&manifest).expect("serialize manifest"),
    )
    .expect("write manifest");
}

#[test]
fn productized_python_requires_manifest_verified_bundled_runtime() {
    let payload = b"verified bundled python fixture";
    let (project_root, desktop_root, python) = python_runtime_fixture("verified", payload);
    let hash = format!("{:x}", Sha256::digest(payload));
    write_python_release_manifest(&project_root, payload, &hash);

    let resolved = resolve_python_for_mode(&desktop_root, false).expect("verified runtime");

    assert_eq!(resolved, python);
    std::fs::remove_dir_all(project_root).expect("remove fixture");
}

#[test]
fn productized_python_rejects_missing_bundle_without_path_fallback() {
    let project_root = std::env::temp_dir().join(format!(
        "mediapipeline-tauri-python-runtime-missing-{}",
        std::process::id()
    ));
    let desktop_root = project_root.join("apps").join("desktop");

    let error = resolve_python_for_mode(&desktop_root, false).expect_err("missing runtime");

    assert!(error.to_string().contains("PATH fallback is disabled"));
}

#[test]
fn productized_python_rejects_missing_or_mismatched_manifest_evidence() {
    let payload = b"untrusted bundled python fixture";
    let (project_root, desktop_root, _) = python_runtime_fixture("untrusted", payload);

    let missing_error =
        resolve_python_for_mode(&desktop_root, false).expect_err("missing manifest");
    assert!(missing_error
        .to_string()
        .contains("requires release manifest"));

    write_python_release_manifest(&project_root, payload, &"0".repeat(64));
    let mismatch_error = resolve_python_for_mode(&desktop_root, false).expect_err("hash mismatch");
    assert!(mismatch_error
        .to_string()
        .contains("SHA-256 does not match"));

    std::fs::remove_dir_all(project_root).expect("remove fixture");
}

#[test]
fn debug_python_retains_explicit_ambient_fallback() {
    let desktop_root = Path::new("missing").join("apps").join("desktop");

    let resolved = resolve_python_for_mode(&desktop_root, true).expect("debug fallback");

    assert_eq!(resolved, PathBuf::from("python"));
}

#[test]
fn isolated_python_bootstrap_contains_only_encoded_release_src_root() {
    let bootstrap = isolated_python_module_bootstrap(Path::new("C:\\Release Root\\src"))
        .expect("isolated bootstrap");

    assert!(bootstrap.contains("sys.path.insert(0,\"C:\\\\Release Root\\\\src\")"));
    assert!(bootstrap.contains("runpy.run_module('mediapipeline.desktop.local_api_main'"));
    assert!(!bootstrap.contains("PYTHONPATH"));
}

#[test]
fn bundled_python_can_import_backend_with_isolated_release_src_root() {
    let manifest_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let desktop_root = manifest_root
        .parent()
        .and_then(Path::parent)
        .expect("apps desktop root");
    let project_root = project_root_from_desktop_root(desktop_root);
    let python = desktop_root
        .join("runtime")
        .join("Python")
        .join("python.exe");
    let bootstrap =
        isolated_python_module_bootstrap(&project_root.join("src")).expect("isolated bootstrap");
    let hostile_root = std::env::temp_dir().join(format!(
        "mediapipeline-tauri-hostile-import-{}",
        std::process::id()
    ));
    let hostile_package = hostile_root.join("mediapipeline");
    std::fs::create_dir_all(&hostile_package).expect("create hostile import root");
    std::fs::write(
        hostile_package.join("__init__.py"),
        "raise SystemExit('HOSTILE_IMPORT_EXECUTED')\n",
    )
    .expect("write hostile shadow package");

    let output = Command::new(python)
        .arg("-I")
        .arg("-c")
        .arg(bootstrap)
        .arg("--help")
        .current_dir(&hostile_root)
        .env("PYTHONPATH", &hostile_root)
        .env_remove("PYTHONPATH")
        .env("PYTHONHOME", &hostile_root)
        .env_remove("PYTHONHOME")
        .env("PYTHONUSERBASE", &hostile_root)
        .env_remove("PYTHONUSERBASE")
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONSAFEPATH", "1")
        .output()
        .expect("run isolated bundled python");
    std::fs::remove_dir_all(hostile_root).expect("remove hostile import root");

    assert!(
        output.status.success(),
        "isolated import failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(String::from_utf8_lossy(&output.stdout).contains("--shell-surface"));
}
