"""kill_stale -- sweep orphaned flipper_mcp processes.

R7-killstale Deliverable B (the "mop"). Hard client kills can leave a leftover
``python.exe`` holding the Flipper's COM port after the normal async-disconnect
finally-path never completed. This standalone CLI enumerates such orphans and
terminates them.

Run:  python -m flipper_mcp.tools.kill_stale [--dry-run] [--force]

Self-contained: stdlib + psutil (+ optional pyserial for the port hint). No
imports from the MCP server internals -- safe to run while nothing else is up.
All human-facing output goes to stdout (this is a CLI tool, not the MCP stdio
server).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import psutil
except ImportError:  # fresh cloner without the dep
    psutil = None

GRACE_SECONDS = 3


def _is_flipper_orphan(name: str, cmdline: list) -> bool:
    """True if a python process whose cmdline names flipper_mcp + a known entrypoint."""
    if not name or not name.lower().startswith("python"):
        return False
    joined = " ".join(cmdline)
    if "flipper_mcp" not in joined:
        return False
    return ("cli.main" in joined) or ("cli/main" in joined) or ("-m flipper_mcp" in joined)


def _safe_pid(proc) -> int:
    try:
        return proc.pid
    except Exception:
        return -1


def find_orphans(self_pid: int, parent_pid: int) -> list:
    """Return psutil.Process objects matching the orphan pattern, minus self/parent.

    Per spec P6: match the pattern FIRST, then drop self/parent by PID (order
    matters). Per-proc access is wrapped -- some Windows/SYSTEM procs raise
    NoSuchProcess/AccessDenied or return a None cmdline.
    """
    matched = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            cmdline = info.get("cmdline") or []
            if _is_flipper_orphan(name, cmdline):
                matched.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            continue
    # Drop self + launching shell only AFTER matching (spec P6).
    return [p for p in matched if _safe_pid(p) not in (self_pid, parent_pid)]


def describe(proc) -> str:
    """One-line victim summary: pid, cpu%, age, cmdline[:80]."""
    pid = _safe_pid(proc)
    try:
        cmdline = " ".join(proc.info.get("cmdline") or [])
    except Exception:
        cmdline = "?"
    try:
        cpu = proc.cpu_percent(interval=None)  # non-blocking; first call returns 0.0
    except Exception:
        cpu = 0.0
    try:
        age_str = f"{time.time() - proc.create_time():.0f}s"
    except Exception:
        age_str = "?"
    return f"  pid={pid} cpu={cpu:.1f}% age={age_str} cmd={cmdline[:80]}"


def _wait_gone(proc, timeout: float) -> bool:
    """True if proc exits within timeout (or is already gone)."""
    try:
        proc.wait(timeout=timeout)
        return True
    except psutil.TimeoutExpired:
        return False
    except psutil.NoSuchProcess:
        return True


def kill_victims(victims: list, force: bool = False) -> list:
    """terminate -> wait <=GRACE_SECONDS -> kill stragglers (or hard-kill on force).

    Returns the list of PIDs that survived (P7: warn + continue, do not raise).
    """
    survivors = []
    for proc in victims:
        pid = _safe_pid(proc)
        try:
            if force:
                proc.kill()
                gone = _wait_gone(proc, GRACE_SECONDS)
            else:
                proc.terminate()
                gone = _wait_gone(proc, GRACE_SECONDS)
                if not gone:
                    proc.kill()
                    gone = _wait_gone(proc, GRACE_SECONDS)
            if not gone:
                print(f"  WARN: pid {pid} survived kill; still running")
                survivors.append(pid)
        except psutil.NoSuchProcess:
            pass  # already gone == success
        except Exception as exc:  # P7: warn, keep going, still exit 0
            print(f"  WARN: could not kill pid {pid}: {exc}")
            survivors.append(pid)
    return survivors


def _print_port_hint() -> None:
    """Best-effort COM-port report. pyserial absence is silent (P7)."""
    try:
        import serial.tools.list_ports as list_ports
    except ImportError:
        return
    try:
        ports = [p.device for p in list_ports.comports()]
    except Exception:
        return
    if ports:
        print(f"COM ports present: {', '.join(ports)}")
    else:
        print("No serial COM ports currently enumerated.")
    flipper_port = os.environ.get("FLIPPER_PORT")
    if flipper_port and flipper_port in ports:
        print(f"  {flipper_port} still present, replug if access-denied persists.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flipper_mcp.tools.kill_stale",
        description="Sweep orphaned flipper_mcp processes that linger after hard exits.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List matching orphans but kill nothing.")
    parser.add_argument("--force", action="store_true",
                        help="Hard-kill immediately, skipping the graceful terminate wait.")
    args = parser.parse_args(argv)

    if psutil is None:
        print("ERROR: psutil is required for kill_stale. Install it with:")
        print("    pip install psutil")
        return 1

    try:
        self_pid = os.getpid()
        parent_pid = os.getppid()
        victims = find_orphans(self_pid, parent_pid)

        if not victims:
            print("No stale flipper_mcp processes found.")
            _print_port_hint()
            return 0

        print(f"Found {len(victims)} stale flipper_mcp process(es):")
        for proc in victims:
            print(describe(proc))

        if args.dry_run:
            print("--dry-run: nothing killed.")
            _print_port_hint()
            return 0

        survivors = kill_victims(victims, force=args.force)
        print(f"Killed {len(victims) - len(survivors)} of {len(victims)} process(es).")
        if survivors:
            print(f"WARN: {len(survivors)} could not be killed: {survivors}")
        _print_port_hint()
        return 0  # P7: the tool ran -> exit 0 even with survivors
    except Exception as exc:  # unexpected top-level failure only
        print(f"ERROR: unexpected failure: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
