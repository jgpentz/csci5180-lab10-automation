"""Phase 3 live checks against Containerlab twin."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

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
from scripts.verify import leaf_ping_tests  # noqa: E402


def _live_tests_enabled() -> bool:
    return os.environ.get("LAB10_LIVE_TESTS") == "1"


def _must_run_live() -> None:
    if not _live_tests_enabled():
        pytest.skip("Set LAB10_LIVE_TESTS=1 to run Containerlab live tests.")
    if "LAB10_SSH_PASSWORD" not in os.environ:
        pytest.skip("Set LAB10_SSH_PASSWORD for SSH access.")


def _inventory_path() -> Path:
    default = AUTOMATION_DIR / "data" / "inventory.containerlab.yaml"
    return Path(os.environ.get("LAB10_INVENTORY", str(default)))


def _topology_path() -> Path:
    default = AUTOMATION_DIR / "data" / "topology.yaml"
    return Path(os.environ.get("LAB10_TOPOLOGY", str(default)))


@pytest.fixture(scope="module")
def live_data() -> tuple[dict, dict]:
    _must_run_live()
    inv = load_inventory(_inventory_path())
    topo = load_topology(_topology_path())
    require_inventory_hosts(inv, hostnames_in_deploy_order(topo))
    return inv, topo


def test_ospf_neighbors_full(live_data: tuple[dict, dict]) -> None:
    netmiko = pytest.importorskip("netmiko")
    ConnectHandler = netmiko.ConnectHandler
    inv, topo = live_data
    hosts = hostnames_in_deploy_order(topo)

    for hostname in hosts:
        want = expected_ospf_neighbors(topo["devices"][hostname])
        kw = netmiko_connect_kwargs(inv, hostname)
        kw["global_delay_factor"] = 2
        with ConnectHandler(**kw) as conn:
            if kw.get("secret"):
                conn.enable()
            output = conn.send_command("show ip ospf neighbor", read_timeout=120)
        got = count_full_ospf_neighbors(output)
        assert got == want, f"{hostname}: got {got} FULL neighbors, expected {want}"


def test_leaf_reachability(live_data: tuple[dict, dict]) -> None:
    netmiko = pytest.importorskip("netmiko")
    ConnectHandler = netmiko.ConnectHandler
    inv, topo = live_data

    for src, dst, src_ip in leaf_ping_tests(topo):
        if src not in inv["devices"]:
            continue
        kw = netmiko_connect_kwargs(inv, src)
        kw["global_delay_factor"] = 2
        with ConnectHandler(**kw) as conn:
            if kw.get("secret"):
                conn.enable()
            cmd = f"ping {dst} repeat 5 source {src_ip}"
            output = conn.send_command(cmd, read_timeout=90)
        assert ping_was_successful(output), f"{src} cannot reach {dst}"
