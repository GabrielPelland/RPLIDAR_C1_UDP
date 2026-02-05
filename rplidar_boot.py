import math
import time
import json
from pyrplidar import PyRPlidar

# -----------------------------
# Config
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3

MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

# Lidar distance filtering (meters)
MIN_DIST_M = 0.05    # 5 cm
MAX_DIST_M = 3.0     # 3 m (ou adapte selon ton lidar)

# ROI square 1m x 1m in front of lidar:
# x left/right, y forward (down the frame)
ROI_HALF_WIDTH_M = 0.5   # +/- 0.5m
ROI_DEPTH_M = 1.0        # 0..1.0m

# Angle alignment:
# We define angle=0° as pointing "forward" (down the frame).
# If your lidar's 0° is not forward, adjust this offset.
ANGLE_OFFSET_DEG = 0.0   # try 0, 90, -90, 180 ...

# Sweep completion detection (hysteresis)
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0

# Output rate control
PRINT_EMPTY_SWEEPS = False  # print even if no points in ROI


def polar_to_xy_m(angle_deg: float, distance_m: float, angle_offset_deg: float) -> tuple[float, float]:
    """
    Convert lidar polar measurement to cartesian (x,y) in meters.
    Convention:
      - y is "forward" (toward the frame, downward)
      - x is left/right
      - angle=0 points forward
      - positive angle rotates CCW (standard math)
    """
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_m * math.sin(a)  # sin gives left/right with our convention
    y = distance_m * math.cos(a)  # cos gives forward
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
        # NOTE: In most versions, force_scan() is iterable directly.
        for scan in lidar.force_scan():
            # scan.angle in degrees, scan.distance in mm (based on your previous script)
            angle = float(scan.angle)
            dist_m = float(scan.distance) / 1000.0

            # Distance gating
            if MIN_DIST_M <= dist_m <= MAX_DIST_M:
                x, y = polar_to_xy_m(angle, dist_m, ANGLE_OFFSET_DEG)

                # Keep only points in the 1m x 1m square ROI
                if in_roi(x, y):
                    points_roi.append({
                        "x": round(x, 4),
                        "y": round(y, 4),
                        "d": round(dist_m, 4),
                        "a": round(angle, 2),
                    })

            # Detect sweep completion with hysteresis
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG)
                if wrapped:
                    sweep_idx += 1
                    payload = {
                        "t": time.time(),
                        "sweep": sweep_idx,
                        "roi": {
                            "half_width_m": ROI_HALF_WIDTH_M,
                            "depth_m": ROI_DEPTH_M
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
        # Be defensive: some libs can throw on stop if already stopped
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
