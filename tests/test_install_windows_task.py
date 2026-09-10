r"""`_enable_catch_up` — the StartWhenAvailable fix in the task installer.

`schtasks /Create` cannot set `StartWhenAvailable`, and without it a trigger
whose time passes while the machine is off is dropped and never retried —
silently, since `LastTaskResult` stays 267011 ("has not yet run"), identical to
a task legitimately waiting for a future date. Two dated one-shot reviews were
lost that way for ~4 months.

The only real logic here is splitting ``Folder\Leaf`` into the `-TaskPath` /
`-TaskName` pair PowerShell wants; everything else is a shell-out. A wrong
split silently targets the wrong task (or none), so that is what is pinned.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def installer():
    path = ROOT / "scripts" / "schedulers" / "automation" / "install_windows_task.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("_install_windows_task", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _spy(monkeypatch, installer, returncode=0, raises=None):
    """Capture the argv `_enable_catch_up` would run, without running it."""
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(argv, returncode, "", "")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    return calls


@pytest.mark.parametrize(
    "tn, leaf, path",
    [
        (r"Edge-Radar\Daily-Summary", "Daily-Summary", "Edge-Radar" + "\\"),
        (
            r"AI-Projects\Edge-Radar-MikesAILab\Hourly-Settle",
            "Hourly-Settle",
            r"AI-Projects\Edge-Radar-MikesAILab" + "\\",
        ),
        ("Top-Level-Task", "Top-Level-Task", "\\"),
    ],
)
def test_splits_folder_from_leaf(installer, monkeypatch, tn, leaf, path):
    calls = _spy(monkeypatch, installer)
    assert installer._enable_catch_up(tn) is True
    script = calls[0][-1]
    assert f"-TaskName '{leaf}'" in script
    assert f"-TaskPath '{path}'" in script
    # The whole point: it must actually set the flag.
    assert "$t.Settings.StartWhenAvailable = $true" in script
    assert "Set-ScheduledTask" in script


def test_prefers_pwsh_and_stops_on_success(installer, monkeypatch):
    calls = _spy(monkeypatch, installer)
    assert installer._enable_catch_up("F" + "\\" + "T") is True
    assert len(calls) == 1, "a success must not also try powershell"
    assert calls[0][0] == "pwsh"


def test_falls_back_to_windows_powershell(installer, monkeypatch):
    """pwsh is not installed everywhere; Windows PowerShell always is."""
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        if argv[0] == "pwsh":
            raise FileNotFoundError("pwsh")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    assert installer._enable_catch_up("F" + "\\" + "T") is True
    assert [c[0] for c in calls] == ["pwsh", "powershell"]


def test_returns_false_when_every_shell_fails(installer, monkeypatch):
    """Non-fatal by design: the caller warns, it does not fail the install.

    A task without the flag still runs whenever the machine is up, so a
    restricted PowerShell is not a reason to reject an otherwise-good install.
    """
    _spy(monkeypatch, installer, returncode=1)
    assert installer._enable_catch_up("F" + "\\" + "T") is False


def test_runs_non_interactively(installer, monkeypatch):
    """Task installs run unattended; a prompting shell would hang the install."""
    calls = _spy(monkeypatch, installer)
    installer._enable_catch_up("F" + "\\" + "T")
    assert "-NonInteractive" in calls[0]
    assert "-NoProfile" in calls[0]
