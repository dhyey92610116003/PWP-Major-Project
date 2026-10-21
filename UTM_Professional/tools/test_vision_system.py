import os
import sys
import time

# Ensure UTM_Professional is on path
base_dir = r"d:\utm\UTM_Professional"
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from machine.machine_controller import MachineController
from communication.serial_manager import SerialManager
from config.settings import SettingsManager
from ui.dashboard import Dashboard

def run_vision_test():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    settings = SettingsManager()
    controller = MachineController()
    
    dashboard = Dashboard(controller, settings)
    dashboard.resize(1200, 750)
    dashboard.show()
    
    # Process events to initialize UI
    app.processEvents()
    time.sleep(1.0)
    app.processEvents()
    
    artifact_dir = r"C:\Users\AJAY RAJA\.gemini\antigravity\brain\24b47c10-db2c-4eea-8e8f-5586d6c8d245"
    os.makedirs(artifact_dir, exist_ok=True)
    
    # 1. Dual View Screenshot
    dashboard._set_active_view("dual")
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    dual_shot = dashboard.grab()
    dual_shot.save(os.path.join(artifact_dir, "view_dual.png"))
    print("Dual view screenshot saved.")
    
    # 2. Camera View Screenshot
    dashboard._set_active_view("camera")
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    cam_shot = dashboard.grab()
    cam_shot.save(os.path.join(artifact_dir, "view_camera.png"))
    print("Camera view screenshot saved.")
    
    # 3. Live Graph View Screenshot
    dashboard._set_active_view("graph")
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    graph_shot = dashboard.grab()
    graph_shot.save(os.path.join(artifact_dir, "view_graph.png"))
    print("Graph view screenshot saved.")
    
    # 4. Switch back to Dual View and test Mock Test Run with Auto-Recording
    dashboard._set_active_view("dual")
    dashboard.chk_mock.setChecked(True)
    app.processEvents()
    
    print("Starting simulated test with auto-video recording...")
    dashboard.btn_start.click()
    
    # Let it run for 4 seconds
    start_time = time.time()
    while time.time() - start_time < 4.0:
        app.processEvents()
        time.sleep(0.05)
        
    print(f"Is camera recording: {dashboard.camera_manager.is_recording()}")
    
    # Take a screenshot during live test with video recording and specimen tracking active
    test_run_shot = dashboard.grab()
    test_run_shot.save(os.path.join(artifact_dir, "view_during_test_recording.png"))
    print("Active test recording screenshot saved.")
    
    # Stop the test
    dashboard.btn_stop.click()
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    
    print(f"Recording stopped. Last recorded video: {dashboard.camera_manager.last_recorded_video}")
    if os.path.exists(dashboard.camera_manager.last_recorded_video):
        size_kb = os.path.getsize(dashboard.camera_manager.last_recorded_video) / 1024
        print(f"Verified MP4 video generated on disk! File size: {size_kb:.1f} KB")
        
    # Test Snapshot capture
    snap_path = dashboard.camera_widget.camera_manager.take_snapshot()
    print(f"Snapshot captured: {snap_path}, exists: {os.path.exists(snap_path)}")
    
    # Clean shutdown
    dashboard.camera_manager.stop_camera()
    dashboard.close()
    app.processEvents()
    print("Test run completed cleanly!")

if __name__ == "__main__":
    run_vision_test()
