#!/usr/bin/env python3
"""Run Phase 3 pipeline: containerlab deploy, render, push, pytest, destroy."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_DIR))

from lab_tools import load_inventory  # noqa: E402


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=_AUTOMATION_DIR, env=env, check=True)


def wait_for_ssh(host: str, port: int, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2)
    return False


def wait_for_all_ssh(inventory_path: Path, timeout_s: int) -> None:
    inv = load_inventory(inventory_path)
    defaults = inv.get("defaults") or {}
    devices = inv.get("devices") or {}
    for hostname, conn in devices.items():
        host = conn["host"]
        port = int(conn.get("port", defaults.get("port", 22)))
        print(f"Waiting for SSH on {hostname} ({host}:{port}) ...")
        if not wait_for_ssh(host, port, timeout_s):
            raise TimeoutError(f"SSH not reachable for {hostname} ({host}:{port})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--clab-topology",
        type=Path,
        default=_AUTOMATION_DIR / "containerlab" / "lab10.clab.yml",
    )
    ap.add_argument(
        "--inventory",
        type=Path,
        default=_AUTOMATION_DIR / "data" / "inventory.containerlab.yaml",
    )
    ap.add_argument(
        "--topology",
        type=Path,
        default=_AUTOMATION_DIR / "data" / "topology.containerlab.yaml",
        help="Lab topology YAML (use topology.containerlab.yaml for clab NIC mapping)",
    )
    ap.add_argument("--pytest-target", default="tests/test_containerlab.py")
    ap.add_argument("--ssh-timeout", type=int, default=180)
    ap.add_argument(
        "--convergence-wait",
        type=int,
        default=20,
        metavar="SEC",
        help="Seconds to sleep after push before live tests (OSPF/routing); 0 to skip",
    )
    ap.add_argument(
        "--keep",
        action="store_true",
        help="Leave the lab running (skip containerlab destroy)",
    )
    args = ap.parse_args()

    if not shutil.which("containerlab"):
        print("containerlab command not found in PATH", file=sys.stderr)
        return 1
    if not args.clab_topology.is_file():
        print(f"Missing topology file: {args.clab_topology}", file=sys.stderr)
        return 1
    if not args.inventory.is_file():
        print(f"Missing inventory file: {args.inventory}", file=sys.stderr)
        return 1
    if "LAB10_SSH_PASSWORD" not in os.environ:
        print("Set LAB10_SSH_PASSWORD before running this pipeline", file=sys.stderr)
        return 1

    clab_name = "lab10-twin"
    deployed = False
    try:
        run(["containerlab", "deploy", "-t", str(args.clab_topology), "--reconfigure"])
        deployed = True
        wait_for_all_ssh(args.inventory, timeout_s=args.ssh_timeout)
        run([sys.executable, "scripts/render.py", "--topology", str(args.topology)])
        run(
            [
                sys.executable,
                "scripts/push.py",
                "--inventory",
                str(args.inventory),
                "--topology",
                str(args.topology),
            ]
        )
        if args.convergence_wait > 0:
            w = args.convergence_wait
            print(f"Waiting {w}s for routing to converge before tests ...")
            time.sleep(args.convergence_wait)
        env = dict(os.environ)
        env["LAB10_LIVE_TESTS"] = "1"
        env["LAB10_INVENTORY"] = str(args.inventory)
        env["LAB10_TOPOLOGY"] = str(args.topology)
        run([sys.executable, "-m", "pytest", "-q", args.pytest_target], env=env)
        return 0
    finally:
        if deployed and not args.keep:
            run(["containerlab", "destroy", "-t", str(args.clab_topology), "--cleanup"])
        elif deployed:
            print(f"Lab left running: {clab_name}")


if __name__ == "__main__":
    raise SystemExit(main())
