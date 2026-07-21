use super::{
    backend_shutdown_request_body, inspect_managed_child, parse_backend_shutdown_outcome,
    resolve_shutdown_with_child, terminate_child, BackendProcess, BackendProcessExit,
    BackendShutdownMode, BackendShutdownOutcome, ChildPoll, ManagedChildProcess,
    ShutdownRequestState, WaitClock,
};
use std::{
    collections::VecDeque,
    fs,
    io,
    io::{Read, Write},
    net::TcpListener,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

#[derive(Default)]
struct FakeWaitClock {
    elapsed: Duration,
    waits: usize,
}

impl WaitClock for FakeWaitClock {
    fn elapsed(&self) -> Duration {
        self.elapsed
    }

    fn wait(&mut self, duration: Duration) {
        self.waits += 1;
        self.elapsed += duration;
    }
}

struct FakeManagedChild {
    polls: VecDeque<io::Result<ChildPoll>>,
    terminate_result: Result<(), String>,
    terminate_calls: usize,
}

impl FakeManagedChild {
    fn new(polls: impl IntoIterator<Item = io::Result<ChildPoll>>) -> Self {
        Self {
            polls: polls.into_iter().collect(),
            terminate_result: Ok(()),
            terminate_calls: 0,
        }
    }
}

impl ManagedChildProcess for FakeManagedChild {
    fn poll(&mut self) -> io::Result<ChildPoll> {
        self.polls
            .pop_front()
            .unwrap_or(Ok(ChildPoll::Running))
    }

    fn terminate_tree_and_verify(&mut self) -> Result<(), String> {
        self.terminate_calls += 1;
        self.terminate_result.clone()
    }
}

fn backend_for_child(child: Option<Child>) -> BackendProcess {
    backend_for_child_and_url(child, "http://127.0.0.1:1")
}

fn backend_for_child_and_url(child: Option<Child>, url: &str) -> BackendProcess {
    BackendProcess {
        child: Mutex::new(child),
        url: url.to_string(),
        token: "test-token".to_string(),
        startup_warnings: Vec::new(),
    }
}

fn serve_once(response: &'static str) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind test backend");
    let address = listener.local_addr().expect("test backend local addr");
    thread::spawn(move || {
        let (mut stream, _) = listener.accept().expect("accept test backend request");
        stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .expect("set test backend read timeout");
        let mut buffer = [0_u8; 4096];
        let _ = stream.read(&mut buffer);
        stream
            .write_all(response.as_bytes())
            .expect("write test backend response");
    });
    format!("http://{address}")
}

#[test]
fn backend_shutdown_request_body_omits_force_for_safe_only() {
    let safe_body = backend_shutdown_request_body(BackendShutdownMode::SafeOnly);
    let force_body = backend_shutdown_request_body(BackendShutdownMode::ConfirmedForceActiveWork);

    assert_eq!(safe_body, r#"{"reason":"tauri-shell-exit"}"#);
    assert!(!safe_body.contains("force_active_work_shutdown"));
    assert_eq!(
        force_body,
        r#"{"reason":"tauri-shell-close","force_active_work_shutdown":true}"#
    );
}

#[test]
fn backend_shutdown_response_parser_blocks_unsafe_safe_only_shutdown() {
    let outcome = parse_backend_shutdown_outcome(
            r#"{"schema_version":"desktop_command_result.v1","command":"backend.shutdown","ok":false,"message":"Backend shutdown blocked because close-readiness is unsafe."}"#,
        )
        .expect("blocked response should parse");

    assert_eq!(outcome, BackendShutdownOutcome::Blocked);
}

#[test]
fn backend_shutdown_response_parser_allows_ok_shutdown() {
    let outcome = parse_backend_shutdown_outcome(
            r#"{"schema_version":"desktop_command_result.v1","command":"backend.shutdown","ok":true,"message":"Backend shutdown requested."}"#,
        )
        .expect("ok response should parse");

    assert_eq!(outcome, BackendShutdownOutcome::Requested);
}

#[test]
fn normal_close_releases_child_only_after_verified_exit() {
    let mut child = FakeManagedChild::new([Ok(ChildPoll::Exited(Some(0)))]);
    let mut clock = FakeWaitClock::default();

    let resolution = resolve_shutdown_with_child(
        &mut child,
        ShutdownRequestState::Acknowledged,
        &mut clock,
        Duration::from_secs(3),
    );

    assert_eq!(resolution.outcome, BackendShutdownOutcome::Requested);
    assert!(resolution.release_ownership);
    assert_eq!(child.terminate_calls, 0);
    assert_eq!(clock.waits, 0);
}

#[test]
fn child_wait_error_after_acknowledgement_is_failed_and_retains_ownership() {
    let mut child = FakeManagedChild::new([Err(io::Error::new(
        io::ErrorKind::PermissionDenied,
        "injected wait handle failure",
    ))]);
    let mut clock = FakeWaitClock::default();

    let resolution = resolve_shutdown_with_child(
        &mut child,
        ShutdownRequestState::Acknowledged,
        &mut clock,
        Duration::from_secs(3),
    );

    assert_eq!(resolution.outcome, BackendShutdownOutcome::Failed);
    assert!(!resolution.release_ownership);
    assert_eq!(child.terminate_calls, 0);
    assert!(resolution.detail.contains("injected wait handle failure"));
}

#[test]
fn child_wait_error_after_transport_failure_is_not_verified_exit() {
    let mut child = FakeManagedChild::new([Err(io::Error::new(
        io::ErrorKind::Other,
        "injected try_wait error",
    ))]);
    let mut clock = FakeWaitClock::default();

    let resolution = resolve_shutdown_with_child(
        &mut child,
        ShutdownRequestState::TransportFailed,
        &mut clock,
        Duration::from_secs(3),
    );

    assert_eq!(resolution.outcome, BackendShutdownOutcome::Failed);
    assert!(!resolution.release_ownership);
    assert_eq!(child.terminate_calls, 0);
}

#[test]
fn descendants_refusing_termination_cannot_report_successful_shutdown() {
    let mut child = FakeManagedChild::new([
        Ok(ChildPoll::Running),
        Ok(ChildPoll::Running),
        Ok(ChildPoll::Running),
    ]);
    child.terminate_result = Err("descendant PID 77 remained alive".to_string());
    let mut clock = FakeWaitClock::default();

    let resolution = resolve_shutdown_with_child(
        &mut child,
        ShutdownRequestState::Acknowledged,
        &mut clock,
        Duration::from_millis(200),
    );

    assert_eq!(resolution.outcome, BackendShutdownOutcome::Failed);
    assert!(!resolution.release_ownership);
    assert_eq!(child.terminate_calls, 1);
    assert!(resolution.detail.contains("descendant PID 77 remained alive"));
}

#[test]
fn backend_exit_between_health_checks_is_observed_as_exit_not_health() {
    let mut child = FakeManagedChild::new([
        Ok(ChildPoll::Running),
        Ok(ChildPoll::Exited(Some(91))),
    ]);

    assert_eq!(
        inspect_managed_child(&mut child).expect("first lifecycle inspection"),
        BackendProcessExit::Running
    );
    assert_eq!(
        inspect_managed_child(&mut child).expect("second lifecycle inspection"),
        BackendProcessExit::Exited(Some(91))
    );
}

#[test]
fn backend_crash_wait_error_remains_monitor_error_not_false_exit() {
    let mut child = FakeManagedChild::new([Err(io::Error::new(
        io::ErrorKind::BrokenPipe,
        "injected monitor wait failure",
    ))]);

    let error = inspect_managed_child(&mut child).expect_err("wait failure must propagate");

    assert!(error.to_string().contains("injected monitor wait failure"));
}

fn wait_for_non_running(process: &BackendProcess) -> BackendProcessExit {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let state = process.try_take_exited().expect("inspect backend child");
        if state != BackendProcessExit::Running {
            return state;
        }
        assert!(
            Instant::now() < deadline,
            "backend child did not leave running state"
        );
        thread::sleep(Duration::from_millis(25));
    }
}

#[cfg(windows)]
fn spawn_child_that_exits(code: i32) -> Child {
    let command = format!("exit {code}");
    Command::new("powershell")
        .args(["-NoProfile", "-Command", &command])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn exiting PowerShell child")
}

#[cfg(windows)]
fn spawn_sleeping_child() -> Child {
    Command::new("powershell")
        .args(["-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn sleeping PowerShell child")
}

#[cfg(windows)]
fn unique_temp_path(name: &str) -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time after epoch")
        .as_nanos();
    std::env::temp_dir().join(format!(
        "mediapipeline-tauri-{name}-{}-{nanos}.txt",
        std::process::id()
    ))
}

#[cfg(windows)]
fn powershell_literal(value: &std::path::Path) -> String {
    value.to_string_lossy().replace('\'', "''")
}

#[cfg(windows)]
fn process_exists(pid: u32) -> bool {
    Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                &format!(
                    "if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}"
                ),
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
}

#[cfg(windows)]
fn wait_for_process_absent(pid: u32) -> bool {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if !process_exists(pid) {
            return true;
        }
        if Instant::now() >= deadline {
            return false;
        }
        thread::sleep(Duration::from_millis(100));
    }
}

#[cfg(unix)]
fn spawn_child_that_exits(code: i32) -> Child {
    Command::new("/bin/sh")
        .args(["-c", &format!("exit {code}")])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn exiting shell child")
}

#[cfg(unix)]
fn spawn_sleeping_child() -> Child {
    Command::new("/bin/sh")
        .args(["-c", "sleep 30"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn sleeping shell child")
}

#[test]
fn try_take_exited_reports_no_child_separately() {
    let process = backend_for_child(None);

    assert_eq!(
        process.try_take_exited().expect("inspect missing child"),
        BackendProcessExit::NoChild
    );
}

#[test]
fn try_take_exited_reports_child_exit_code() {
    let process = backend_for_child(Some(spawn_child_that_exits(7)));

    assert_eq!(
        wait_for_non_running(&process),
        BackendProcessExit::Exited(Some(7))
    );
    assert_eq!(
        process.try_take_exited().expect("inspect taken child"),
        BackendProcessExit::NoChild
    );
}

#[test]
fn safe_only_shutdown_transport_error_allows_exited_backend_child() {
    let process = backend_for_child(Some(spawn_child_that_exits(0)));

    assert_eq!(
        process.shutdown(BackendShutdownMode::SafeOnly),
        BackendShutdownOutcome::Requested
    );
    assert_eq!(
        process.try_take_exited().expect("inspect exited child"),
        BackendProcessExit::NoChild
    );
}

#[test]
fn safe_only_shutdown_transport_error_retains_running_backend_child() {
    let process = backend_for_child(Some(spawn_sleeping_child()));

    assert_eq!(
        process.shutdown(BackendShutdownMode::SafeOnly),
        BackendShutdownOutcome::Failed
    );
    assert_eq!(
        process.try_take_exited().expect("inspect retained child"),
        BackendProcessExit::Running
    );

    let mut child = process
        .child
        .lock()
        .expect("lock retained child")
        .take()
        .expect("retained child should remain available");
    terminate_child(&mut child);
}

#[test]
fn confirmed_force_shutdown_transport_error_retains_running_backend_child() {
    let process = backend_for_child(Some(spawn_sleeping_child()));

    assert_eq!(
        process.shutdown(BackendShutdownMode::ConfirmedForceActiveWork),
        BackendShutdownOutcome::Failed
    );
    assert_eq!(
        process.try_take_exited().expect("inspect retained child"),
        BackendProcessExit::Running
    );

    let mut child = process
        .child
        .lock()
        .expect("lock retained child")
        .take()
        .expect("retained child should remain available");
    terminate_child(&mut child);
}

#[test]
fn safe_only_shutdown_blocked_retains_backend_child() {
    let url = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_command_result.v1\",\"ok\":false}",
        );
    let process = backend_for_child_and_url(Some(spawn_sleeping_child()), &url);

    assert_eq!(
        process.shutdown(BackendShutdownMode::SafeOnly),
        BackendShutdownOutcome::Blocked
    );
    assert_eq!(
        process.try_take_exited().expect("inspect retained child"),
        BackendProcessExit::Running
    );

    let mut child = process
        .child
        .lock()
        .expect("lock retained child")
        .take()
        .expect("retained child should remain available");
    terminate_child(&mut child);
}

#[test]
#[cfg(windows)]
fn terminate_child_removes_windows_process_tree() {
    let child_pid_file = unique_temp_path("child-pid");
    let command = format!(
            "$child = Start-Process -FilePath powershell -ArgumentList @('-NoProfile','-Command','Start-Sleep -Seconds 60') -PassThru; Set-Content -LiteralPath '{}' -Value $child.Id; Start-Sleep -Seconds 60",
            powershell_literal(&child_pid_file)
        );
    let mut parent = Command::new("powershell")
        .args(["-NoProfile", "-Command", &command])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn parent PowerShell process");
    let deadline = Instant::now() + Duration::from_secs(5);
    while !child_pid_file.exists() {
        assert!(Instant::now() < deadline, "child pid file was not written");
        thread::sleep(Duration::from_millis(100));
    }
    let child_pid = fs::read_to_string(&child_pid_file)
        .expect("read child pid")
        .trim()
        .parse::<u32>()
        .expect("parse child pid");

    terminate_child(&mut parent);
    let child_absent = wait_for_process_absent(child_pid);
    if !child_absent {
        let _ = Command::new("taskkill")
            .args(["/PID", &child_pid.to_string(), "/T", "/F"])
            .status();
    }
    let _ = fs::remove_file(&child_pid_file);

    assert!(child_absent, "descendant process should be terminated");
}

#[test]
#[cfg(windows)]
fn killed_backend_process_reports_exit_code_on_windows() {
    let process = backend_for_child(Some(spawn_sleeping_child()));

    assert_eq!(
        process.try_take_exited().expect("inspect running child"),
        BackendProcessExit::Running
    );
    {
        let mut guard = process.child.lock().expect("lock backend child");
        let child = guard.as_mut().expect("child should still be stored");
        child.kill().expect("kill sleeping child");
    }

    match wait_for_non_running(&process) {
        BackendProcessExit::Exited(Some(_code)) => {}
        other => panic!("expected killed Windows child to report an exit code, got {other:?}"),
    }
}

#[test]
#[cfg(unix)]
fn killed_backend_process_reports_missing_exit_code_on_unix() {
    let process = backend_for_child(Some(spawn_sleeping_child()));

    assert_eq!(
        process.try_take_exited().expect("inspect running child"),
        BackendProcessExit::Running
    );
    {
        let mut guard = process.child.lock().expect("lock backend child");
        let child = guard.as_mut().expect("child should still be stored");
        child.kill().expect("kill sleeping child");
    }

    assert_eq!(
        wait_for_non_running(&process),
        BackendProcessExit::Exited(None)
    );
}

#[test]
fn bootstrap_stdout_redacts_personal_and_unc_paths() {
    let value = r#"startup config=C:\Users\operator\AppData\Local\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1 LocalBase=C:\MediaPipeline\Scratch source=\\private-server\media\Movie.mkv token=secret-token Authorization: Bearer bearer-secret"#;
    let redacted = super::redact_bootstrap_stdout(value);

    assert!(!redacted.contains("C:\\Users\\operator"));
    assert!(!redacted.contains("\\\\private-server\\media"));
    assert!(!redacted.contains("secret-token"));
    assert!(!redacted.contains("C:\\MediaPipeline\\Scratch"));
    assert!(!redacted.contains("bearer-secret"));
    assert!(redacted.contains("[redacted-path]"));
    assert!(redacted.contains("[redacted]"));
}
