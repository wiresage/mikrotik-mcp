"""Contract tests for the uv packaging/release toolchain (T4/T5/T6/T7).

Per the test plan, the release chain (AC-04/06/09) and the block-a-bad-state
guards (AC-03/05/08) are verified at *contract* level: parse the committed
artifact (CI + release workflows, Dockerfile, manifest, lockfile) and assert the
required declaration/flag is present and correctly set — no live process.

These assertions codify the migration's invariants so they cannot silently
regress once the feature ships.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"
PUBLISH = REPO / ".github" / "workflows" / "publish.yml"
DOCKERFILE = REPO / "Dockerfile"
PYPROJECT = REPO / "pyproject.toml"
UV_LOCK = REPO / "uv.lock"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load(path: Path) -> dict:
    return yaml.safe_load(_text(path))


def _all_run_steps(workflow: dict) -> str:
    """Concatenate every step's `run:` script across all jobs."""
    chunks = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if run:
                chunks.append(run)
    return "\n".join(chunks)


def _python_matrices(workflow: dict) -> list[list]:
    out = []
    for job in workflow.get("jobs", {}).values():
        versions = (job.get("strategy", {}) or {}).get("matrix", {}).get("python-version")
        if versions:
            out.append([str(v) for v in versions])
    return out


# --- AC-03 (T4): CI carries a lockfile-drift gate that fails on a stale lock ---

def test_ci_has_lockfile_drift_gate():
    runs = _all_run_steps(_load(CI))
    assert "uv lock --check" in runs, (
        "ci.yml must run `uv lock --check` to block an out-of-date lockfile"
    )


def test_ci_drift_gate_names_the_lockfile_in_plain_language():
    runs = _all_run_steps(_load(CI))
    assert "out of date" in runs.lower() and "uv.lock" in runs, (
        "the drift gate must fail with a plain-language message naming uv.lock as out of date"
    )


# --- AC-01/AC-02: CI proves the 3.10/3.11/3.12 matrix on the frozen lock ---

def test_ci_runs_full_python_matrix_on_frozen_lock():
    wf = _load(CI)
    matrices = _python_matrices(wf)
    assert any({"3.10", "3.11", "3.12"} <= set(m) for m in matrices), (
        f"ci.yml must test Python 3.10/3.11/3.12; found matrices {matrices}"
    )
    runs = _all_run_steps(wf)
    assert "uv sync --frozen" in runs, "ci.yml must provision with `uv sync --frozen`"
    assert "uv run pytest" in runs, "ci.yml must run the suite via `uv run pytest`"


# --- AC-04 (T5): release workflow builds from the frozen lockfile ---

def test_publish_builds_from_frozen_lock():
    runs = _all_run_steps(_load(PUBLISH))
    assert "uv build" in runs, "publish.yml must build the distributable with `uv build`"
    assert "uv lock --check" in runs, (
        "publish.yml must verify the frozen lock (`uv lock --check`) before building, "
        "so the published artifact is produced from the locked-and-tested set"
    )


# --- AC-06: publish is gated on OIDC authorization, no stored token ---

def test_publish_is_gated_on_oidc_trusted_publisher():
    wf = _load(PUBLISH)
    has_id_token = any(
        (job.get("permissions", {}) or {}).get("id-token") == "write"
        for job in wf.get("jobs", {}).values()
    )
    assert has_id_token, "a publish job must request `id-token: write` for OIDC"
    text = _text(PUBLISH)
    assert "pypa/gh-action-pypi-publish" in text, "publish must use the PyPI trusted-publisher action"
    assert "skip-existing" in text, "publish must set skip-existing to tolerate duplicate versions"


# --- AC-06 (T7): release-time tooling is pinned + integrity-verified ---

def test_mcp_publisher_is_pinned_and_checksum_verified():
    text = _text(PUBLISH)
    assert "/latest/download/" not in text, (
        "mcp-publisher must be pinned to a specific release, not pulled from /latest/"
    )
    assert "sha256sum -c" in text, (
        "the downloaded mcp-publisher tarball must be checksum-verified before use"
    )


# --- AC-09 (T6): container build installs from the frozen lock on the pinned base ---

def test_dockerfile_uses_frozen_lock_on_pinned_uv_base():
    text = _text(DOCKERFILE)
    assert "ghcr.io/astral-sh/uv:0.11" in text, "Dockerfile must use the pinned uv base image"
    assert "uv sync --frozen" in text, "Dockerfile must install deps with `uv sync --frozen`"


# --- AC-08: manifest declares the minimum supported Python floor ---

def test_pyproject_declares_python_floor():
    text = _text(PYPROJECT)
    assert 'requires-python = ">=3.10"' in text, (
        "pyproject.toml must declare requires-python >=3.10 so a lower interpreter is refused"
    )


# --- AC-05: every registry-sourced dependency in the lockfile carries a hash ---

def test_uv_lock_records_integrity_hash_for_every_registry_package():
    blocks = _text(UV_LOCK).split("[[package]]")
    # a package's own source line starts at column 0; dependency entries that mention
    # `source = { registry` are indented inside the `dependencies = [...]` list
    registry_pkgs = [b for b in blocks if re.search(r"^source = \{ registry", b, re.MULTILINE)]
    assert registry_pkgs, "uv.lock should pin registry packages"
    missing = [
        b.splitlines()[1] if len(b.splitlines()) > 1 else b[:40]
        for b in registry_pkgs
        if "sha256:" not in b
    ]
    assert not missing, f"registry packages in uv.lock without an integrity hash: {missing}"


# --- release plumbing that the migration touches and that can fail silently ---

DOCKER_PUBLISH = REPO / ".github" / "workflows" / "docker-publish.yml"
DOCKERIGNORE = REPO / ".dockerignore"
GITIGNORE = REPO / ".gitignore"


def _push_paths(path: Path) -> list:
    wf = _load(path)
    trigger = wf.get("on", wf.get(True))  # PyYAML (YAML 1.1) reads the bare key `on` as True
    return trigger["push"]["paths"]


def test_release_workflows_share_one_paths_guard():
    """publish.yml and docker-publish.yml must release on the same changes: the image version has to match a PyPI release."""
    assert _push_paths(PUBLISH) == _push_paths(DOCKER_PUBLISH)


def test_paths_guard_tracks_the_lockfile_not_requirements_txt():
    """uv.lock decides what the Docker image installs, so changing it must release; requirements.txt no longer exists."""
    paths = _push_paths(PUBLISH)
    assert "uv.lock" in paths
    assert "requirements.txt" not in paths
    assert not (REPO / "requirements.txt").exists(), "dependencies live in pyproject.toml and uv.lock"


def test_pyproject_has_exactly_one_line_the_release_sed_rewrites():
    """CI runs sed 's/version = ".*"/version = "<computed>"/' on pyproject.toml; any second matching line would be rewritten too."""
    hits = [line for line in _text(PYPROJECT).splitlines() if 'version = "' in line]
    assert len(hits) == 1, f"the release version injection rewrites every line containing `version = \"`: {hits}"
    assert hits[0].startswith("version = "), hits


def test_docker_context_keeps_readme_for_the_build_backend():
    """pyproject.toml declares readme = README.md; the build backend reads it, and `*.md` is dockerignored."""
    ignore = _text(DOCKERIGNORE).splitlines()
    assert "!README.md" in ignore, "README.md must be re-included after the *.md rule, or the image build fails"
    assert "COPY pyproject.toml uv.lock README.md" in _text(DOCKERFILE)


def test_dockerfile_builds_the_venv_on_the_images_own_python():
    """The production stage copies the venv; a uv-managed interpreter would leave its python symlink dangling there."""
    text = _text(DOCKERFILE)
    assert "UV_PYTHON_DOWNLOADS=never" in text
    assert "UV_PYTHON_PREFERENCE=only-system" in text


def test_uv_lock_is_tracked_not_ignored():
    lines = [line.strip() for line in _text(GITIGNORE).splitlines()]
    assert "uv.lock" not in lines, "uv.lock is committed; the build, CI and the image install from it"
