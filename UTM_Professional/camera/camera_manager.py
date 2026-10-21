"""
UTM Professional v2.5 - Enterprise Vision & Video Recording Subsystem
Integrated Optical Extensometer, Real-time Specimen Object Detector & Telemetry Video Recorder.
Seamlessly interfaces with USB Mobile Cameras, Webcams, and IP Streams.
"""

import os
import sys
import time
import math
import logging
from datetime import datetime

# Suppress noisy OpenCV internal C++ device probe warnings on Windows
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

import cv2
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QMutex, QMutexLocker
from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)

class DetectionMode:
    SPECIMEN_NECKING = "Necking & Contour"
    GAUGE_EXTENSOMETER = "Extensometer"
    MOTION_DEFORMATION = "Deformation Map"
    MANUAL_ROI = "Manual ROI"
    RAW_FEED = "Raw Video Feed"

class CameraWorker(QThread):
    frame_ready = Signal(QImage, dict, dict) # qimage, telemetry, detection_stats
    recording_started = Signal(str)
    recording_stopped = Signal(str, float)
    break_detected = Signal()
    camera_connected = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.mutex = QMutex()
        
        # Source configuration
        self.source_id = 0  # Camera index or URL string
        self.cap = None
        self.target_fps = 30.0
        self.frame_width = 640
        self.frame_height = 480
        self.last_open_attempt = 0.0
        self.retry_interval = 2.0  # Seconds between retry attempts when camera offline
        
        # Detection Mode
        self.detection_mode = DetectionMode.SPECIMEN_NECKING
        self.show_telemetry_hud = True
        self.manual_roi = None # (x, y, w, h)
        
        # Video Recording
        self.is_recording = False
        self.video_writer = None
        self.recording_path = ""
        self.record_start_time = 0.0
        self.frames_recorded = 0
        
        # Live Test Telemetry stamped on frames
        self.telemetry = {
            "load_kN": 0.0,
            "stress_MPa": 0.0,
            "ext_mm": 0.0,
            "strain_pct": 0.0,
            "time_str": "00:00:00",
            "state_str": "IDLE",
            "sample_id": "SMP-001",
            "material": "Structural Steel",
            "standard": "ASTM E8"
        }
        
        # Extensometer baseline
        self.gauge_l0_px = None
        self.gauge_mm_per_px = 0.25 # Calibration factor: 1 px = 0.25 mm (50 mm / 200 px)
        self.prev_gray = None
        self.sim_phase = 0.0

    def update_telemetry(self, data: dict):
        with QMutexLocker(self.mutex):
            self.telemetry.update(data)

    def set_source(self, source):
        with QMutexLocker(self.mutex):
            self.source_id = source
            self.last_open_attempt = 0.0
            if self.cap:
                self.cap.release()
                self.cap = None

    def set_detection_mode(self, mode: str):
        with QMutexLocker(self.mutex):
            self.detection_mode = mode

    def set_hud_enabled(self, enabled: bool):
        with QMutexLocker(self.mutex):
            self.show_telemetry_hud = enabled

    def set_manual_roi(self, roi):
        with QMutexLocker(self.mutex):
            self.manual_roi = roi

    def start_recording(self, sample_id: str, output_dir: str) -> str:
        with QMutexLocker(self.mutex):
            if self.is_recording:
                return self.recording_path
                
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_sample = "".join(c if c.isalnum() or c in "-_" else "_" for c in sample_id) or "SMP"
            self.recording_path = os.path.join(output_dir, f"UTM_REC_{clean_sample}_{timestamp}.mp4")
            
            # Try mp4v codec first
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                self.recording_path, 
                fourcc, 
                self.target_fps, 
                (self.frame_width, self.frame_height)
            )
            
            # Fallback 1: XVID
            if not self.video_writer or not self.video_writer.isOpened():
                fourcc_xvid = cv2.VideoWriter_fourcc(*'XVID')
                self.video_writer = cv2.VideoWriter(
                    self.recording_path, fourcc_xvid, self.target_fps, (self.frame_width, self.frame_height)
                )
            
            # Fallback 2: MJPG
            if not self.video_writer or not self.video_writer.isOpened():
                fourcc_mjpg = cv2.VideoWriter_fourcc(*'MJPG')
                self.video_writer = cv2.VideoWriter(
                    self.recording_path, fourcc_mjpg, self.target_fps, (self.frame_width, self.frame_height)
                )
            
            self.is_recording = True
            self.record_start_time = time.time()
            self.frames_recorded = 0
            self.recording_started.emit(self.recording_path)
            return self.recording_path

    def stop_recording(self) -> str:
        with QMutexLocker(self.mutex):
            if not self.is_recording:
                return ""
                
            duration = max(0.1, time.time() - self.record_start_time)
            self.is_recording = False
            
            if self.video_writer is not None:
                try:
                    self.video_writer.release()
                except Exception as e:
                    logger.error(f"Error releasing video writer: {e}")
                self.video_writer = None
                
            path = self.recording_path
            
        self.recording_stopped.emit(path, duration)
        return path

    def take_snapshot(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sample_id = self.telemetry.get("sample_id", "SMP")
        clean_sample = "".join(c if c.isalnum() or c in "-_" else "_" for c in sample_id)
        path = os.path.join(output_dir, f"UTM_SNAP_{clean_sample}_{timestamp}.png")
        
        # Save snapshot using latest frame
        if hasattr(self, '_latest_processed_frame') and self._latest_processed_frame is not None:
            cv2.imwrite(path, self._latest_processed_frame)
            self._latest_snapshot_path = path
            return path
        return ""

    def run(self):
        self.running = True
        prev_time = time.time()
        
        while self.running:
            # 1. Manage Capture Device (throttled retry to avoid flooding Windows COM)
            if self.cap is None and self.source_id != -1:
                now = time.time()
                if now - self.last_open_attempt > self.retry_interval:
                    self.last_open_attempt = now
                    try:
                        if isinstance(self.source_id, int):
                            # Try 1: Default Windows video backend (MSMF - fastest & native)
                            self.cap = cv2.VideoCapture(self.source_id)
                            if not self.cap or not self.cap.isOpened():
                                if self.cap:
                                    self.cap.release()
                                # Try 2: DirectShow fallback for legacy USB webcams
                                self.cap = cv2.VideoCapture(self.source_id, cv2.CAP_DSHOW)
                                if not self.cap or not self.cap.isOpened():
                                    if self.cap:
                                        self.cap.release()
                                    self.cap = None
                        else:
                            # IP stream or URL (e.g. http://192.168.1.15:8080/video)
                            url_str = str(self.source_id)
                            # Fast socket connectivity pre-check (350ms max) to prevent blocking thread
                            reachable = True
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(url_str)
                                host = parsed.hostname or ""
                                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                                if host:
                                    import socket
                                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    s.settimeout(0.35)
                                    reachable = (s.connect_ex((host, port)) == 0)
                                    s.close()
                            except Exception:
                                pass
                                
                            if not reachable:
                                self.camera_connected.emit(False, "IP Camera Unreachable")
                                self.cap = None
                            else:
                                # Try 1: FFMPEG backend (standard for network video streams)
                                self.cap = cv2.VideoCapture(url_str, cv2.CAP_FFMPEG)
                                if not self.cap or not self.cap.isOpened():
                                    if self.cap:
                                        self.cap.release()
                                    # Try 2: Default backend
                                    self.cap = cv2.VideoCapture(url_str)
                            
                        if self.cap and self.cap.isOpened():
                            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                            self.camera_connected.emit(True, f"Camera {self.source_id}")
                        else:
                            self.camera_connected.emit(False, "Offline / Simulating")
                            if self.cap:
                                self.cap.release()
                            self.cap = None
                    except Exception as e:
                        logger.warning(f"Failed to open camera {self.source_id}: {e}")
                        if self.cap:
                            self.cap.release()
                        self.cap = None
                        self.camera_connected.emit(False, "Failed to connect")

            # 2. Acquire Raw Frame
            frame = None
            if self.cap and self.cap.isOpened():
                ret, raw_frame = self.cap.read()
                if ret and raw_frame is not None:
                    frame = raw_frame
                    if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
                        frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            
            # 2b. Direct HTTP frame acquisition fallback for IP Webcam (/shot.jpg)
            if frame is None and isinstance(self.source_id, str) and self.source_id.startswith("http"):
                try:
                    import urllib.request
                    base_url = self.source_id.split("/video")[0].split("/mjpeg")[0].rstrip("/")
                    shot_url = f"{base_url}/shot.jpg"
                    req = urllib.request.urlopen(shot_url, timeout=0.8)
                    raw_data = req.read()
                    if raw_data:
                        dec = cv2.imdecode(np.asarray(bytearray(raw_data), dtype=np.uint8), cv2.IMREAD_COLOR)
                        if dec is not None:
                            frame = cv2.resize(dec, (self.frame_width, self.frame_height))
                            if not getattr(self, "_ip_connected_notified", False):
                                self.camera_connected.emit(True, "Phone IP Camera")
                                self._ip_connected_notified = True
                except Exception:
                    pass
            
            # If camera is unavailable or source is -1, generate real-time UTM Simulation Feed
            if frame is None:
                frame = self._generate_simulated_specimen()

            # 3. Process Frame with Object Detection and Telemetry HUD
            detection_stats = {}
            with QMutexLocker(self.mutex):
                telem_copy = dict(self.telemetry)
                mode = self.detection_mode
                hud_on = self.show_telemetry_hud
                recording = self.is_recording
                writer = self.video_writer
                rec_start = self.record_start_time

            # Apply Computer Vision
            processed_frame, detection_stats = self._apply_vision(frame, mode, telem_copy)

            # Apply Enterprise Telemetry HUD
            if hud_on:
                processed_frame = self._draw_telemetry_hud(processed_frame, telem_copy, recording, rec_start)

            self._latest_processed_frame = processed_frame

            # 4. Stream to Video Recording File if Active (thread-safe synchronization)
            with QMutexLocker(self.mutex):
                if self.is_recording and self.video_writer is not None:
                    try:
                        # Guarantee exact frame dimension matching VideoWriter (prevents silent frame drops)
                        if processed_frame.shape[1] != self.frame_width or processed_frame.shape[0] != self.frame_height:
                            frame_to_record = cv2.resize(processed_frame, (self.frame_width, self.frame_height))
                        else:
                            frame_to_record = processed_frame
                        self.video_writer.write(frame_to_record)
                        self.frames_recorded += 1
                    except Exception as e:
                        logger.error(f"Error writing video frame: {e}")

            # 5. Convert to QImage and Emit to UI Canvas
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            
            self.frame_ready.emit(qimg, telem_copy, detection_stats)

            # Frame Rate Limiter
            elapsed = time.time() - prev_time
            sleep_time = max(0.001, (1.0 / self.target_fps) - elapsed)
            time.sleep(sleep_time)
            prev_time = time.time()

        # Clean up on thread exit
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        if self.cap:
            self.cap.release()
            self.cap = None

    def stop(self):
        self.running = False
        self.wait(1500)

    # =========================================================================
    # COMPUTER VISION & OBJECT DETECTION ALGORITHMS
    # =========================================================================
    def _apply_vision(self, frame: np.ndarray, mode: str, telem: dict) -> tuple[np.ndarray, dict]:
        annotated = frame.copy()
        stats = {}
        
        if mode == DetectionMode.RAW_FEED:
            return annotated, stats

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ---------------------------------------------------------------------
        # MODE 1: SPECIMEN OBJECT TRACKING & NECKING DETECTION
        # ---------------------------------------------------------------------
        if mode == DetectionMode.SPECIMEN_NECKING:
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            # Use Otsu's thresholding for high-contrast segmentation
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            best_cnt = None
            max_score = 0
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                # Tensile specimens are slender vertical objects in the central test zone
                # Ensure width does not cover entire screen (max 40% of width) and has vertical aspect
                if 15 <= cw <= int(w * 0.40) and ch >= 60 and (ch / float(max(1, cw))) >= 1.05:
                    center_dist = abs((x + cw / 2.0) - (w / 2.0))
                    if center_dist < w * 0.30:
                        score = (ch * 2.0) - center_dist
                        if score > max_score:
                            max_score = score
                            best_cnt = cnt

            if best_cnt is not None:
                bx, by, bw, bh = cv2.boundingRect(best_cnt)
                cx = bx + bw // 2
                cy = by + bh // 2
                
                # Draw high-tech Specimen Bounding Box (Corner Bracket Style)
                color = (0, 220, 0) # Precision Green
                self._draw_corner_box(annotated, bx, by, bw, bh, color, 2)
                
                # Center Axis Line & Centroid
                cv2.line(annotated, (cx, by), (cx, by + bh), (0, 220, 255), 1, cv2.LINE_AA)
                cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)
                
                # Necking Analysis: Scan horizontal cross-section slices in gauge section
                mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.drawContours(mask, [best_cnt], -1, 255, -1)
                
                slice_start = by + int(bh * 0.25)
                slice_end = by + int(bh * 0.75)
                
                row_widths = []
                scan_rows = []
                for scan_y in range(slice_start, slice_end, 3):
                    row_pixels = np.count_nonzero(mask[scan_y, bx:bx+bw])
                    if row_pixels > 8:
                        row_widths.append(row_pixels)
                        scan_rows.append(scan_y)
                        
                if row_widths:
                    w0 = float(np.percentile(row_widths, 80))
                    min_width = min(row_widths)
                    min_idx = row_widths.index(min_width)
                    neck_y = scan_rows[min_idx]
                    reduction_pct = max(0.0, (1.0 - (min_width / max(1.0, w0))) * 100.0)
                else:
                    w0 = float(bw)
                    min_width = bw
                    neck_y = cy
                    reduction_pct = 0.0

                # Draw Necking Caliper Line
                cv2.line(annotated, (cx - min_width // 2, neck_y), (cx + min_width // 2, neck_y), (0, 0, 255), 2, cv2.LINE_AA)
                cv2.circle(annotated, (cx, neck_y), 3, (0, 0, 255), -1)
                
                stats = {
                    "object_detected": True,
                    "bbox": (bx, by, bw, bh),
                    "necking_y": neck_y,
                    "necking_width_px": min_width,
                    "w0_px": int(w0),
                    "reduction_pct": reduction_pct
                }
                
                # Clean Label overlay above bounding box
                label_txt = f"SPECIMEN [W:{bw}px H:{bh}px] | NECK: {min_width}px (-{reduction_pct:.1f}%)"
                label_y = max(18, by - 6)
                text_size, _ = cv2.getTextSize(label_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
                cv2.rectangle(annotated, (bx, label_y - text_size[1] - 4), (bx + text_size[0] + 6, label_y + 4), (0, 180, 0), -1)
                cv2.putText(annotated, label_txt, (bx + 3, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # MODE 2: DUAL GAUGE MARKS OPTICAL EXTENSOMETER
        # ---------------------------------------------------------------------
        elif mode == DetectionMode.GAUGE_EXTENSOMETER:
            # Detect two high-contrast circular or horizontal gauge marks
            _, mark_thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            mark_cnts, _ = cv2.findContours(mark_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            valid_marks = []
            for cnt in mark_cnts:
                area = cv2.contourArea(cnt)
                if 10 < area < 800:
                    mx, my, mw, mh = cv2.boundingRect(cnt)
                    # Marks should be within central 50% width
                    if w * 0.25 < mx < w * 0.75:
                        mcx = mx + mw // 2
                        mcy = my + mh // 2
                        valid_marks.append((mcx, mcy, area))
                        
            # Sort marks vertically
            valid_marks.sort(key=lambda m: m[1])
            
            if len(valid_marks) >= 2:
                top_mark = valid_marks[0]
                bottom_mark = valid_marks[-1]
                
                # Draw Mark Crosshairs
                cv2.circle(annotated, (top_mark[0], top_mark[1]), 8, (255, 100, 0), 2)
                cv2.circle(annotated, (bottom_mark[0], bottom_mark[1]), 8, (255, 100, 0), 2)
                
                # Caliper Line
                cv2.line(annotated, (top_mark[0], top_mark[1]), (bottom_mark[0], bottom_mark[1]), (255, 200, 0), 2, cv2.LINE_AA)
                
                # Measure gauge distance
                gauge_px = abs(bottom_mark[1] - top_mark[1])
                if self.gauge_l0_px is None or telem.get("state_str") in ["IDLE", "READY"]:
                    self.gauge_l0_px = gauge_px
                    
                delta_px = gauge_px - self.gauge_l0_px
                optical_ext_mm = delta_px * self.gauge_mm_per_px
                optical_strain_pct = (delta_px / float(self.gauge_l0_px)) * 100.0 if self.gauge_l0_px > 0 else 0.0
                
                stats = {
                    "gauge_px": gauge_px,
                    "optical_ext_mm": optical_ext_mm,
                    "optical_strain_pct": optical_strain_pct
                }
                
                # Measure Banner
                mid_y = (top_mark[1] + bottom_mark[1]) // 2
                tag = f"GAUGE: {optical_ext_mm:+.2f} mm ({optical_strain_pct:+.1f}%)"
                cv2.putText(annotated, tag, (top_mark[0] + 16, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # MODE 3: MOTION & DEFORMATION HEATMAP
        # ---------------------------------------------------------------------
        elif mode == DetectionMode.MOTION_DEFORMATION:
            if self.prev_gray is not None and self.prev_gray.shape == gray.shape:
                frame_diff = cv2.absdiff(gray, self.prev_gray)
                _, diff_thresh = cv2.threshold(frame_diff, 20, 255, cv2.THRESH_BINARY)
                diff_cnts, _ = cv2.findContours(diff_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for d_cnt in diff_cnts:
                    if cv2.contourArea(d_cnt) > 80:
                        dx, dy, dw, dh = cv2.boundingRect(d_cnt)
                        cv2.rectangle(annotated, (dx, dy), (dx + dw, dy + dh), (0, 165, 255), 1)
                        
            self.prev_gray = gray.copy()

        # ---------------------------------------------------------------------
        # MODE 4: MANUAL ROI TRACKING
        # ---------------------------------------------------------------------
        elif mode == DetectionMode.MANUAL_ROI and self.manual_roi:
            rx, ry, rw, rh = self.manual_roi
            cv2.rectangle(annotated, (rx, ry), (rx + rw, ry + rh), (0, 255, 255), 2)
            cv2.putText(annotated, "USER ROI TRACKER", (rx, max(14, ry - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        return annotated, stats

    # =========================================================================
    # ENTERPRISE HUD TELEMETRY WATERMARK OVERLAY
    # =========================================================================
    def _draw_telemetry_hud(self, frame: np.ndarray, telem: dict, recording: bool, rec_start: float) -> np.ndarray:
        h, w = frame.shape[:2]
        
        # 1. Top HUD Ribbon (Dark Semi-Transparent Banner)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 36), (15, 23, 42), -1)
        
        # 2. Bottom Telemetry HUD Ribbon
        cv2.rectangle(overlay, (0, h - 38), (w, h), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
        
        # Top Header Content
        # Left: Brand & Sample
        sample = telem.get("sample_id", "SMP-001")
        mat = telem.get("material", "Steel")
        cv2.putText(frame, f"UTM PRO VISION  |  {sample} ({mat})", (12, 23), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Right: Recording Badge
        if recording:
            rec_dur = time.time() - rec_start
            mins = int(rec_dur // 60)
            secs = int(rec_dur % 60)
            ms = int((rec_dur * 10) % 10)
            rec_str = f"REC  {mins:02d}:{secs:02d}.{ms}"
            
            # Blinking red dot
            if int(time.time() * 2) % 2 == 0:
                cv2.circle(frame, (w - 110, 18), 6, (0, 0, 255), -1)
            else:
                cv2.circle(frame, (w - 110, 18), 6, (50, 50, 150), -1)
                
            cv2.putText(frame, rec_str, (w - 96, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 255), 2, cv2.LINE_AA)
        else:
            state = telem.get("state_str", "STANDBY")
            cv2.circle(frame, (w - 95, 18), 5, (0, 200, 0) if state == "RUNNING" else (160, 160, 160), -1)
            cv2.putText(frame, state, (w - 82, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

        # Bottom Telemetry Ribbon Content (Load, Stress, Extension, Time)
        load = telem.get("load_kN", 0.0)
        stress = telem.get("stress_MPa", 0.0)
        ext = telem.get("ext_mm", 0.0)
        strain = telem.get("strain_pct", 0.0)
        t_str = telem.get("time_str", "00:00:00")
        
        telem_txt = f"LOAD: {load:6.2f} kN   STRESS: {stress:6.1f} MPa   EXT: {ext:5.2f} mm   STRAIN: {strain:5.2f}%   TIME: {t_str}"
        cv2.putText(frame, telem_txt, (12, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 230, 255), 1, cv2.LINE_AA)

        return frame

    # =========================================================================
    # SIMULATED SPECIMEN GENERATOR (When physical camera is offline / test mode)
    # =========================================================================
    def _generate_simulated_specimen(self) -> np.ndarray:
        h, w = self.frame_height, self.frame_width
        # Clean neutral laboratory background
        frame = np.ones((h, w, 3), dtype=np.uint8) * 248
        
        # Machine Column Uprights
        cv2.rectangle(frame, (60, 0), (120, h), (218, 222, 228), -1)
        cv2.rectangle(frame, (w - 120, 0), (w - 60, h), (218, 222, 228), -1)
        
        # Test Extension amount from telemetry
        ext_mm = self.telemetry.get("ext_mm", 0.0)
        load_kN = self.telemetry.get("load_kN", 0.0)
        is_running = self.telemetry.get("state_str") == "RUNNING"
        
        stretch_px = int(ext_mm * 15.0)
        
        # Grips (Upper crosshead moving up, lower bed fixed)
        upper_grip_y = max(30, 90 - stretch_px)
        lower_grip_y = 380
        
        # Upper Grip
        cv2.rectangle(frame, (230, upper_grip_y - 60), (410, upper_grip_y), (85, 95, 110), -1)
        cv2.rectangle(frame, (230, upper_grip_y - 60), (410, upper_grip_y), (40, 50, 65), 2)
        # Lower Grip
        cv2.rectangle(frame, (230, lower_grip_y), (410, lower_grip_y + 60), (85, 95, 110), -1)
        cv2.rectangle(frame, (230, lower_grip_y), (410, lower_grip_y + 60), (40, 50, 65), 2)
        
        # Tensile Dogbone Specimen
        mid_y = (upper_grip_y + lower_grip_y) // 2
        spec_w = 64
        # Necking shrinks the center width when load/extension is high
        neck_shrink = int(min(24.0, ext_mm * 4.0)) if is_running else 0
        center_w = max(16, spec_w - neck_shrink)
        
        pts = np.array([
            [w//2 - spec_w//2, upper_grip_y],
            [w//2 + spec_w//2, upper_grip_y],
            [w//2 + center_w//2, mid_y],
            [w//2 + spec_w//2, lower_grip_y],
            [w//2 - spec_w//2, lower_grip_y],
            [w//2 - center_w//2, mid_y]
        ], np.int32)
        
        # Specimen metallic gradient
        cv2.fillPoly(frame, [pts], (60, 65, 75))
        cv2.polylines(frame, [pts], True, (30, 35, 45), 2)
        
        # Dual Contrast Gauge Marks for Optical Extensometer
        mark_top_y = upper_grip_y + int((lower_grip_y - upper_grip_y) * 0.28)
        mark_bot_y = upper_grip_y + int((lower_grip_y - upper_grip_y) * 0.72)
        cv2.circle(frame, (w//2, mark_top_y), 5, (255, 255, 255), -1)
        cv2.circle(frame, (w//2, mark_top_y), 5, (0, 0, 0), 1)
        cv2.circle(frame, (w//2, mark_bot_y), 5, (255, 255, 255), -1)
        cv2.circle(frame, (w//2, mark_bot_y), 5, (0, 0, 0), 1)

        return frame

    def _draw_corner_box(self, img, x, y, w, h, color, thickness=2, length=12):
        # Top-Left
        cv2.line(img, (x, y), (x + length, y), color, thickness)
        cv2.line(img, (x, y), (x, y + length), color, thickness)
        # Top-Right
        cv2.line(img, (x + w, y), (x + w - length, y), color, thickness)
        cv2.line(img, (x + w, y), (x + w, y + length), color, thickness)
        # Bottom-Left
        cv2.line(img, (x, y + h), (x + length, y + h), color, thickness)
        cv2.line(img, (x, y + h), (x, y + h - length), color, thickness)
        # Bottom-Right
        cv2.line(img, (x + w, y + h), (x + w - length, y + h), color, thickness)
        cv2.line(img, (x + w, y + h), (x + w, y + h - length), color, thickness)


class CameraManager(QObject):
    """
    Public Facade for the Vision and Video Recording System.
    Manages camera lifecycle, device enumeration, auto-recording hooks, and snapshots.
    """
    frame_ready = Signal(QImage, dict, dict)
    recording_started = Signal(str)
    recording_stopped = Signal(str, float)
    camera_connected = Signal(bool, str)

    def __init__(self, output_dir=None):
        super().__init__()
        # Always resolve to canonical UTM_Professional/reports path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = output_dir or os.path.join(base_dir, "reports", "videos")
        self.snapshot_dir = os.path.join(base_dir, "reports", "snapshots")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        self.worker = CameraWorker()
        self.worker.frame_ready.connect(self.frame_ready.emit)
        self.worker.recording_started.connect(self.recording_started.emit)
        self.worker.recording_stopped.connect(self.recording_stopped.emit)
        self.worker.camera_connected.connect(self.camera_connected.emit)
        
        self.auto_record_enabled = True
        self.last_recorded_video = ""

    def start_camera(self):
        if not self.worker.isRunning():
            self.worker.start()

    def stop_camera(self):
        if self.worker.isRunning():
            self.worker.stop()

    @staticmethod
    def detect_connected_mobile_usb() -> dict:
        """Detect if an Android or Samsung mobile device is connected via USB in MTP/Storage mode"""
        try:
            import subprocess
            cmd = "Get-PnpDevice -Class WPD -Status OK | Select-Object -ExpandProperty FriendlyName"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=2)
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            for name in lines:
                if any(k in name.lower() for k in ["samsung", "s2", "s23", "s24", "galaxy", "phone", "pixel", "redmi", "oneplus", "xiaomi", "android"]):
                    return {"detected": True, "name": name}
            if lines:
                return {"detected": True, "name": lines[0]}
        except Exception:
            pass
        return {"detected": False, "name": ""}

    def scan_available_cameras(self) -> list:
        """Scan for connected USB webcams and mobile phones without blocking UI or colliding with worker thread"""
        cameras = []
        # Index 0: Default USB / Built-in Webcam
        cameras.append({"id": 0, "name": "Camera 0 (USB / Built-in Webcam)"})
        
        # Check secondary camera only if worker is not actively using it
        if not (self.worker.isRunning() and self.worker.source_id == 1):
            try:
                cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
                if cap and cap.isOpened():
                    cap.release()
                    cameras.append({"id": 1, "name": "Camera 1 (Secondary USB Webcam)"})
                elif cap:
                    cap.release()
            except Exception:
                pass

        # Check if mobile phone is plugged in via USB in MTP mode
        phone = self.detect_connected_mobile_usb()
        if phone["detected"]:
            cameras.append({"id": "phone_help", "name": f"📱 Phone: {phone['name']} (Setup USB Cam)"})

        # Option to connect IP / WiFi mobile camera directly from dropdown
        cameras.append({"id": "open_ip_dialog", "name": "🌐 Connect Mobile via IP / WiFi (IP Webcam)..."})

        # Always provide Virtual Specimen Simulator as secondary option
        cameras.append({"id": -1, "name": "🧪 Virtual Specimen Simulator (Offline)"})
        return cameras

    def set_camera_source(self, source_id):
        self.worker.set_source(source_id)

    def set_detection_mode(self, mode: str):
        self.worker.set_detection_mode(mode)

    def set_hud_enabled(self, enabled: bool):
        self.worker.set_hud_enabled(enabled)

    def set_manual_roi(self, roi):
        self.worker.set_manual_roi(roi)

    def update_telemetry(self, telemetry_dict: dict):
        self.worker.update_telemetry(telemetry_dict)

    def start_recording(self, sample_id: str = "SMP-001") -> str:
        self.start_camera() # Guarantee worker thread is active
        path = self.worker.start_recording(sample_id, self.output_dir)
        self.last_recorded_video = path
        return path

    def stop_recording(self) -> str:
        path = self.worker.stop_recording()
        if path:
            self.last_recorded_video = path
        return path

    def is_recording(self) -> bool:
        return self.worker.is_recording

    def take_snapshot(self) -> str:
        return self.worker.take_snapshot(self.snapshot_dir)
