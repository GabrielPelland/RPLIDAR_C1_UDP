import math
import time
import socket
from collections import deque, defaultdict

import pygame
from pyrplidar import PyRPlidar
from pyrplidar_protocol import PyRPlidarProtocolError  # pour catcher le sync mismatch

# -----------------------------
# UDP target
# -----------------------------
UDP_IP = "10.0.1.5"
UDP_PORT = 5005
SEND_HZ = 60.0
SEND_PERIOD = 1.0 / SEND_HZ

# -----------------------------
# Micro-buffer + nettoyage
# -----------------------------
WINDOW_MS = 70
GRID_STEP = 0.01
MIN_HITS = 2
MAX_POINTS_PER_PACKET = 600

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
ROI_WIDTH_MM = 950
ROI_DEPTH_MM = 950
ANGLE_OFFSET_DEG = 0.0

# -----------------------------
# Pygame UI / Viz
# -----------------------------
WIN_W, WIN_H = 900, 900
PANEL_H = 110
BG = (12, 12, 16)
GRID_COL = (35, 35, 50)
AXIS = (80, 80, 110)
PTS = (240, 240, 255)
TXT = (200, 200, 220)
PANEL = (18, 18, 26)
WARN = (255, 170, 80)
OK = (120, 255, 160)

POINT_RADIUS = 3
DRAW_GRID = True
DRAW_AXES = True
FPS_LIMIT = 120


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def in_roi(x_mm: float, y_mm: float, w_mm: float, d_mm: float) -> bool:
    half = w_mm / 2.0
    return (-half <= x_mm <= half) and (0.0 <= y_mm <= d_mm)


def normalize_xy01(x_mm: float, y_mm: float, w_mm: float, d_mm: float):
    half = w_mm / 2.0
    x01 = (x_mm + half) / w_mm
    y01 = y_mm / d_mm
    return clamp01(x01), clamp01(y01)


def quantize(x01: float, y01: float, step: float):
    gx = int(x01 / step)
    gy = int(y01 / step)
    return gx, gy


def build_xy_packet(points):
    lines = ["x\ty"]
    for x, y in points:
        lines.append(f"{x:.4f}\t{y:.4f}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def xy01_to_screen(x01: float, y01: float, w: int, h: int):
    x = int(x01 * (w - 1))
    y = int(y01 * (h - 1))
    return x, y


def draw_grid(surface, w, h):
    for i in range(1, 10):
        x = int(i * w / 10)
        y = int(i * h / 10)
        pygame.draw.line(surface, GRID_COL, (x, 0), (x, h), 1)
        pygame.draw.line(surface, GRID_COL, (0, y), (w, y), 1)


def draw_panel(screen, font, lines, status_line=None, warning=None):
    y0 = WIN_H - PANEL_H
    pygame.draw.rect(screen, PANEL, pygame.Rect(0, y0, WIN_W, PANEL_H))
    pygame.draw.line(screen, GRID_COL, (0, y0), (WIN_W, y0), 1)

    y = y0 + 10
    for s in lines:
        surf = font.render(s, True, TXT)
        screen.blit(surf, (10, y))
        y += surf.get_height() + 4

    if status_line:
        text, color = status_line
        surf = font.render(text, True, color)
        screen.blit(surf, (10, y0 + PANEL_H - surf.get_height() - 10))

    if warning:
        surf = font.render(warning, True, WARN)
        screen.blit(surf, (10, y0 + PANEL_H - surf.get_height() - 10))


def safe_lidar_stop(lidar):
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


def connect_and_get_scan_generator(lidar, status_cb=None, max_tries=999999):
    """
    Essaie d'obtenir un scan_generator = lidar.force_scan()
    en gérant les sync mismatch par reconnect/stop/pause.
    """
    tries = 0
    while True:
        tries += 1
        try:
            if status_cb:
                status_cb(f"Connecting... (try #{tries})", OK)

            lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
            lidar.set_motor_pwm(MOTOR_PWM)
            time.sleep(STARTUP_DELAY_S)

            gen = lidar.force_scan()  # <-- point de crash actuel
            if status_cb:
                status_cb("Connected + scanning.", OK)
            return gen

        except PyRPlidarProtocolError as e:
            # ex: sync bytes mismatched
            if status_cb:
                status_cb(f"Protocol sync error -> retry ({str(e)})", WARN)
            safe_lidar_stop(lidar)
            time.sleep(0.5)

        except Exception as e:
            if status_cb:
                status_cb(f"Error -> retry ({repr(e)})", WARN)
            safe_lidar_stop(lidar)
            time.sleep(0.5)


def main():
    # UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (UDP_IP, UDP_PORT)

    # Pygame
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("RPLidar -> UDP + Viz (ROI normalized 0..1)")
    font = pygame.font.SysFont("monospace", 18)
    clock = pygame.time.Clock()

    # Lidar
    lidar = PyRPlidar()

    # Buffer glissant: (t, x01, y01, gx, gy)
    buf = deque()
    window_s = WINDOW_MS / 1000.0

    last_send = time.perf_counter()
    last_packet_points = []
    last_packet_time = time.perf_counter()

    # UI state
    running = True
    status_line = ("Starting...", OK)

    def set_status(text, color):
        nonlocal status_line
        status_line = (text[:120], color)

    scan_generator = connect_and_get_scan_generator(lidar, status_cb=set_status)

    try:
        while running:
            now = time.perf_counter()

            # ---- events UI ----
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_g:
                        global DRAW_GRID
                        DRAW_GRID = not DRAW_GRID
                    elif event.key == pygame.K_a:
                        global DRAW_AXES
                        DRAW_AXES = not DRAW_AXES
                    elif event.key == pygame.K_r:
                        # Reconnect manuel
                        set_status("Manual reconnect requested...", WARN)
                        safe_lidar_stop(lidar)
                        scan_generator = connect_and_get_scan_generator(lidar, status_cb=set_status)

            # ---- lire un scan ----
            try:
                # generator() -> itère des objects scan
                scan = next(scan_generator())
            except StopIteration:
                # rare, mais on reconnect
                set_status("Scan generator ended -> reconnecting...", WARN)
                safe_lidar_stop(lidar)
                scan_generator = connect_and_get_scan_generator(lidar, status_cb=set_status)
                continue
            except PyRPlidarProtocolError as e:
                set_status(f"Protocol error during scan -> reconnect ({str(e)})", WARN)
                safe_lidar_stop(lidar)
                scan_generator = connect_and_get_scan_generator(lidar, status_cb=set_status)
                continue
            except Exception as e:
                set_status(f"Scan read error -> reconnect ({repr(e)})", WARN)
                safe_lidar_stop(lidar)
                scan_generator = connect_and_get_scan_generator(lidar, status_cb=set_status)
                continue

            # ---- ton pipeline inchangé ----
            dist_mm = float(scan.distance)
            if MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM:
                angle = float(scan.angle)
                x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)

                if in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                    x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)
                    gx, gy = quantize(x01, y01, GRID_STEP)
                    buf.append((now, x01, y01, gx, gy))

            cutoff = now - window_s
            while buf and buf[0][0] < cutoff:
                buf.popleft()

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
                last_packet_points = points
                last_packet_time = now

            # ---- render ----
            draw_h = WIN_H - PANEL_H
            screen.fill(BG)

            if DRAW_GRID:
                draw_grid(screen, WIN_W, draw_h)

            if DRAW_AXES:
                pygame.draw.rect(screen, AXIS, pygame.Rect(0, 0, WIN_W - 1, draw_h - 1), 1)
                cx = int(0.5 * (WIN_W - 1))
                pygame.draw.line(screen, AXIS, (cx, 0), (cx, draw_h), 1)

            for x01, y01 in last_packet_points:
                x, y = xy01_to_screen(x01, y01, WIN_W, draw_h)
                pygame.draw.circle(screen, PTS, (x, y), POINT_RADIUS)

            fps = clock.get_fps()
            age_ms = (now - last_packet_time) * 1000.0
            warning = None
            if age_ms > 250:
                warning = f"WARNING: no UDP packet update for {age_ms:.0f} ms"

            lines = [
                f"UDP -> {UDP_IP}:{UDP_PORT}   SEND_HZ={SEND_HZ:.1f}   packet_pts={len(last_packet_points)}",
                f"WINDOW_MS={WINDOW_MS}  GRID_STEP={GRID_STEP:.3f}  MIN_HITS={MIN_HITS}  buf_samples={len(buf)}",
                f"ROI {ROI_WIDTH_MM}x{ROI_DEPTH_MM} mm   ANGLE_OFFSET={ANGLE_OFFSET_DEG:.1f} deg   FPS={fps:.1f}",
                "Keys: ESC quit | G grid | A axes | R reconnect",
            ]
            draw_panel(screen, font, lines, status_line=status_line, warning=warning)

            pygame.display.flip()
            clock.tick(FPS_LIMIT)

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        safe_lidar_stop(lidar)
        try:
            sock.close()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
