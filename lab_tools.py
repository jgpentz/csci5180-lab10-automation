"""YAML loads, deploy order, Netmiko kwargs, IOS output parsing."""

from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Any

import yaml

ROLE_ORDER = {"spine": 0, "leaf": 1, "gateway": 2}


def load_topology(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_inventory(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def ios_ipv4_with_mask(cidr: str) -> tuple[str, str]:
    iface = ipaddress.IPv4Interface(cidr)
    return str(iface.ip), str(iface.network.netmask)


def router_id(topo: dict[str, Any], hostname: str) -> str:
    d = topo["devices"][hostname]
    if d.get("router_id"):
        return str(d["router_id"])
    return str(ipaddress.IPv4Interface(d["loopback"]["cidr"]).ip)


def expected_ospf_neighbors(device: dict[str, Any]) -> int:
    return len(device.get("interfaces") or [])


def netmiko_connect_kwargs(inv: dict[str, Any], hostname: str) -> dict[str, Any]:
    conn = inv["devices"][hostname]
    dfl = inv.get("defaults") or {}
    pwd_env = conn.get("password_env") or dfl.get("password_env", "LAB10_SSH_PASSWORD")
    pw = os.environ.get(pwd_env)
    if not pw: 
        raise KeyError(f"Set {pwd_env} for SSH ({hostname!r}).")

    port = conn.get("port")
    if port is None:
        port = dfl.get("port", 22)

    params: dict[str, Any] = {
        "device_type": conn.get("device_type") or dfl.get("device_type", "cisco_ios"),
        "host": conn["host"],
        "username": conn.get("username") or dfl.get("username", "cisco"),
        "password": pw,
        "port": port,
        "conn_timeout": 30,
    }

    secret = None
    if "secret_env" in conn:
        if conn["secret_env"] == "":
            secret = None
        elif conn["secret_env"]:
            secret = os.environ.get(conn["secret_env"])
    else:
        env_name = dfl.get("secret_env", "LAB10_ENABLE_SECRET")
        if env_name:
            secret = os.environ.get(env_name)
    if secret:
        params["secret"] = secret
    return params


def hostnames_in_deploy_order(
    topology: dict[str, Any],
    only: frozenset[str] | None = None,
) -> list[str]:
    devices = topology["devices"]
    names = list(devices.keys())
    if only is not None:
        names = [n for n in names if n in only]
        unknown = only - set(names)
        if unknown:
            raise ValueError(f"Unknown hostnames: {sorted(unknown)}")
    return sorted(
        names,
        key=lambda h: (ROLE_ORDER[devices[h]["role"]], h),
    )


def require_inventory_hosts(inventory: dict[str, Any], hostnames: list[str]) -> None:
    devs = inventory["devices"]
    missing = [h for h in hostnames if h not in devs]
    if missing:
        raise ValueError(f"Inventory missing: {missing}")


def count_full_ospf_neighbors(show_output: str) -> int:
    return sum(1 for line in show_output.splitlines() if "FULL/" in line.upper())


def ping_was_successful(output: str) -> bool:
    m = re.search(r"Success rate is (\d+) percent", output, re.IGNORECASE)
    return bool(m and m.group(1) == "100")
