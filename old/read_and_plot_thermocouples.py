import subprocess
import time
import os
import signal
import csv
from datetime import datetime
import matplotlib.pyplot as plt

# Board and channel settings
board_ids = [0, 1]
channels = range(1, 9)
csv_file = "temperature_log.csv"

# For plotting
channel_labels = [f"{b}-{c}" for b in board_ids for c in channels]
temp_history = {label: [] for label in channel_labels}
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
        try:
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return stdout.strip()
            else:
                return f"Error: {stderr.strip()}"
        except subprocess.TimeoutExpired:
            print(f"Timeout: killing smtc for board {board_id}, channel {channel}")
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            return "Timeout"
    except Exception as e:
        return f"Exception: {str(e)}"

def read_all(csv_writer, sample_index):
    timestamp = datetime.now().isoformat(timespec='seconds')
    time_history.append(sample_index)
    for board_id in board_ids:
        print(f"HAT ID {board_id}")
        for ch in channels:
            label = f"{board_id}-{ch}"
            value = read_channel(board_id, ch)
            print(f"  Channel {ch}: {value} °C")
            try:
                temp = float(value)
                csv_writer.writerow([timestamp, board_id, ch, temp])
                temp_history[label].append(temp)
            except ValueError:
                csv_writer.writerow([timestamp, board_id, ch, value])
                temp_history[label].append(None)
        print()

def update_plot():
    plt.clf()
    for label in channel_labels:
        values = temp_history[label]
        if values:
            plt.plot(time_history, values, label=label)
    plt.xlabel("Sample #")
    plt.ylabel("Temperature (°C)")
    plt.title("Live Thermocouple Readings")
    plt.legend(loc='upper right', fontsize='small', ncol=2)
    plt.grid(True)
    plt.tight_layout()
    plt.pause(0.01)

if __name__ == "__main__":
    try:
        interval = int(input("Seconds between reads: "))
        count = int(input("How many times to read: "))
        print("\nStarting sensor reads...\n")

        # Prepare plotting window
        plt.ion()
        fig = plt.figure(figsize=(12, 6))

        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["timestamp", "board_id", "channel", "temperature_c"])

            for i in range(count):
                print(f"--- Read {i+1} of {count} ---")
                read_all(writer, i)
                update_plot()
                if i < count - 1:
                    time.sleep(interval)

        print(f"\nAll done! Data saved to: {csv_file}")
        plt.ioff()
        plt.show()

    except ValueError:
        print("Invalid input. Please enter integers only.")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
