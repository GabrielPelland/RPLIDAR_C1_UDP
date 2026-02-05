import math
import time
import socket
import struct
from pyrplidar import PyRPlidar

# -----------------------------
# Network (TouchDesigner)
# -----------------------------
OSC_IP = "192.168.0.12"
OSC_PORT = 9000

# Envoi points: batch sur ~5ms (faible latence, moins de spam UDP)
BATCH_MAX_MS = 5.0
MAX_POINTS_PER_BUNDLE = 120

# Détection: garde "detect=1" pendant HOLD_MS après le dernier point ROI
DETECT_HOLD_MS = 80

# -----------------------------
# Lidar
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3
MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

MIN_DISTANCE_MM = 50
MAX_DISTANCE_MM = 3000

# -----------------------------
# ROI (mm) + orientation
# -----------------------------
ROI_WIDTH_MM = 1000
ROI_DEPTH_MM = 1000
ANGLE_OFFSET_DEG = 0.0  # ajuste si nécessaire

# Sweep detection
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    # Repère: y = avant (bas), x = droite ; angle 0° = avant
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def in_roi(x_mm: float, y_mm: float, w_mm: float, d_mm: float) -> bool:
    half = w_mm / 2.0
    return (-half <= x_mm <= half) and (0.0 <= y_mm <= d_mm)


def normalize_xy01(x_mm: float, y_mm: float, w_mm: float, d_mm: float):
    half = w_mm / 2.0
    x01 = (x_mm + half) / w_mm      # 0 gauche -> 1 droite
    y01 = y_mm / d_mm               # 0 haut   -> 1 bas
    return clamp01(x01), clamp01(y01)


# -----------------------------
# Minimal OSC encoder (no deps)
# -----------------------------
def _pad4(b: bytes) -> bytes:
    return b + (b"\x00" * ((4 - (len(b) % 4)) % 4))


def osc_message(address: str, args):
    # args: ints => 'i', floats => 'f'
    addr = _pad4(address.encode("utf-8") + b"\x00")
    tags = "," + "".join("i" if isinstance(a, int) else "f" for a in args)
    tags_b = _pad4(tags.encode("utf-8") + b"\x00")

    data = b""
    for a in args:
        if isinstance(a, int):
            data += struct.pack(">i", int(a))
        else:
            data += struct.pack(">f", float(a))

    return addr + tags_b + data


def osc_bundle(messages):
    header = _pad4(b"#bundle\x00")
    timetag = struct.pack(">Q", 1)  # immediate
    out = header + timetag
    for m in messages:
        out += struct.pack(">i", len(m)) + m
    return out


def send_bundle(sock, target, msgs):
    if not msgs:
        return
    sock.sendto(osc_bundle(msgs), target)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (OSC_IP, OSC_PORT)

    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # Pattern identique à ton script original
    scan_generator = lidar.force_scan()

    batch_msgs = []
    last_send = time.perf_counter()
    t_batch = BATCH_MAX_MS / 1000.0

    # Detect state
    detect_state = 0
    last_roi_point_t = 0.0

    # Sweep detection
    prev_angle = None
    sweep_idx = 0
    points_in_current_sweep = 0

    try:
        for scan in scan_generator():
            now = time.perf_counter()

            # --- Sweep wrap detection (reset signal to TD)
            angle = float(scan.angle)
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG) or (angle < prev_angle)
                if wrapped:
                    sweep_idx += 1
                    points_in_current_sweep = 0

                    # Flush points first (to keep ordering clean), then emit /sweep
                    send_bundle(sock, target, batch_msgs)
                    batch_msgs.clear()

                    # /sweep 1 with sweep index
                    # TD can use /sweep to clear point cloud buffer
                    sweep_msgs = [
                        osc_message("/sweep", [1]),
                        osc_message("/sweep_idx", [sweep_idx]),
                    ]
                    send_bundle(sock, target, sweep_msgs)
                    last_send = now  # reset batch timer too

            prev_angle = angle

            # --- Distance gate
            dist_mm = float(scan.distance)
            if not (MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM):
                # periodic send if needed
                if (now - last_send) >= t_batch and batch_msgs:
                    send_bundle(sock, target, batch_msgs)
                    batch_msgs.clear()
                    last_send = now
                continue

            # --- ROI filter
            x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)
            if not in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                if (now - last_send) >= t_batch and batch_msgs:
                    send_bundle(sock, target, batch_msgs)
                    batch_msgs.clear()
                    last_send = now
                continue

            # --- Normalize + send point
            x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)
            batch_msgs.append(osc_message("/pt", [x01, y01]))
            points_in_current_sweep += 1
            last_roi_point_t = now

            # --- Detect flag logic (low-latency)
            new_detect_state = 1  # we just saw an ROI point
            if new_detect_state != detect_state:
                detect_state = new_detect_state
                batch_msgs.append(osc_message("/detect", [detect_state]))

            # --- Batch flush conditions
            if (len(batch_msgs) >= MAX_POINTS_PER_BUNDLE) or ((now - last_send) >= t_batch):
                send_bundle(sock, target, batch_msgs)
                batch_msgs.clear()
                last_send = now

            # --- Detect auto-off after hold
            # (we do this check here so it runs frequently)
            if detect_state == 1:
                hold_s = DETECT_HOLD_MS / 1000.0
                if (now - last_roi_point_t) > hold_s:
                    detect_state = 0
                    # send detect=0 immediately
                    send_bundle(sock, target, [osc_message("/detect", [0])])
                    # don't touch last_send for point batching

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        # final flush
        try:
            send_bundle(sock, target, batch_msgs)
        except Exception:
            pass

        # send detect=0 on shutdown (optional)
        try:
            send_bundle(sock, target, [osc_message("/detect", [0])])
        except Exception:
            pass

        try:
            lidar.stop()
        except Exception:
            pass
        try:
            lidar.set_motor_pwm(0)
        except Exception:
            pass
        try:
            lidar.disconnect()
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
