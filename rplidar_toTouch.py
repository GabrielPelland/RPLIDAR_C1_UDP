import math
import time
import socket
from collections import deque
from pyrplidar import PyRPlidar

# -----------------------------
# UDP target
# -----------------------------
UDP_IP = "192.168.0.12"
UDP_PORT = 5005  # mets le port que tu écoutes dans TD

# Envoi snapshot (Hz)
SEND_HZ = 60.0
SEND_PERIOD = 1.0 / SEND_HZ

# Fenêtre glissante pour le nuage (ms)
WINDOW_MS = 60  # 30-100ms typique: plus bas = plus réactif

# Détection
DETECT_MIN_POINTS = 6  # ajuste selon bruit

# Limite points dans un paquet (évite paquets trop gros)
MAX_POINTS_PER_PACKET = 600  # ajuste si besoin

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
ANGLE_OFFSET_DEG = 0.0

# Sweep detection
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    # Repère: angle 0° = "devant", y = avant (bas), x = droite
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def in_roi(x_mm: float, y_mm: float, w_mm: float, d_mm: float) -> bool:
    half = w_mm / 2.0
    return (-half <= x_mm <= half) and (0.0 <= y_mm <= d_mm)


def normalize_xy01(x_mm: float, y_mm: float, w_mm: float, d_mm: float):
    half = w_mm / 2.0
    x01 = (x_mm + half) / w_mm   # 0 gauche → 1 droite
    y01 = y_mm / d_mm            # 0 haut   → 1 bas
    return clamp01(x01), clamp01(y01)


def build_table_packet(sweep_idx: int, detect: int, pts01):
    # pts01: list[(x01,y01)]
    lines = []
    lines.append(
        f"meta\tsweep\t{sweep_idx}\tdetect\t{detect}\tcount\t{len(pts01)}\twidth_mm\t{ROI_WIDTH_MM}\tdepth_mm\t{ROI_DEPTH_MM}"
    )
    lines.append("x\ty")
    for x, y in pts01:
        lines.append(f"{x:.4f}\t{y:.4f}")
    return ("\n".join(lines)).encode("utf-8")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (UDP_IP, UDP_PORT)

    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # Pattern identique à ton script original
    scan_generator = lidar.force_scan()

    # Buffer glissant: (t, x01, y01)
    buf = deque()

    prev_angle = None
    sweep_idx = 0

    last_send = time.perf_counter()
    window_s = WINDOW_MS / 1000.0

    try:
        for scan in scan_generator():
            now = time.perf_counter()

            angle = float(scan.angle)
            dist_mm = float(scan.distance)

            # Sweep detection (optionnel, mais utile en meta)
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG) or (angle < prev_angle)
                if wrapped:
                    sweep_idx += 1
            prev_angle = angle

            # Ajout point si ROI
            if MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM:
                x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)
                if in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                    x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)
                    buf.append((now, x01, y01))

            # Purge fenêtre glissante
            cutoff = now - window_s
            while buf and buf[0][0] < cutoff:
                buf.popleft()

            # Envoi périodique (low latency)
            if (now - last_send) >= SEND_PERIOD:
                # Snapshot des points
                pts = [(x, y) for (_t, x, y) in buf]

                # Option: limiter nb de points (garde des points espacés)
                if len(pts) > MAX_POINTS_PER_PACKET:
                    step = len(pts) / MAX_POINTS_PER_PACKET
                    pts = [pts[int(i * step)] for i in range(MAX_POINTS_PER_PACKET)]

                detect = 1 if len(pts) >= DETECT_MIN_POINTS else 0

                pkt = build_table_packet(sweep_idx, detect, pts)
                sock.sendto(pkt, target)

                last_send = now

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
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
