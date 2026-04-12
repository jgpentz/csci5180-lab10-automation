#!/usr/bin/env python3
"""Render Cisco IOL configs from data/topology.yaml into artifacts/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_AUTOMATION_DIR = Path(__file__).resolve().parent.parent
if str(_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_DIR))

from lab_tools import ios_ipv4_with_mask, load_topology, router_id  # noqa: E402

ROLE_TEMPLATES = {
    "leaf": "leaf.j2",
    "spine": "spine.j2",
    "gateway": "gateway.j2",
}


def device_context(hostname: str, topo: dict) -> dict:
    dev = topo["devices"][hostname]
    g = topo["global"]
    lb = dev["loopback"]
    mg = dev["management"]
    lb_ip, lb_mask = ios_ipv4_with_mask(lb["cidr"])
    mg_ip, mg_mask = ios_ipv4_with_mask(mg["cidr"])
    management: dict = {"type": mg["type"], "ip": mg_ip, "mask": mg_mask}
    if mg["type"] == "svi":
        management["vlan"] = mg["vlan"]
    else:
        management["interface"] = mg["interface"]

    fabric = []
    for intf in dev.get("interfaces") or []:
        ip, mask = ios_ipv4_with_mask(intf["cidr"])
        on = intf.get("ospf_network", "point-to-point")
        fabric.append(
            {
                "name": intf["name"],
                "ip": ip,
                "mask": mask,
                "ospf_network": on.replace("_", "-"),
            }
        )

    return {
        "hostname": hostname,
        "router_id": router_id(topo, hostname),
        "loopback": {
            "interface": lb.get("interface", "Loopback0"),
            "ip": lb_ip,
            "mask": lb_mask,
        },
        "management": management,
        "fabric_interfaces": fabric,
        "fabric_interface_names": [f["name"] for f in fabric],
        "ospf": {"process_id": g["ospf_process_id"], "area": g["ospf_area"]},
    }


def render_all(
    topology_path: Path,
    templates_dir: Path,
    output_dir: Path,
    *,
    write: bool = True,
) -> dict[str, str]:
    topo = load_topology(topology_path)
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: dict[str, str] = {}
    for hostname, dev in topo["devices"].items():
        template_name = ROLE_TEMPLATES[dev["role"]]
        template = env.get_template(template_name)
        text = template.render(**device_context(hostname, topo))
        rendered[hostname] = text
        if write:
            out_file = output_dir / f"{hostname}.cfg"
            out_file.write_text(text, encoding="utf-8")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--topology",
        type=Path,
        default=_AUTOMATION_DIR / "data" / "topology.yaml",
        help="Path to topology YAML",
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=_AUTOMATION_DIR / "templates",
        help="Jinja2 templates directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_AUTOMATION_DIR / "artifacts",
        help="Directory for rendered .cfg files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render to stdout only (first device only for brevity)",
    )
    args = parser.parse_args()

    if not args.topology.is_file():
        print(f"Topology file not found: {args.topology}", file=sys.stderr)
        return 1

    if args.dry_run:
        topo = load_topology(args.topology)
        hostname = next(iter(topo["devices"]))
        env = Environment(
            loader=FileSystemLoader(str(args.templates)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        dev = topo["devices"][hostname]
        template = env.get_template(ROLE_TEMPLATES[dev["role"]])
        print(template.render(**device_context(hostname, topo)))
        return 0

    written = render_all(args.topology, args.templates, args.output_dir, write=True)
    print(f"Wrote {len(written)} configs to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
