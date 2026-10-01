import sys
import os
from pathlib import Path

# Ensure src is on python path
src_dir = str(Path(__file__).parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import signal
import time
from PyQt6.QtWidgets import QApplication

from foxhole_hud.controller import StrategicControlLoop, ControllerSignals
from foxhole_hud.overlay import StrategicOverlayHUD

PID_FILE = "/dev/shm/foxhole_hud.pid"

def kill_previous_instance():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(0.2)
        except Exception:
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def main():
    os.environ["DISPLAY"] = ":0"
    os.environ["XAUTHORITY"] = "/home/user/.Xauthority"
    kill_previous_instance()
    
    app = QApplication(sys.argv)
    
    signals = ControllerSignals()
    controller = StrategicControlLoop(signals)
    
    hud = StrategicOverlayHUD(controller)
    hud.show()
    
    signals.frame_processed.connect(hud.update)
    controller.start()
    
    def signal_handler(sig, frame):
        print("[Supervisor] Clean exit...")
        controller.stop()
        app.quit()
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
