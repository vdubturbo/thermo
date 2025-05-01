import os
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
import sys
from datetime import datetime
import time
import threading
import subprocess

# Control flags
running = False
paused = False
show_corrected = True

# CSV logging
csv_file = "temperature_log.csv"

# Thermocouple probes: 2 boards (ID 0 and 1), channels 1-8
all_probes = [(0, ch) for ch in range(1, 9)] + [(1, ch) for ch in range(1, 9)]
probe_widgets = []  # Stores (enable_var, label, dropdown) tuples
temp_history = {}
temp_history_raw = {}
time_history = []

def read_channel(board_id, channel):
    try:
        process = subprocess.Popen(
            ["smtc", str(board_id), "read", str(channel)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        stdout, stderr = process.communicate(timeout=2)
        if process.returncode == 0:
            return stdout.strip()
        else:
            return f"Error: {stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"

def get_cj_temp():
    """
    Read the CPU temperature from the system thermal zone as the cold junction reference.
    Returns temperature in °C as a float, or None on error.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            milli_c = int(f.read().strip())
        return milli_c / 1000.0
    except Exception:
        return None

def read_all(csv_writer, sample_index, active_probes, ambient_temp, cj_label):
    timestamp = datetime.now().isoformat(timespec='seconds')
    time_history.append(sample_index)
    cj_temp = get_cj_temp()
    print(f"DEBUG: Sample {sample_index} | Board CJ Temp = {cj_temp} °C")

    if cj_temp is not None:
        correction_delta = cj_temp - ambient_temp
        cj_label.config(text=f"CJ Temp: {cj_temp:.1f}°C | Correction Δ: {correction_delta:.1f}°C")
    else:
        cj_label.config(text="CJ Temp: N/A | Correction Δ: N/A")

    for probe in active_probes:
        board_id = probe["board"]
        ch = probe["channel"]
        tc_type = probe["type"]
        label = f"{board_id}-{ch}"
        value = read_channel(board_id, ch)

        try:
            raw_temp = float(value)  # Already CPU-compensated temperature
            temp_history_raw[label].append(raw_temp)

            if cj_temp is not None:
                corrected = raw_temp - (cj_temp - ambient_temp)
            else:
                corrected = raw_temp

            temp_history[label].append(corrected)

            csv_writer.writerow([timestamp, board_id, ch, tc_type, cj_temp, raw_temp, corrected])

        except ValueError:
            csv_writer.writerow([timestamp, board_id, ch, tc_type, cj_temp, value, "ERR"])
            temp_history[label].append(None)
            temp_history_raw[label].append(None)

def update_plot(ax):
    ax.clear()
    # When show_corrected is True, display raw temps; otherwise display corrected
    source = temp_history_raw if show_corrected else temp_history
    for label in source:
        if source[label]:
            ax.plot(time_history, source[label], label=label)
    title = "Raw Thermocouple Readings" if show_corrected else "Corrected Thermocouple Readings"
    ax.set_title(title)
    ax.set_xlabel("Sample #")
    ax.set_ylabel("Temperature (°C)")
    ax.grid(True)
    ax.legend(loc='upper right', fontsize='small', ncol=2)
    plt.tight_layout()

def start_monitoring(interval, count, ax, canvas, start_button, pause_button, ambient_temp, cj_label):
    global temp_history, time_history, temp_history_raw
    start_button.config(state='disabled')
    pause_button.config(state='normal', text='Pause')

    active_probes = []
    temp_history = {}
    temp_history_raw = {}
    time_history = []

    for widgets in probe_widgets:
        var_enabled, label, dropdown = widgets
        if var_enabled.get():
            board, ch = map(int, label.split("-"))
            tc_type = dropdown.get()
            active_probes.append({
                "board": board,
                "channel": ch,
                "type": tc_type
            })
            temp_history[label] = []
            temp_history_raw[label] = []

    threading.Thread(
        target=monitor_loop,
        args=(interval, count, ax, canvas, start_button, pause_button, active_probes, ambient_temp, cj_label),
        daemon=True
    ).start()

def monitor_loop(interval, count, ax, canvas, start_button, pause_button, active_probes, ambient_temp, cj_label):
    global running, paused
    running = True
    paused = False

    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["timestamp", "board_id", "channel", "type", "cpu_temp", "raw_temp", "corrected_temp"])

        for i in range(count):
            if not running:
                break
            while paused and running:
                time.sleep(0.2)
            if not running:
                break

            read_all(writer, i, active_probes, ambient_temp, cj_label)
            # Set flag for plotting source dynamically based on show_corrected (already global)
            update_plot(ax)
            canvas.draw()
            if i < count - 1:
                time.sleep(interval)

    start_button.config(state='normal')
    pause_button.config(state='disabled')

def build_probe_config_panel(parent):
    global probe_widgets
    probe_widgets = []
    types = ["K"]  # Only K-type, combobox disabled below

    frame = ttk.Frame(parent)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=10)

    # Top row: board 0 channels 1–8; bottom row: board 1 channels 1–8
    for board in (0, 1):
        for ch in range(1, 9):
            row = board  # 0 for board 0, 1 for board 1
            col = ch - 1
            var_enabled = tk.BooleanVar(value=True)
            label = f"{board}-{ch}"

            cell_frame = ttk.Frame(frame, padding=2)
            cell_frame.grid(row=row, column=col, sticky="w", padx=5, pady=5)

            check = ttk.Checkbutton(cell_frame, variable=var_enabled)
            check.grid(row=0, column=0, sticky="w")

            ttk.Label(cell_frame, text=label).grid(row=0, column=1, padx=2, sticky="w")

            dropdown = ttk.Combobox(cell_frame, values=types, width=4, state="disabled")
            dropdown.set("K")
            dropdown.grid(row=0, column=2, padx=2)

            probe_widgets.append((var_enabled, label, dropdown))

def launch_gui():
    global running, paused
    root = tk.Tk()
    root.title("Thermocouple Monitor")

    input_frame = ttk.Frame(root, padding=10)
    input_frame.pack(side=tk.TOP, fill=tk.X)

    ttk.Label(input_frame, text="Seconds between reads:").pack(side=tk.LEFT)
    interval_entry = ttk.Entry(input_frame, width=5)
    interval_entry.insert(0, "5")
    interval_entry.pack(side=tk.LEFT, padx=5)

    ttk.Label(input_frame, text="Number of reads:").pack(side=tk.LEFT)
    count_entry = ttk.Entry(input_frame, width=5)
    count_entry.insert(0, "10")
    count_entry.pack(side=tk.LEFT, padx=5)

    ttk.Label(input_frame, text="Ambient Temp (°C):").pack(side=tk.LEFT)
    ambient_entry = ttk.Entry(input_frame, width=5)
    ambient_entry.insert(0, "25")
    ambient_entry.pack(side=tk.LEFT, padx=5)

    start_button = ttk.Button(input_frame, text="Start Monitoring")
    start_button.pack(side=tk.LEFT, padx=10)

    pause_button = ttk.Button(input_frame, text="Pause", state='disabled')
    pause_button.pack(side=tk.LEFT)

    build_probe_config_panel(root)

    fig, ax = plt.subplots(figsize=(10, 5))
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    cj_label = ttk.Label(root, text="CJ Temp: N/A | Correction Δ: N/A")
    cj_label.pack(side=tk.TOP, pady=5)

    view_var = tk.BooleanVar(value=False)
    def on_toggle_view():
        global show_corrected
        show_corrected = view_var.get()
        update_plot(ax)
        canvas.draw()
    view_checkbox = ttk.Checkbutton(root, text="Show Raw Temps", variable=view_var, command=on_toggle_view)
    view_checkbox.pack(side=tk.TOP, pady=5)

    def on_start():
        try:
            interval = int(interval_entry.get())
            count = int(count_entry.get())
            ambient = float(ambient_entry.get())
            start_monitoring(interval, count, ax, canvas, start_button, pause_button, ambient, cj_label)
        except ValueError:
            print("Invalid input.")

    def on_pause_toggle():
        global paused
        paused = not paused
        pause_button.config(text="Resume" if paused else "Pause")

    def on_close():
        global running
        running = False
        try:
            os.system("pkill -f smtc")
        except Exception as e:
            print(f"Cleanup error: {e}")
        root.destroy()
        sys.exit(0)

    start_button.config(command=on_start)
    pause_button.config(command=on_pause_toggle)
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()