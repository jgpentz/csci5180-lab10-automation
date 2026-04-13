# Lab10 automation

Render Cisco IOL-style configs from YAML, push them with Netmiko, and optionally run checks against a **GNS3-style** lab or a **Containerlab** twin.

All commands below assume your current directory is **`automation/`** and you use [uv](https://docs.astral.sh/uv/) for the project virtualenv.

```bash
uv sync --all-groups
```

## Topology and inventory

| Use case | Topology | Inventory |
|----------|----------|-----------|
| Golden / GNS3 (mgmt on `Ethernet1/0`, fabric `Ethernet0/0`+) | `data/topology.yaml` | `data/inventory.yaml` (copy from `data/inventory.example.yaml`) |
| Containerlab (fabric names match clab `eth1+` → IOS; mgmt block skipped in render) | `data/topology.containerlab.yaml` | `data/inventory.containerlab.yaml` |

Rendered files are written to `artifacts/<hostname>.cfg`.

## Environment variables

| Variable | When |
|----------|------|
| `LAB10_SSH_PASSWORD` | Golden inventory (`inventory.yaml` / example defaults); also **required** by `clab_twin.py` before deploy |
| `LAB10_SSH_PASSWORD_CLAB` | Containerlab inventory (`password_env` in `inventory.containerlab.yaml`) for `push.py` and live tests |
| `LAB10_ENABLE_SECRET` | Optional, if IOS needs `enable` for configuration |

You can set both SSH variables to the same password when using the clab pipeline (e.g. default IOL `admin`).

## Golden configs (GNS3-style)

Explicit paths (same as the script defaults for golden files):

```bash
uv run python scripts/render.py --topology data/topology.yaml
uv run python scripts/push.py --inventory data/inventory.yaml --topology data/topology.yaml
```

Shorter form (defaults in `render.py` / `push.py` point at `topology.yaml` and `inventory.yaml`):

```bash
uv run python scripts/render.py
uv run python scripts/push.py
```

Dry-run push (no SSH):

```bash
uv run python scripts/push.py --dry-run
```

Post-push checks (OSPF + leaf loopback pings):

```bash
uv run python scripts/verify.py --inventory data/inventory.yaml --topology data/topology.yaml
```

## Containerlab

Render and push using the clab overlay topology and inventory:

```bash
uv run python scripts/render.py --topology data/topology.containerlab.yaml
uv run python scripts/push.py \
  --inventory data/inventory.containerlab.yaml \
  --topology data/topology.containerlab.yaml
```

Full disposable pipeline (deploy → wait for SSH → render → push → short convergence wait → live pytest → destroy):

```bash
export LAB10_SSH_PASSWORD=admin
export LAB10_SSH_PASSWORD_CLAB=admin

uv run python scripts/clab_twin.py --ssh-timeout 300
```

Useful flags:

```bash
uv run python scripts/clab_twin.py --keep              # leave lab running
uv run python scripts/clab_twin.py --convergence-wait 45 # seconds after push before tests
uv run python scripts/clab_twin.py --convergence-wait 0  # no wait
```

Live tests only (lab already deployed and configured):

```bash
export LAB10_LIVE_TESTS=1
export LAB10_SSH_PASSWORD_CLAB=admin
export LAB10_INVENTORY=data/inventory.containerlab.yaml
export LAB10_TOPOLOGY=data/topology.containerlab.yaml

uv run pytest tests/test_containerlab.py -v
```

## Tests and lint

```bash
uv run pytest tests/ -v
uv run ruff check .
```

## More detail

See `phases.md` for phase breakdown, data model notes, and troubleshooting.
