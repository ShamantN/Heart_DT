# Aerospace Digital Twin: Real-Time Bio-Simulation

![C++](https://img.shields.io/badge/C++-20-blue?logo=cplusplus&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python&logoColor=white)
![Unreal Engine](https://img.shields.io/badge/Unreal%20Engine-5.3-black?logo=unrealengine&logoColor=white)
![BioGears](https://img.shields.io/badge/BioGears-7.x-red)
![Platform](https://img.shields.io/badge/Platform-Windows-informational?logo=windows)
![License](https://img.shields.io/badge/License-Academic%20Use-lightgrey)

> A real-time human physiology simulation of a rocket launch and long-duration spaceflight,
> built by bridging the **BioGears C++ Physiology Engine** with a **Python Mission Control Dashboard**
> and an **Unreal Engine 5** anatomical visualizer — connected live over UDP telemetry.

---

## Abstract

The **Aerospace Digital Twin** is a full-stack bio-simulation system that models the physiological
response of an astronaut across four distinct flight phases: pre-launch 1G baseline, +3Gz rocket
ascent, microgravity arrival, and long-term orbital adaptation.

The core challenge — and the primary engineering contribution of this project — is that BioGears
is a *clinical* physiology engine, not an aerospace one. It has no built-in concept of
gravitational acceleration. This project solves that problem through a set of scientifically
grounded **Physiological Proxies**: real BioGears patient actions (hemorrhage, respiratory
distress, acute stress) whose documented biological effects are medically analogous to the
cardiovascular and respiratory consequences of spaceflight. The result is a physiologically
accurate simulation of an astronaut's heart rate, stroke volume, cardiac output, and blood oxygen
saturation — live, in real time — without requiring custom engine modifications.

Telemetry is broadcast over UDP to a 4-panel Python Matplotlib dashboard and an Unreal Engine 5
scene simultaneously, demonstrating a multi-consumer, real-time bio-data pipeline.

---

## The Scientific Model: Physiological Proxies

Because BioGears does not natively model gravitational acceleration, spaceflight physiology is
induced by composing real, clinically documented patient actions into phase-specific "proxy sets."
This methodology is consistent with how aerospace medicine researchers adapt general-purpose
physiology simulators to mission contexts.

### Flight Phase Breakdown

| Phase | Time Window | Event | Proxies Applied | Physiological Rationale |
|-------|-------------|-------|-----------------|------------------------|
| **1 — 1G Baseline** | T+0s to T+30s | Pre-Launch Pad Hold | *(none — stable homeostasis)* | Establishes the astronaut's resting cardiovascular baseline from the BioGears StandardMale state. All systems in homeostatic equilibrium. |
| **2 — +3Gz Ascent** | T+30s to T+90s | Rocket Ignition → MECO | `SEHemorrhage` (LeftLeg, 300 mL/min) + `SEAcuteRespiratoryDistress` (severity 0.7) + `SEAcuteStress` (severity 1.0) | Under +3Gz, hydrostatic pressure drains blood into the lower extremities (**venous pooling**), reducing cardiac preload and stroke volume. The weighted chest wall impairs tidal volume and creates a **V/Q mismatch**, dropping SpO2. Simultaneously, rocket ignition triggers a peak **catecholamine (adrenaline) dump** — driving tachycardia, vasoconstriction, and elevated contractility. |
| **3 — 0G Arrival** | T+90s to T+120s | Main Engine Cutoff (MECO) | All Phase 2 proxies zeroed | At MECO, gravitational acceleration ceases. The hydrostatic gradient collapses, and ~1–2 L of previously pooled lower-body fluid immediately redistributes toward the thorax and head: the **Cephalad Fluid Shift**. This elevates central venous pressure, increases cardiac preload, and triggers atrial stretch receptors — producing early space diuresis and the characteristic "puffy face / bird legs" appearance of astronauts in microgravity. |
| **4 — Long-Term Adaptation** | T+120s+ | Orbital Deconditioning | `SEHemorrhage` (VenaCava, 50 mL/min) + `SEAcuteStress` (severity 0.2) | Two chronic processes dominate: **(a) Space Diuresis** — atrial stretch receptors, misreading the fluid shift as volume overload, trigger Atrial Natriuretic Peptide (ANP) release, causing the kidneys to contract plasma volume by 10–15% over 24–48 hours. **(b) Cardiac Deconditioning** — without pumping against gravity, the left ventricle undergoes structural atrophy, reducing maximum cardiac output and orthostatic tolerance. Returning astronauts frequently experience orthostatic hypotension (fainting upon standing) from this maladaptation. |

---

## System Architecture

The project is a two-tier, broadcast UDP pipeline:

```
┌─────────────────────────────────────────────────┐
│             C++ BIOGEARS BRIDGE                 │
│  (BioGears_UE5_Bridge/main.cpp → bridge.exe)   │
│                                                 │
│  • Loads StandardMale@0s physiological state    │
│  • Advances simulation at 10 Hz (0.1s steps)   │
│  • Applies phase proxy actions on schedule      │
│  • Extracts HR, SV, SpO2 every frame            │
│  • Writes Flight_Telemetry.csv (full log)       │
│  • Broadcasts JSON via UDP → 127.0.0.1:8080     │
└──────────────────────┬──────────────────────────┘
                       │  UDP/8080  {"HR":..,"SV":..,"SPO2":..}
          ┌────────────┴────────────┐
          │                        │
          ▼                        ▼
┌──────────────────┐    ┌─────────────────────────┐
│  live_graph.py   │    │   Unreal Engine 5       │
│  Python Mission  │    │   Heart_Digital_Twin    │
│  Control         │    │   (heart_only.umap)     │
│  Dashboard       │    │   Blueprint UDP Receiver│
│                  │    │   + Procedural Animation│
│  4-panel live    │    │                         │
│  Matplotlib      │    │   3D anatomical heart   │
│  telemetry       │    │   driven by live HR/SpO2│
└──────────────────┘    └─────────────────────────┘
```

**Why UDP?** UDP's connectionless, fire-and-forget semantics allow a single `sendto()` call to
reach all listeners simultaneously — no separate socket or connection per consumer. At 10 Hz,
occasional packet loss causes a cosmetic one-frame gap, not a system failure.

---

## Prerequisites

### Required Software

| Dependency | Version | Notes |
|------------|---------|-------|
| **CMake** | ≥ 3.16 | Build system generator |
| **Visual Studio** | 2019 or 2022 | MSVC C++20 toolchain (Community edition sufficient) |
| **Python** | ≥ 3.10 | For the live dashboard |
| **matplotlib** | ≥ 3.7 | `pip install matplotlib` |
| **Unreal Engine** | 5.3 | Optional — only required for 3D visualization |

### Critical: BioGears Windows SDK

The C++ bridge requires the **pre-compiled BioGears 7.x Windows SDK** installed to:

```
C:\Program Files\BioGears\
```

The build system expects the following layout:

```
C:\Program Files\BioGears\
├── bin\
│   └── states\
│       └── StandardMale@0s.xml    ← Patient state file (REQUIRED at runtime)
└── lib\
    ├── biogears.lib
    ├── biogears_cdm.lib
    ├── biogears_io.lib
    └── libbiogears_common_st.lib
```

Download the BioGears SDK from the
[BioGears GitHub Releases](https://github.com/BioGearsEngine/core/releases).

Additionally, the build requires:
- **Eigen 3.4.0** — auto-downloaded by CMake via FetchContent (internet required on first build)
- **Apache Xerces-C 3.2.4** — XML parser required by BioGears CDM (paths configured in `CMakeLists.txt`)
- **XSD 4.0.0** — Codesynthesis XSD for CDM schema bindings (paths configured in `CMakeLists.txt`)

---

## Build & Run Instructions

### Step 1 — Configure and Build the C++ Bridge

Open a **Developer Command Prompt for VS** (or any terminal with MSVC in `PATH`):

```powershell
# Navigate to the bridge source directory
cd BioGears_UE5_Bridge

# Create and enter the build directory
mkdir build
cd build

# Configure the project with CMake (Release mode)
cmake .. -G "Visual Studio 17 2022" -A x64

# Build the bridge executable
cmake --build . --config Release
```

The output executable will be located at:
```
BioGears_UE5_Bridge/build/Release/bridge.exe
```

> **Note:** The first build will download Eigen (~50 MB) automatically via CMake FetchContent.
> Ensure an internet connection is available.

---

### Step 2 — Start the Python Mission Control Dashboard

In a separate terminal, before or immediately after launching the bridge:

```powershell
# Install dependency if not already present
pip install matplotlib

# Launch the dashboard
python BioGears_UE5_Bridge/live_graph.py
```

The dashboard window will appear and display `--` readouts until the bridge begins broadcasting.

---

### Step 3 — Launch the Simulation

```powershell
# Run the compiled bridge executable
.\BioGears_UE5_Bridge\build\Release\bridge.exe
```

Console output will confirm engine initialization and begin streaming telemetry:

```
Engine Ready. Systems Green for Launch...
T+0s | HR: 72 BPM | SV: 71 mL | SpO2: 98%
T+1s | HR: 72 BPM | SV: 71 mL | SpO2: 98%
...
[FLIGHT T+30s] IGNITION: +Gz stress beginning...
T+31s | HR: 89 BPM | SV: 58 mL | SpO2: 93%
```

Phase transition markers will appear on the Python dashboard automatically.

---

### Step 4 — (Optional) Open Unreal Engine Visualizer

1. Open `Heart_Digital_Twin/Heart_Digital_Twin.uproject` in Unreal Engine 5.3+
2. Load the `heart_only` level from the Content Browser
3. Press **Play** — the UE5 Blueprint will begin receiving telemetry from the same UDP/8080 stream

---

### Post-Mission Analysis

After the simulation runs, `Flight_Telemetry.csv` is generated in the same directory as
`bridge.exe`. It contains the full mission record:

```csv
Time(s),HeartRate(BPM),StrokeVolume(mL),SpO2(%),MissionPhase
0.1,72.3,71.2,98.1,1_Pad_1G
...
30.1,88.7,57.4,93.2,2_Ascent_3G
...
```

This file can be analyzed with pandas, Excel, or MATLAB to generate publication-quality plots
of the full physiological trajectory.

---

## Repository Structure

```
Aerospace_Digital_Twin/
│
├── BioGears_UE5_Bridge/          # C++ simulation engine + Python dashboard
│   ├── main.cpp                  # BioGears bridge — core simulation logic
│   ├── live_graph.py             # Python Mission Control Dashboard (4-panel live)
│   ├── CMakeLists.txt            # CMake build configuration
│   ├── biogears_include/         # BioGears SDK header files (copied locally)
│   └── build/                    # CMake build output directory (gitignored)
│
├── Heart_Digital_Twin/           # Unreal Engine 5 project
│   ├── Heart_Digital_Twin.uproject
│   └── Content/
│       └── heart_only.umap       # Primary level — 3D heart anatomy + UDP receiver
│
├── .gitattributes                # Git LFS tracking rules for .uasset / .umap
├── .gitignore                    # Excludes build artifacts, BioGears logs, CSV output
└── README.md                     # This file
```

---

## Academic Disclaimer

> **This project is an educational simulation and is not certified for, nor intended for use in,
> actual medical diagnosis, patient care, aerospace flight hardware, or mission-critical systems.**

The physiological proxy values used in this simulation (hemorrhage rates, respiratory distress
severity, stress levels) are calibrated to produce *physiologically plausible* trends consistent
with published aerospace medicine literature. They are approximations chosen for simulation
fidelity within the BioGears engine — not validated clinical parameters derived from controlled
human trials or flight data.

BioGears itself is an open-source research tool developed by Applied Research Associates (ARA)
and is similarly not FDA-approved for clinical decision support. All simulation outputs should
be interpreted as illustrative of aerospace physiological principles, not as predictive models
of individual human response.

This project was developed as part of an academic coursework submission demonstrating the
integration of C++ physiology simulation, real-time data pipelines, and interactive 3D
visualization in an aerospace engineering context.

---

## Acknowledgements

- [BioGears Engine](https://github.com/BioGearsEngine/core) — Applied Research Associates (ARA)
- [Eigen](https://eigen.tuxfamily.org/) — Linear algebra library (BioGears dependency)
- [Apache Xerces-C](https://xerces.apache.org/xerces-c/) — XML parsing (BioGears CDM)
- [Matplotlib](https://matplotlib.org/) — Python scientific visualization
- [Unreal Engine 5](https://www.unrealengine.com/) — Epic Games

---

*Author: Shamant N | Aerospace Digital Twin Project*
