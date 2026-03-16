# SM3ChainGuard

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Crypto" src="https://img.shields.io/badge/Hash-SM3-8A2BE2">
  <img alt="Pipeline" src="https://img.shields.io/badge/Pipeline-Stage1%E2%86%922%E2%86%923-00A86B">
  <img alt="Dataset" src="https://img.shields.io/badge/Dataset-Not%20Included-FF6B6B">
  <img alt="License" src="https://img.shields.io/badge/Status-Research%20Prototype-F39C12">
</p>

> A reproducible multimodal tamper-detection workflow based on a temporal SM3 hash chain.

---

## Project Overview

SM3ChainGuard is an end-to-end workflow for multimodal data integrity protection and tamper localization:

- **Stage-1 Synchronization**: align multi-camera timestamps and action annotations.
- **Stage-2 Chain Building**: build a three-layer temporal SM3 hash chain.
- **Stage-3 Verification**: recompute hashes from source data and detect/locate mismatches.
- **Benchmark & Metrics**: run tamper simulations and summarize detection performance.

---

## Repository Structure

```text
SM3ChainGuard/
├─ src/sm3_chain_guard/           # Core package
│  ├─ data/                       # Dataset loader
│  ├─ hashing/                    # SM3 hashing and chain logic
│  ├─ pipeline/                   # Stage-1 / Stage-2 pipeline
│  ├─ verification/               # Stage-3 verifier
│  └─ simulation/                 # Tamper simulation
├─ scripts/                       # Reproducible experiment entry scripts
├─ data/                          # Local artifacts / experiment outputs (dataset not included)
└─ requirements.txt
```

---

## Environment Setup

### 1) Create virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Dataset (Not Uploaded)

This repository **does not include raw dataset files**.  
Please download OpenRoboCare / Robo-Care data from the official page:

- [OpenRoboCare Download](https://emprise.cs.cornell.edu/robo-care/docs/download.html)

After downloading, place the dataset to match this expected layout:

```text
data/raw/robo-care/
├─ RGB/OT10/Task1/Cam1/RGB/*.jpg
├─ RGB/OT10/Task1/Cam2/RGB/*.jpg
├─ RGB/OT10/Task1/Cam3/RGB/*.jpg
├─ Timestamps/OT10/10-1-10_timestamps.json
└─ Action Labeling/OT10/10-1-10_2_rgb_ch.csv
```

> If your downloaded folder names differ, pass custom paths via script arguments.

---

## Reproducible Experiment Steps

Run the following in order from project root:

### Step 1 - Stage-1 sync and standardization

```powershell
python scripts/run_stage1_sync.py
```

Outputs:
- `data/interim/task1_standardized_frames_b64.json`
- `data/interim/task1_standardized_frames_metadata.jsonl`

### Step 2 - Stage-2 temporal SM3 chain build

```powershell
python scripts/run_stage2_chain.py
```

Output:
- `data/artifacts/task1_temporal_defense_chain.json`

### Step 3 - Stage-3 chain verification

```powershell
python scripts/run_verify_chain.py
```

Output:
- `data/artifacts/task1_verification_report.json`

### Step 4 - Tamper benchmark

```powershell
python scripts/run_tamper_benchmark.py
```

Outputs:
- `data/experiments/tamper_benchmark/benchmark_summary.json`
- `data/experiments/tamper_benchmark/benchmark_summary.csv`
- `data/experiments/tamper_benchmark/reports/*_report.json`

### Step 5 - Aggregate performance metrics

```powershell
python scripts/summarize_experiment_metrics.py
```

Outputs:
- `data/experiments/tamper_benchmark/performance_metrics.json`
- `data/experiments/tamper_benchmark/per_attack_metrics.csv`
- `data/experiments/tamper_benchmark/performance_metrics.md`

### Step 6 - Generate paper-ready figures

```powershell
python scripts/generate_ieee_figures.py
```

Outputs:
- `docs/figures/fig_attack_detection.png`
- `docs/figures/fig_first_failed_step.png`
- `docs/figures/fig_cascade_impact.png`
- `docs/figures/fig_system_architecture.png`

---

## Common Optional Arguments

All scripts support `--help`, for example:

```powershell
python scripts/run_stage1_sync.py --help
```

Frequently used overrides:

- `--dataset-root`
- `--timestamp-file`
- `--annotation-file`
- `--sample-stride`
- `--target-step-index` (tamper benchmark)

---

## Upload to GitHub (Without Dataset)

### 1) Ensure large/raw data is ignored

Keep dataset and generated local artifacts out of version control (see `.gitignore` in this repo).

### 2) Initialize and commit

```powershell
git init
git add .
git commit -m "Initial commit: SM3ChainGuard pipeline and experiment scripts"
```

### 3) Create remote repository and push

```powershell
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

---

## Notes

- This project is currently configured around Task1-related files and default paths.
- For reproducibility, keep Python and dependency versions aligned with `requirements.txt`.
- For benchmarking consistency, avoid modifying raw dataset files outside controlled tamper simulation.
