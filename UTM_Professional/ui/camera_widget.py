"""
UTM Professional v2.5 - Live Video Recording & Computer Vision Tracking Widget
Interfaces with Webcams, USB Mobile Cameras, Virtual Feeds, and IP Streams.
Provides real-time specimen object tracking, necking analysis, optical extensometer,
and automatic synchronized video recording stamped with machine telemetry.
"""

import os
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QCheckBox, QFrame, QSizePolicy, QInputDialog,
    QMessageBox, QToolTip
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QUrl, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont, QDesktopServices

from camera.camera_manager import CameraManager, DetectionMode
from ui.theme import Theme


class VideoViewport(QWidget):
    """
    High-performance video canvas supporting aspect-ratio preservation,
    rubberband mouse ROI selection, and floating HUD status badges.
    """
    roi_selected = Signal(tuple) # (x, y, w, h) in video coordinates

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        
        self.current_qimage = None
        self.video_width = 640
        self.video_height = 480
        self.hud_enabled = True
        
        # Interactive ROI Selection
        self.is_selecting_roi = False
        self.roi_start = QPoint()
        self.roi_end = QPoint()
        self.active_roi_rect = None # QRect in viewport widget coordinates
        
        # Overlay Badges & Telemetry
        self.connection_text = "INITIALIZING FEED..."
        self.is_connected = False
        self.is_recording = False
        self.record_time_str = "00:00"
        self.detection_stats_text = "Waiting for specimen..."
        self.fps_text = "30 FPS"
        
        # Styling
        self.setStyleSheet("""
            background-color: #0f172a;
            border-radius: 6px;
        """)

    def update_frame(self, qimg: QImage, telem: dict, stats: dict):
        self.current_qimage = qimg
        self.video_width = qimg.width()
        self.video_height = qimg.height()
        
        # Format detection stats readout
        if stats.get("object_detected"):
            w_px = stats.get("necking_width_px", 0)
            red_pct = stats.get("reduction_pct", 0.0)
            self.detection_stats_text = f"Specimen Detected | Necking: {w_px}px (-{red_pct:.1f}%)"
        elif "optical_ext_mm" in stats:
            ext_mm = stats.get("optical_ext_mm", 0.0)
            strain_pct = stats.get("optical_strain_pct", 0.0)
            self.detection_stats_text = f"Optical Ext: {ext_mm:+.2f} mm ({strain_pct:+.1f}%)"
        else:
            self.detection_stats_text = "Specimen Vision Active"
            
        self.update()

    def set_connection_status(self, connected: bool, text: str):
        self.is_connected = connected
        self.connection_text = text.upper()
        self.update()

    def set_recording_state(self, recording: bool, duration_str: str = "00:00"):
        self.is_recording = recording
        self.record_time_str = duration_str
        self.update()

    def show_saved_notification(self, text: str):
        self.saved_notice_text = text
        self.saved_notice_until = time.time() + 7.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting_roi = True
            self.roi_start = event.pos()
            self.roi_end = event.pos()
            self.active_roi_rect = QRect(self.roi_start, self.roi_end)
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting_roi:
            self.roi_end = event.pos()
            self.active_roi_rect = QRect(self.roi_start, self.roi_end).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting_roi:
            self.is_selecting_roi = False
            self.roi_end = event.pos()
            rect = QRect(self.roi_start, self.roi_end).normalized()
            
            if rect.width() > 15 and rect.height() > 15 and self.current_qimage:
                # Map viewport widget coordinates to video frame coordinates
                mapped_roi = self._map_to_video_coords(rect)
                if mapped_roi:
                    self.active_roi_rect = rect
                    self.roi_selected.emit(mapped_roi)
            else:
                self.active_roi_rect = None
            self.update()

    def mouseDoubleClickEvent(self, event):
        # Double click clears manual ROI
        self.active_roi_rect = None
        self.roi_selected.emit((0, 0, 0, 0))
        self.update()

    def _map_to_video_coords(self, rect: QRect):
        vw = self.width()
        vh = self.height()
        if vw <= 0 or vh <= 0 or self.video_width <= 0 or self.video_height <= 0:
            return None
            
        # Calculate video presentation rect with KeepAspectRatio
        scale = min(vw / self.video_width, vh / self.video_height)
        disp_w = self.video_width * scale
        disp_h = self.video_height * scale
        offset_x = (vw - disp_w) / 2.0
        offset_y = (vh - disp_h) / 2.0
        
        # Clamp selection rect to video presentation rect
        rx = max(offset_x, min(offset_x + disp_w, rect.x()))
        ry = max(offset_y, min(offset_y + disp_h, rect.y()))
        rw = min(disp_w - (rx - offset_x), rect.width())
        rh = min(disp_h - (ry - offset_y), rect.height())
        
        # Convert to video coordinates
        vid_x = int((rx - offset_x) / scale)
        vid_y = int((ry - offset_y) / scale)
        vid_w = int(rw / scale)
        vid_h = int(rh / scale)
        
        return (vid_x, vid_y, vid_w, vid_h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        vw = self.width()
        vh = self.height()
        
        # Clean dark background
        painter.fillRect(0, 0, vw, vh, QColor("#0b1120"))
        
        if self.current_qimage and not self.current_qimage.isNull():
            # Calculate scaled dimensions preserving aspect ratio
            scale = min(vw / self.video_width, vh / self.video_height)
            disp_w = int(self.video_width * scale)
            disp_h = int(self.video_height * scale)
            offset_x = int((vw - disp_w) / 2)
            offset_y = int((vh - disp_h) / 2)
            
            target_rect = QRect(offset_x, offset_y, disp_w, disp_h)
            painter.drawImage(target_rect, self.current_qimage)
            
            # Subtle frame outline
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawRect(target_rect)
            
            # If recording and frame telemetry HUD is disabled, show clean non-intrusive REC pill
            if self.is_recording and not self.hud_enabled:
                rec_w = 95
                badge_h = 22
                rec_x = offset_x + disp_w - rec_w - 6
                rec_y = offset_y + 6
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(220, 38, 38, 230))
                painter.drawRoundedRect(rec_x, rec_y, rec_w, badge_h, 4, 4)
                
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(rec_x + 8, rec_y + 6, 8, 8)
                
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Consolas", 9, QFont.Bold))
                painter.drawText(rec_x + 22, rec_y + 15, f"REC {self.record_time_str}")
        else:
            # Standby Graphic & Prompt
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            standby_txt = "CAMERA FEED STANDBY / INITIALIZING"
            painter.drawText(QRect(0, vh//2 - 30, vw, 30), Qt.AlignCenter, standby_txt)
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(QRect(0, vh//2 + 5, vw, 25), Qt.AlignCenter, "Connect USB Mobile Device or Select Camera Source")

        # Draw Rubberband selection box if user is dragging ROI
        if self.is_selecting_roi and self.active_roi_rect:
            painter.setPen(QPen(QColor("#38bdf8"), 2, Qt.DashLine))
            painter.setBrush(QColor(56, 189, 248, 40))
            painter.drawRect(self.active_roi_rect)
        elif self.active_roi_rect:
            painter.setPen(QPen(QColor("#0284c7"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.active_roi_rect)

        # Draw floating on-screen banner when video is saved
        if hasattr(self, 'saved_notice_until') and time.time() < self.saved_notice_until:
            banner_w = min(vw - 24, 380)
            banner_h = 50
            bx = (vw - banner_w) // 2
            by = 12
            
            painter.setPen(QPen(QColor("#22c55e"), 2))
            painter.setBrush(QColor(15, 23, 42, 235))
            painter.drawRoundedRect(bx, by, banner_w, banner_h, 8, 8)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#16a34a"))
            painter.drawRoundedRect(bx + 10, by + 9, 32, 32, 6, 6)
            
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(bx + 10, by + 9, 32, 32, Qt.AlignCenter, "✔")
            
            lines = getattr(self, 'saved_notice_text', '').split('\n')
            title = lines[0] if lines else "VIDEO RECORDING SAVED"
            subtitle = lines[1] if len(lines) > 1 else ""
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QColor("#4ade80"))
            painter.drawText(bx + 50, by + 22, title)
            
            if subtitle:
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#cbd5e1"))
                painter.drawText(bx + 50, by + 39, subtitle)


class CameraWidget(QWidget):
    """
    Complete Video Surveillance & Optical Computer Vision Control Panel.
    Embeds directly into UTM Dashboard with toolbar controls,
    streamlined source selector, vision mode switcher, and video recording triggers.
    """
    def __init__(self, camera_manager: CameraManager = None, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager or CameraManager()
        
        # UI State
        self.rec_start_time = 0.0
        self.rec_timer = QTimer(self)
        self.rec_timer.timeout.connect(self._update_rec_timer)
        
        self._setup_ui()
        self._connect_signals()
        
        # Initial Camera Population
        self.refresh_camera_sources()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)
        
        # =========================================================================
        # 1. TOP VISION & RECORDING CONTROL TOOLBAR (2-Row Responsive Layout)
        # =========================================================================
        toolbar_card = QFrame()
        toolbar_card.setObjectName("card")
        toolbar_card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        toolbar_layout = QVBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)
        toolbar_layout.setSpacing(6)
        
        # Row 1: Camera Source Selector & Recording Action
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(6)
        
        lbl_source = QLabel("Cam:")
        lbl_source.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        row1_layout.addWidget(lbl_source)
        
        self.cb_sources = QComboBox()
        self.cb_sources.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        row1_layout.addWidget(self.cb_sources, 1)
        
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedSize(24, 22)
        self.btn_refresh.setToolTip("Scan Connected USB Webcams / Mobile Phones")
        self.btn_refresh.setStyleSheet("padding: 0px; font-size: 13px; font-weight: bold; background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px;")
        row1_layout.addWidget(self.btn_refresh)
        
        self.btn_ip_stream = QPushButton("IP")
        self.btn_ip_stream.setToolTip("Connect to Phone IP Camera (DroidCam / RTSP / HTTP Stream)")
        self.btn_ip_stream.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; font-weight: 600;")
        row1_layout.addWidget(self.btn_ip_stream)
        
        self.btn_phone_help = QPushButton("📱")
        self.btn_phone_help.setFixedSize(26, 22)
        self.btn_phone_help.setToolTip("How to connect Samsung / Android Phone as USB Camera")
        self.btn_phone_help.setStyleSheet("padding: 0px; font-size: 13px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px;")
        row1_layout.addWidget(self.btn_phone_help)
        
        row1_layout.addSpacing(6)
        
        self.btn_record = QPushButton("● REC")
        self.btn_record.setObjectName("btnRecord")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #dc2626;
                border: 1px solid #dc2626;
                border-radius: 4px;
                font-weight: 700;
                font-size: 11px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #fef2f2;
            }
        """)
        self.btn_record.setToolTip("Start or Stop Video Recording")
        row1_layout.addWidget(self.btn_record)
        
        toolbar_layout.addLayout(row1_layout)
        
        # Row 2: Vision Algorithm Mode, Overlays & Utility Buttons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(6)
        
        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        row2_layout.addWidget(lbl_mode)
        
        self.cb_mode = QComboBox()
        self.cb_mode.addItems([
            DetectionMode.SPECIMEN_NECKING,
            DetectionMode.GAUGE_EXTENSOMETER,
            DetectionMode.MOTION_DEFORMATION,
            DetectionMode.MANUAL_ROI,
            DetectionMode.RAW_FEED
        ])
        self.cb_mode.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        row2_layout.addWidget(self.cb_mode, 1)
        
        self.chk_hud = QCheckBox("HUD")
        self.chk_hud.setChecked(True)
        self.chk_hud.setToolTip("Overlay Load, Stress, Strain & Timestamp directly on video")
        self.chk_hud.setStyleSheet("font-size: 11px; font-weight: 600; color: #334155;")
        row2_layout.addWidget(self.chk_hud)
        
        self.chk_auto_rec = QCheckBox("Auto")
        self.chk_auto_rec.setChecked(True)
        self.chk_auto_rec.setToolTip("Automatically record video when test starts and finalize MP4 on stop")
        self.chk_auto_rec.setStyleSheet("font-size: 11px; font-weight: 700; color: #0284c7;")
        row2_layout.addWidget(self.chk_auto_rec)
        
        self.btn_snapshot = QPushButton("📸")
        self.btn_snapshot.setFixedSize(28, 22)
        self.btn_snapshot.setStyleSheet("""
            QPushButton {
                background-color: #f0f9ff;
                color: #0284c7;
                border: 1px solid #bae6fd;
                border-radius: 4px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e0f2fe;
            }
        """)
        self.btn_snapshot.setToolTip("Capture High-Resolution Frame Snapshot Image")
        row2_layout.addWidget(self.btn_snapshot)
        
        self.btn_open_folder = QPushButton("📁")
        self.btn_open_folder.setFixedSize(28, 22)
        self.btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_open_folder.setToolTip("Open Video Recording & Snapshot Directory")
        row2_layout.addWidget(self.btn_open_folder)
        
        toolbar_layout.addLayout(row2_layout)
        
        root_layout.addWidget(toolbar_card)
        
        # =========================================================================
        # 2. MAIN INTERACTIVE VIDEO VIEWPORT CANVAS
        # =========================================================================
        self.viewport = VideoViewport(self)
        root_layout.addWidget(self.viewport, 1)
        
        # =========================================================================
        # 3. BOTTOM NOTIFICATION & PLAYBACK STRIP
        # =========================================================================
        self.status_bar = QFrame()
        self.status_bar.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        """)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(8)
        
        self.lbl_status_msg = QLabel("Tip: Click & drag on video to set custom Tracking ROI. Double-click to reset.")
        self.lbl_status_msg.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        status_layout.addWidget(self.lbl_status_msg, 1)
        
        self.btn_play_last = QPushButton("▶ Play Last Video")
        self.btn_play_last.setVisible(False)
        self.btn_play_last.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                font-size: 10px;
                border-radius: 4px;
                padding: 2px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
        """)
        self.btn_play_last.clicked.connect(self._play_last_video)
        status_layout.addWidget(self.btn_play_last)
        
        root_layout.addWidget(self.status_bar)

    def _connect_signals(self):
        # Camera Manager Events
        self.camera_manager.frame_ready.connect(self._on_frame_ready)
        self.camera_manager.camera_connected.connect(self._on_camera_connected)
        self.camera_manager.recording_started.connect(self._on_recording_started)
        self.camera_manager.recording_stopped.connect(self._on_recording_stopped)
        
        # UI Control Events
        self.cb_sources.currentIndexChanged.connect(self._on_source_changed)
        self.btn_refresh.clicked.connect(self.refresh_camera_sources)
        self.btn_ip_stream.clicked.connect(self._enter_ip_stream)
        self.cb_mode.currentTextChanged.connect(self._on_mode_changed)
        self.chk_hud.toggled.connect(self._on_hud_toggled)
        self.chk_auto_rec.toggled.connect(self._on_auto_rec_toggled)
        
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_snapshot.clicked.connect(self._take_snapshot)
        self.btn_open_folder.clicked.connect(self._open_video_folder)
        self.btn_phone_help.clicked.connect(self._show_phone_help)
        
        # Viewport mouse ROI selection
        self.viewport.roi_selected.connect(self._on_roi_selected)

    def _on_frame_ready(self, qimg: QImage, telem: dict, stats: dict):
        self.viewport.update_frame(qimg, telem, stats)
        if stats.get("object_detected"):
            w_px = stats.get("necking_width_px", 0)
            red_pct = stats.get("reduction_pct", 0.0)
            w0_px = stats.get("w0_px", w_px)
            self.lbl_status_msg.setText(f"● Specimen Detected | Gauge Width: {w_px}px (W₀: {w0_px}px) | Necking: -{red_pct:.1f}%")
        elif "optical_ext_mm" in stats:
            ext_mm = stats.get("optical_ext_mm", 0.0)
            strain_pct = stats.get("optical_strain_pct", 0.0)
            self.lbl_status_msg.setText(f"● Optical Extensometer | ΔL: {ext_mm:+.2f} mm | Strain: {strain_pct:+.2f}%")
        else:
            cam_name = self.cb_sources.currentText()
            self.lbl_status_msg.setText(f"Live Vision Feed Active: {cam_name}")

    def _show_phone_help(self):
        phone_info = CameraManager.detect_connected_mobile_usb()
        phone_name = phone_info.get("name", "Mobile Phone")
        is_detected = phone_info.get("detected", False)
        
        banner_html = ""
        if is_detected:
            banner_html = f"""
            <div style='background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 10px; margin-bottom: 12px;'>
                <b style='color: #166534; font-size: 13px;'>✓ Connected Phone Found: {phone_name}</b><br>
                <span style='color: #15803d; font-size: 11px;'>
                Your phone is plugged in via USB, but currently in <b>File Transfer (MTP) mode</b>.<br>
                Follow Step 1 below on your phone to switch it to <b>Webcam mode</b>!
                </span>
            </div>
            """

        msg = QMessageBox(self)
        msg.setWindowTitle("Connecting Mobile Phone Camera via USB")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            f"{banner_html}"
            "<h3 style='color: #0284c7; margin-top: 4px;'>How to Connect Your Phone Camera:</h3>"
            "<hr>"
            "<p><b>Method A: Free 'IP Webcam' App (Fastest & 100% Reliable):</b><br>"
            "1. On your phone, install free <b>IP Webcam</b> from Google Play Store.<br>"
            "2. Open the app, scroll to the bottom, and tap <b>'Start server'</b>.<br>"
            "3. Your phone screen will show an address (e.g. <code>http://192.168.1.50:8080/video</code>).<br>"
            "4. In this software, click <b>'IP'</b> in the toolbar, paste that address, and click <b>OK</b>!<br>"
            "<i>(Streams full-resolution HD video immediately with zero PC drivers!)</i></p>"
            "<p><b>Method B: Free DroidCam USB App:</b><br>"
            "1. Install <b>DroidCam</b> from Play Store on your phone, and install the free Windows DroidCam Client.<br>"
            "2. Connect USB cable, open DroidCam, select 'USB', and click 'Start'.<br>"
            "3. In this software, click <b>↻ (Refresh)</b> and select the new Camera!</p>"
            "<p><b>Method C: Windows 11 Native 'Connected Camera':</b><br>"
            "• On your PC, open Windows <b>Settings</b> &rarr; <b>Bluetooth & devices</b> &rarr; <b>Mobile devices</b>.<br>"
            "• Turn on <b>'Allow this PC to access your mobile devices'</b> &rarr; Toggle <b>'Use as a connected camera'</b>.</p>"
        )
        msg.exec()

    def refresh_camera_sources(self):
        """Scan available video devices and populate combobox"""
        self.cb_sources.blockSignals(True)
        self.cb_sources.clear()
        
        cams = self.camera_manager.scan_available_cameras()
        default_idx = 0
        for i, cam in enumerate(cams):
            self.cb_sources.addItem(cam["name"], cam["id"])
            if cam["id"] == 0:
                default_idx = i
            
        self.cb_sources.blockSignals(False)
        
        if self.cb_sources.count() > 0:
            self.cb_sources.setCurrentIndex(default_idx)
            self._on_source_changed(default_idx)

    def _on_source_changed(self, index: int):
        if index >= 0:
            source_id = self.cb_sources.currentData()
            if source_id == "phone_help":
                self._show_phone_help()
                self._restore_default_cam()
                return
            elif source_id == "open_ip_dialog":
                self._enter_ip_stream()
                return
            self.camera_manager.set_camera_source(source_id)
            self.lbl_status_msg.setText(f"Connected to: {self.cb_sources.currentText()}")

    def _restore_default_cam(self):
        for i in range(self.cb_sources.count()):
            if self.cb_sources.itemData(i) == 0:
                self.cb_sources.blockSignals(True)
                self.cb_sources.setCurrentIndex(i)
                self.cb_sources.blockSignals(False)
                break

    def _enter_ip_stream(self):
        # Auto-detect PC IP subnet for smart hint
        default_hint = "http://192.168.1.100:8080/video"
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            my_ip = s.getsockname()[0]
            s.close()
            parts = my_ip.split(".")
            if len(parts) == 4:
                default_hint = f"http://{parts[0]}.{parts[1]}.{parts[2]}.100:8080/video"
        except Exception:
            pass

        url, ok = QInputDialog.getText(
            self, 
            "Connect Phone Camera via IP / WiFi", 
            "Enter the stream URL shown at the bottom of your phone screen in the IP Webcam app:\n(e.g. http://192.168.1.xxx:8080)",
            text=default_hint
        )
        if ok and url.strip():
            url = url.strip()
            if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("rtsp://"):
                url = "http://" + url
                
            from urllib.parse import urlparse
            p = urlparse(url)
            # If user omitted port, add default 8080
            if not p.port and p.hostname:
                path_part = p.path or ""
                url = f"{p.scheme}://{p.hostname}:8080{path_part}"
                p = urlparse(url)

            if (url.startswith("http://") or url.startswith("https://")) and not any(url.endswith(x) for x in ["/video", "/mjpeg", ".mjpg", "/live", ".mp4", "/shot.jpg"]):
                url = url.rstrip("/") + "/video"
                
            # Fast socket connectivity pre-check (400ms max)
            host = p.hostname or ""
            port = p.port or 8080
            reachable = False
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.4)
                reachable = (sock.connect_ex((host, port)) == 0)
                sock.close()
            except Exception:
                pass
                
            item_name = f"Phone IP: {url}"
            # Check if already in combobox
            idx = self.cb_sources.findText(item_name)
            if idx < 0:
                self.cb_sources.addItem(item_name, url)
                idx = self.cb_sources.count() - 1
            self.cb_sources.setCurrentIndex(idx)
            
            if reachable:
                self.lbl_status_msg.setText(f"✓ Connected to Phone IP Webcam: {url}")
            else:
                self.lbl_status_msg.setText(f"Waiting for Phone ({host}:{port})... Tap 'Start server' in IP Webcam app.")
                QMessageBox.information(
                    self, 
                    "IP Camera Connection Guide",
                    f"Attempting connection to:\n<b>{url}</b>\n\n"
                    "If the video feed does not appear:\n"
                    "1. Open <b>IP Webcam</b> app on your phone.\n"
                    "2. Scroll all the way down and tap <b>'Start server'</b>.\n"
                    "3. Make sure phone and PC are connected to the same Wi-Fi router.\n"
                    "4. Verify the exact IP address displayed on your phone screen."
                )
            self.cb_sources.setCurrentIndex(self.cb_sources.count() - 1)

    def _on_mode_changed(self, mode: str):
        self.camera_manager.set_detection_mode(mode)
        self.lbl_status_msg.setText(f"Vision Algorithm: {mode}")

    def _on_hud_toggled(self, checked: bool):
        self.viewport.hud_enabled = checked
        self.camera_manager.set_hud_enabled(checked)

    def _on_auto_rec_toggled(self, checked: bool):
        self.camera_manager.auto_record_enabled = checked

    def _on_roi_selected(self, roi):
        if roi == (0, 0, 0, 0):
            self.camera_manager.set_manual_roi(None)
            self.lbl_status_msg.setText("Manual ROI reset. Resuming automatic specimen tracking.")
        else:
            self.camera_manager.set_manual_roi(roi)
            # Automatically switch mode to Manual ROI
            idx = self.cb_mode.findText(DetectionMode.MANUAL_ROI)
            if idx >= 0:
                self.cb_mode.setCurrentIndex(idx)
            self.lbl_status_msg.setText(f"Target ROI Tracked: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")

    def _toggle_recording(self):
        if not self.camera_manager.is_recording():
            # Try to grab current sample ID from main dashboard
            s_id = "MANUAL_TEST"
            try:
                win = self.window()
                if hasattr(win, 'in_sample'):
                    s_id = win.in_sample.text().strip() or "MANUAL_TEST"
            except Exception:
                pass
            path = self.camera_manager.start_recording(s_id)
        else:
            self.camera_manager.stop_recording()

    def _on_recording_started(self, path: str):
        self.rec_start_time = time.time()
        self.rec_timer.start(500)
        self.btn_record.setText("⏹ STOP")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                border-radius: 4px;
                font-weight: 700;
                font-size: 11px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.viewport.set_recording_state(True, "00:00")
        self.lbl_status_msg.setText(f"Recording Video: {os.path.basename(path)}")
        self.btn_play_last.setVisible(False)

    def _on_recording_stopped(self, path: str, duration: float):
        self.rec_timer.stop()
        self.btn_record.setText("● REC")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #dc2626;
                border: 1px solid #dc2626;
                border-radius: 4px;
                font-weight: 700;
                font-size: 11px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #fef2f2;
            }
        """)
        self.viewport.set_recording_state(False)
        
        file_size_kb = 0
        if path and os.path.exists(path):
            file_size_kb = os.path.getsize(path) / 1024.0
            
        if file_size_kb > 2:
            size_str = f"{file_size_kb / 1024.0:.2f} MB" if file_size_kb > 1024 else f"{file_size_kb:.0f} KB"
            fname = os.path.basename(path)
            self.lbl_status_msg.setText(f"✔ Video Saved ({duration:.1f}s, {size_str}): {fname}")
            self.btn_play_last.setText(f"▶ Play Last Video ({size_str})")
            self.btn_play_last.setVisible(True)
            self.btn_play_last.setStyleSheet("""
                QPushButton {
                    background-color: #16a34a;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 4px;
                    padding: 3px 10px;
                    border: 1px solid #15803d;
                }
                QPushButton:hover {
                    background-color: #15803d;
                }
            """)
            
            # Show floating banner directly on the video viewport canvas
            self.viewport.show_saved_notification(f"✔ VIDEO RECORDING SAVED ({size_str})\n{fname}")
            
            # Show interactive toast on Folder button
            QToolTip.showText(
                self.btn_open_folder.mapToGlobal(QPoint(0, self.btn_open_folder.height())),
                f"Video Saved ({size_str}):\n{fname}\n\nLocation:\n{path}\n(Click 📁 to open folder)", 
                self, QRect(), 5000
            )
        else:
            self.lbl_status_msg.setText("Notice: Test stopped too quickly to finalize video frame buffer.")

    def _update_rec_timer(self):
        if self.camera_manager.is_recording():
            dur = int(time.time() - self.rec_start_time)
            mins = dur // 60
            secs = dur % 60
            time_str = f"{mins:02d}:{secs:02d}"
            self.viewport.set_recording_state(True, time_str)

    def _take_snapshot(self):
        snap_path = self.camera_manager.take_snapshot()
        if snap_path and os.path.exists(snap_path):
            self.lbl_status_msg.setText(f"📸 Snapshot saved: {os.path.basename(snap_path)}")
            # Show brief notification toast / popup
            QToolTip.showText(self.btn_snapshot.mapToGlobal(QPoint(0, self.btn_snapshot.height())),
                              f"Snapshot saved:\n{snap_path}", self, QRect(), 3000)
        else:
            self.lbl_status_msg.setText("Failed to capture snapshot.")

    def _open_video_folder(self):
        os.makedirs(self.camera_manager.output_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.camera_manager.output_dir))

    def _play_last_video(self):
        last_video = self.camera_manager.last_recorded_video
        if last_video and os.path.exists(last_video):
            QDesktopServices.openUrl(QUrl.fromLocalFile(last_video))
        else:
            self._open_video_folder()

    def _on_camera_connected(self, connected: bool, name: str):
        self.viewport.set_connection_status(connected, name)
