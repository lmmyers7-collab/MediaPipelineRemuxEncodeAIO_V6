use crate::http_helpers::bounded_text;

use super::types::BackendRoute;

pub(crate) fn format_list_preview(items: &[String], max_items: usize) -> String {
    let preview = items
        .iter()
        .take(max_items)
        .map(|item| bounded_text(item, 80))
        .collect::<Vec<String>>()
        .join(", ");
    if items.len() > max_items {
        format!("{preview}, ...")
    } else {
        preview
    }
}

pub(crate) fn format_route_sample(routes: &[BackendRoute], max_items: usize) -> String {
    let preview = routes
        .iter()
        .take(max_items)
        .map(|route| {
            format!(
                "{} {} auth_required={}",
                route.method, route.path, route.auth_required
            )
        })
        .collect::<Vec<String>>()
        .join("; ");
    if routes.len() > max_items {
        format!("{preview}; ...")
    } else {
        preview
    }
}
