#!/usr/bin/env python3
"""After push: check OSPF neighbor counts and leaf1↔leaf2 loopback pings."""

from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path

_AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_DIR))

from lab_tools import (  # noqa: E402
    count_full_ospf_neighbors,
    expected_ospf_neighbors,
    hostnames_in_deploy_order,
    load_inventory,
    load_topology,
    netmiko_connect_kwargs,
    ping_was_successful,
    require_inventory_hosts,
)


def leaf_ping_tests(topo: dict) -> list[tuple[str, str, str]]:
    devs = topo["devices"]
    if "leaf1" not in devs or "leaf2" not in devs:
        return []
    a = str(ipaddress.IPv4Interface(devs["leaf1"]["loopback"]["cidr"]).ip)
    b = str(ipaddress.IPv4Interface(devs["leaf2"]["loopback"]["cidr"]).ip)
    return [("leaf1", b, a), ("leaf2", a, b)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    data = _AUTOMATION_DIR / "data"
    ap.add_argument("--inventory", type=Path, default=data / "inventory.yaml")
    ap.add_argument("--topology", type=Path, default=data / "topology.yaml")
    ap.add_argument("--only", default="", help="Comma-separated subset for OSPF checks")
    ap.add_argument("--skip-ping", action="store_true")
    args = ap.parse_args()

    if not args.inventory.is_file():
        print(f"Missing {args.inventory}", file=sys.stderr)
        return 1
    try:
        from netmiko import ConnectHandler
    except ImportError:
        print("Run: uv sync", file=sys.stderr)
        return 1

    inv = load_inventory(args.inventory)
    topo = load_topology(args.topology)
    only = frozenset(x.strip() for x in args.only.split(",") if x.strip()) or None
    hosts = hostnames_in_deploy_order(topo, only=only)
    require_inventory_hosts(inv, hosts)

    ospf_bad: list[str] = []
    for h in hosts:
        want = expected_ospf_neighbors(topo["devices"][h])
        kw = netmiko_connect_kwargs(inv, h)
        kw["global_delay_factor"] = 2
        with ConnectHandler(**kw) as conn:
            if kw.get("secret"):
                conn.enable()
            out = conn.send_command("show ip ospf neighbor", read_timeout=120)
        got = count_full_ospf_neighbors(out)
        ok = got == want
        print(f"OSPF {h}: {got}/{want} FULL {'OK' if ok else 'FAIL'}")
        if not ok:
            ospf_bad.append(h)

    ping_bad: list[str] = []
    if not args.skip_ping:
        for src, dst, src_ip in leaf_ping_tests(topo):
            if src not in inv["devices"]:
                continue
            kw = netmiko_connect_kwargs(inv, src)
            kw["global_delay_factor"] = 2
            with ConnectHandler(**kw) as conn:
                if kw.get("secret"):
                    conn.enable()
                cmd = f"ping {dst} repeat 5 source {src_ip}"
                raw = conn.send_command(cmd, read_timeout=90)
            ok = ping_was_successful(raw)
            print(f"Ping {src} -> {dst}: {'OK' if ok else 'FAIL'}")
            if not ok:
                ping_bad.append(f"{src}->{dst}")
                print(raw)

    if ospf_bad or ping_bad:
        print("Failures:", ospf_bad + ping_bad, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
