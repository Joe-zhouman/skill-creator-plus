"""Behavioral tests for check-skill.py — drive the script via subprocess and inspect exit codes."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent  # tests/ -> repo root
SCRIPT = REPO / "skills" / "skill-creator++" / "scripts" / "check-skill.py"


def run_check(skill_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), str(skill_path)], capture_output=True, text=True)


def make_minimal_skill(tmp: Path, name: str = "test-skill") -> Path:
    """Build a skill that passes every check."""
    skill_dir = tmp / name
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "assets").mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "tests").mkdir()
    (skill_dir / "tests" / "discipline-tests.md").write_text("# test\n")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: Use when testing.\n"
        "---\n\n"
        "# test-skill\n"
    )
    return skill_dir


def test_passes_on_valid_skill(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    result = run_check(skill)
    assert result.returncode == 0, f"expected pass, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_passes_with_minimal_yaml_frontmatter(tmp_path: Path):
    """Per Joe: script checks yaml structure, LLM judges description content."""
    skill_dir = tmp_path / "test-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "assets").mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "tests").mkdir()
    (skill_dir / "tests" / "discipline-tests.md").write_text("# test\n")
    (skill_dir / "SKILL.md").write_text("---\n---\n\n# t\n")
    result = run_check(skill_dir)
    assert result.returncode == 0, f"expected pass with bare --- markers, got {result.returncode}\nstdout: {result.stdout}"


def test_fails_when_tests_missing(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    import shutil
    shutil.rmtree(skill / "tests")
    result = run_check(skill)
    assert result.returncode != 0
    assert "#4" in result.stdout or "tests" in result.stdout.lower()


def test_fails_when_frontmatter_missing(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    (skill / "SKILL.md").write_text("# no frontmatter\n\nbody\n")
    result = run_check(skill)
    assert result.returncode != 0


def test_fails_when_script_not_executable(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    bad_script = skill / "scripts" / "bad.sh"
    bad_script.write_text("#!/usr/bin/env bash\necho hi\n")
    bad_script.chmod(0o644)
    result = run_check(skill)
    assert result.returncode != 0


def test_fails_when_referenced_file_missing(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: Use when testing.\n"
        "---\n\n"
        "# test-skill\n\nSee [patterns.md](references/does-not-exist.md).\n"
    )
    result = run_check(skill)
    assert result.returncode != 0


def test_fails_when_skill_md_exceeds_500_lines(tmp_path: Path):
    skill = make_minimal_skill(tmp_path)
    body = "---\nname: t\ndescription: Use when testing.\n---\n\n# t\n" + ("line\n" * 510)
    (skill / "SKILL.md").write_text(body)
    result = run_check(skill)
    assert result.returncode != 0
    assert "500" in result.stdout or "lines" in result.stdout.lower()


def test_self_check_passes_on_meta_skill():
    """The meta skill itself must pass its own lint — Success Criterion #3."""
    meta_skill = REPO / "skills" / "skill-creator++"
    result = run_check(meta_skill)
    assert result.returncode == 0, f"meta skill failed self-check:\n{result.stdout}\n{result.stderr}"