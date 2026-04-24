"""
Aerospace Digital Twin — Live Telemetry Dashboard
==================================================
Module: live_graph.py
Version: 2.0
Author:  Shamant N

Overview
--------
This script acts as the **Mission Control Dashboard** for the Aerospace Digital
Twin simulation. It operates as a real-time UDP telemetry receiver and live
Matplotlib visualization system, consuming physiological data broadcast by the
C++ BioGears bridge (bridge.exe) and rendering it as a 4-panel mission display.

The dashboard is designed to mirror the layout and aesthetic of real aerospace
ground-control monitoring systems, displaying cardiovascular and respiratory
metrics across the entire mission timeline from T+0 through long-duration
orbital adaptation.

Data Flow
---------
    bridge.exe (BioGears C++ engine)
        |-- UDP/8080 --> [This Script] --> 4-panel Matplotlib live display
                                       --> Real-time HUD readouts
                                       --> Phase annotation overlays

Panels
------
    1. Heart Rate (BPM)        — Primary cardiac frequency metric
    2. Stroke Volume (mL)      — Volume ejected per beat (derived)
    3. Cardiac Output (L/min)  — Derived from HR × SV / 1000
    4. Blood Oxygen (SpO2 %)   — Arterial oxygen saturation

Usage
-----
    Ensure bridge.exe is running and broadcasting on UDP 8080, then:
        $ python live_graph.py

Scientific Notes
----------------
- Cardiac Output is derived client-side: CO (L/min) = HR (bpm) × SV (mL) / 1000.
  This is algebraically equivalent to the standard clinical Fick-equation derivation
  and matches the thermodilution measurement technique used in ICU settings.
- SpO2 is transmitted as a [0,1] fraction by the C++ bridge and converted to
  percentage on receipt.
- All data is accumulated without a rolling buffer limit, providing a full-history
  view of the entire mission timeline — important for observing the cumulative
  effects of long-term adaptation (Phase 4).
"""

import socket
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec

# =============================================================================
# SECTION 1: UDP SOCKET SETUP
# =============================================================================
# We bind a UDP socket (SOCK_DGRAM) to localhost:8080 to receive telemetry
# packets from the C++ bridge.
#
# SO_REUSEADDR is the critical option here. Without it, only ONE process could
# bind to port 8080 at a time — meaning you would have to choose between the
# Python dashboard OR the Unreal Engine 5 Blueprint listener, not both.
# Setting SO_REUSEADDR allows multiple processes on the same machine to bind
# to the same UDP port simultaneously. When the bridge broadcasts a packet
# to 127.0.0.1:8080, the OS delivers a copy to EVERY bound listener — both
# this Python script and the UE5 receiver — with no additional configuration.
#
# setblocking(False) puts the socket in non-blocking mode: recvfrom() raises
# a BlockingIOError immediately if no packet is waiting, rather than halting
# the animation loop until one arrives. This keeps the Matplotlib event loop
# responsive and prevents dropped animation frames during low-traffic intervals.
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Enable multi-listener sharing
sock.bind(("127.0.0.1", 8080))
sock.setblocking(False)  # Non-blocking so the animation loop never stalls

# =============================================================================
# SECTION 2: DATA BUFFERS
# =============================================================================
# All buffers are unbounded lists — data accumulates for the full mission
# duration. No rolling window is applied because the dashboard is intended
# to display the complete physiological trajectory from pad to long-term orbit,
# making it possible to visually compare Phase 1 baseline values against the
# Phase 4 deconditioning signature on the same chart.
times, hr_data, sv_data, co_data, spo2_data = [], [], [], [], []
time_counter = 0  # Counts received packets (deciseconds at 10 Hz)

# =============================================================================
# SECTION 3: DESIGN SYSTEM — COLOR PALETTE
# =============================================================================
# A high-contrast neon-on-dark palette chosen to maximize readability in dim
# control-room environments and produce a premium "mission control" aesthetic.
plt.style.use('dark_background')  # Set Matplotlib global dark theme

C_BG       = '#0A0A0F'   # Near-black background (figure)
C_PANEL    = '#0E0E16'   # Slightly lighter panel faces
C_GRID     = '#1E1E2E'   # Subtle grid lines
C_BORDER   = '#2A2A3A'   # Panel spine borders
C_HR       = '#FF2A6D'   # Neon pink — Heart Rate
C_SV       = '#05D9E8'   # Cyan — Stroke Volume
C_CO       = '#FFD700'   # Gold — Cardiac Output
C_SPO2     = '#39FF14'   # Neon green — Blood Oxygen
C_STRESS   = '#FF7F00'   # Orange — stress annotations
C_WARN     = '#FF3333'   # Red — danger threshold
C_TEXT     = '#CCCCCC'   # Body text
C_DIM      = '#555566'   # Dimmed labels

# =============================================================================
# SECTION 4: FIGURE LAYOUT
# =============================================================================
# GridSpec divides the figure into a 4-row × 2-column grid.
# Column 0 (width ratio 5): the four time-series chart panels.
# Column 1 (width ratio 1): four HUD stat boxes displaying the current value
# of each metric as a large, bold readout — inspired by ICU bedside monitors.
fig = plt.figure(figsize=(16, 10), facecolor=C_BG)
fig.canvas.manager.set_window_title('Aerospace Digital Twin — Mission Control v2')

gs = GridSpec(4, 2, figure=fig, width_ratios=[5, 1],
              hspace=0.45, wspace=0.08,
              left=0.07, right=0.97, top=0.91, bottom=0.06)

ax_hr   = fig.add_subplot(gs[0, 0])              # Panel 1: Heart Rate
ax_sv   = fig.add_subplot(gs[1, 0], sharex=ax_hr) # Panel 2: Stroke Volume
ax_co   = fig.add_subplot(gs[2, 0], sharex=ax_hr) # Panel 3: Cardiac Output
ax_spo2 = fig.add_subplot(gs[3, 0], sharex=ax_hr) # Panel 4: SpO2

# Four HUD stat boxes — one per row in column 1
hud_axes = [fig.add_subplot(gs[i, 1]) for i in range(4)]

# =============================================================================
# SECTION 5: HEADER & PHASE STATUS BAR
# =============================================================================
fig.text(0.5, 0.955,
         '⬡  AEROSPACE DIGITAL TWIN  ⬡  LIVE PHYSIOLOGICAL TELEMETRY',
         ha='center', va='top', fontsize=13, fontweight='bold',
         color=C_HR, fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#1A0010',
                   edgecolor=C_HR, linewidth=1.2))

# Dynamic phase status bar — updated at each phase transition event
phase_label = fig.text(0.5, 0.925, 'PHASE: PRE-LAUNCH  |  STATUS: NOMINAL',
                       ha='center', va='top', fontsize=9,
                       color=C_DIM, fontfamily='monospace')

# =============================================================================
# SECTION 6: PANEL STYLING HELPER
# =============================================================================
def style_panel(ax, title, ylabel, ycolor):
    """Apply mission-control dark styling to a chart panel.

    Args:
        ax     : Matplotlib Axes object to style.
        title  : Short panel identifier string (displayed top-left, monospace).
        ylabel : Y-axis unit label.
        ycolor : Accent color for the Y-axis label and tick marks.
    """
    ax.set_facecolor(C_PANEL)
    ax.set_ylabel(ylabel, color=ycolor, fontsize=8.5, fontweight='bold', labelpad=6)
    ax.tick_params(axis='both', colors=C_DIM, labelsize=7.5)
    ax.grid(color=C_GRID, linestyle='-', linewidth=0.8, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color(C_BORDER)
        spine.set_linewidth(0.8)
    # Panel title rendered as an overlay text element (not a true axes title)
    # to allow precise positioning relative to the data area.
    ax.text(0.01, 0.93, title, transform=ax.transAxes,
            fontsize=8, color=C_DIM, fontfamily='monospace', va='top')

style_panel(ax_hr,   '[ HEART RATE ]',     'BPM',    C_HR)
style_panel(ax_sv,   '[ STROKE VOLUME ]',  'mL',     C_SV)
style_panel(ax_co,   '[ CARDIAC OUTPUT ]', 'L/min',  C_CO)
style_panel(ax_spo2, '[ BLOOD OXYGEN ]',   'SpO2 %', C_SPO2)

ax_spo2.set_xlabel('Mission Time (deciseconds)', color=C_DIM, fontsize=8)

# =============================================================================
# SECTION 7: SPO2 AXIS — HARD-LOCKED Y RANGE
# =============================================================================
# The SpO2 axis is intentionally hard-locked to 82–102% rather than using
# the same autoscale logic applied to HR, SV, and CO. The reasons are:
#
#   (a) Clinical interpretability: SpO2 is only medically meaningful within
#       a fixed reference frame. Normal saturation (95-100%) and the critical
#       hypoxia threshold (90%) must appear at consistent, predictable positions
#       on the chart so that any observer can instantly recognize a dangerous
#       desaturation event without interpreting axis labels.
#
#   (b) Preventing misleading autoscaling: Autoscaling on SpO2 would expand
#       the axis to fill the panel regardless of the data range. A drop from
#       98% to 93% (clinically significant) might autoscale to fill the full
#       panel height, appearing catastrophic visually. The hard-locked range
#       provides accurate proportional context.
#
#   (c) Below 82% is incompatible with consciousness — any values in that
#       range would indicate a simulation error, not a physiological state.
#       The 82% floor effectively clips simulation artifacts.
ax_spo2.set_ylim(82, 102)

# Danger threshold reference line at 90% SpO2 (clinical hypoxia threshold)
ax_spo2.axhline(y=90, color=C_WARN, linewidth=1, linestyle=':', alpha=0.7)
ax_spo2.text(0.01, 90.5, 'HYPOXIA THRESHOLD',
             transform=ax_spo2.get_yaxis_transform(),
             fontsize=6.5, color=C_WARN, fontfamily='monospace', alpha=0.8)

# Subtle green fill for the nominal SpO2 range (95–100%)
ax_spo2.axhspan(95, 102, alpha=0.06, color=C_SPO2)

# =============================================================================
# SECTION 8: PLOT LINES & GLOW FILLS
# =============================================================================
# Each metric gets a colored line and a translucent fill-under-curve
# to create a "glowing waveform" effect reminiscent of oscilloscope displays.
hr_line,   = ax_hr.plot([],   [], color=C_HR,   linewidth=1.8)
sv_line,   = ax_sv.plot([],   [], color=C_SV,   linewidth=1.8)
co_line,   = ax_co.plot([],   [], color=C_CO,   linewidth=1.8)
spo2_line, = ax_spo2.plot([], [], color=C_SPO2, linewidth=1.8)

# Initial empty fill_between objects (replaced periodically in the update loop)
hr_fill   = ax_hr.fill_between([],   [], alpha=0.12, color=C_HR)
sv_fill   = ax_sv.fill_between([],   [], alpha=0.12, color=C_SV)
co_fill   = ax_co.fill_between([],   [], alpha=0.12, color=C_CO)
spo2_fill = ax_spo2.fill_between([], [], alpha=0.10, color=C_SPO2)

# =============================================================================
# SECTION 9: HUD STAT BOXES
# =============================================================================
def make_hud(ax, label, value_str, color):
    """Construct a digital readout HUD box in the right-side column.

    Each box has a dimmed label line and a large bold current-value readout,
    styled to resemble an ICU bedside monitor or avionics display unit.

    Args:
        ax        : Axes object for this HUD cell.
        label     : Metric name (e.g. 'HEART RATE').
        value_str : Initial placeholder value (e.g. '--').
        color     : Accent color matching the corresponding chart panel.

    Returns:
        Tuple (label_text_obj, value_text_obj) for live updates.
    """
    ax.set_facecolor(C_BG)
    for spine in ax.spines.values():
        spine.set_color(color)
        spine.set_linewidth(1.5)
    ax.set_xticks([]); ax.set_yticks([])
    lbl = ax.text(0.5, 0.70, label, ha='center', va='center',
                  transform=ax.transAxes, fontsize=8,
                  color=C_DIM, fontfamily='monospace')
    val = ax.text(0.5, 0.30, value_str, ha='center', va='center',
                  transform=ax.transAxes, fontsize=22,
                  fontweight='bold', color=color, fontfamily='monospace')
    return lbl, val

_, hr_val = make_hud(hud_axes[0], 'HEART RATE',   '--', C_HR)
_, sv_val = make_hud(hud_axes[1], 'STROKE VOL.',  '--', C_SV)
_, co_val = make_hud(hud_axes[2], 'CARDIAC OUT.', '--', C_CO)
_, o2_val = make_hud(hud_axes[3], 'BLOOD OXYGEN', '--', C_SPO2)

# Unit labels at the bottom of each HUD box
unit_font = dict(fontsize=8, color=C_DIM, fontfamily='monospace',
                 ha='center', va='center', transform=None)
for ax, unit in zip(hud_axes, ['BPM', 'mL', 'L/min', '%']):
    unit_font['transform'] = ax.transAxes
    ax.text(0.5, 0.10, unit, **unit_font)

# =============================================================================
# SECTION 10: FLIGHT PHASE EVENT DEFINITIONS
# =============================================================================
# Phase transitions are defined in deciseconds (10 per second at 10 Hz)
# to align with the time_counter unit, which increments by 1 per received packet.
# Each entry: (trigger_decisecond, chart_label, color_hex, status_bar_text)
PHASE_EVENTS = [
    (300,  'T+30s  IGNITION',   '#FF4444', 'PHASE: ASCENT  |  +GZ STRESS ACTIVE'),
    (900,  'T+90s  MECO',       '#4444FF', 'PHASE: ORBIT   |  ZERO-G'),
    (1200, 'T+120s ADAPTATION', '#AA44FF', 'PHASE: ADAPT.  |  CARDIAC DECONDITIONING'),
]
drawn_phases = set()  # Tracks which phase markers have already been drawn

# =============================================================================
# SECTION 11: ANIMATION UPDATE FUNCTION
# =============================================================================
def update(frame):
    """Called by FuncAnimation every 100ms to update all dashboard elements.

    Workflow per frame:
        1. Attempt to receive one UDP packet from the bridge.
        2. Parse the JSON telemetry payload.
        3. Derive Cardiac Output from Heart Rate and Stroke Volume.
        4. Append data to history buffers.
        5. Draw phase transition markers as they become due.
        6. Update all chart lines, fill-under-curves, and HUD readouts.
        7. Apply the SpO2 danger color logic.

    Args:
        frame : Frame counter provided by FuncAnimation (unused directly).

    Returns:
        Tuple of Artist objects updated this frame (for blit optimization).
    """
    global time_counter, hr_fill, sv_fill, co_fill, spo2_fill

    # -------------------------------------------------------------------------
    # Step 1: Non-blocking UDP receive
    # -------------------------------------------------------------------------
    # recvfrom() returns immediately in non-blocking mode.
    # BlockingIOError is raised (and silently caught) when no packet is waiting —
    # this is the normal idle state, not an error condition.
    # json.JSONDecodeError catches any malformed packets (e.g., during startup).
    try:
        data, _ = sock.recvfrom(1024)
        telemetry = json.loads(data.decode('utf-8'))
    except (BlockingIOError, json.JSONDecodeError):
        # No packet available this frame — return current artists unchanged.
        return (hr_line, sv_line, co_line, spo2_line,
                hr_val, sv_val, co_val, o2_val)

    # -------------------------------------------------------------------------
    # Step 2: Extract and derive metrics
    # -------------------------------------------------------------------------
    hr   = telemetry['HR']    # Heart Rate (BPM), directly from BioGears
    sv   = telemetry['SV']    # Stroke Volume (mL), derived in bridge.exe

    # Cardiac Output derivation: CO (L/min) = HR (bpm) × SV (mL) / 1000
    # This derivation is performed client-side (here) rather than in the bridge
    # to keep the UDP payload minimal (~60 bytes) and allow the dashboard to
    # independently verify internal data consistency. The formula is equivalent
    # to the standard clinical cardiac output measurement relationship.
    co   = (hr * sv) / 1000.0

    # Convert SpO2 from the transmitted [0,1] fraction to percentage display
    spo2 = telemetry['SPO2'] * 100

    # Append to full-history buffers (no rolling window limit)
    times.append(time_counter)
    hr_data.append(hr)
    sv_data.append(sv)
    co_data.append(co)
    spo2_data.append(spo2)
    time_counter += 1

    # -------------------------------------------------------------------------
    # Step 3: Draw flight phase transition markers (once each)
    # -------------------------------------------------------------------------
    # Each PHASE_EVENT fires exactly once when time_counter first reaches the
    # trigger decisecond. A vertical dashed line and a rotated label are drawn
    # on all four panels simultaneously for visual alignment, and the header
    # status bar is updated with the new phase description.
    for t_dec, label, color, phase_text in PHASE_EVENTS:
        if t_dec not in drawn_phases and time_counter >= t_dec:
            for ax in [ax_hr, ax_sv, ax_co, ax_spo2]:
                ax.axvline(x=t_dec, color=color, linewidth=1.2,
                           linestyle='--', alpha=0.7)
                ax.text(t_dec + 4, ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else 0,
                        label, color=color, fontsize=6.5,
                        fontfamily='monospace', alpha=0.85,
                        rotation=90, va='bottom')
            phase_label.set_text(phase_text)
            phase_label.set_color(color)
            drawn_phases.add(t_dec)

    # -------------------------------------------------------------------------
    # Step 4: Update time-series lines
    # -------------------------------------------------------------------------
    hr_line.set_data(times, hr_data)
    sv_line.set_data(times, sv_data)
    co_line.set_data(times, co_data)
    spo2_line.set_data(times, spo2_data)

    # -------------------------------------------------------------------------
    # Step 5: Update fill-under-curve (glow effect)
    # -------------------------------------------------------------------------
    # fill_between() returns a PolyCollection object that cannot be updated
    # in-place — it must be removed and redrawn. Doing this every frame is
    # expensive for large datasets, so it is throttled to every 10th frame
    # (approximately once per second), which is imperceptible to the eye.
    if time_counter % 10 == 0:
        hr_fill.remove();   hr_fill   = ax_hr.fill_between(times, hr_data,   alpha=0.10, color=C_HR)
        sv_fill.remove();   sv_fill   = ax_sv.fill_between(times, sv_data,   alpha=0.10, color=C_SV)
        co_fill.remove();   co_fill   = ax_co.fill_between(times, co_data,   alpha=0.10, color=C_CO)
        spo2_fill.remove(); spo2_fill = ax_spo2.fill_between(times, spo2_data, alpha=0.08, color=C_SPO2)

    # -------------------------------------------------------------------------
    # Step 6: Autoscale HR, SV, CO panels
    # -------------------------------------------------------------------------
    # These three panels use Matplotlib's automatic axis scaling to always
    # display the full data range with appropriate margins — the values change
    # significantly between phases and a fixed range would clip the data.
    # SpO2 is intentionally excluded here (see Section 7 above for rationale).
    for ax in [ax_hr, ax_sv, ax_co]:
        ax.relim()
        ax.autoscale_view()

    # -------------------------------------------------------------------------
    # Step 7: SpO2 hypoxia alert — HUD color flash
    # -------------------------------------------------------------------------
    # If SpO2 drops below the 90% clinical hypoxia threshold, the SpO2 HUD
    # readout switches from neon green to alarm red. This provides an
    # immediate, color-coded alert that does not require the operator to
    # read a numerical value to detect a dangerous desaturation.
    o2_color = C_WARN if spo2 < 90 else C_SPO2
    o2_val.set_color(o2_color)

    # -------------------------------------------------------------------------
    # Step 8: Update HUD digital readouts
    # -------------------------------------------------------------------------
    hr_val.set_text(f'{int(hr)}')      # Whole BPM (sub-integer resolution unnecessary)
    sv_val.set_text(f'{int(sv)}')      # Whole mL
    co_val.set_text(f'{co:.1f}')       # One decimal place (L/min)
    o2_val.set_text(f'{spo2:.1f}')     # One decimal place (clinically relevant)

    return (hr_line, sv_line, co_line, spo2_line,
            hr_val, sv_val, co_val, o2_val)

# =============================================================================
# SECTION 12: ANIMATION ENGINE
# =============================================================================
# FuncAnimation drives the live dashboard by calling update() at the specified
# interval. interval=100ms matches the 10 Hz broadcast rate of the C++ bridge,
# so each animation frame corresponds to exactly one expected telemetry packet.
#
# blit=False is required because we redraw phase marker lines and fill polygons
# (which are not simple Artist objects compatible with Matplotlib's blitting
# optimization). blit=True would skip redrawing these elements.
#
# cache_frame_data=False prevents FuncAnimation from storing every frame in
# memory — essential for a session that may run for hundreds of seconds.
ani = FuncAnimation(fig, update, interval=100, blit=False, cache_frame_data=False)
plt.show()