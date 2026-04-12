"""Phase 2: inventory, deploy order, IOS parsing, push dry-run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from lab_tools import (  # noqa: E402
    count_full_ospf_neighbors,
    hostnames_in_deploy_order,
    load_inventory,
    load_topology,
    ping_was_successful,
    require_inventory_hosts,
)

EXAMPLE_INV = AUTOMATION_DIR / "data" / "inventory.example.yaml"
TOPOLOGY_PATH = AUTOMATION_DIR / "data" / "topology.yaml"


@pytest.fixture
def topo() -> dict:
    return load_topology(TOPOLOGY_PATH)


def test_example_inventory_yaml_readable() -> None:
    inv = load_inventory(EXAMPLE_INV)
    assert "leaf1" in inv["devices"]


def test_load_inventory_file() -> None:
    inv = load_inventory(EXAMPLE_INV)
    assert inv["devices"]["spine1"]["host"] == "192.168.99.11"


def test_deploy_order(topo: dict) -> None:
    order = hostnames_in_deploy_order(topo)
    assert order[:2] == ["spine1", "spine2"]
    assert order[-2:] == ["gw1", "gw2"]


def test_deploy_subset(topo: dict) -> None:
    order = hostnames_in_deploy_order(topo, only=frozenset({"leaf1", "spine2"}))
    assert order == ["spine2", "leaf1"]


def test_deploy_unknown_host(topo: dict) -> None:
    with pytest.raises(ValueError, match="Unknown"):
        hostnames_in_deploy_order(topo, only=frozenset({"leaf1", "ghost"}))


def test_inventory_covers_hosts(topo: dict) -> None:
    inv = load_inventory(EXAMPLE_INV)
    require_inventory_hosts(inv, hostnames_in_deploy_order(topo))
    with pytest.raises(ValueError, match="missing"):
        require_inventory_hosts(inv, ["leaf1", "nope"])


def test_push_dry_run_subprocess() -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(AUTOMATION_DIR / "scripts" / "push.py"),
            "--inventory",
            str(EXAMPLE_INV),
            "--dry-run",
        ],
        cwd=str(AUTOMATION_DIR),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "spine1:" in r.stdout


SAMPLE_NEI = """
10.255.12.1       0   FULL/  -        00:00:37    10.0.12.0       Ethernet0/1
10.255.11.1       0   FULL/DR         00:00:38    10.0.11.0       Ethernet0/0
"""


def test_ospf_full_count() -> None:
    assert count_full_ospf_neighbors(SAMPLE_NEI) == 2


def test_ping_parse() -> None:
    ok = """
Success rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms
"""
    assert ping_was_successful(ok)
    assert not ping_was_successful("Success rate is 0 percent (0/5)")


if __name__ == "__main__":
    pytest.main()
