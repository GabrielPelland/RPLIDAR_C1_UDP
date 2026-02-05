import math
import time
import json
from pyrplidar import PyRPlidar

# -----------------------------
# Config (calquée sur ton script)
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3

MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

# Distances (mm) comme ton script
MIN_DISTANCE_MM = 50
MAX_DISTANCE_MM = 3000

# ROI: carré 1m x 1m "devant" le lidar
# Repère choisi:
#   y = vers l'avant (vers le bas du cadre)
#   x = gauche/droite
ROI_HALF_WIDTH_MM = 500   # x ∈ [-500, +500]
ROI_DEPTH_MM = 1000       # y ∈ [0, 1000]

# Orientation:
# On veut que l'angle 0° pointe "vers l'avant" (vers le bas du cadre).
# Si ce n'est pas le cas, ajuste ANGLE_OFFSET_DEG (0, 90, -90, 180, etc.)
ANGLE_OFFSET_DEG = 0.0

# Détection de fin de tour (comme ton approche prev_angle)
# (optionnel) hystérésis pour réduire les faux wraps
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0

PRINT_EMPTY_SWEEPS = False


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    """
    Convertit (angle°, distance mm) en (x,y) mm.
    Convention:
      - y positif = devant (vers le bas du cadre)
      - x positif = droite (si tu regardes dans la direction "devant")
      - angle 0° = devant
    """
    a = math.radians(angle_deg + angle_offset_deg)
    # y = cos, x = sin => 0° donne (x=0, y=+d)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def in_roi(x_mm: float, y_mm: float) -> bool:
    return (-ROI_HALF_WIDTH_MM <= x_mm <= ROI_HALF_WIDTH_MM) and (0.0 <= y_mm <= ROI_DEPTH_MM)


def main():
    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # EXACTEMENT comme ton premier script: factory -> appel -> itération
    scan_generator = lidar.force_scan()

    points_roi = []
    prev_angle = None
    sweep_idx = 0

    try:
        for scan in scan_generator():
            angle = float(scan.angle)
            dist = float(scan.distance)  # mm

            # filtre distance
            if MIN_DISTANCE_MM <= dist <= MAX_DISTANCE_MM:
                x_mm, y_mm = polar_to_xy_mm(angle, dist, ANGLE_OFFSET_DEG)

                # filtre ROI 1m x 1m
                if in_roi(x_mm, y_mm):
                    points_roi.append({
                        "x_mm": int(round(x_mm)),
                        "y_mm": int(round(y_mm)),
                        "d_mm": int(round(dist)),
                        "a_deg": round(angle, 2),
                    })

            # fin de tour (wrap)
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG) or (angle < prev_angle)
                if wrapped:
                    sweep_idx += 1
                    payload = {
                        "t": time.time(),
                        "sweep": sweep_idx,
                        "roi": {
                            "width_mm": ROI_HALF_WIDTH_MM * 2,
                            "depth_mm": ROI_DEPTH_MM,
                            "angle_offset_deg": ANGLE_OFFSET_DEG
                        },
                        "count": len(points_roi),
                        "points": points_roi
                    }

                    if PRINT_EMPTY_SWEEPS or points_roi:
                        print(json.dumps(payload, ensure_ascii=False))

                    points_roi = []

            prev_angle = angle

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        # Nettoyage défensif
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


if __name__ == "__main__":
    main()
