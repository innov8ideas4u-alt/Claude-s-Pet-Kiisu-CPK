"""Pure-mock tests for the kill_stale sweeper (R7-killstale Deliverable B).

No hardware, no real process spawning. psutil.process_iter is mocked with
synthesized fake procs; terminate/kill/wait are MagicMocks whose behaviour the
test dictates.
"""

from __future__ import annotations

from unittest import mock

import pytest

psutil = pytest.importorskip("psutil")  # present in Victor's env; skip on fresh CI

from flipper_mcp.tools import kill_stale


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _fake_proc(pid, name, cmdline):
    """A MagicMock standing in for a psutil.Process."""
    proc = mock.MagicMock(name=f"proc-{pid}")
    proc.pid = pid
    proc.info = {"pid": pid, "name": name, "cmdline": cmdline}
    proc.cpu_percent.return_value = 0.0
    proc.create_time.return_value = 0.0
    return proc


SELF_PID = 1000
PARENT_PID = 1001
ORPHAN_PID = 4242
OTHER_PY_PID = 5555


def _proc_set():
    """orphan (real target), unrelated python, a proc carrying the self PID."""
    orphan = _fake_proc(
        ORPHAN_PID, "python.exe",
        ["C:\\Python313\\python.exe", "-m", "flipper_mcp.cli.main"],
    )
    other_py = _fake_proc(
        OTHER_PY_PID, "python.exe",
        ["python.exe", "some_other_script.py"],
    )
    # Matches the pattern but carries SELF_PID -> must be excluded.
    self_proc = _fake_proc(
        SELF_PID, "python.exe",
        ["python.exe", "-m", "flipper_mcp.cli.main"],
    )
    # A non-python proc that happens to mention the string -> must be excluded.
    non_python = _fake_proc(
        7777, "explorer.exe",
        ["explorer.exe", "flipper_mcp", "cli.main"],
    )
    return orphan, other_py, self_proc, non_python


# --------------------------------------------------------------------------- #
# Matcher
# --------------------------------------------------------------------------- #
def test_matcher_unit():
    assert kill_stale._is_flipper_orphan(
        "python.exe", ["python.exe", "-m", "flipper_mcp.cli.main"]) is True
    assert kill_stale._is_flipper_orphan(
        "python3.13", ["python3.13", "-m", "flipper_mcp"]) is True
    # flipper_mcp present but no known entrypoint
    assert kill_stale._is_flipper_orphan(
        "python.exe", ["python.exe", "flipper_mcp", "frobnicate.py"]) is False
    # entrypoint-ish but no flipper_mcp
    assert kill_stale._is_flipper_orphan(
        "python.exe", ["python.exe", "-m", "something.cli.main"]) is False
    # not a python process
    assert kill_stale._is_flipper_orphan(
        "explorer.exe", ["explorer.exe", "flipper_mcp", "cli.main"]) is False
    # empty / None-ish cmdline
    assert kill_stale._is_flipper_orphan("python.exe", []) is False


def test_find_orphans_selects_only_real_orphan():
    orphan, other_py, self_proc, non_python = _proc_set()
    procs = [orphan, other_py, self_proc, non_python]
    with mock.patch.object(kill_stale.psutil, "process_iter", return_value=iter(procs)):
        found = kill_stale.find_orphans(SELF_PID, PARENT_PID)
    assert found == [orphan]
    assert self_proc not in found      # never sweep self
    assert other_py not in found       # never sweep unrelated python
    assert non_python not in found     # never sweep non-python


def test_find_orphans_excludes_parent_pid():
    parent_match = _fake_proc(
        PARENT_PID, "python.exe",
        ["python.exe", "-m", "flipper_mcp.cli.main"],
    )
    with mock.patch.object(kill_stale.psutil, "process_iter",
                           return_value=iter([parent_match])):
        found = kill_stale.find_orphans(SELF_PID, PARENT_PID)
    assert found == []  # parent shell is never swept


def test_find_orphans_skips_inaccessible_procs():
    good = _fake_proc(ORPHAN_PID, "python.exe",
                      ["python.exe", "-m", "flipper_mcp.cli.main"])
    bad = mock.MagicMock(name="proc-bad")
    bad.pid = 9999
    # Accessing .info raises -- simulates a SYSTEM proc we can't read.
    type(bad).info = mock.PropertyMock(side_effect=psutil.AccessDenied(9999))
    with mock.patch.object(kill_stale.psutil, "process_iter",
                           return_value=iter([bad, good])):
        found = kill_stale.find_orphans(SELF_PID, PARENT_PID)
    assert found == [good]


# --------------------------------------------------------------------------- #
# Kill behaviour
# --------------------------------------------------------------------------- #
def test_dry_run_kills_nothing():
    orphan, *_ = _proc_set()
    with mock.patch.object(kill_stale, "find_orphans", return_value=[orphan]), \
         mock.patch.object(kill_stale, "_print_port_hint"):
        rc = kill_stale.main(["--dry-run"])
    assert rc == 0
    orphan.terminate.assert_not_called()
    orphan.kill.assert_not_called()


def test_default_terminate_clears_no_kill():
    orphan, *_ = _proc_set()
    orphan.wait.return_value = None  # terminate cleared it within the grace wait
    survivors = kill_stale.kill_victims([orphan], force=False)
    orphan.terminate.assert_called_once()
    orphan.kill.assert_not_called()
    assert survivors == []


def test_default_kill_when_terminate_does_not_clear():
    orphan, *_ = _proc_set()
    # First wait (after terminate) times out -> kill; second wait clears.
    orphan.wait.side_effect = [psutil.TimeoutExpired(kill_stale.GRACE_SECONDS), None]
    survivors = kill_stale.kill_victims([orphan], force=False)
    orphan.terminate.assert_called_once()
    orphan.kill.assert_called_once()
    assert survivors == []


def test_force_hard_kills_immediately_no_terminate():
    orphan, *_ = _proc_set()
    orphan.wait.return_value = None
    survivors = kill_stale.kill_victims([orphan], force=True)
    orphan.terminate.assert_not_called()
    orphan.kill.assert_called_once()
    assert survivors == []


def test_survivor_reported_but_exit_zero():
    orphan, *_ = _proc_set()
    # Never clears -> after terminate and kill it is still alive.
    orphan.wait.side_effect = psutil.TimeoutExpired(kill_stale.GRACE_SECONDS)
    survivors = kill_stale.kill_victims([orphan], force=False)
    assert survivors == [ORPHAN_PID]


def test_main_exit_zero_when_nothing_found():
    with mock.patch.object(kill_stale, "find_orphans", return_value=[]), \
         mock.patch.object(kill_stale, "_print_port_hint"):
        rc = kill_stale.main([])
    assert rc == 0


def test_main_default_path_kills_and_exits_zero():
    orphan, *_ = _proc_set()
    with mock.patch.object(kill_stale, "find_orphans", return_value=[orphan]), \
         mock.patch.object(kill_stale, "kill_victims", return_value=[]) as kv, \
         mock.patch.object(kill_stale, "_print_port_hint"):
        rc = kill_stale.main([])
    assert rc == 0
    kv.assert_called_once()


def test_main_missing_psutil_exits_one():
    with mock.patch.object(kill_stale, "psutil", None):
        rc = kill_stale.main([])
    assert rc == 1
