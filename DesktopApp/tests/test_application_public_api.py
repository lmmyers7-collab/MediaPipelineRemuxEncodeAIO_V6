from __future__ import annotations

import ast
import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


APP_PACKAGE = "mediapipeline_desktop_app.application"
APPLICATION_ROOT = Path(__file__).resolve().parents[1] / "mediapipeline_desktop_app" / "application"
PUBLIC_MODULE_PATTERNS = ("facade*.py", "dto*.py")


def _public_boundary_modules() -> list[Path]:
    paths: list[Path] = []
    for pattern in PUBLIC_MODULE_PATTERNS:
        paths.extend(APPLICATION_ROOT.glob(pattern))
    return sorted({path for path in paths if path.name != "__init__.py"})


def _literal_all(tree: ast.Module, path: Path) -> list[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, ast.List):
            raise AssertionError(f"{path.name} must define __all__ as a literal list")
        names: list[str] = []
        for item in node.value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                raise AssertionError(f"{path.name} __all__ entries must be literal strings")
            names.append(item.value)
        return names
    raise AssertionError(f"{path.name} is missing __all__")


def _defined_public_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_") and target.id.isupper():
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if not name.startswith("_") and name.isupper():
                names.append(name)
    return names


class ApplicationPublicApiTests(unittest.TestCase):
    def test_application_package_public_surface_is_explicit(self) -> None:
        package = importlib.import_module(APP_PACKAGE)
        public_names = list(getattr(package, "__all__", ()))

        self.assertIn("MediaPipelineApplicationFacade", public_names)
        self.assertIn("CommandResult", public_names)
        self.assertTrue(public_names)
        self.assertEqual(len(public_names), len(set(public_names)))
        for name in public_names:
            self.assertFalse(name.startswith("_"), name)
            self.assertTrue(hasattr(package, name), name)
            self.assertFalse(name.startswith("facade_"), name)
            self.assertFalse(name.startswith("dto_"), name)

    def test_facade_and_dto_modules_declare_all_exports(self) -> None:
        for path in _public_boundary_modules():
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                exported = _literal_all(tree, path)
                defined = _defined_public_names(tree)

                self.assertEqual(len(exported), len(set(exported)), path.name)
                for name in defined:
                    self.assertIn(name, exported, f"{path.name} should export defined public symbol {name}")
                for name in exported:
                    self.assertFalse(name.startswith("_"), f"{path.name} exports private symbol {name}")

    def test_declared_facade_and_dto_exports_resolve(self) -> None:
        for path in _public_boundary_modules():
            module_name = f"{APP_PACKAGE}.{path.stem}"
            with self.subTest(module=module_name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                module = importlib.import_module(module_name)
                for name in _literal_all(tree, path):
                    self.assertTrue(hasattr(module, name), f"{module_name}.{name} does not resolve")


if __name__ == "__main__":
    unittest.main()
