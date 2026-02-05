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

# Batching: envoie un paquet toutes les ~5ms (faible latence, moins de spam UDP)
BATCH_MAX_MS = 5.0
# Sécurité taille paquet: limite le nombre de points par bundle
MAX_POINTS_PER_BUNDLE = 120  # ajuste si besoin

# -----------------------------
# Lidar (comme ton setup)
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
ROI_WIDTH_MM = 1000      # 1m
ROI_DEPTH_MM = 1000      # 1m
ANGLE_OFFSET_DEG = 0.0   # ajuste si "devant" n'est pas aligné

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
    # args: floats only here
    addr = _pad4(address.encode("utf-8") + b"\x00")
    tags = _pad4((",{}".format("f" * len(args))).encode("utf-8") + b"\x00")
    data = b"".join(struct.pack(">f", float(a)) for a in args)
    return addr + tags + data

def osc_bundle(messages):
    # OSC Bundle header: "#bundle" + 8-byte timetag
    header = _pad4(b"#bundle\x00")
    timetag = struct.pack(">Q", 1)  # "immediate"
    out = header + timetag
    for m in messages:
        out += struct.pack(">i", len(m)) + m
    return out

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (OSC_IP, OSC_PORT)

    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # IMPORTANT: pattern identique à ton script original
    scan_generator = lidar.force_scan()

    batch_msgs = []
    last_send = time.perf_counter()
    t_batch = BATCH_MAX_MS / 1000.0

    # optionnel: compteur pour debug
    sent_points = 0

    try:
        for scan in scan_generator():
            dist_mm = float(scan.distance)
            if not (MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM):
                continue

            angle = float(scan.angle)
            x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)

            if not in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                continue

            x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)

            # Message OSC par point. Adresse simple "/pt" => args: x, y
            # (tu peux ajouter d si tu veux: args [x01, y01, dist_mm])
            batch_msgs.append(osc_message("/pt", [x01, y01]))
            sent_points += 1

            now = time.perf_counter()
            # Envoi si: batch plein OU délai atteint
            if (len(batch_msgs) >= MAX_POINTS_PER_BUNDLE) or ((now - last_send) >= t_batch):
                pkt = osc_bundle(batch_msgs)
                sock.sendto(pkt, target)
                batch_msgs.clear()
                last_send = now

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        # flush final
        try:
            if batch_msgs:
                sock.sendto(osc_bundle(batch_msgs), target)
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
