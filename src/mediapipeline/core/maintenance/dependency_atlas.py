from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mediapipeline.desktop.subprocess_runner import run_capture


class DependencyAtlasServiceMixin:
    """Maintenance tooling runner for the generated Python dependency atlas."""

    def dependency_atlas_generator_path(self) -> Path:
        return self.workspace_root / "src" / "mediapipeline" / "tools" / "dev" / "generate_dependency_atlas.py"

    def dependency_atlas_python_path(self) -> Path:
        candidates = (
            self.workspace_root / "apps" / "desktop" / "runtime" / "Python" / "python.exe",
            self.app_root / "runtime" / "Python" / "python.exe",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(sys.executable)

    def dependency_atlas_output_dir(self) -> Path:
        return self.workspace_root / "docs/generated/dependency-atlas"

    def generate_dependency_atlas(
        self,
        *,
        timeout_seconds: int,
        min_overview_edge_count: int,
        min_overview_files: int,
    ) -> dict[str, Any]:
        script = self.dependency_atlas_generator_path()
        python_path = self.dependency_atlas_python_path()
        output_dir = self.dependency_atlas_output_dir()
        html_path = output_dir / "dependency-atlas.html"
        png_path = output_dir / "dependency-atlas.png"
        svg_path = output_dir / "dependency-atlas.svg"
        assets_dir = output_dir / "assets"
        summary_csv = assets_dir / "dependency_summary.csv"
        domain_edges_csv = assets_dir / "dependency_edges.csv"
        module_edges_csv = assets_dir / "dependency_module_edges.csv"

        if not script.exists():
            return {
                "success": False,
                "timed_out": False,
                "returncode": 127,
                "command": f'"{python_path}" -m mediapipeline.tools.dev.generate_dependency_atlas',
                "stdout": "",
                "stderr": f"Dependency atlas generator not found: {script}",
                "elapsed_seconds": 0.0,
                "atlas_html": str(html_path),
                "atlas_png": str(png_path),
                "atlas_svg": str(svg_path),
                "assets_dir": str(assets_dir),
                "summary_csv": str(summary_csv),
                "domain_edges_csv": str(domain_edges_csv),
                "module_edges_csv": str(module_edges_csv),
                "html_exists": html_path.exists(),
                "png_exists": png_path.exists(),
                "svg_exists": svg_path.exists(),
                "summary_csv_exists": summary_csv.exists(),
                "domain_edges_csv_exists": domain_edges_csv.exists(),
                "module_edges_csv_exists": module_edges_csv.exists(),
            }

        args = [
            str(python_path),
            "-m",
            "mediapipeline.tools.dev.generate_dependency_atlas",
            "--min-overview-edge-count",
            str(max(1, int(min_overview_edge_count))),
            "--min-overview-files",
            str(max(1, int(min_overview_files))),
        ]
        command_line = subprocess.list2cmdline(args)
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.info("Dependency atlas generation requested: %s", command_line)

        env = self._build_launch_environment()
        src_root = self.workspace_root / "src"
        if src_root.exists():
            src_root_text = str(src_root)
            existing_pythonpath = env.get("PYTHONPATH", "")
            pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
            if src_root_text.casefold() not in {part.casefold() for part in pythonpath_parts}:
                pythonpath_parts.insert(0, src_root_text)
            env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        started = time.monotonic()
        result = run_capture(
            args,
            cwd=str(self.workspace_root),
            env=env,
            encoding="utf-8",
            errors="replace",
            timeout_seconds=max(30, int(timeout_seconds)),
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
            label="dependency atlas",
            kill_tree=getattr(self, "kill_process_tree", None),
        )
        outputs_exist = html_path.exists() and png_path.exists() and svg_path.exists()
        csvs_exist = summary_csv.exists() and domain_edges_csv.exists() and module_edges_csv.exists()
        return {
            "success": result.returncode == 0 and not result.timed_out and outputs_exist and csvs_exist,
            "timed_out": bool(result.timed_out),
            "returncode": result.returncode,
            "command": command_line,
            "stdout": result.stdout,
            "stderr": result.stderr or result.kill_message,
            "elapsed_seconds": time.monotonic() - started,
            "atlas_html": str(html_path),
            "atlas_png": str(png_path),
            "atlas_svg": str(svg_path),
            "assets_dir": str(assets_dir),
            "summary_csv": str(summary_csv),
            "domain_edges_csv": str(domain_edges_csv),
            "module_edges_csv": str(module_edges_csv),
            "html_exists": html_path.exists(),
            "png_exists": png_path.exists(),
            "svg_exists": svg_path.exists(),
            "summary_csv_exists": summary_csv.exists(),
            "domain_edges_csv_exists": domain_edges_csv.exists(),
            "module_edges_csv_exists": module_edges_csv.exists(),
        }


__all__ = [
    "DependencyAtlasServiceMixin",
]
