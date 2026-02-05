import math
import time
import json
import socket
import pygame
from pyrplidar import PyRPlidar

# -----------------------------
# UDP config
# -----------------------------
UDP_IP = "192.168.0.12"
UDP_PORT = 5005
UDP_SEND_ALL_POINTS = False  # False = envoie uniquement points ROI

# -----------------------------
# Window / UI
# -----------------------------
WIDTH, HEIGHT = 900, 900
BLACK = (0, 0, 0)
GRID = (0, 70, 0)
WHITE = (255, 255, 255)
CYAN = (0, 200, 255)
MAGENTA = (255, 0, 255)
RED = (255, 70, 70)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)

# -----------------------------
# Lidar config
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3
MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

MIN_DISTANCE_MM = 50
MAX_DISTANCE_MM = 3000

# -----------------------------
# ROI (modifiable en live)
# -----------------------------
roi_width_mm = 1000   # largeur totale (x: -w/2..+w/2)
roi_depth_mm = 1000   # profondeur (y: 0..depth)
ROI_STEP_MM = 50      # pas d’ajustement

# Vue / zoom
zoom = 1.0
ZOOM_STEP = 0.1
padding_ratio = 0.12

# Orientation
ANGLE_OFFSET_DEG = 0.0

# Détection fin de tour
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0


def clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def dist_color(dist_mm: float):
    if dist_mm <= 1000:
        return RED
    elif dist_mm <= 2000:
        return YELLOW
    return GREEN


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    """
    Repère:
      y positif = avant (bas du cadre)
      x positif = droite
      angle 0° = avant
    """
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def in_roi(x_mm: float, y_mm: float, roi_w_mm: float, roi_d_mm: float) -> bool:
    half = roi_w_mm / 2.0
    return (-half <= x_mm <= half) and (0.0 <= y_mm <= roi_d_mm)


def normalize_xy01(x_mm: float, y_mm: float, roi_w_mm: float, roi_d_mm: float):
    """
    Normalisation:
      x01: 0 gauche, 1 droite
      y01: 0 haut (lidar), 1 bas
    """
    half = roi_w_mm / 2.0
    x01 = (x_mm + half) / roi_w_mm
    y01 = y_mm / roi_d_mm
    return clamp01(x01), clamp01(y01)


def compute_view_transform(roi_w_mm: float, roi_d_mm: float, zoom: float, padding_ratio: float):
    pad_x = roi_w_mm * padding_ratio
    pad_y = roi_d_mm * padding_ratio

    world_w = roi_w_mm + 2 * pad_x
    world_h = roi_d_mm + 2 * pad_y

    scale_fit = min(WIDTH / world_w, HEIGHT / world_h)
    scale = scale_fit * zoom

    roi_center_x = 0.0
    roi_center_y = roi_d_mm / 2.0
    screen_center = (WIDTH / 2.0, HEIGHT / 2.0)

    def world_to_screen(x_mm: float, y_mm: float):
        sx = screen_center[0] + (x_mm - roi_center_x) * scale
        sy = screen_center[1] + (y_mm - roi_center_y) * scale
        return int(sx), int(sy)

    return world_to_screen, scale


def draw_grid_and_roi(screen, world_to_screen, roi_w_mm, roi_d_mm, font):
    screen.fill(BLACK)

    grid_step = 100  # 10 cm
    half = roi_w_mm / 2.0

    # vertical lines
    x = -half
    while x <= half + 1e-6:
        p0 = world_to_screen(x, 0)
        p1 = world_to_screen(x, roi_d_mm)
        pygame.draw.line(screen, GRID, p0, p1, 1)
        x += grid_step

    # horizontal lines
    y = 0
    while y <= roi_d_mm + 1e-6:
        p0 = world_to_screen(-half, y)
        p1 = world_to_screen(half, y)
        pygame.draw.line(screen, GRID, p0, p1, 1)
        y += grid_step

    # ROI rect
    top_left = world_to_screen(-half, 0)
    bottom_right = world_to_screen(half, roi_d_mm)
    left = min(top_left[0], bottom_right[0])
    top = min(top_left[1], bottom_right[1])
    w = abs(bottom_right[0] - top_left[0])
    h = abs(bottom_right[1] - top_left[1])
    pygame.draw.rect(screen, CYAN, pygame.Rect(left, top, w, h), 3)

    # lidar origin marker at (0,0)
    ox, oy = world_to_screen(0, 0)
    pygame.draw.circle(screen, WHITE, (ox, oy), 5)
    fx, fy = world_to_screen(0, min(roi_d_mm, 200))
    pygame.draw.line(screen, WHITE, (ox, oy), (fx, fy), 2)

    label = font.render("ROI view (zoomed) + UDP", True, WHITE)
    screen.blit(label, (20, 20))


def main():
    global roi_width_mm, roi_depth_mm, zoom, ANGLE_OFFSET_DEG

    # UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_target = (UDP_IP, UDP_PORT)

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RPLidar C1 - ROI Zoom UI + UDP")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 22)
    font_small = pygame.font.SysFont(None, 20)

    # Lidar init
    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # même pattern que ton script original
    scan_generator = lidar.force_scan()

    running = True
    paused = False
    show_all_points = False  # UI view mode
    prev_angle = None
    sweep_idx = 0

    points_all = []   # (x_mm, y_mm, dist_mm, angle_deg)
    points_roi = []   # (x_mm, y_mm, dist_mm, angle_deg)

    try:
        for scan in scan_generator():
            # ---- events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_a:
                        show_all_points = not show_all_points

                    # angle offset
                    elif event.key == pygame.K_LEFT:
                        ANGLE_OFFSET_DEG -= 5.0
                    elif event.key == pygame.K_RIGHT:
                        ANGLE_OFFSET_DEG += 5.0
                    elif event.key == pygame.K_DOWN:
                        ANGLE_OFFSET_DEG -= 1.0
                    elif event.key == pygame.K_UP:
                        ANGLE_OFFSET_DEG += 1.0
                    elif event.key == pygame.K_r:
                        ANGLE_OFFSET_DEG = 0.0

                    # ROI size
                    elif event.key == pygame.K_w:
                        roi_width_mm = min(4000, roi_width_mm + ROI_STEP_MM)
                    elif event.key == pygame.K_s:
                        roi_width_mm = max(200, roi_width_mm - ROI_STEP_MM)
                    elif event.key == pygame.K_e:
                        roi_depth_mm = min(4000, roi_depth_mm + ROI_STEP_MM)
                    elif event.key == pygame.K_d:
                        roi_depth_mm = max(200, roi_depth_mm - ROI_STEP_MM)

                    # zoom
                    elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        zoom = min(5.0, zoom + ZOOM_STEP)
                    elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                        zoom = max(0.2, zoom - ZOOM_STEP)
                    elif event.key == pygame.K_z:
                        zoom = 1.0

            if not running:
                break

            if paused:
                clock.tick(60)
                continue

            angle = float(scan.angle)
            dist_mm = float(scan.distance)

            if MIN_DISTANCE_MM <= dist_mm <= MAX_DISTANCE_MM:
                x_mm, y_mm = polar_to_xy_mm(angle, dist_mm, ANGLE_OFFSET_DEG)
                points_all.append((x_mm, y_mm, dist_mm, angle))

                if in_roi(x_mm, y_mm, roi_width_mm, roi_depth_mm):
                    points_roi.append((x_mm, y_mm, dist_mm, angle))

            # ---- end-of-sweep
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG) or (angle < prev_angle)
                if wrapped:
                    sweep_idx += 1

                    # --- Build UDP payload (normalized 0..1)
                    pts_src = points_all if UDP_SEND_ALL_POINTS else points_roi
                    pts01 = []
                    half = roi_width_mm / 2.0

                    for x_mm, y_mm, d_mm, a_deg in pts_src:
                        # si on envoie "all", on normalise quand même par rapport à la ROI (clamp)
                        x01, y01 = normalize_xy01(x_mm, y_mm, roi_width_mm, roi_depth_mm)
                        pts01.append({
                            "x": round(x01, 4),
                            "y": round(y01, 4),
                            "d_mm": int(round(d_mm)),
                            "a_deg": round(a_deg, 2),
                        })

                    payload = {
                        "t": time.time(),
                        "sweep": sweep_idx,
                        "roi_mm": {"width": roi_width_mm, "depth": roi_depth_mm},
                        "angle_offset_deg": ANGLE_OFFSET_DEG,
                        "count": len(pts01),
                        "points": pts01
                    }

                    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    sock.sendto(data, udp_target)

                    # --- UI draw
                    world_to_screen, _ = compute_view_transform(roi_width_mm, roi_depth_mm, zoom, padding_ratio)
                    draw_grid_and_roi(screen, world_to_screen, roi_width_mm, roi_depth_mm, font)

                    if show_all_points:
                        for x_mm, y_mm, d, _a in points_all:
                            px, py = world_to_screen(x_mm, y_mm)
                            pygame.draw.circle(screen, dist_color(d), (px, py), 2)
                    else:
                        for x_mm, y_mm, d, _a in points_roi:
                            px, py = world_to_screen(x_mm, y_mm)
                            pygame.draw.circle(screen, MAGENTA, (px, py), 3)

                    ui_lines = [
                        f"Sweep: {sweep_idx}   Sent UDP -> {UDP_IP}:{UDP_PORT}   Points sent: {len(pts01)}",
                        f"Mode view: {'ALL' if show_all_points else 'ROI only'} (toggle A)",
                        f"ROI: width={roi_width_mm}mm  depth={roi_depth_mm}mm (W/S width, E/D depth)",
                        f"Zoom: {zoom:.1f} (+/-)  Z reset",
                        f"Angle offset: {ANGLE_OFFSET_DEG:.1f} deg (arrows)  R reset",
                        f"Points(all): {len(points_all)}  Points(ROI): {len(points_roi)}",
                        "Controls: Q/Esc quit | Space pause",
                    ]
                    y_txt = HEIGHT - 22 * (len(ui_lines) + 1)
                    for line in ui_lines:
                        surf = font_small.render(line, True, WHITE)
                        screen.blit(surf, (20, y_txt))
                        y_txt += 22

                    pygame.display.flip()
                    clock.tick(60)

                    points_all.clear()
                    points_roi.clear()

            prev_angle = angle

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
        pygame.quit()


if __name__ == "__main__":
    main()
