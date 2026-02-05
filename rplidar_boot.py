import math
import time
import pygame
from pyrplidar import PyRPlidar

# -----------------------------
# Screen / UI config
# -----------------------------
WIDTH, HEIGHT = 900, 900
CENTER = (WIDTH // 2, HEIGHT // 2 + 150)  # un peu plus bas pour avoir de l'espace UI en haut

BLACK = (0, 0, 0)
DARK_GREEN = (0, 90, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
RED = (255, 70, 70)
WHITE = (255, 255, 255)
CYAN = (0, 200, 255)
MAGENTA = (255, 0, 255)

# -----------------------------
# Lidar config (calquée sur ton script)
# -----------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 460800
TIMEOUT_S = 3

MOTOR_PWM = 500
STARTUP_DELAY_S = 2.0

MIN_DISTANCE_MM = 50
MAX_DISTANCE_MM = 3000

# Radar scale (pixels/mm)
SCALE = (WIDTH * 0.45) / MAX_DISTANCE_MM

# ROI (1m x 1m) en mm dans le repère "devant"
ROI_HALF_WIDTH_MM = 500   # x ∈ [-500, +500]
ROI_DEPTH_MM = 1000       # y ∈ [0, 1000]

# Orientation: 0° = "devant" (vers le bas du cadre)
ANGLE_OFFSET_DEG = 0.0

# Détection fin de tour
WRAP_HIGH_DEG = 350.0
WRAP_LOW_DEG = 10.0


def polar_to_xy_mm(angle_deg: float, distance_mm: float, angle_offset_deg: float):
    """Repère: y avant, x gauche/droite. angle 0° pointe vers l'avant."""
    a = math.radians(angle_deg + angle_offset_deg)
    x = distance_mm * math.sin(a)
    y = distance_mm * math.cos(a)
    return x, y


def xy_mm_to_screen(x_mm: float, y_mm: float):
    """Projette (x,y) mm vers coordonnées écran. y avant = vers le bas de l'écran."""
    x_px = CENTER[0] + int(x_mm * SCALE)
    y_px = CENTER[1] + int(y_mm * SCALE)
    return x_px, y_px


def in_roi(x_mm: float, y_mm: float) -> bool:
    return (-ROI_HALF_WIDTH_MM <= x_mm <= ROI_HALF_WIDTH_MM) and (0.0 <= y_mm <= ROI_DEPTH_MM)


def dist_color(dist_mm: float):
    if dist_mm <= 1000:
        return RED
    elif dist_mm <= 2000:
        return YELLOW
    return GREEN


def build_background(font_small, font_title):
    """Surface statique: cercles + labels + titre (évite de redessiner tout à chaque tour)."""
    bg = pygame.Surface((WIDTH, HEIGHT))
    bg.fill(BLACK)

    # Cercles de référence (tous les 50 cm)
    for r in range(500, MAX_DISTANCE_MM + 1, 500):
        pygame.draw.circle(bg, DARK_GREEN, CENTER, int(r * SCALE), 1)
        label = font_small.render(f"{r//10} cm", True, WHITE)
        bg.blit(label, (CENTER[0] + int(r * SCALE) - 25, CENTER[1] - 10))

    # Axe avant (ligne centrale)
    pygame.draw.line(bg, DARK_GREEN, CENTER, (CENTER[0], CENTER[1] + int(MAX_DISTANCE_MM * SCALE)), 1)

    # Titre
    title_surface = font_title.render("RPLidar C1 - ROI 1m x 1m (UI)", True, WHITE)
    bg.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 20))

    return bg


def draw_roi_rect(screen):
    """Dessine le carré ROI 1m×1m devant le lidar (en mm => pixels)."""
    # ROI en coords mm: x [-500, +500], y [0, 1000]
    x0, y0 = xy_mm_to_screen(-ROI_HALF_WIDTH_MM, 0)
    x1, y1 = xy_mm_to_screen( ROI_HALF_WIDTH_MM, ROI_DEPTH_MM)

    # pygame rect needs top-left and width/height
    left = min(x0, x1)
    top = min(y0, y1)
    w = abs(x1 - x0)
    h = abs(y1 - y0)

    pygame.draw.rect(screen, CYAN, pygame.Rect(left, top, w, h), 2)

    # petit repère "avant"
    pygame.draw.circle(screen, CYAN, xy_mm_to_screen(0, ROI_DEPTH_MM), 4)


def main():
    global ANGLE_OFFSET_DEG

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RPLidar C1 UI")
    clock = pygame.time.Clock()

    font_small = pygame.font.SysFont(None, 20)
    font_ui = pygame.font.SysFont(None, 22)
    font_title = pygame.font.SysFont(None, 28, bold=True)

    # Pré-render background
    background = build_background(font_small, font_title)

    # Lidar init
    lidar = PyRPlidar()
    lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
    lidar.set_motor_pwm(MOTOR_PWM)
    time.sleep(STARTUP_DELAY_S)

    # Pattern identique à ton script
    scan_generator = lidar.force_scan()

    running = True
    paused = False
    show_all_points = True   # True: affiche tout, False: affiche seulement ROI
    points_all = []          # points du tour (pour affichage)
    points_roi = []          # points filtrés ROI (pour stats + affichage)
    prev_angle = None
    sweep_idx = 0

    try:
        for scan in scan_generator():
            # Events UI
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False

                    elif event.key == pygame.K_SPACE:
                        paused = not paused

                    elif event.key == pygame.K_a:
                        show_all_points = not show_all_points

                    # Ajuster l'offset d'angle
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

            if not running:
                break

            if paused:
                # on ne consomme pas/affiche pas, mais on laisse la boucle tourner
                clock.tick(60)
                continue

            angle = float(scan.angle)
            dist = float(scan.distance)  # mm

            # Filtrage distance
            if MIN_DISTANCE_MM <= dist <= MAX_DISTANCE_MM:
                x_mm, y_mm = polar_to_xy_mm(angle, dist, ANGLE_OFFSET_DEG)

                # Stocker pour display (tous points)
                points_all.append((x_mm, y_mm, dist))

                # Filtrer ROI
                if in_roi(x_mm, y_mm):
                    points_roi.append((x_mm, y_mm, dist))

            # Détection fin de tour (wrap)
            if prev_angle is not None:
                wrapped = (prev_angle > WRAP_HIGH_DEG and angle < WRAP_LOW_DEG) or (angle < prev_angle)
                if wrapped:
                    sweep_idx += 1

                    # Redraw frame
                    screen.blit(background, (0, 0))
                    draw_roi_rect(screen)

                    # Choix d'affichage: tous points ou seulement ROI
                    if show_all_points:
                        for x_mm, y_mm, dist_mm in points_all:
                            px, py = xy_mm_to_screen(x_mm, y_mm)
                            pygame.draw.circle(screen, dist_color(dist_mm), (px, py), 2)
                    else:
                        for x_mm, y_mm, dist_mm in points_roi:
                            px, py = xy_mm_to_screen(x_mm, y_mm)
                            pygame.draw.circle(screen, MAGENTA, (px, py), 3)

                    # UI overlay
                    ui_lines = [
                        f"Sweep: {sweep_idx}",
                        f"Points (all): {len(points_all)}",
                        f"Points (ROI 1m x 1m): {len(points_roi)}",
                        f"Angle offset: {ANGLE_OFFSET_DEG:.1f} deg",
                        "Controls: Q/Esc=Quit | Space=Pause | A=Toggle all/ROI | Arrows=Offset (±1/±5) | R=Reset offset",
                    ]

                    y = 60
                    for line in ui_lines:
                        surf = font_ui.render(line, True, WHITE)
                        screen.blit(surf, (20, y))
                        y += 22

                    pygame.display.flip()
                    clock.tick(60)

                    # Reset buffers pour prochain tour
                    points_all.clear()
                    points_roi.clear()

            prev_angle = angle

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        # Stop propre
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
        pygame.quit()


if __name__ == "__main__":
    main()
