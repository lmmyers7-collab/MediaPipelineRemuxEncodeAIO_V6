import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dev" / "check_marketecture.py"
POLICY_PATH = REPO_ROOT / "Docs" / "inventories" / "MARKETECTURE_GUARDRAIL.v1.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_marketecture", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


module = _load_module()


def test_policy_file_exists_and_matches_schema():
    assert POLICY_PATH.is_file()
    import json

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["schema_version"] == module.SCHEMA_VERSION
    assert policy["terms"]


def test_flags_clear_buzzword():
    findings = module.findings_for_text("This is a world-class encoder.", "Docs/example.md")
    assert any(finding.term == "world-class" for finding in findings)
    assert all(finding.rule_id == "MKT001" for finding in findings)


def test_flags_multiple_terms_on_one_line():
    findings = module.findings_for_text("blazing-fast and cutting-edge", "Docs/example.md")
    terms = {finding.term for finding in findings}
    assert {"blazing-fast", "cutting-edge"} <= terms


def test_clean_text_passes():
    text = "The encoder copies sources to scratch and decides remux versus encode."
    assert module.findings_for_text(text, "Docs/example.md") == []


def test_ambiguous_technical_words_not_flagged():
    # These are deliberately excluded to avoid false positives.
    text = "A robust, scalable, performant, first-class, holistic design that we leverage."
    assert module.findings_for_text(text, "Docs/example.md") == []


def test_suppression_marker_skips_line():
    text = "world-class result allow-marketecture"
    assert module.findings_for_text(text, "Docs/example.md") == []


def test_word_boundary_avoids_substring_noise():
    # "synergy" must not match inside an unrelated longer token.
    text = "The intersynergybridge identifier is fine."
    assert module.findings_for_text(text, "Docs/example.md") == []


def test_is_scannable_respects_globs():
    include = module.load_include_globs()
    exclude = module.load_exclude_globs()
    assert module.is_scannable("Docs/architecture/ARCHITECTURE.md", include, exclude)
    assert module.is_scannable("DesktopApp/mediapipeline_desktop_app/services.py", include, exclude)
    assert not module.is_scannable("node_modules/pkg/readme.md", include, exclude)
    assert not module.is_scannable("Docs/archive/old.md", include, exclude)
    assert not module.is_scannable("DesktopApp/Runtime/Python/Lib/foo.py", include, exclude)


def test_paths_mode_clean_file_returns_zero(tmp_path, capsys):
    clean = REPO_ROOT / "README.md"
    # README is real and expected clean; running --paths against it should pass.
    rc = module.main(["--paths", "README.md"])
    assert rc == 0


def test_paths_mode_flags_buzzword_file(tmp_path):
    target = REPO_ROOT / "Docs" / "generated" / "_marketecture_test_fixture.md"
    target.write_text("A world-class, turnkey solution.\n", encoding="utf-8")
    try:
        rc = module.main(["--paths", "Docs/generated/_marketecture_test_fixture.md"])
        assert rc == 1
    finally:
        target.unlink(missing_ok=True)
