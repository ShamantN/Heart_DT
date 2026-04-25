# Aerospace Digital Twin: Real-Time Bio-Simulation

![C++](https://img.shields.io/badge/C++-20-blue?logo=cplusplus&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python&logoColor=white)
![Unreal Engine](https://img.shields.io/badge/Unreal%20Engine-5.3-black?logo=unrealengine&logoColor=white)
![COMSOL](https://img.shields.io/badge/COMSOL-6.3-orange)
![BioGears](https://img.shields.io/badge/BioGears-7.x-red)
![Platform](https://img.shields.io/badge/Platform-Windows-informational?logo=windows)
![License](https://img.shields.io/badge/License-Academic%20Use-lightgrey)

> A real-time human physiology simulation of a rocket launch and long-duration spaceflight,
> built by bridging the **BioGears C++ Physiology Engine** with a **Python Mission Control Dashboard**,
> an **Unreal Engine 5** anatomical visualizer, and a **COMSOL Multiphysics 6.3** reduced-order
> structural heart twin.

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

In parallel, a **COMSOL Multiphysics 6.3** structural twin is being developed as an offline/
reduced-order mechanics layer. This module converts chamber-level physiology into wall motion,
strain, and stress fields for the heart geometry, creating exportable morph targets and scalar
fields that can be reused in Unreal Engine 5 for higher-fidelity visualization.

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
| **COMSOL Multiphysics** | 6.3 | Optional — used for the structural heart twin |
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

## COMSOL Multiphysics 6.3 Structural Twin (Current Work)

Alongside the live BioGears → Python → UE5 telemetry path, a reduced-order **COMSOL 6.3** heart
mechanics model is being assembled to translate physiologic state variables into geometric
deformation, wall stress, and exportable morph targets.

### Objective

The COMSOL model is not intended to replace BioGears. Instead, it acts as a **mechanics translator**
between physiology and visualization:

- **BioGears / assumed physiology** provides scalar mission-state inputs such as heart rate (HR),
  stroke volume (SV), oxygen saturation (SpO2), preload loss, and scenario phase.
- **COMSOL** converts those scenario inputs into chamber-wall motion, displacement magnitude, and
  wall stress/strain fields on the heart geometry.
- **Unreal Engine 5** consumes exported deformed meshes and scalar data for animation, material
  effects, and gamified visualization.

### Current Geometry Pipeline Completed

The current COMSOL build uses the Zenodo whole-heart surface dataset and the following chamber
surfaces:

- `epicard`
- `cavityLV`
- `cavityRV`
- `cavityLA`
- `cavityRA`

Current implementation status:

1. The heart surfaces were imported into COMSOL and, for robustness during CAD operations,
   converted into **STEP-based solids** for the working model.
2. A **Boolean Difference** was used to subtract the four chamber cavities from the epicardial
   shell.
3. **Form Union** was then used to finalize the geometry.
4. The finalized structural model contains:
   - **1 myocardium domain**
   - **4 finite voids** corresponding to the LV, RV, LA, and RA cavities

This is the key milestone that turns the original surface dataset into a usable structural shell.

### Boundary Operators and Variables Added

Four **Integration** nonlocal couplings were created under **Component → Definitions**:

- `int_LV`
- `int_RV`
- `int_LA`
- `int_RA`

These are used to compute chamber-surface areas through expressions of the form:

```text
A_LV = int_LV(1)
A_RV = int_RV(1)
A_LA = int_LA(1)
A_RA = int_RA(1)
```

The model variables now include:

```text
u_LV = -(dVpre_LV + phase*SV)/A_LV
u_RV = -(dVpre_RV + phase*SV)/A_RV
u_LA = -(0.2*dVpre_LV + phase*dVat)/A_LA
u_RA = -(0.2*dVpre_RV + phase*dVat)/A_RA
BeatHz   = HR/60[1/s]
ContrIdx = SV/70[ml]
HypoxIdx = max(0,(98-SpO2)/10)
```

These variables provide the first reduced-order mapping from mission physiology to chamber-wall
displacement.

### Structural Stabilization Method Used

The initial plan assumed dedicated support surfaces such as `outerTrunks` and `outerPeri`.
Because the current working model was built first from only the epicardium and chamber cavities,
the support strategy was changed to a **manual 3–2–1 anti-rigid-body method**.

The active stabilization scheme is:

- **P1** on the outer epicardium above the LA region:
  - `u = 0, v = 0, w = 0`
- **P2** on the outer epicardium near the RA side:
  - two constrained directions only
- **P3** on the outer epicardium above-left of the LV side:
  - one constrained direction only

In COMSOL this is implemented with **point-level Prescribed Displacement** nodes, not boundary
fixes, so that rigid-body motion is suppressed without freezing a large portion of the heart wall.

### Chamber-Wall Motion Strategy

The chamber motion itself is applied with **boundary-level Prescribed Displacement** nodes on:

- LV cavity wall
- RV cavity wall
- LA cavity wall
- RA cavity wall

A **Boundary System** / local boundary frame is used so that displacement is prescribed along the
local wall normal while the tangential directions remain free. This avoids locking the wall in
unphysical Cartesian directions.

### Scenario Logic Implemented

The COMSOL model is organized around two scenario parameters:

- `case`
- `phase`

Current intended values are:

- `case = 0` → Earth baseline
- `case = 1` → adapted microgravity (~48 h)
- `case = 2` → chronic microgravity / deconditioning
- `case = 3` → optional launch visual mode / +3Gz

and

- `phase = 0` → ED-like state
- `phase = 1` → ES-like state

This lets the model generate paired morph states for each mission condition without requiring a
full electrophysiology solve.

### Planned Solve / Output Workflow

The working COMSOL solve path is:

1. Build the tetrahedral mesh on the single myocardium domain
2. Add a **Parametric Sweep** over:
   - `case = 0 1 2`
   - `phase = 0 1`
3. Enable **geometric nonlinearity** if the displacement field becomes large
4. Evaluate:
   - `solid.disp`
   - `solid.mises`
   - global `BeatHz`, `ContrIdx`, `HypoxIdx`
5. Export:
   - nodal CSV field data
   - deformed STL meshes for UE5 morph targets

### UE5-Oriented Export Targets

The COMSOL twin is being set up specifically to feed Unreal Engine with reusable assets:

- **Deformed STL meshes** for:
  - Earth ED-like
  - Earth ES-like
  - microgravity ED-like
  - microgravity ES-like
- **CSV nodal fields** containing:
  - `x, y, z`
  - `u, v, w`
  - `solid.disp`
  - `solid.mises`
- **Global scenario scalars** such as:
  - `BeatHz`
  - `ContrIdx`
  - `HypoxIdx`

These outputs align directly with a UE5 pipeline that blends morph targets, adjusts heartbeat
frequency, drives material color change from oxygenation/hypoxia proxies, and overlays stress-like
visual effects.

### Important Implementation Notes

- The current COMSOL model is a **reduced-order structural twin**, not yet a full cardiac
  electromechanics model.
- `Rigid Motion Suppression` was treated only as a temporary setup aid; the final manual support
  method uses the **3–2–1 point constraint strategy**.
- Large fixed boundary patches are intentionally avoided, because over-constraining the epicardium
  makes the heart motion look artificially stiff.
- The long-term upgrade path is to replace the kinematic wall-motion prescription with:
  - volumetric mesh import
  - fiber orientation
  - active stress/strain laws
  - chamber pressure waveforms
  - tighter coupling to BioGears outputs

### Current Development Status

The project now consists of **two connected layers**:

1. **Live physiology layer (completed and running)**  
   BioGears → Python dashboard → Unreal Engine UDP visualization

2. **Structural mechanics layer (working WIP)**  
   COMSOL geometry shell, cavity operators, reduced-order wall motion logic, and manual 3–2–1
   stabilization for future stress/strain export into UE5

This means the digital twin has already progressed beyond a pure telemetry demo and now includes
the first practical steps toward a mechanics-aware heart visualization pipeline.

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

> **Local development note:** a working `Heart Digital Twin.mph` COMSOL model is also used during
> development for the reduced-order structural twin, but it may remain outside version control due
> to file size and iterative experimentation.

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
