use url::Url;

pub(crate) fn normalized_webview_origin(url: &Url) -> String {
    url.origin().ascii_serialization()
}

pub(crate) fn navigation_matches_webview_origin(candidate: &Url, allowed_origin: &str) -> bool {
    normalized_webview_origin(candidate) == allowed_origin
}

#[cfg(test)]
mod tests {
    use super::{navigation_matches_webview_origin, normalized_webview_origin};
    use url::Url;

    #[test]
    fn exact_loopback_origin_allows_paths_queries_and_fragments_only() {
        for backend in [
            "http://127.0.0.1:8765/",
            "http://localhost:8765/",
            "http://[::1]:8765/",
        ] {
            let backend = Url::parse(backend).expect("backend URL");
            let allowed_origin = normalized_webview_origin(&backend);
            let same_origin = backend
                .join("assets/app.js?cache=1#section")
                .expect("same-origin URL");
            assert!(navigation_matches_webview_origin(
                &same_origin,
                &allowed_origin
            ));
        }
    }

    #[test]
    fn sibling_ports_hosts_and_schemes_are_denied() {
        let backend = Url::parse("http://127.0.0.1:8765/").expect("backend URL");
        let allowed_origin = normalized_webview_origin(&backend);
        for denied in [
            "http://127.0.0.1:8766/",
            "http://localhost:8765/",
            "http://[::1]:8765/",
            "https://127.0.0.1:8765/",
            "http://example.com:8765/",
            "data:text/html,foreign",
            "about:blank",
        ] {
            let denied = Url::parse(denied).expect("denied URL");
            assert!(
                !navigation_matches_webview_origin(&denied, &allowed_origin),
                "{denied} should not match {allowed_origin}"
            );
        }
    }
}
