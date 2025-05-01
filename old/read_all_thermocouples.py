import subprocess
import time
import os
import signal
import csv
from datetime import datetime

# HAT stack levels (IDs)
board_ids = [0, 1]
channels = range(1, 9)
csv_file = "temperature_log.csv"

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

def read_all(csv_writer):
    timestamp = datetime.now().isoformat(timespec='seconds')
    for board_id in board_ids:
        print(f"HAT ID {board_id}")
        for ch in channels:
            value = read_channel(board_id, ch)
            print(f"  Channel {ch}: {value} °C")
            # Only log valid numeric readings
            try:
                temp_float = float(value)
                csv_writer.writerow([timestamp, board_id, ch, temp_float])
            except ValueError:
                # Skip logging if not a valid float
                csv_writer.writerow([timestamp, board_id, ch, value])
        print()

if __name__ == "__main__":
    try:
        interval = int(input("Seconds between reads: "))
        count = int(input("How many times to read: "))
        print("\nStarting sensor reads...\n")

        # Open CSV file in append mode
        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)

            # Write header if file is empty
            if file.tell() == 0:
                writer.writerow(["timestamp", "board_id", "channel", "temperature_c"])

            for i in range(count):
                print(f"--- Read {i+1} of {count} ---")
                read_all(writer)
                if i < count - 1:
                    time.sleep(interval)

        print(f"\nAll done! Data saved to: {csv_file}")

    except ValueError:
        print("Invalid input. Please enter integers only.")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
