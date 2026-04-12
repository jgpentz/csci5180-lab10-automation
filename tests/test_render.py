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
TEMPLATES = AUTOMATION_DIR / "templates"


def test_topology_yaml_loads() -> None:
    topo = load_topology(TOPOLOGY)
    assert len(topo["devices"]) == 6
    roles = {d["role"] for d in topo["devices"].values()}
    assert roles == {"leaf", "spine", "gateway"}
    assert expected_ospf_neighbors(topo["devices"]["leaf1"]) == 4
    assert expected_ospf_neighbors(topo["devices"]["spine1"]) == 2
    assert expected_ospf_neighbors(topo["devices"]["gw1"]) == 2


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


if __name__ == "__main__":
    pytest.main()
