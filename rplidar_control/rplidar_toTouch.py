import math
import time
import socket
import sys
import signal
import json
import threading
from collections import deque, defaultdict
from pyrplidar import PyRPlidar

# -----------------------------
# UDP config
# -----------------------------
UDP_TARGETS = ["127.0.0.1", "10.0.1.2"]  # 127.0.0.1 for local, 10.0.1.2 for external PC
UDP_PORT = 5005
COMMAND_PORT = 5006       # Listener for config updates
SEND_HZ = 60.0
SEND_PERIOD = 1.0 / SEND_HZ

# -----------------------------
# Lidar / ROI state (Mutable)
# -----------------------------
CONFIG = {
    "WINDOW_MS": 70,
    "GRID_STEP": 0.01,
    "MIN_HITS": 2,
    "MAX_POINTS": 600,
    "MIN_DIST": 50,
    "MAX_DIST": 3000,
    "ROI_WIDTH": 1000,
    "ROI_DEPTH": 1000,
    "ANGLE_OFFSET": 0.0,
    "MOTOR_PWM": 500
}

# -----------------------------
# Utils
# -----------------------------
def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def polar_to_xy_mm(angle_deg: float, distance_mm: float, offset: float):
    # Repère: angle 0° = "devant", y = devant (haut), x = droite
    a = math.radians(angle_deg + offset)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y

def in_roi(x, y, w, d):
    half = w / 2.0
    return (-half <= x <= half) and (0.0 <= y <= d)

def normalize_xy01(x, y, w, d):
    half = w / 2.0
    x01 = (x + half) / w
    y01 = y / d
    return clamp01(x01), clamp01(y01)

def quantize(x01, y01, step):
    return int(x01 / step), int(y01 / step)

# -----------------------------
# Command Listener (Thread)
# -----------------------------
def command_listener():
    global CONFIG
    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        cmd_sock.bind(("", COMMAND_PORT))
        print(f"Command Listener : ON port {COMMAND_PORT}", flush=True)
        while True:
            data, addr = cmd_sock.recvfrom(1024)
            try:
                msg = json.loads(data.decode("utf-8"))
                print(f"Command Received : {msg} from {addr}", flush=True)
                for k, v in msg.items():
                    if k in CONFIG:
                        CONFIG[k] = type(CONFIG[k])(v)
                        print(f"  Updated {k} = {CONFIG[k]}", flush=True)
            except Exception as e:
                print(f"Command error : {e}", flush=True)
    except Exception as e:
        print(f"Command listener failed : {e}", flush=True)
    finally:
        cmd_sock.close()

# -----------------------------
# Main
# -----------------------------
def main():
    # Start command thread
    threading.Thread(target=command_listener, daemon=True).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    lidar = PyRPlidar()
    PORT = "/dev/ttyUSB0"
    BAUDRATE = 460800
    
    print("PyRPlidar Info : initializing device...", flush=True)
    try:
        lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=3)
        lidar.stop()
        time.sleep(1.0)
        lidar.disconnect()
        time.sleep(1.0)
        lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=3)
        lidar.reset()
        time.sleep(2.0)
    except Exception as e:
        print(f"PyRPlidar Warning : Init cleanup failed: {e}", flush=True)

    lidar.set_motor_pwm(CONFIG["MOTOR_PWM"])
    time.sleep(2.0)

    def handle_sigterm(signum, frame):
        print("\nSIGTERM received. Stopping lidar...", flush=True)
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, handle_sigterm)

    MAX_RETRIES = 5
    scan_generator = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"PyRPlidar Info : Starting scan (attempt {attempt+1}/{MAX_RETRIES})...", flush=True)
            scan_generator = lidar.force_scan()
            _test = next(scan_generator()) 
            print("PyRPlidar Info : Scan started successfully.", flush=True)
            break
        except Exception as e:
            print(f"PyRPlidar Error : {e}", flush=True)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return

    buf = deque()
    last_send = time.perf_counter()
    packet_count = 0

    try:
        # scan_generator is a function that returns the iterator in some versions, 
        # or is the iterator itself. Let's handle both.
        it = scan_generator() if callable(scan_generator) else scan_generator
        for scan in it:
            now = time.perf_counter()
            
            dist_mm = float(scan.distance)
            if CONFIG["MIN_DIST"] <= dist_mm <= CONFIG["MAX_DIST"]:
                angle = float(scan.angle)
                x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, CONFIG["ANGLE_OFFSET"])

                if in_roi(x_mm, y_mm, CONFIG["ROI_WIDTH"], CONFIG["ROI_DEPTH"]):
                    x01, y01 = normalize_xy01(x_mm, y_mm, CONFIG["ROI_WIDTH"], CONFIG["ROI_DEPTH"])
                    gx, gy = quantize(x01, y01, CONFIG["GRID_STEP"])
                    buf.append((now, x01, y01, gx, gy))

            # Purge
            cutoff = now - (CONFIG["WINDOW_MS"] / 1000.0)
            while buf and buf[0][0] < cutoff:
                buf.popleft()

            # Periodic Send
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
                    if c >= CONFIG["MIN_HITS"]:
                        sx, sy = sums[key]
                        points.append({"x": round(sx / c, 4), "y": round(sy / c, 4)})

                if points:
                    if len(points) > CONFIG["MAX_POINTS"]:
                        step = len(points) / CONFIG["MAX_POINTS"]
                        points = [points[int(i * step)] for i in range(CONFIG["MAX_POINTS"])]

                    payload = {
                        "type": "lidar_points",
                        "t": time.time(),
                        "count": len(points),
                        "points": points,
                        "roi": {"w": CONFIG["ROI_WIDTH"], "d": CONFIG["ROI_DEPTH"]}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    
                    # Broadcast to all targets
                    for ip in UDP_TARGETS:
                        try:
                            sock.sendto(data, (ip, UDP_PORT))
                        except:
                            pass
                            
                    packet_count += 1
                    if packet_count % 100 == 0:
                        print(f"UDP Info : Sent {packet_count} packets. Points in ROI: {len(points)}", flush=True)

                last_send = now

    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        try:
            lidar.stop()
            lidar.set_motor_pwm(0)
            lidar.disconnect()
            sock.close()
        except:
            pass

if __name__ == "__main__":
    main()
