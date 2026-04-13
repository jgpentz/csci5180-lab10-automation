"""Phase 1: topology loads and renders for every device."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from lab_tools import expected_ospf_neighbors, load_topology

TOPOLOGY = AUTOMATION_DIR / "data" / "topology.yaml"
TOPOLOGY_CLAB = AUTOMATION_DIR / "data" / "topology.containerlab.yaml"
TEMPLATES = AUTOMATION_DIR / "templates"


def test_topology_yaml_loads() -> None:
    topo = load_topology(TOPOLOGY)
    assert len(topo["devices"]) == 6
    roles = {d["role"] for d in topo["devices"].values()}
    assert roles == {"leaf", "spine", "gateway"}
    assert expected_ospf_neighbors(topo["devices"]["leaf1"]) == 4
    assert expected_ospf_neighbors(topo["devices"]["spine1"]) == 2
    assert expected_ospf_neighbors(topo["devices"]["gw1"]) == 2


def test_topology_containerlab_overlay_loads() -> None:
    topo = load_topology(TOPOLOGY_CLAB)
    assert topo["global"]["containerlab_render"]["skip_management_interface"] is True
    assert topo["devices"]["leaf1"]["interfaces"][0]["name"] == "Ethernet0/1"


def test_render_all_produces_non_empty_configs() -> None:
    pytest.importorskip("jinja2")

    if str(AUTOMATION_DIR) not in sys.path:
        sys.path.insert(0, str(AUTOMATION_DIR))

    from scripts.render import render_all

    out_dir = AUTOMATION_DIR / "artifacts" / "_test_out"
    out = render_all(TOPOLOGY, TEMPLATES, out_dir, write=True)
    assert len(out) == 6
    for hostname, cfg in out.items():
        assert hostname in cfg
        assert "router ospf" in cfg
        assert "ip ospf" in cfg
        assert "snmp-server community public RO" in cfg
        assert "snmp-server host 192.168.99.1 public" in cfg


def test_render_containerlab_skips_mgmt_and_offsets_fabric() -> None:
    pytest.importorskip("jinja2")

    if str(AUTOMATION_DIR) not in sys.path:
        sys.path.insert(0, str(AUTOMATION_DIR))

    from scripts.render import render_all

    out_dir = AUTOMATION_DIR / "artifacts" / "_test_out_clab"
    out = render_all(TOPOLOGY_CLAB, TEMPLATES, out_dir, write=True)
    leaf1 = out["leaf1"]
    assert "Out-of-band management" not in leaf1
    assert "interface Ethernet0/0" not in leaf1
    assert "interface Ethernet0/1" in leaf1
    assert "interface Ethernet1/0" in leaf1
    spine1 = out["spine1"]
    assert "interface Ethernet0/0" not in spine1
    assert "interface Ethernet0/1" in spine1


if __name__ == "__main__":
    pytest.main()
