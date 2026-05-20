use std::{
    io::{Read, Write},
    net::{TcpStream, ToSocketAddrs},
    time::Duration,
};

use crate::dialogs::shell_error;
use crate::{ShellResult, MAX_BACKEND_RESPONSE_BYTES};

pub(crate) fn request_backend_json(
    backend_url: &str,
    method: &str,
    path: &str,
    token: &str,
    body: &str,
) -> ShellResult<String> {
    let parsed = url::Url::parse(backend_url)?;
    if parsed.scheme() != "http" {
        return Err(shell_error(
            "Only http backend URLs are supported for shell backend requests.",
        ));
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| shell_error("Backend URL is missing a host."))?;
    let port = parsed
        .port_or_known_default()
        .ok_or_else(|| shell_error("Backend URL is missing a port."))?;
    let mut addresses = format!("{host}:{port}").to_socket_addrs()?;
    let address = addresses
        .next()
        .ok_or_else(|| shell_error("Backend URL did not resolve to a socket address."))?;
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(2))?;
    stream.set_read_timeout(Some(Duration::from_secs(2)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;
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
    let request = format!(
        "{method} {path} HTTP/1.1\r\nHost: {host}\r\n{authorization}{content_headers}Connection: close\r\n\r\n{body}",
    );
    stream.write_all(request.as_bytes())?;
    let response = read_backend_response_capped(&mut stream, MAX_BACKEND_RESPONSE_BYTES)?;
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
