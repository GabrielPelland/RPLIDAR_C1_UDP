import time
from pyrplidar import PyRPlidar

lidar = PyRPlidar()
lidar.connect(port="/dev/ttyUSB0", baudrate=460800, timeout=3)

try:
    try:
        lidar.stop()
    except Exception:
        pass
    try:
        lidar.set_motor_pwm(0)
    except Exception:
        pass
    time.sleep(0.2)
finally:
    try:
        lidar.disconnect()
    except Exception:
        pass
