"""Phase 1: topology validates and renders for every device."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from topology_schema import Topology

TOPOLOGY = AUTOMATION_DIR / "data" / "topology.yaml"
TEMPLATES = AUTOMATION_DIR / "templates"


def test_topology_yaml_validates() -> None:
    import yaml

    raw = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8"))
    topo = Topology.model_validate(raw)
    assert len(topo.devices) == 6
    roles = {d.role for d in topo.devices.values()}
    assert roles == {"leaf", "spine", "gateway"}


def test_render_all_produces_non_empty_configs() -> None:
    pytest.importorskip("jinja2")

    import sys

    if str(AUTOMATION_DIR) not in sys.path:
        sys.path.insert(0, str(AUTOMATION_DIR))

    from scripts.render import render_all

    out_dir = AUTOMATION_DIR / "artifacts" / "_test_out"
    out = render_all(TOPOLOGY, TEMPLATES, out_dir, write=False)
    assert len(out) == 6
    for hostname, cfg in out.items():
        assert hostname in cfg  # hostname line contains name
        assert "router ospf" in cfg
        assert "ip ospf" in cfg
