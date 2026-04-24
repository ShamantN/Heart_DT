import socket
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D

# ============================================================
#   AEROSPACE DIGITAL TWIN — LIVE TELEMETRY DASHBOARD v2
#   4-Panel Mission Control Display with Phase Annotations
# ============================================================

plt.style.use('dark_background')

# --- UDP Socket Setup ---
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", 8080))
sock.setblocking(False)

# 2. Setup Data Buffers (no size limit — accumulate full history)
times, hr_data, sv_data, co_data, spo2_data = [], [], [], [], []
time_counter = 0

# --- Flight Phase Event Log (time_counter value, label, color) ---
phase_events = []  # filled dynamically at runtime

# --- Colors ---
C_BG       = '#0A0A0F'
C_PANEL    = '#0E0E16'
C_GRID     = '#1E1E2E'
C_BORDER   = '#2A2A3A'
C_HR       = '#FF2A6D'   # Neon pink
C_SV       = '#05D9E8'   # Cyan
C_CO       = '#FFD700'   # Gold
C_SPO2     = '#39FF14'   # Neon green
C_STRESS   = '#FF7F00'   # Orange
C_WARN     = '#FF3333'   # Red
C_TEXT     = '#CCCCCC'
C_DIM      = '#555566'

# ============================================================
#   LAYOUT: Figure + 4 Panels + right-side HUD column
# ============================================================
fig = plt.figure(figsize=(16, 10), facecolor=C_BG)
fig.canvas.manager.set_window_title('Aerospace Digital Twin — Mission Control v2')

# GridSpec: 4 rows of charts, 1 narrow column for HUD stats
from matplotlib.gridspec import GridSpec
gs = GridSpec(4, 2, figure=fig, width_ratios=[5, 1],
              hspace=0.45, wspace=0.08,
              left=0.07, right=0.97, top=0.91, bottom=0.06)

ax_hr    = fig.add_subplot(gs[0, 0])  # Heart Rate
ax_sv    = fig.add_subplot(gs[1, 0], sharex=ax_hr)  # Stroke Volume
ax_co    = fig.add_subplot(gs[2, 0], sharex=ax_hr)  # Cardiac Output
ax_spo2  = fig.add_subplot(gs[3, 0], sharex=ax_hr)  # SpO2

hud_axes = [fig.add_subplot(gs[i, 1]) for i in range(4)]  # 4 HUD boxes

# --- Header Title ---
fig.text(0.5, 0.955, '⬡  AEROSPACE DIGITAL TWIN  ⬡  LIVE PHYSIOLOGICAL TELEMETRY',
         ha='center', va='top', fontsize=13, fontweight='bold',
         color=C_HR, fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#1A0010', edgecolor=C_HR, linewidth=1.2))

phase_label = fig.text(0.5, 0.925, 'PHASE: PRE-LAUNCH  |  STATUS: NOMINAL',
                       ha='center', va='top', fontsize=9,
                       color=C_DIM, fontfamily='monospace')

# ============================================================
#   PANEL STYLING HELPER
# ============================================================
def style_panel(ax, title, ylabel, ycolor):
    ax.set_facecolor(C_PANEL)
    ax.set_ylabel(ylabel, color=ycolor, fontsize=8.5, fontweight='bold', labelpad=6)
    ax.tick_params(axis='both', colors=C_DIM, labelsize=7.5)
    ax.grid(color=C_GRID, linestyle='-', linewidth=0.8, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color(C_BORDER)
        spine.set_linewidth(0.8)
    ax.text(0.01, 0.93, title, transform=ax.transAxes,
            fontsize=8, color=C_DIM, fontfamily='monospace', va='top')

style_panel(ax_hr,   '[ HEART RATE ]',     'BPM',    C_HR)
style_panel(ax_sv,   '[ STROKE VOLUME ]',  'mL',     C_SV)
style_panel(ax_co,   '[ CARDIAC OUTPUT ]', 'L/min',  C_CO)
style_panel(ax_spo2, '[ BLOOD OXYGEN ]',   'SpO2 %', C_SPO2)

ax_spo2.set_xlabel('Mission Time (deciseconds)', color=C_DIM, fontsize=8)
ax_spo2.set_ylim(82, 102)

# Danger threshold line on SpO2
ax_spo2.axhline(y=90, color=C_WARN, linewidth=1, linestyle=':', alpha=0.7)
ax_spo2.text(0.01, 90.5, 'HYPOXIA THRESHOLD', transform=ax_spo2.get_yaxis_transform(),
             fontsize=6.5, color=C_WARN, fontfamily='monospace', alpha=0.8)

# Nominal range fill on SpO2 (95–100% = green zone)
ax_spo2.axhspan(95, 102, alpha=0.06, color=C_SPO2)

# ============================================================
#   PLOT LINES
# ============================================================
hr_line,   = ax_hr.plot([], [],   color=C_HR,     linewidth=1.8)
sv_line,   = ax_sv.plot([], [],   color=C_SV,     linewidth=1.8)
co_line,   = ax_co.plot([], [],   color=C_CO,     linewidth=1.8)
spo2_line, = ax_spo2.plot([], [], color=C_SPO2,   linewidth=1.8)

# Fill-under (glowing effect)
hr_fill   = ax_hr.fill_between([],   [], alpha=0.12, color=C_HR)
sv_fill   = ax_sv.fill_between([],   [], alpha=0.12, color=C_SV)
co_fill   = ax_co.fill_between([],   [], alpha=0.12, color=C_CO)
spo2_fill = ax_spo2.fill_between([], [], alpha=0.10, color=C_SPO2)

# ============================================================
#   HUD STAT BOXES (right column — 1 per panel)
# ============================================================
def make_hud(ax, label, value_str, color):
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

_, hr_val  = make_hud(hud_axes[0], 'HEART RATE',     '--',  C_HR)
_, sv_val  = make_hud(hud_axes[1], 'STROKE VOL.',    '--',  C_SV)
_, co_val  = make_hud(hud_axes[2], 'CARDIAC OUT.',   '--',  C_CO)
_, o2_val  = make_hud(hud_axes[3], 'BLOOD OXYGEN',   '--',  C_SPO2)

unit_font = dict(fontsize=8, color=C_DIM, fontfamily='monospace',
                 ha='center', va='center', transform=None)
for ax, unit in zip(hud_axes, ['BPM', 'mL', 'L/min', '%']):
    unit_font['transform'] = ax.transAxes
    ax.text(0.5, 0.10, unit, **unit_font)

# ============================================================
#   FLIGHT PHASE DEFINITIONS
#   (in deciseconds, matching bridge.exe timing at 10Hz)
# ============================================================
PHASE_EVENTS = [
    (300,  'T+30s  IGNITION',    '#FF4444', 'PHASE: ASCENT  |  +GZ STRESS ACTIVE'),
    (900,  'T+90s  MECO',        '#4444FF', 'PHASE: ORBIT   |  ZERO-G'),
    (1200, 'T+120s ADAPTATION',  '#AA44FF', 'PHASE: ADAPT.  |  CARDIAC DECONDITIONING'),
]
drawn_phases = set()

# ============================================================
#   ANIMATION UPDATE LOOP
# ============================================================
def update(frame):
    global time_counter, hr_fill, sv_fill, co_fill, spo2_fill

    try:
        data, _ = sock.recvfrom(1024)
        telemetry = json.loads(data.decode('utf-8'))
    except (BlockingIOError, json.JSONDecodeError):
        return (hr_line, sv_line, co_line, spo2_line,
                hr_val, sv_val, co_val, o2_val)

    hr   = telemetry['HR']
    sv   = telemetry['SV']
    co   = (hr * sv) / 1000.0
    spo2 = telemetry['SPO2'] * 100

    times.append(time_counter)
    hr_data.append(hr)
    sv_data.append(sv)
    co_data.append(co)
    spo2_data.append(spo2)
    time_counter += 1


    # --- Draw flight phase markers (once each) ---
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

    # --- Update lines ---
    hr_line.set_data(times, hr_data)
    sv_line.set_data(times, sv_data)
    co_line.set_data(times, co_data)
    spo2_line.set_data(times, spo2_data)

    # --- Update fill-under-curve (only redraw periodically to keep performance) ---
    if time_counter % 10 == 0:
        hr_fill.remove();   hr_fill   = ax_hr.fill_between(times,   hr_data,   alpha=0.10, color=C_HR)
        sv_fill.remove();   sv_fill   = ax_sv.fill_between(times,   sv_data,   alpha=0.10, color=C_SV)
        co_fill.remove();   co_fill   = ax_co.fill_between(times,   co_data,   alpha=0.10, color=C_CO)
        spo2_fill.remove(); spo2_fill = ax_spo2.fill_between(times, spo2_data, alpha=0.08, color=C_SPO2)

    # --- Autoscale active panels ---
    for ax in [ax_hr, ax_sv, ax_co]:
        ax.relim(); ax.autoscale_view()

    # --- SpO2 danger: flash red HUD if below 90% ---
    o2_color = C_WARN if spo2 < 90 else C_SPO2
    o2_val.set_color(o2_color)

    # --- Update HUD readouts ---
    hr_val.set_text(f'{int(hr)}')
    sv_val.set_text(f'{int(sv)}')
    co_val.set_text(f'{co:.1f}')
    o2_val.set_text(f'{spo2:.1f}')

    return (hr_line, sv_line, co_line, spo2_line,
            hr_val, sv_val, co_val, o2_val)

# ============================================================
#   RUN
# ============================================================
ani = FuncAnimation(fig, update, interval=100, blit=False, cache_frame_data=False)
plt.show()