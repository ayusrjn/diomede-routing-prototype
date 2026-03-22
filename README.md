# Diomede — Dynamic DICOM Router

A prototype implementation of dynamic DICOM endpoint routing for the [Diomede GSoC project](https://github.com/KathiraveluLab/Diomede).

Instead of sending every image to a fixed static PACS node, this router checks which destination is healthiest at send-time and routes accordingly.

---

## Architecture

```
┌─────────────┐        ┌──────────────────────────────────────┐
│  .dcm file  │──────▶ │           DynamicRouter               │
└─────────────┘        │                                      │
                       │  1. Read DICOM metadata              │
                       │  2. HealthMonitor polls all nodes     │
                       │     (C-ECHO latency + REST queue)    │
                       │  3. RoutingStrategy picks best node  │
                       │  4. C-STORE sender forwards file     │
                       └──────┬───────────┬───────────┬───────┘
                              │           │           │
                        ┌─────▼──┐  ┌────▼───┐  ┌───▼────┐
                        │ Node1  │  │ Node2  │  │ Node3  │
                        │Orthanc │  │Orthanc │  │Orthanc │
                        │:4242   │  │:4243   │  │:4244   │
                        └────────┘  └────────┘  └────────┘
```

## Project Structure

```
diomede/
├── diomede/
│   ├── endpoints.py   # DicomEndpoint dataclass + node registry
│   ├── health.py      # C-ECHO + REST health monitor
│   ├── routing.py     # Pluggable routing strategies
│   ├── sender.py      # C-STORE sender with retry
│   └── router.py      # DynamicRouter — main entry point
├── tests/
│   └── test_routing.py
├── docker-compose.yml  # 3 Orthanc nodes
├── cli.py              # Command-line interface
└── generate_samples.py # Generate test DICOM files
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install pynetdicom pydicom requests pytest
```

### 2. Start Orthanc nodes

```bash
docker compose up -d
```

This starts 3 Orthanc PACS nodes:

| Node  | AE Title | DICOM Port | REST API              |
|-------|----------|------------|-----------------------|
| Node1 | NODE1    | 4242       | http://localhost:8042 |
| Node2 | NODE2    | 4243       | http://localhost:8043 |
| Node3 | NODE3    | 4244       | http://localhost:8044 |

### 3. Generate sample DICOM files

```bash
python generate_samples.py
```

---

## Usage

### Check node health

```bash
python cli.py --status
```

```
── Node Health Check ──────────────────────────────
  Node1     ✓ UP    queue=   0  latency=  12.3ms  AET=NODE1  port=4242
  Node2     ✓ UP    queue=   0  latency=  14.1ms  AET=NODE2  port=4243
  Node3     ✓ UP    queue=   0  latency=  11.8ms  AET=NODE3  port=4244
───────────────────────────────────────────────────
```

### Route a single file

```bash
python cli.py --file sample_dicoms/sample_01_CT.dcm --strategy modality_aware
```

### Route a whole directory

```bash
python cli.py --dir sample_dicoms/ --strategy least_queue
```

---

## Routing Strategies

| Strategy         | How it works                                                               |
|------------------|----------------------------------------------------------------------------|
| `least_queue`    | Routes to the node with the fewest stored instances (lightest load)        |
| `round_robin`    | Cycles through all available nodes equally                                 |
| `modality_aware` | Routes by DICOM modality affinity first (CT→Node1, MR→Node2), then falls back to `least_queue` |

### Modality affinity map (configurable in `routing.py`)

| Modality | Preferred Node |
|----------|----------------|
| CT       | Node1          |
| MR       | Node2          |
| PT (PET) | Node3          |
| CR / DX  | Node1          |

---

## Programmatic API

```python
from pathlib import Path
from diomede import DynamicRouter

router = DynamicRouter(strategy="modality_aware")

# Route a single file
destination = router.route(Path("scan.dcm"))
print(f"Sent to {destination.name}")

# Route a whole directory
results = router.route_directory(Path("./dicoms"))
# returns {"scan1.dcm": "Node2", "scan2.dcm": "Node1", ...}
```

---

## How the health monitor works

For each node, the router:

1. **C-ECHO** — sends a DICOM ping and measures round-trip latency. If the node doesn't respond, it's marked as unreachable and excluded from routing.

2. **REST `/statistics`** — queries Orthanc's REST API to get `CountInstances`. This approximates queue depth — a node with more stored instances is considered more loaded.

The best node is chosen by lowest queue depth, with latency as a tiebreaker.

---

## Running tests

```bash
python -m pytest tests/ -v
```

All tests use mocks and run without live Orthanc nodes.
# diomede-routing-prototype
