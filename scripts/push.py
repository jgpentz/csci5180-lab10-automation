#!/usr/bin/env python3
"""Push artifacts/<host>.cfg to routers (SSH / Netmiko, merge into running config)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_DIR))

from lab_tools import (  # noqa: E402
    hostnames_in_deploy_order,
    load_inventory,
    load_topology,
    netmiko_connect_kwargs,
    require_inventory_hosts,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    data = _AUTOMATION_DIR / "data"
    ap.add_argument("--inventory", type=Path, default=data / "inventory.yaml")
    ap.add_argument("--topology", type=Path, default=data / "topology.yaml")
    ap.add_argument("--artifacts", type=Path, default=_AUTOMATION_DIR / "artifacts")
    ap.add_argument("--only", default="", help="Comma-separated hosts (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="Print plan only")
    ap.add_argument("--continue-on-error", action="store_true")
    args = ap.parse_args(argv)

    if not args.inventory.is_file():
        print(f"Missing {args.inventory}", file=sys.stderr)
        print("Copy data/inventory.example.yaml to inventory.yaml.", file=sys.stderr)
        return 1
    if not args.topology.is_file():
        print(f"Missing {args.topology}", file=sys.stderr)
        return 1

    inv = load_inventory(args.inventory)
    topo = load_topology(args.topology)
    only = frozenset(x.strip() for x in args.only.split(",") if x.strip()) or None
    hosts = hostnames_in_deploy_order(topo, only=only)
    require_inventory_hosts(inv, hosts)

    if args.dry_run:
        dfl = inv.get("defaults") or {}
        for h in hosts:
            dc = inv["devices"][h]
            port = dc.get("port")
            if port is None:
                port = dfl.get("port", 22)
            print(f"{h}: {args.artifacts / (h + '.cfg')} -> {dc['host']}:{port}")
        return 0

    try:
        from netmiko import ConnectHandler
    except ImportError:
        print("Run: uv sync", file=sys.stderr)
        return 1

    errors: list[str] = []
    for h in hosts:
        cfg = args.artifacts / f"{h}.cfg"
        if not cfg.is_file():
            errors.append(f"{h}: no file {cfg}")
            print(errors[-1], file=sys.stderr)
            if not args.continue_on_error:
                return 1
            continue
        kw = netmiko_connect_kwargs(inv, h)
        kw["global_delay_factor"] = 2
        print(f"{h} ({kw['host']}) ...")
        try:
            with ConnectHandler(**kw) as conn:
                if kw.get("secret"):
                    conn.enable()
                conn.send_config_from_file(str(cfg), exit_config_mode=True)
        except Exception as e:
            errors.append(f"{h}: {e}")
            print(errors[-1], file=sys.stderr)
            if not args.continue_on_error:
                return 1

    if errors:
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    # # Debug (no args): same as
    # #   uv run python scripts/push.py --inventory data/inventory.containerlab.yaml \
    # #     --topology data/topology.containerlab.yaml
    # # With args: normal CLI, e.g. uv run python scripts/push.py --dry-run
    # _debug = [
    #     "--inventory",
    #     str(_AUTOMATION_DIR / "data" / "inventory.containerlab.yaml"),
    #     "--topology",
    #     str(_AUTOMATION_DIR / "data" / "topology.containerlab.yaml"),
    # ]
    # raise SystemExit(main(_debug))
