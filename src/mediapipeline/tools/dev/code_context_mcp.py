"""Expose the read-only MediaPipeline repository context service over MCP stdio."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mediapipeline.tools.dev.code_context_service import BundleFileRequest, CodeContextService


SERVER_NAME = "mediapipeline-code"
SERVER_INSTRUCTIONS = "Read-only repository navigation. Start with repo_context, then use bounded lookup, search, and reads."
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def create_mcp_server(service: CodeContextService | None = None) -> FastMCP:
    context_service = service or CodeContextService()
    server = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS, json_response=True)

    @server.tool(annotations=READ_ONLY)
    def repo_context(
        task: str,
        budget: int = 2000,
        include_history: bool = False,
        retrieval_tier: str = "active",
    ) -> dict[str, Any]:
        """Get a token-bounded implementation slice for a repository task."""
        return context_service.repo_context(
            task,
            budget=budget,
            include_history=include_history,
            retrieval_tier=retrieval_tier,
        )

    @server.tool(annotations=READ_ONLY)
    def code_lookup(
        query: str,
        feature_id: str | None = None,
        owner_domain: str | None = None,
        file_type: str | None = None,
        limit: int = 20,
        retrieval_tier: str = "active",
    ) -> dict[str, Any]:
        """Find catalog records; an exact path includes relationships and tests."""
        return context_service.code_lookup(
            query,
            feature_id=feature_id,
            owner_domain=owner_domain,
            file_type=file_type,
            limit=limit,
            retrieval_tier=retrieval_tier,
        )

    @server.tool(annotations=READ_ONLY)
    def code_search(
        query: str,
        path_prefix: str | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 40,
    ) -> dict[str, Any]:
        """Search current active repository text with bounded results."""
        return context_service.code_search(
            query,
            path_prefix=path_prefix,
            regex=regex,
            case_sensitive=case_sensitive,
            max_results=max_results,
        )

    @server.tool(annotations=READ_ONLY)
    def code_read(path: str, start_line: int = 1, end_line: int | None = None, detail: str = "compact") -> dict[str, Any]:
        """Read a bounded UTF-8 line range from an allowed repository file."""
        return context_service.code_read(path, start_line=start_line, end_line=end_line, detail=detail)

    @server.tool(annotations=READ_ONLY)
    def code_bundle(files: list[BundleFileRequest], budget: int = 3000) -> dict[str, Any]:
        """Read up to eight source ranges under one shared token budget."""
        return context_service.code_bundle(files, budget=budget)

    return server


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
