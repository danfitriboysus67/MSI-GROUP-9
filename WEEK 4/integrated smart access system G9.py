import serial
import matplotlib.pyplot as plt
import numpy as np
from collections import deque
import threading
import time


def is_circular_motion(x_data, y_data):
    if len(x_data) < 10:
        return False
    x_centered = x_data - np.mean(x_data)
    y_centered = y_data - np.mean(y_data)
    if np.var(x_centered) < 10000 or np.var(y_centered) < 10000:
        return False
    std_x = np.std(x_centered)
    std_y = np.std(y_centered)
    if std_x == 0 or std_y == 0:
        return False
    ratio = std_x / std_y
    if ratio < 0.5 or ratio > 2.0:
        return False
    clockwise_turns = 0
    total_turns = len(x_data) - 1
    for i in range(total_turns):
        cross_product = (x_centered[i] * y_centered[i + 1]) - (y_centered[i] * x_centered[i + 1])
        if cross_product > 0:
            clockwise_turns += 1
    turn_ratio = clockwise_turns / total_turns
    if turn_ratio > 0.70 or turn_ratio < 0.30:
        return True
    return False


def classify_motion(x_data, y_data, z_data, noise_threshold=3000):
    if is_circular_motion(x_data, y_data):
        return "Rotation (Circular) 🔄"
    std_x = np.std(x_data)
    std_y = np.std(y_data)
    std_z = np.std(z_data)
    max_std = max(std_x, std_y, std_z)
    if max_std < noise_threshold:
        return "Idle 🛑"
    if max_std == std_x:
        return "Left / Right ↔️"
    elif max_std == std_y:
        return "Front / Back ↕️"
    elif max_std == std_z:
        return "Up / Down ⬆️⬇️"
    return "Unknown 🤔"


# ================= RFID THREADING SETUP =================
# Updated with your specific USB RFID card code
AUTHORIZED_UIDS = ["0013020304"]
scanned_uid = None
system_state = "WAIT_RFID"
action_time = 0


def rfid_listener():
    """Background thread to catch the USB RFID keyboard emulation."""
    global scanned_uid
    while True:
        try:
            uid = input()
            if uid:
                scanned_uid = uid.strip()
        except:
            pass


threading.Thread(target=rfid_listener, daemon=True).start()

# Updated to COM5
ser = serial.Serial('COM5', 9600, timeout=1)

window_size = 40
history_x = deque(maxlen=window_size)
history_y = deque(maxlen=window_size)
history_z = deque(maxlen=window_size)

plot_x, plot_y = [], []

plt.ion()
fig, ax = plt.subplots()
ax.set_xlim(-20000, 20000)
ax.set_ylim(-20000, 20000)
line, = ax.plot([], [], 'ro')

print("\n--- SYSTEM LOCKED ---")
print("Make sure this PyCharm terminal is in focus.")
print("Tap your USB RFID card now...")

while True:
    try:
        current_time = time.time()

        # 1. Check if the 5-second door sequence has finished (giving it 6s to be safe)
        if system_state == "DOOR_BUSY" and (current_time - action_time >= 6.0):
            system_state = "WAIT_RFID"
            print("\n--- SYSTEM LOCKED ---")
            print("Tap your USB RFID card now...")

        # 2. Check for new RFID scans
        if system_state == "WAIT_RFID" and scanned_uid is not None:
            if scanned_uid in AUTHORIZED_UIDS:
                print(f"✅ Access Granted [UID: {scanned_uid}]")
                print("Waiting for Rotation gesture...")
                ser.write(b'W')  # Tell Arduino to pulse red LED
                system_state = "WAIT_MOTION"
            else:
                print(f"❌ Access Denied [UID: {scanned_uid}]")

            scanned_uid = None
            history_x.clear()
            history_y.clear()

        # 3. Read MPU6050 Data
        data = ser.readline().decode('utf-8', errors='ignore').strip()
        if data:
            values = data.split(',')

            if len(values) == 3:
                try:
                    ax_val, ay_val, az_val = int(values[0]), int(values[1]), int(values[2])

                    history_x.append(ax_val)
                    history_y.append(ay_val)
                    history_z.append(az_val)

                    plot_x.append(ax_val)
                    plot_y.append(ay_val)

                    if len(plot_x) > 100:
                        plot_x.pop(0)
                        plot_y.pop(0)

                    line.set_data(plot_x, plot_y)
                    plt.draw()
                    plt.pause(0.01)

                    # 4. Analyze Motion ONLY if we are in the WAIT_MOTION state
                    if len(history_x) == window_size:
                        if system_state == "WAIT_MOTION":
                            motion_type = classify_motion(history_x, history_y, history_z)

                            if "Idle" not in motion_type:
                                if "Rotation" in motion_type:
                                    print("🔄 Rotation verified! Opening door for 5 seconds.")
                                    ser.write(b'R')
                                    system_state = "DOOR_BUSY"
                                    action_time = current_time
                                else:
                                    print(f"❌ Incorrect gesture ({motion_type}). Try again.")

                        history_x.clear()
                        history_y.clear()
                        history_z.clear()

                except ValueError:
                    pass
    except KeyboardInterrupt:
        print("\nProgram terminated.")
        break

ser.close()