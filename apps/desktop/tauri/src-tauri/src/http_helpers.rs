use std::{
    io::{self, Read, Write},
    net::{TcpStream, ToSocketAddrs},
    time::{Duration, Instant},
};

use crate::dialogs::shell_error;
use crate::{ShellResult, MAX_BACKEND_RESPONSE_BYTES};

const BACKEND_IO_TIMEOUT: Duration = Duration::from_secs(2);
const BACKEND_REQUEST_TIMEOUT: Duration = Duration::from_secs(5);

pub(crate) fn request_backend_json(
    backend_url: &str,
    method: &str,
    path: &str,
    token: &str,
    body: &str,
) -> ShellResult<String> {
    request_backend_json_inner(
        backend_url,
        method,
        path,
        token,
        body,
        None,
        BACKEND_REQUEST_TIMEOUT,
    )
}

pub(crate) fn request_backend_json_with_command_id(
    backend_url: &str,
    method: &str,
    path: &str,
    token: &str,
    body: &str,
    command_id: &str,
) -> ShellResult<String> {
    let value = command_id.trim();
    if !(8..=128).contains(&value.len())
        || !value.bytes().enumerate().all(|(index, byte)| {
            byte.is_ascii_alphanumeric() || (index > 0 && b"._:-".contains(&byte))
        })
    {
        return Err(shell_error("Backend command ID is invalid."));
    }
    request_backend_json_inner(
        backend_url,
        method,
        path,
        token,
        body,
        Some(value),
        BACKEND_REQUEST_TIMEOUT,
    )
}

fn request_backend_json_inner(
    backend_url: &str,
    method: &str,
    path: &str,
    token: &str,
    body: &str,
    command_id: Option<&str>,
    total_timeout: Duration,
) -> ShellResult<String> {
    let deadline = Instant::now() + total_timeout;
    let parsed = validate_loopback_backend_url(backend_url)?;
    let host = parsed
        .host_str()
        .ok_or_else(|| shell_error("Backend URL is missing a host."))?;
    let port = parsed
        .port()
        .ok_or_else(|| shell_error("Backend URL is missing an explicit port."))?;
    let socket_target = if host.contains(':') {
        format!("[{host}]:{port}")
    } else {
        format!("{host}:{port}")
    };
    let mut addresses = socket_target.to_socket_addrs()?;
    let address = addresses
        .next()
        .ok_or_else(|| shell_error("Backend URL did not resolve to a socket address."))?;
    let connect_timeout = remaining_backend_request_time(deadline)?.min(BACKEND_IO_TIMEOUT);
    let mut stream = TcpStream::connect_timeout(&address, connect_timeout)
        .map_err(|error| backend_request_io_error(error, deadline))?;
    let authorization = if token.trim().is_empty() {
        String::new()
    } else {
        format!("Authorization: Bearer {token}\r\n")
    };
    let content_headers = if body.is_empty() {
        String::new()
    } else {
        format!(
            "Content-Type: application/json\r\nContent-Length: {}\r\n",
            body.len()
        )
    };
    let command_header = command_id
        .map(|value| format!("X-MediaPipeline-Command-ID: {value}\r\n"))
        .unwrap_or_default();
    let request = format!(
        "{method} {path} HTTP/1.1\r\nHost: {host}\r\n{authorization}{command_header}{content_headers}Connection: close\r\n\r\n{body}",
    );
    write_backend_request_until(&mut stream, request.as_bytes(), deadline)?;
    let response =
        read_backend_response_capped_until(&mut stream, MAX_BACKEND_RESPONSE_BYTES, deadline)?;
    if !(response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")) {
        let status_line = response.lines().next().unwrap_or("<no response>");
        let preview = backend_response_body_preview(&response, 500);
        let detail = if preview.is_empty() {
            status_line.to_string()
        } else {
            format!("{status_line}; body: {preview}")
        };
        return Err(shell_error(format!(
            "Backend request did not return HTTP 200: {detail}"
        )));
    }
    let Some((_, body)) = response.split_once("\r\n\r\n") else {
        return Err(shell_error(
            "Backend response did not include an HTTP body.",
        ));
    };
    Ok(body.to_string())
}

fn remaining_backend_request_time(deadline: Instant) -> ShellResult<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|remaining| !remaining.is_zero())
        .ok_or_else(|| shell_error("Backend request exceeded its total deadline."))
}

fn backend_request_io_error(error: io::Error, deadline: Instant) -> Box<dyn std::error::Error> {
    if matches!(
        error.kind(),
        io::ErrorKind::TimedOut | io::ErrorKind::WouldBlock
    ) && Instant::now() >= deadline
    {
        shell_error("Backend request exceeded its total deadline.")
    } else {
        error.into()
    }
}

fn write_backend_request_until(
    stream: &mut TcpStream,
    request: &[u8],
    deadline: Instant,
) -> ShellResult<()> {
    let mut written = 0;
    while written < request.len() {
        let remaining = remaining_backend_request_time(deadline)?;
        stream.set_write_timeout(Some(remaining.min(BACKEND_IO_TIMEOUT)))?;
        match stream.write(&request[written..]) {
            Ok(0) => return Err(io::Error::from(io::ErrorKind::WriteZero).into()),
            Ok(count) => written += count,
            Err(error) => return Err(backend_request_io_error(error, deadline)),
        }
    }
    Ok(())
}

fn read_backend_response_capped_until(
    stream: &mut TcpStream,
    max_bytes: usize,
    deadline: Instant,
) -> ShellResult<String> {
    let mut response: Vec<u8> = Vec::new();
    let mut buffer = [0_u8; 8192];
    loop {
        let remaining = remaining_backend_request_time(deadline)?;
        stream.set_read_timeout(Some(remaining.min(BACKEND_IO_TIMEOUT)))?;
        let count = stream
            .read(&mut buffer)
            .map_err(|error| backend_request_io_error(error, deadline))?;
        if Instant::now() >= deadline {
            return Err(shell_error("Backend request exceeded its total deadline."));
        }
        if count == 0 {
            break;
        }
        if response.len().saturating_add(count) > max_bytes {
            return Err(shell_error(format!(
                "Backend response exceeded {max_bytes} byte limit."
            )));
        }
        response.extend_from_slice(&buffer[..count]);
    }
    String::from_utf8(response)
        .map_err(|error| shell_error(format!("Backend response was not UTF-8: {error}")))
}

pub(crate) fn validate_loopback_backend_url(backend_url: &str) -> ShellResult<url::Url> {
    let parsed = url::Url::parse(backend_url)?;
    if parsed.scheme() != "http" {
        return Err(shell_error(
            "Only http backend URLs are supported for shell backend requests.",
        ));
    }
    if parsed.port().is_none() {
        return Err(shell_error("Backend URL is missing an explicit port."));
    }
    match parsed.host() {
        Some(url::Host::Domain(host)) if host.eq_ignore_ascii_case("localhost") => Ok(parsed),
        Some(url::Host::Ipv4(address)) if address.is_loopback() => Ok(parsed),
        Some(url::Host::Ipv6(address)) if address.is_loopback() => Ok(parsed),
        _ => Err(shell_error(
            "Backend URL must use an explicit http loopback host.",
        )),
    }
}

fn backend_response_body_preview(response: &str, max_chars: usize) -> String {
    let Some((_, body)) = response.split_once("\r\n\r\n") else {
        return String::new();
    };
    let trimmed = body.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    bounded_text(trimmed, max_chars)
}

pub(crate) fn bounded_text(value: &str, max_chars: usize) -> String {
    let mut preview = String::new();
    for (index, ch) in value.chars().enumerate() {
        if index >= max_chars {
            preview.push_str("...");
            break;
        }
        preview.push(ch);
    }
    preview
}

#[cfg(test)]
pub(crate) fn read_backend_response_capped(
    reader: &mut impl Read,
    max_bytes: usize,
) -> ShellResult<String> {
    let mut response: Vec<u8> = Vec::new();
    let mut buffer = [0_u8; 8192];
    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        if response.len().saturating_add(count) > max_bytes {
            return Err(shell_error(format!(
                "Backend response exceeded {max_bytes} byte limit."
            )));
        }
        response.extend_from_slice(&buffer[..count]);
    }
    String::from_utf8(response)
        .map_err(|error| shell_error(format!("Backend response was not UTF-8: {error}")))
}

#[cfg(test)]
mod tests {
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
        time::{Duration, Instant},
    };

    use super::{request_backend_json_inner, validate_loopback_backend_url};

    #[test]
    fn validate_loopback_backend_url_accepts_explicit_http_loopback_hosts() {
        for url in [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://[::1]:8765",
        ] {
            let parsed = validate_loopback_backend_url(url).expect("loopback URL should pass");
            assert_eq!(parsed.scheme(), "http");
        }
    }

    #[test]
    fn validate_loopback_backend_url_rejects_non_loopback_and_implicit_ports() {
        for url in [
            "https://127.0.0.1:8765",
            "http://127.0.0.1",
            "http://example.com:8765",
            "http://192.168.1.10:8765",
            "http://[2001:db8::1]:8765",
        ] {
            assert!(
                validate_loopback_backend_url(url).is_err(),
                "{url} should be rejected"
            );
        }
    }

    #[test]
    fn backend_request_total_deadline_rejects_slow_drip_response() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback listener");
        let address = listener.local_addr().expect("listener address");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept request");
            let mut request = [0_u8; 4096];
            let _ = stream.read(&mut request).expect("read request");
            for byte in b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}" {
                if stream.write_all(&[*byte]).is_err() {
                    break;
                }
                thread::sleep(Duration::from_millis(15));
            }
        });

        let started = Instant::now();
        let error = request_backend_json_inner(
            &format!("http://{address}"),
            "GET",
            "/api/slow",
            "",
            "",
            None,
            Duration::from_millis(120),
        )
        .expect_err("slow-drip response must exceed the total deadline");
        let elapsed = started.elapsed();

        assert!(error.to_string().contains("total deadline"), "{error}");
        assert!(elapsed < Duration::from_secs(1), "elapsed: {elapsed:?}");
        server.join().expect("join slow-drip server");
    }
}
