## Where the code lives

| Piece | Purpose |
|--------|---------|
| `lab_tools.py` | Load YAML (`load_topology` / `load_inventory`), deploy order, Netmiko kwargs, IOS parsing |
| `scripts/render.py` | Build `artifacts/*.cfg` from templates |
| `scripts/push.py` | Copy configs to routers (Netmiko) |
| `scripts/verify.py` | OSPF neighbor + ping checks |
| `tests/` | `test_render.py` (Phase 1), `test_lab.py` (Phase 2 helpers) |

## Phase 1 — usage

From the `automation/` directory (uses [uv](https://docs.astral.sh/uv/) for the virtualenv and lockfile):

```bash
uv sync --all-groups   # once (or after dependency changes); creates .venv
uv run python scripts/render.py
uv run pytest tests/
```

Rendered configs land in `artifacts/<hostname>.cfg` (ignored by git). Use `--dry-run` to print one sample to stdout. All nodes are **IOU L3**: management is a **routed** `Ethernet…` address from `topology.yaml` (no VLANs/SVIs). Match interface names to `show ip interface brief` and your GNS3 links; leaves use `Ethernet1/0` for mgmt by default (see comment in `topology.yaml`).

## Phase 2 — usage

Copy `data/inventory.example.yaml` to `data/inventory.yaml` (gitignored) and set each device `host` to the SSH address you use from your workstation (often the management subnet from `topology.yaml`). Export credentials before push:

```bash
export LAB10_SSH_PASSWORD=...
# optional, only if IOS requires enable for config:
export LAB10_ENABLE_SECRET=...
```

Render, then push in **spine → leaf → gateway** order (enforced by `scripts/push.py`):

```bash
uv run python scripts/render.py
uv run python scripts/push.py --dry-run    # optional: show plan without SSH
uv run python scripts/push.py
```

Verify **FULL** OSPF neighbor counts (from `topology.yaml` interface lists) and sample **leaf1 ↔ leaf2** loopback pings:

```bash
uv run python scripts/verify.py
uv run python scripts/verify.py --skip-ping   # OSPF only
uv run python scripts/push.py --only spine1,spine2
```

**Merge vs replace:** `push.py` uses Netmiko `send_config_from_file` (configuration mode, incremental). That is **merge** behavior; it does **not** replace the entire running config. These snippets are not suitable for `configure replace` unless you build a complete file.

**Common failures:** SSH timeout or auth errors → fix `host`/port/firewall or `LAB10_SSH_PASSWORD`. Missing `artifacts/<name>.cfg` → run `render.py` first. OSPF neighbor count low → physical link or IP mismatch vs `topology.yaml`, or interface still shutdown. Ping fails while OSPF is OK → check loopback addresses, `passive-interface`, or wait for convergence. Enable errors → leave `LAB10_ENABLE_SECRET` unset if you already log in at privilege 15, or set per-device `secret_env: ""` in `inventory.yaml` to skip enable.

---

Phase 1 — Data model and rendering
Description: Describe the network (devices, roles, interfaces, IPs, OSPF, OOB) in YAML and generate per-device Cisco configs from Jinja2—no hardware required.

Goal: Configs are deterministic, repeatable, and reviewable in Git.

Steps:

Model two spines, two leaves, two gateways (Cisco IOL L3 routers as default gateways), fabric links, loopbacks, and management reachability in YAML.
Implement leaf.j2, spine.j2, gateway.j2 driven by that data.
Add a render CLI producing artifacts/<hostname>.cfg.
(Optional) Schema-validate YAML before render.
Spot-check one device in lab for syntax and behavior.

Phase 2 — Deploy and verify on GNS3 (manual automation) — **implemented**
Description: Push rendered configs to the GNS3 IOL topology over OOB and prove routing behavior.

Goal: Netmiko push works for all nodes; verification (OSPF + ping) is scripted or runbooked.

Steps:

Inventory management IPs and access for each node (`data/inventory.example.yaml` → `inventory.yaml`, passwords via env vars).
Implement Netmiko push (`scripts/push.py`); merge semantics and apply order in `lab_tools.hostnames_in_deploy_order`.
Verify OSPF neighbors and ping (`scripts/verify.py`); expected neighbor count from `lab_tools.expected_ospf_neighbors()`.
Document common failure modes and recovery (Phase 2 usage section).

Phase 3 — Containerlab twin and automated tests
Description: Same logical design with IOL in Containerlab, same templates/data (or a small CI inventory overlay), then automated tests after push.

Goal: Disposable lab: deploy → configure → test → destroy, without GNS3.

Steps:

Write *.clab.yml for IOL with links and mgmt access from the runner.
Align interface naming/hostnames between CL and data model.
Automate deploy, render, push.
Pytest: OSPF neighbor counts/states, reachability.
Teardown with containerlab destroy.

Phase 4 — CI on commit
Description: CI runs validation + Containerlab pipeline on each commit/PR; store artifacts.

Goal: Bad changes fail in CI before promotion; green builds produce traceable artifacts.

Steps:

CI job: deps, schema/render tests.
CI job: Containerlab deploy, push, pytest.
Upload rendered configs + checksums as artifacts.
(Optional) PR = phases 1–3 only; main adds promotion.
Phase 5 — Promotion to GNS3 (golden path)
Description: After a green CI build, apply golden configs to the GNS3 “production” topology.

Goal: Clear test vs prod separation and a controlled promotion step.

Steps:

Define trigger (manual, merge to main, or tag).
Push to GNS3 from CI artifacts (or re-render from locked Git SHA—document one approach).
Re-run verification against GNS3 or course sign-off.
(Optional) Drift detection vs show run.
If you want the next iteration of the plan to lock in single-area OSPF vs multi-area or exact leaf↔gateway pattern, say which you prefer and we can fold that into Phase 1’s data model section only.

