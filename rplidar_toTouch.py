import math
import time
import socket
import asyncio
from collections import deque, defaultdict

import pygame

# rplidarc1 (repo dsaadatmandi)
from scanner import RPLidar  # <-- important: c'est comme dans le README rplidarc1

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
# Lidar (C1)
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 0.2  # rplidarc1 utilise des timeouts courts (voir README)

MIN_DISTANCE_MM = 50
MAX_DISTANCE_MM = 3000

# -----------------------------
# ROI + orientation
# -----------------------------
ROI_WIDTH_MM = 950
ROI_DEPTH_MM = 950
ANGLE_OFFSET_DEG = 0.0

# -----------------------------
# Pygame viz
# -----------------------------
WIN_W, WIN_H = 900, 900
BG = (12, 12, 16)
GRID = (30, 30, 42)
AXIS = (70, 70, 95)
PTS = (240, 240, 255)
TXT = (190, 190, 210)

POINT_RADIUS = 3
DRAW_GRID = True
DRAW_AXES = True


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
    return int(x01 / step), int(y01 / step)


def build_xy_packet(points):
    lines = ["x\ty"]
    for x, y in points:
        lines.append(f"{x:.4f}\t{y:.4f}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def xy01_to_screen(x01: float, y01: float, w: int, h: int):
    return int(x01 * (w - 1)), int(y01 * (h - 1))


def draw_grid(screen, w, h):
    for i in range(1, 10):
        x = int(i * w / 10)
        y = int(i * h / 10)
        pygame.draw.line(screen, GRID, (x, 0), (x, h), 1)
        pygame.draw.line(screen, GRID, (0, y), (w, y), 1)


def draw_overlay(screen, font, points_count, raw_buf_count, window_ms, send_hz, fps):
    pad = 10
    lines = [
        f"points sent: {points_count}",
        f"raw samples in window: {raw_buf_count}  (WINDOW_MS={window_ms})",
        f"SEND_HZ: {send_hz:.1f}   FPS(viz): {fps:.1f}",
        "ESC / Close window to quit",
    ]
    y = pad
    for s in lines:
        surf = font.render(s, True, TXT)
        screen.blit(surf, (pad, y))
        y += surf.get_height() + 4


async def main_async():
    # UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (UDP_IP, UDP_PORT)

    # Pygame init (DOIT être dans le thread principal)
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("RPLIDAR C1 ROI (x,y normalized 0..1)")
    font = pygame.font.SysFont("monospace", 16)
    clock = pygame.time.Clock()

    # Lidar (rplidarc1)
    lidar = RPLidar(PORT, BAUDRATE, timeout=TIMEOUT_S)

    # Buffer glissant: (t, x01, y01, gx, gy)
    buf = deque()
    window_s = WINDOW_MS / 1000.0

    last_send = time.perf_counter()
    last_viz = time.perf_counter()

    latest_points = []
    running = True

    # Lance le scan en tâche asyncio (alimente lidar.output_queue)
    scan_task = asyncio.create_task(lidar.simple_scan(make_return_dict=False))

    try:
        while running:
            now = time.perf_counter()

            # --- events pygame ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            # --- consommer des mesures depuis la queue (non bloquant) ---
            # On vide la queue pour rattraper le débit
            drained = 0
            while not lidar.output_queue.empty():
                data = await lidar.output_queue.get()
                drained += 1

                angle = float(data["a_deg"])
                dist_mm = float(data["d_mm"])

                if MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM:
                    x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)
                    if in_roi(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM):
                        x01, y01 = normalize_xy01(x_mm, y_mm, ROI_WIDTH_MM, ROI_DEPTH_MM)
                        gx, gy = quantize(x01, y01, GRID_STEP)
                        buf.append((now, x01, y01, gx, gy))

            # purge fenêtre glissante
            cutoff = now - window_s
            while buf and buf[0][0] < cutoff:
                buf.popleft()

            # --- envoi UDP périodique ---
            if (now - last_send) >= SEND_PERIOD:
                counts = defaultdict(int)
                sums = defaultdict(lambda: [0.0, 0.0])

                for _t, x01, y01, gx, gy in buf:
                    k = (gx, gy)
                    counts[k] += 1
                    sums[k][0] += x01
                    sums[k][1] += y01

                points = []
                for k, c in counts.items():
                    if c >= MIN_HITS:
                        sx, sy = sums[k]
                        points.append((sx / c, sy / c))

                if len(points) > MAX_POINTS_PER_PACKET:
                    step = len(points) / MAX_POINTS_PER_PACKET
                    points = [points[int(i * step)] for i in range(MAX_POINTS_PER_PACKET)]

                sock.sendto(build_xy_packet(points), target)
                latest_points = points
                last_send = now

            # --- viz ~60fps ---
            if (now - last_viz) >= (1.0 / 60.0):
                screen.fill(BG)

                if DRAW_GRID:
                    draw_grid(screen, WIN_W, WIN_H)

                if DRAW_AXES:
                    pygame.draw.rect(screen, AXIS, pygame.Rect(0, 0, WIN_W - 1, WIN_H - 1), 1)
                    cx = int(0.5 * (WIN_W - 1))
                    pygame.draw.line(screen, AXIS, (cx, 0), (cx, WIN_H), 1)

                for x01, y01 in latest_points:
                    x, y = xy01_to_screen(x01, y01, WIN_W, WIN_H)
                    pygame.draw.circle(screen, PTS, (x, y), POINT_RADIUS)

                fps = clock.get_fps()
                draw_overlay(
                    screen, font,
                    points_count=len(latest_points),
                    raw_buf_count=len(buf),
                    window_ms=WINDOW_MS,
                    send_hz=SEND_HZ,
                    fps=fps
                )

                pygame.display.flip()
                clock.tick(120)
                last_viz = now

            # Laisse respirer l’event loop
            await asyncio.sleep(0)

    except KeyboardInterrupt:
        pass
    finally:
        # stop scan
        try:
            lidar.stop_event.set()
        except Exception:
            pass

        # attend la fin du task scan
        try:
            await asyncio.wait_for(scan_task, timeout=1.0)
        except Exception:
            pass

        # shutdown / reset
        try:
            lidar.shutdown()
        except Exception:
            try:
                lidar.reset()
            except Exception:
                pass

        try:
            sock.close()
        except Exception:
            pass

        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main_async())
