import math
import time
import socket
import pygame
import threading
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import deque, defaultdict
from pyrplidar import PyRPlidar

# -----------------------------
# UDP target
# -----------------------------
UDP_IP = "10.0.1.5"
UDP_PORT = 5005
SEND_HZ = 60.0           # latence ~ 1/60 = 16.6ms
SEND_PERIOD = 1.0 / SEND_HZ

# -----------------------------
# Web Stream Config
# -----------------------------
STREAM_PORT = 8080
STREAM_HZ = 30.0         # Limiter le CPU (30 fps suffisent pour le web)
STREAM_PERIOD = 1.0 / STREAM_HZ

# -----------------------------
# Visualization / UI
# -----------------------------
WIDTH, HEIGHT = 800, 800
BLACK   = (15, 15, 20)
GRID    = (40, 40, 50)
WHITE   = (255, 255, 255)
CYAN    = (0, 255, 255)
MAGENTA = (255, 0, 255)
RED     = (255, 50, 50)

# -----------------------------
# Micro-buffer + nettoyage
# -----------------------------
WINDOW_MS = 70            # fenêtre glissante courte (50-90ms)
GRID_STEP = 0.02          # taille cellule en coords 0..1 (0.01 = 1% => ~1 cm si ROI=1m)
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
ROI_WIDTH_MM = 950
ROI_DEPTH_MM = 950
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


# --- Classes pour le streaming Web ---

class StreamingOutput:
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def update(self, frame):
        with self.condition:
            self.frame = frame
            self.condition.notify_all()

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with global_output.condition:
                        global_output.condition.wait()
                        frame = global_output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception:
                pass
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return # Désactiver les logs envahissants dans le terminal

global_output = StreamingOutput()


def main():
    # --- Networking ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (UDP_IP, UDP_PORT)

    # --- Pygame Init ---
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RPLidar C1 - TouchDesigner Bridge & Viz")
    font = pygame.font.SysFont(None, 24)

    # Padding and scaling for visualization
    padding = 50
    draw_w = WIDTH - 2 * padding
    draw_h = HEIGHT - 2 * padding

    def to_screen(x01, y01):
        sx = padding + x01 * draw_w
        sy = padding + y01 * draw_h
        return int(sx), int(sy)

    # --- Streaming Server Start ---
    server = HTTPServer(('', STREAM_PORT), StreamingHandler)
    stream_thread = threading.Thread(target=server.serve_forever, daemon=True)
    stream_thread.start()
    print(f"Serveur Web actif sur http://localhost:{STREAM_PORT} (ou l'IP de ce Mac)")

    # --- Lidar Init ---
    lidar = PyRPlidar()
    try:
        lidar.connect(port=PORT, baudrate=BAUDRATE, timeout=TIMEOUT_S)
        lidar.set_motor_pwm(MOTOR_PWM)
        time.sleep(STARTUP_DELAY_S)
        scan_generator = lidar.force_scan()
    except Exception as e:
        print(f"Error connecting to Lidar: {e}")
        return

    # Buffer glissant: (t, x01, y01, gx, gy)
    buf = deque()
    window_s = WINDOW_MS / 1000.0
    last_send = time.perf_counter()
    last_stream = 0
    running = True

    try:
        for scan in scan_generator():
            # 0) Events Pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False

            if not running:
                break

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

            # 3) Envoi périodique + Visualisation
            if (now - last_send) >= SEND_PERIOD:
                counts = defaultdict(int)
                sums = defaultdict(lambda: [0.0, 0.0])

                for _t, x01, y01, gx, gy in buf:
                    key = (gx, gy)
                    counts[key] += 1
                    sums[key][0] += x01
                    sums[key][1] += y01

                points_to_send = []
                for key, c in counts.items():
                    if c >= MIN_HITS:
                        sx, sy = sums[key]
                        points_to_send.append((sx / c, sy / c))

                # --- Draw ---
                screen.fill(BLACK)
                
                # Draw ROI boundary
                r_left, r_top = to_screen(0, 0)
                r_right, r_bottom = to_screen(1, 1)
                pygame.draw.rect(screen, GRID, (r_left, r_top, r_right-r_left, r_bottom-r_top), 1)

                # Draw Lidar Source (0.5 on X center, 0 on Y top)
                lx, ly = to_screen(0.5, 0)
                pygame.draw.circle(screen, WHITE, (lx, ly), 5)

                # Draw raw points from buffer (fading magenta)
                for _t, x01, y01, gx, gy in buf:
                    px, py = to_screen(x01, y01)
                    pygame.draw.rect(screen, MAGENTA, (px-1, py-1, 2, 2))

                # Draw aggregated points (sent to TD)
                for x01, y01 in points_to_send:
                    px, py = to_screen(x01, y01)
                    pygame.draw.circle(screen, CYAN, (px, py), 4)

                # Info
                status_txt = f"Sending {len(points_to_send)} points to {UDP_IP}:{UDP_PORT} @ {SEND_HZ}Hz"
                txt_surf = font.render(status_txt, True, WHITE)
                screen.blit(txt_surf, (10, HEIGHT - 30))

                pygame.display.flip()

                # --- Capture pour le Stream ---
                if (now - last_stream) >= STREAM_PERIOD:
                    try:
                        img_buffer = io.BytesIO()
                        # Pygame supporte le JPEG via sauvegarde dans un buffer avec l'extension suggérée
                        pygame.image.save(screen, "screenshot.jpg")
                        with open("screenshot.jpg", "rb") as f:
                            global_output.update(f.read())
                        last_stream = now
                    except Exception as e:
                        print(f"Error capturing for stream: {e}")

                # --- Send ---
                if len(points_to_send) > MAX_POINTS_PER_PACKET:
                    step = len(points_to_send) / MAX_POINTS_PER_PACKET
                    points_to_send = [points_to_send[int(i * step)] for i in range(MAX_POINTS_PER_PACKET)]

                # Toujours envoyer le paquet (au moins le header si points_to_send est vide)
                sock.sendto(build_xy_packet(points_to_send), target)

                last_send = now

    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")

    finally:
        try:
            lidar.stop()
            lidar.set_motor_pwm(0)
            lidar.disconnect()
        except: pass
        try:
            sock.close()
            server.shutdown()
        except: pass
        pygame.quit()


if __name__ == "__main__":
    main()

