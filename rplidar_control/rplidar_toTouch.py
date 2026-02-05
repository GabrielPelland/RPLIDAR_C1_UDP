import math
import time
import socket
from collections import deque, defaultdict
from pyrplidar import PyRPlidar

# -----------------------------
# UDP target
# -----------------------------
UDP_IP = "10.0.1.2"
UDP_PORT = 5005
SEND_HZ = 60.0           # latence ~ 1/60 = 16.6ms
SEND_PERIOD = 1.0 / SEND_HZ

# -----------------------------
# Micro-buffer + nettoyage
# -----------------------------
WINDOW_MS = 70            # fenêtre glissante courte (50-90ms)
GRID_STEP = 0.01          # taille cellule en coords 0..1 (0.01 = 1% => ~1 cm si ROI=1m)
MIN_HITS = 2              # cellule doit être vue au moins 2 fois dans la fenêtre
MAX_POINTS_PER_PACKET = 600  # MTU

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
# ROI + orientation
# -----------------------------
ROI_WIDTH_MM = 1000
ROI_DEPTH_MM = 1000
ANGLE_OFFSET_DEG = 0.0 


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


def quantize(x01: float, y01: float, step: float):
    # Convertit en "cellule" stable
    gx = int(x01 / step)
    gy = int(y01 / step)
    return gx, gy


def build_xy_packet(points):
    lines = ["x\ty"]
    for x, y in points:
        lines.append(f"{x:.4f}\t{y:.4f}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (UDP_IP, UDP_PORT)

    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    scan_generator = lidar.force_scan()

    # Buffer glissant: (t, x01, y01, gx, gy)
    buf = deque()
    window_s = WINDOW_MS / 1000.0

    last_send = time.perf_counter()

    try:
        for scan in scan_generator():
            now = time.perf_counter()

            # 1) Ajouter point si ROI
            dist_mm = float(scan.distance)
            if MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM:
                angle = float(scan.angle)
                x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)

                if in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                    x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)
                    gx, gy = quantize(x01, y01, GRID_STEP)
                    buf.append((now, x01, y01, gx, gy))

            # 2) Purge fenêtre glissante
            cutoff = now - window_s
            while buf and buf[0][0] < cutoff:
                buf.popleft()

            # 3) Envoi périodique
            if (now - last_send) >= SEND_PERIOD:
                counts = defaultdict(int)
                sums = defaultdict(lambda: [0.0, 0.0])

                for _t, x01, y01, gx, gy in buf:
                    key = (gx, gy)
                    counts[key] += 1
                    sums[key][0] += x01
                    sums[key][1] += y01

                points = []
                for key, c in counts.items():
                    if c >= MIN_HITS:
                        sx, sy = sums[key]
                        points.append((sx / c, sy / c))

                if len(points) > MAX_POINTS_PER_PACKET:
                    step = len(points) / MAX_POINTS_PER_PACKET
                    points = [points[int(i * step)] for i in range(MAX_POINTS_PER_PACKET)]

                sock.sendto(build_xy_packet(points), target)

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
