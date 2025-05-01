import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import os
import signal
import csv
import sys
from datetime import datetime
import time
import threading

# Control flags
running = False
paused = False

# CSV logging
csv_file = "temperature_log.csv"

# All 16 channels with labels
all_probes = [(0, ch) for ch in range(1, 9)] + [(1, ch) for ch in range(1, 9)]
probe_widgets = []  # Stores widget references
temp_history = {}
time_history = []

# Calibration functions
calibration_curves = {
    "K": lambda t: t + 0.5,
    "J": lambda t: t - 0.3,
    "T": lambda t: t,
    "E": lambda t: t + 0.2,
    "N": lambda t: t - 0.4,
    "S": lambda t: t + 1.0,
    "R": lambda t: t + 1.0,
    "B": lambda t: t + 2.0,
}

def read_channel(board_id, channel):
    try:
        process = subprocess.Popen(
            ["smtc", str(board_id), "read", str(channel)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        try:
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return stdout.strip()
            else:
                return f"Error: {stderr.strip()}"
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            return "Timeout"
    except Exception as e:
        return f"Exception: {str(e)}"

def read_all(csv_writer, sample_index, active_probes):
    timestamp = datetime.now().isoformat(timespec='seconds')
    time_history.append(sample_index)
    for probe in active_probes:
        board_id = probe["board"]
        ch = probe["channel"]
        tc_type = probe["type"]
        label = f"{board_id}-{ch}"
        value = read_channel(board_id, ch)

        try:
            raw_temp = float(value)
            calibrated = calibration_curves.get(tc_type, lambda t: t)(raw_temp)
            csv_writer.writerow([timestamp, board_id, ch, tc_type, calibrated])
            temp_history[label].append(calibrated)
        except ValueError:
            csv_writer.writerow([timestamp, board_id, ch, tc_type, value])
            temp_history[label].append(None)

def update_plot(ax):
    ax.clear()
    for label in temp_history:
        if temp_history[label]:
            ax.plot(time_history, temp_history[label], label=label)
    ax.set_title("Live Thermocouple Readings (Calibrated)")
    ax.set_xlabel("Sample #")
    ax.set_ylabel("Temperature (°C)")
    ax.grid(True)
    ax.legend(loc='upper right', fontsize='small', ncol=2)
    plt.tight_layout()

def start_monitoring(interval, count, ax, canvas, start_button, pause_button):
    global temp_history, time_history
    start_button.config(state='disabled')
    pause_button.config(state='normal', text='Pause')

    # Get active probes and types from UI
    active_probes = []
    temp_history = {}
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

    threading.Thread(
        target=monitor_loop,
        args=(interval, count, ax, canvas, start_button, pause_button, active_probes),
        daemon=True
    ).start()

def monitor_loop(interval, count, ax, canvas, start_button, pause_button, active_probes):
    global running, paused
    running = True
    paused = False

    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["timestamp", "board_id", "channel", "type", "temperature_c"])

        for i in range(count):
            if not running:
                break
            while paused and running:
                time.sleep(0.2)
            if not running:
                break

            read_all(writer, i, active_probes)
            update_plot(ax)
            canvas.draw()
            if i < count - 1:
                time.sleep(interval)

    start_button.config(state='normal')
    pause_button.config(state='disabled')

def build_probe_config_panel(parent):
    global probe_widgets
    probe_widgets = []

    types = ["K", "J", "T", "E", "N", "S", "R", "B"]

    frame = ttk.Frame(parent)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=10)

    for idx, (board, ch) in enumerate(all_probes):
        row = idx // 4
        col = idx % 4
        var_enabled = tk.BooleanVar(value=False)
        label = f"{board}-{ch}"

        cell_frame = ttk.Frame(frame, padding=2)
        cell_frame.grid(row=row, column=col, sticky="w", padx=5, pady=5)

        check = ttk.Checkbutton(cell_frame, variable=var_enabled)
        check.grid(row=0, column=0, sticky="w")

        ttk.Label(cell_frame, text=f"{label}").grid(row=0, column=1, padx=2, sticky="w")

        dropdown = ttk.Combobox(cell_frame, values=types, width=4)
        dropdown.set("K")
        dropdown.grid(row=0, column=2, padx=2)

        probe_widgets.append((var_enabled, label, dropdown))

def launch_gui():
    global running, paused

    root = tk.Tk()
    root.title("Thermocouple Monitor")

    # Input frame
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

    start_button = ttk.Button(input_frame, text="Start Monitoring")
    start_button.pack(side=tk.LEFT, padx=10)

    pause_button = ttk.Button(input_frame, text="Pause", state='disabled')
    pause_button.pack(side=tk.LEFT)

    # Probe config panel (grid layout)
    build_probe_config_panel(root)

    # Plotting area
    fig, ax = plt.subplots(figsize=(10, 5))
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def on_start():
        try:
            interval = int(interval_entry.get())
            count = int(count_entry.get())
            start_monitoring(interval, count, ax, canvas, start_button, pause_button)
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
        sys.exit(0)  # 🔥 Forcefully exit Python process

    start_button.config(command=on_start)
    pause_button.config(command=on_pause_toggle)
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
