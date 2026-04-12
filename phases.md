## Phase 1 — usage

From the `automation/` directory (uses [uv](https://docs.astral.sh/uv/) for the virtualenv and lockfile):

```bash
uv sync --all-groups   # once (or after dependency changes); creates .venv
uv run python scripts/render.py
uv run pytest tests/
```

Rendered configs land in `artifacts/<hostname>.cfg` (ignored by git). Use `--dry-run` to print one sample to stdout. Adjust interface names and `/31` addressing in `data/topology.yaml` to match your GNS3 wiring. Gateways use a routed management interface (no SVI). For SVI management on leaves/spines, place at least one access port in VLAN 99 (not generated in Phase 1).

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
Phase 2 — Deploy and verify on GNS3 (manual automation)
Description: Push rendered configs to the GNS3 IOL topology over OOB and prove routing behavior.

Goal: Netmiko push works for all nodes; verification (OSPF + ping) is scripted or runbooked.

Steps:

Inventory management IPs and access for each node.
Implement Netmiko push (merge vs replace documented); define apply order if needed.
Verify OSPF neighbors, routes, and ping between test addresses.
Document common failure modes and recovery.
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

