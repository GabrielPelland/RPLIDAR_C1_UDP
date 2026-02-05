import math
import time
import json
from pyrplidar import PyRPlidar

PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3

MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

MIN_DIST_M = 0.05
MAX_DIST_M = 3.0

ROI_HALF_WIDTH_M = 0.5   # x ∈ [-0.5, +0.5]
ROI_DEPTH_M = 1.0        # y ∈ [0, 1.0]

ANGLE_OFFSET_DEG = 0.0   # ajuste 0 / 90 / -90 / 180 si nécessaire

WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0

PRINT_EMPTY_SWEEPS = False


def polar_to_xy_m(angle_deg: float, distance_m: float, angle_offset_deg: float):
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_m * math.sin(a)   # gauche/droite
    y = distance_m * math.cos(a)   # avant (vers le bas du cadre)
    return x, y


def in_roi(x: float, y: float) -> bool:
    return (-ROI_HALF_WIDTH_M <= x <= ROI_HALF_WIDTH_M) and (0.0 <= y <= ROI_DEPTH_M)


def main():
    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    points_roi = []
    prev_angle = None
    sweep_idx = 0

    try:
        # IMPORTANT: on évite force_scan() ici
        # Selon ta version, ça peut être start_scan() ou scan()
        scan_iter = lidar.start_scan()  # <-- si AttributeError, remplace par lidar.scan() ou lidar.start_scan_express()

        for scan in scan_iter:
            angle = float(scan.angle)
            dist_m = float(scan.distance) / 1000.0

            if MIN_DIST_M <= dist_m <= MAX_DIST_M:
                x, y = polar_to_xy_m(angle, dist_m, ANGLE_OFFSET_DEG)
                if in_roi(x, y):
                    points_roi.append({
                        "x": round(x, 4),
                        "y": round(y, 4),
                        "d": round(dist_m, 4),
                        "a": round(angle, 2),
                    })

            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG)
                if wrapped:
                    sweep_idx += 1
                    payload = {
                        "t": time.time(),
                        "sweep": sweep_idx,
                        "count": len(points_roi),
                        "roi": {"half_width_m": ROI_HALF_WIDTH_M, "depth_m": ROI_DEPTH_M},
                        "points": points_roi,
                    }
                    if PRINT_EMPTY_SWEEPS or points_roi:
                        print(json.dumps(payload, ensure_ascii=False))
                    points_roi = []

            prev_angle = angle

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        for fn in ("stop",):
            try:
                getattr(lidar, fn)()
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
