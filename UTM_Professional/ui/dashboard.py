import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                 QPushButton, QLabel, QComboBox, QGroupBox, 
                                 QGridLayout, QMessageBox, QLineEdit,
                                 QCheckBox, QFrame, QScrollArea, QFileDialog, QSizePolicy, QLayout, QSplitter)
from PySide6.QtCore import Qt, QTimer, QTime, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QAction

from machine.machine_state import MachineState
from ui.graphs import LiveGraph
from ui.theme import Theme
from ui.history_dialog import HistoryDialog
from ui.diagnostic_dialog import DiagnosticDialog
from database.models import DBManager
from reports.generator import ReportGenerator
from reports.exporter import DataExporter
from camera.camera_manager import CameraManager
from ui.camera_widget import CameraWidget

class Dashboard(QMainWindow):
    def __init__(self, machine_controller, settings_manager):
        super().__init__()
        self.controller = machine_controller
        self.settings = settings_manager
        self.db_manager = DBManager()
        self.report_generator = ReportGenerator()
        
        self.setWindowTitle("UTM Professional v2.5 - Materials Testing Workstation")
        self.setMinimumSize(1020, 520)
        self.resize(1200, 750)
        
        # Apply Enterprise Light Theme
        self.setStyleSheet(Theme.get_stylesheet())
        
        # Test Duration Timer
        self.test_time = QTime(0, 0, 0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        
        # Initialize Enterprise Vision & Video Subsystem
        self.camera_manager = CameraManager()
        
        self._setup_menu()
        self._setup_ui()
        self._connect_signals()
        
        # Start camera capture thread safely after UI is completely initialized
        self.camera_manager.start_camera()
        
        # Apply initial dimensions
        self._update_dimensions()
        
        # Auto-detect and select connected machine COM port (e.g. COM3)
        self._refresh_ports()
        saved_port = self.settings.get("com_port")
        if saved_port and self.cb_ports.findText(saved_port) >= 0:
            self.cb_ports.setCurrentText(saved_port)

    def _setup_menu(self):
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("File")
        
        act_save = QAction("Save Current Test to DB", self)
        act_save.triggered.connect(self._save_test_to_db)
        file_menu.addAction(act_save)
        
        act_export = QAction("Export to CSV", self)
        act_export.triggered.connect(self._export_csv)
        file_menu.addAction(act_export)
        
        file_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)
        
        # Machine Menu
        machine_menu = menu_bar.addMenu("Machine")
        self.mock_action = QAction("Enable Simulation Mode", self)
        self.mock_action.setCheckable(True)
        self.mock_action.toggled.connect(self._on_mock_toggled)
        machine_menu.addAction(self.mock_action)
        
        act_tare = QAction("Zero / Tare Sensors", self)
        act_tare.triggered.connect(self.controller.tare)
        machine_menu.addAction(act_tare)
        
        act_diag = QAction("Hardware Diagnostics & Console", self)
        act_diag.triggered.connect(self._open_diagnostic_dialog)
        machine_menu.addAction(act_diag)
        
        # Vision & Camera Menu
        cam_menu = menu_bar.addMenu("Vision && Camera")
        act_dual_view = QAction("Dual View (Graph + Camera)", self)
        act_dual_view.triggered.connect(lambda: self._set_active_view("dual"))
        cam_menu.addAction(act_dual_view)
        
        act_graph_view = QAction("Live Graph Only", self)
        act_graph_view.triggered.connect(lambda: self._set_active_view("graph"))
        cam_menu.addAction(act_graph_view)
        
        act_cam_view = QAction("Live Camera & Vision Only", self)
        act_cam_view.triggered.connect(lambda: self._set_active_view("camera"))
        cam_menu.addAction(act_cam_view)
        
        cam_menu.addSeparator()
        act_snap = QAction("Take Video Snapshot", self)
        act_snap.triggered.connect(lambda: self.camera_widget._take_snapshot())
        cam_menu.addAction(act_snap)
        
        act_open_vids = QAction("Open Recorded Videos Folder", self)
        act_open_vids.triggered.connect(lambda: self.camera_widget._open_video_folder())
        cam_menu.addAction(act_open_vids)
        
        # Reports Menu
        reports_menu = menu_bar.addMenu("Reports")
        act_report = QAction("Generate PDF Report", self)
        act_report.triggered.connect(self._generate_pdf_report)
        reports_menu.addAction(act_report)
        
        # Database Menu
        database_menu = menu_bar.addMenu("Database")
        act_history = QAction("View Test History & Archives", self)
        act_history.triggered.connect(self._view_history)
        database_menu.addAction(act_history)

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 10, 14, 14)
        root_layout.setSpacing(10)
        
        # =========================================================================
        # 1. TOP HEADER & STATUS BAR (Light Professional)
        # =========================================================================
        header_card = QFrame()
        header_card.setObjectName("card")
        header_card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(16)
        
        # Brand & App Info
        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        lbl_brand_icon = QLabel("🔬")
        lbl_brand_icon.setStyleSheet("font-size: 22px;")
        
        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(0)
        lbl_app_name = QLabel("UTM PROFESSIONAL")
        lbl_app_name.setStyleSheet("font-size: 16px; font-weight: 800; color: #0284c7; letter-spacing: 0.5px;")
        lbl_app_sub = QLabel("Universal Testing Machine Workstation")
        lbl_app_sub.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        brand_text_box.addWidget(lbl_app_name)
        brand_text_box.addWidget(lbl_app_sub)
        
        brand_box.addWidget(lbl_brand_icon)
        brand_box.addLayout(brand_text_box)
        header_layout.addLayout(brand_box)
        
        header_layout.addSpacing(12)
        
        # Connection Status Pill
        self.pill_conn = QFrame()
        self.pill_conn.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 16px;
        """)
        conn_pill_layout = QHBoxLayout(self.pill_conn)
        conn_pill_layout.setContentsMargins(12, 4, 12, 4)
        conn_pill_layout.setSpacing(8)
        
        self.lbl_conn_dot = QLabel("●")
        self.lbl_conn_dot.setStyleSheet("color: #dc2626; font-size: 14px;")
        self.lbl_conn_status = QLabel("Disconnected")
        self.lbl_conn_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #dc2626;")
        conn_pill_layout.addWidget(self.lbl_conn_dot)
        conn_pill_layout.addWidget(self.lbl_conn_status)
        header_layout.addWidget(self.pill_conn)
        
        # Machine State Pill
        self.pill_state = QFrame()
        self.pill_state.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 16px;
        """)
        state_pill_layout = QHBoxLayout(self.pill_state)
        state_pill_layout.setContentsMargins(12, 4, 12, 4)
        state_pill_layout.setSpacing(6)
        
        lbl_state_title = QLabel("STATE:")
        lbl_state_title.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700;")
        self.lbl_state_val = QLabel("IDLE")
        self.lbl_state_val.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 12px;")
        state_pill_layout.addWidget(lbl_state_title)
        state_pill_layout.addWidget(self.lbl_state_val)
        header_layout.addWidget(self.pill_state)
        
        header_layout.addStretch()
        
        # Test Duration Clock
        clock_card = QFrame()
        clock_card.setStyleSheet("""
            background-color: #f0f9ff;
            border: 1px solid #0284c7;
            border-radius: 6px;
        """)
        clock_layout = QHBoxLayout(clock_card)
        clock_layout.setContentsMargins(10, 4, 10, 4)
        clock_layout.setSpacing(6)
        lbl_clock_icon = QLabel("⏱")
        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setStyleSheet("font-family: 'Consolas', monospace; font-size: 14px; font-weight: bold; color: #0284c7;")
        clock_layout.addWidget(lbl_clock_icon)
        clock_layout.addWidget(self.lbl_time)
        header_layout.addWidget(clock_card)
        
        # Simulation Mode Checkbox
        self.chk_mock = QCheckBox("Simulation Mode")
        self.chk_mock.setToolTip("Simulate live test curve without physical machine connection")
        self.chk_mock.toggled.connect(self._on_mock_toggled)
        header_layout.addWidget(self.chk_mock)
        
        root_layout.addWidget(header_card)
        
        # =========================================================================
        # 2. MAIN SPLIT WORKSPACE
        # =========================================================================
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(12)
        
        # -------------------------------------------------------------------------
        # LEFT SIDEBAR: SCROLLABLE HARDWARE & SPECIMEN SETUP
        # -------------------------------------------------------------------------
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setFixedWidth(380)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sidebar_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContent")
        sidebar_widget.setStyleSheet("#sidebarContent { background: transparent; }")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setSizeConstraint(QLayout.SetMinimumSize)
        sidebar_layout.setContentsMargins(0, 0, 6, 6)
        sidebar_layout.setSpacing(10)
        
        # Card A: Hardware Connection
        grp_conn = QGroupBox("Hardware Connection")
        grp_conn_layout = QVBoxLayout(grp_conn)
        grp_conn_layout.setContentsMargins(10, 10, 10, 10)
        grp_conn_layout.setSpacing(8)
        
        port_row = QHBoxLayout()
        port_row.setSpacing(6)
        lbl_p = QLabel("Port:")
        lbl_p.setFixedWidth(38)
        self.cb_ports = QComboBox()
        self.cb_ports.addItems(self.controller.serial_manager.get_available_ports())
        self.btn_refresh_ports = QPushButton("↻")
        self.btn_refresh_ports.setFixedSize(30, 26)
        self.btn_refresh_ports.setStyleSheet("padding: 0px; font-size: 15px; font-weight: bold; background-color: #f1f5f9;")
        self.btn_refresh_ports.setToolTip("Scan COM Ports")
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        port_row.addWidget(lbl_p)
        port_row.addWidget(self.cb_ports, 1)
        port_row.addWidget(self.btn_refresh_ports)
        grp_conn_layout.addLayout(port_row)
        
        baud_row = QHBoxLayout()
        baud_row.setSpacing(6)
        lbl_b = QLabel("Baud:")
        lbl_b.setFixedWidth(38)
        self.cb_baud = QComboBox()
        self.cb_baud.addItems(["9600", "2400", "4800", "19200", "38400", "57600", "115200"])
        baud_row.addWidget(lbl_b)
        baud_row.addWidget(self.cb_baud, 1)
        
        self.chk_dtr = QCheckBox("DTR")
        self.chk_dtr.setChecked(True)
        self.chk_dtr.setToolTip("Data Terminal Ready pin")
        self.chk_rts = QCheckBox("RTS")
        self.chk_rts.setChecked(True)
        self.chk_rts.setToolTip("Request to Send pin")
        baud_row.addSpacing(6)
        baud_row.addWidget(self.chk_dtr)
        baud_row.addWidget(self.chk_rts)
        grp_conn_layout.addLayout(baud_row)
        
        self.btn_connect = QPushButton("CONNECT TO MACHINE")
        self.btn_connect.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; font-size: 12px; padding: 6px; border-radius: 6px; border: 1px solid #0369a1;")
        grp_conn_layout.addWidget(self.btn_connect)
        
        sidebar_layout.addWidget(grp_conn)
        
        # Card B: Specimen & Test Parameters
        grp_specimen = QGroupBox("Specimen && Test Setup")
        grp_specimen_layout = QVBoxLayout(grp_specimen)
        grp_specimen_layout.setContentsMargins(10, 10, 10, 10)
        grp_specimen_layout.setSpacing(8)
        
        grid_params = QGridLayout()
        grid_params.setVerticalSpacing(8)
        grid_params.setHorizontalSpacing(8)
        grid_params.setColumnStretch(1, 1)
        grid_params.setColumnStretch(3, 1)
        
        def _create_param_input(val):
            inp = QLineEdit(val)
            return inp

        # Row 0: Sample ID & Material
        lbl_sm = QLabel("Sample:")
        lbl_sm.setStyleSheet("font-weight: 500; color: #475569;")
        self.in_sample = _create_param_input("SMP-001")
        lbl_mat = QLabel("Material:")
        lbl_mat.setStyleSheet("font-weight: 500; color: #475569;")
        self.in_material = _create_param_input("Steel 1018")
        grid_params.addWidget(lbl_sm, 0, 0)
        grid_params.addWidget(self.in_sample, 0, 1)
        grid_params.addWidget(lbl_mat, 0, 2)
        grid_params.addWidget(self.in_material, 0, 3)
        
        # Row 1: Standard & Operator
        lbl_std = QLabel("Standard:")
        lbl_std.setStyleSheet("font-weight: 500; color: #475569;")
        self.in_standard = _create_param_input("ASTM E8")
        lbl_op = QLabel("Operator:")
        lbl_op.setStyleSheet("font-weight: 500; color: #475569;")
        self.in_operator = _create_param_input("Engineer")
        grid_params.addWidget(lbl_std, 1, 0)
        grid_params.addWidget(self.in_standard, 1, 1)
        grid_params.addWidget(lbl_op, 1, 2)
        grid_params.addWidget(self.in_operator, 1, 3)
        
        # Row 2: Customer (Spans full width)
        lbl_cust = QLabel("Customer:")
        lbl_cust.setStyleSheet("font-weight: 500; color: #475569;")
        self.in_customer = _create_param_input("Lab Standard")
        grid_params.addWidget(lbl_cust, 2, 0)
        grid_params.addWidget(self.in_customer, 2, 1, 1, 3)
        
        grp_specimen_layout.addLayout(grid_params)
        
        # Geometry Dimensions Sub-section
        lbl_geom = QLabel("Geometry Dimensions:")
        lbl_geom.setStyleSheet("font-weight: 700; color: #0284c7; font-size: 11px; margin-top: 2px;")
        grp_specimen_layout.addWidget(lbl_geom)
        
        dim_row = QHBoxLayout()
        dim_row.setSpacing(6)
        
        def _create_dim_box(label_text, default_val):
            box = QVBoxLayout()
            box.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 10px; color: #64748b; font-weight: 600;")
            lbl.setAlignment(Qt.AlignCenter)
            inp = QLineEdit(default_val)
            inp.setAlignment(Qt.AlignCenter)
            box.addWidget(lbl)
            box.addWidget(inp)
            return box, inp

        box_w, self.in_width = _create_dim_box("Width (mm)", "10.0")
        box_th, self.in_thickness = _create_dim_box("Thick (mm)", "5.0")
        box_ga, self.in_gauge = _create_dim_box("Gauge (mm)", "50.0")
        
        dim_row.addLayout(box_w)
        dim_row.addLayout(box_th)
        dim_row.addLayout(box_ga)
        grp_specimen_layout.addLayout(dim_row)
        
        # Dynamic Cross-Section Area Display
        self.card_area = QFrame()
        self.card_area.setMinimumHeight(30)
        self.card_area.setStyleSheet("""
            background-color: #f0fdf4;
            border: 1px dashed #16a34a;
            border-radius: 6px;
        """)
        area_layout = QHBoxLayout(self.card_area)
        area_layout.setContentsMargins(10, 4, 10, 4)
        lbl_area_title = QLabel("Cross-Section Area:")
        lbl_area_title.setStyleSheet("font-size: 11px; color: #166534; font-weight: 600;")
        self.lbl_area_val = QLabel("50.00 mm²")
        self.lbl_area_val.setStyleSheet("font-size: 13px; font-weight: bold; color: #15803d;")
        area_layout.addWidget(lbl_area_title)
        area_layout.addStretch()
        area_layout.addWidget(self.lbl_area_val)
        grp_specimen_layout.addWidget(self.card_area)
        
        sidebar_layout.addWidget(grp_specimen)
        
        # Card C: Safety & Diagnostic Tools
        grp_auto = QGroupBox("Safety && Diagnostics")
        auto_layout = QVBoxLayout(grp_auto)
        auto_layout.setContentsMargins(10, 10, 10, 10)
        auto_layout.setSpacing(6)
        
        self.chk_autobreak = QCheckBox("Auto-Break Detection (40%)")
        self.chk_autobreak.setChecked(True)
        self.chk_autobreak.setToolTip("Automatically halts test when specimen fractures")
        auto_layout.addWidget(self.chk_autobreak)
        
        lbl_filter = QLabel("✔ Noise Filter: 5-Point Rolling Avg")
        lbl_filter.setStyleSheet("font-size: 11px; color: #16a34a; font-weight: 500;")
        auto_layout.addWidget(lbl_filter)
        
        self.btn_open_diag = QPushButton("Diagnostic & Serial Console")
        self.btn_open_diag.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; font-weight: 600;")
        self.btn_open_diag.setToolTip("Send raw commands & inspect incoming packets")
        self.btn_open_diag.clicked.connect(self._open_diagnostic_dialog)
        auto_layout.addWidget(self.btn_open_diag)
        
        sidebar_layout.addWidget(grp_auto)
        sidebar_layout.addStretch()
        
        self.sidebar_scroll.setWidget(sidebar_widget)
        workspace_layout.addWidget(self.sidebar_scroll)
        
        # -------------------------------------------------------------------------
        # RIGHT MAIN MONITORING AREA
        # -------------------------------------------------------------------------
        main_content = QVBoxLayout()
        main_content.setSpacing(6)
        
        # A. Digital KPI Metric Cards (Gauges)
        gauge_grid = QGridLayout()
        gauge_grid.setSpacing(6)
        
        self.lbl_load = self._create_kpi_card("LIVE LOAD", "0.00", "kN", "#0284c7", gauge_grid, 0, 0)
        self.lbl_stress = self._create_kpi_card("LIVE STRESS", "0.00", "MPa", "#7c3aed", gauge_grid, 0, 1)
        self.lbl_ext = self._create_kpi_card("EXTENSION", "0.00", "mm", "#d97706", gauge_grid, 0, 2)
        
        self.lbl_strain = self._create_kpi_card("STRAIN", "0.00", "%", "#0d9488", gauge_grid, 1, 0)
        self.lbl_peak_load = self._create_kpi_card("PEAK LOAD", "0.00", "kN", "#16a34a", gauge_grid, 1, 1, tag="MAX")
        self.lbl_peak_stress = self._create_kpi_card("PEAK STRESS", "0.00", "MPa", "#16a34a", gauge_grid, 1, 2, tag="UTS")
        
        main_content.addLayout(gauge_grid)
        
        # B. View Mode Switcher Header
        view_bar = QFrame()
        view_bar.setObjectName("card")
        view_bar.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        view_bar_layout = QHBoxLayout(view_bar)
        view_bar_layout.setContentsMargins(10, 6, 10, 6)
        view_bar_layout.setSpacing(8)
        
        lbl_view_title = QLabel("DISPLAY VIEW:")
        lbl_view_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")
        view_bar_layout.addWidget(lbl_view_title)
        
        self.btn_view_dual = QPushButton("Dual View (Graph + Camera)")
        self.btn_view_graph = QPushButton("Live Graph View")
        self.btn_view_camera = QPushButton("Live Camera View")
        
        for btn in (self.btn_view_dual, self.btn_view_graph, self.btn_view_camera):
            btn.setCursor(Qt.PointingHandCursor)
            view_bar_layout.addWidget(btn)
            
        self.btn_view_dual.clicked.connect(lambda: self._set_active_view("dual"))
        self.btn_view_graph.clicked.connect(lambda: self._set_active_view("graph"))
        self.btn_view_camera.clicked.connect(lambda: self._set_active_view("camera"))
        
        view_bar_layout.addStretch()
        
        # Camera Quick Status Tag in view bar
        self.lbl_cam_indicator = QLabel("● Vision Active")
        self.lbl_cam_indicator.setStyleSheet("font-size: 11px; font-weight: 700; color: #16a34a; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 2px 10px;")
        view_bar_layout.addWidget(self.lbl_cam_indicator)
        
        main_content.addWidget(view_bar)
        
        # C. Center Monitoring Workspace (Resizable Splitter for Dual/Single View)
        self.view_splitter = QSplitter(Qt.Horizontal)
        self.view_splitter.setChildrenCollapsible(False)
        self.view_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 4px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #0284c7;
            }
        """)
        
        # Container 1: Live Graph Card
        self.graph_card = QFrame()
        self.graph_card.setObjectName("card")
        self.graph_card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        graph_layout = QVBoxLayout(self.graph_card)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        self.graph = LiveGraph()
        graph_layout.addWidget(self.graph)
        self.view_splitter.addWidget(self.graph_card)
        
        # Container 2: Live Camera & Vision Card
        self.camera_card = QFrame()
        self.camera_card.setObjectName("card")
        self.camera_card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        camera_layout = QVBoxLayout(self.camera_card)
        camera_layout.setContentsMargins(6, 6, 6, 6)
        self.camera_widget = CameraWidget(self.camera_manager, self)
        camera_layout.addWidget(self.camera_widget)
        self.view_splitter.addWidget(self.camera_card)
        
        main_content.addWidget(self.view_splitter, 1)
        
        # Set default view to Dual View
        self._set_active_view("dual")
        
        # C. Bottom Action Controls Dock (Proper Spacing & No Truncation)
        action_bar = QFrame()
        action_bar.setObjectName("card")
        action_bar.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(12, 10, 12, 10)
        action_layout.setSpacing(8)
        
        # Primary Test Controls
        self.btn_start = QPushButton("START TEST")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.btn_stop = QPushButton("STOP TEST")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.btn_tare = QPushButton("ZERO / TARE")
        self.btn_tare.setObjectName("btnTare")
        self.btn_tare.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        action_layout.addWidget(self.btn_start)
        action_layout.addWidget(self.btn_stop)
        action_layout.addWidget(self.btn_tare)
        
        action_layout.addStretch()
        
        # Data & Report Controls
        self.btn_pdf = QPushButton("PDF REPORT")
        self.btn_pdf.setObjectName("btnPdf")
        self.btn_pdf.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.btn_export = QPushButton("EXPORT CSV")
        self.btn_export.setObjectName("btnExport")
        self.btn_export.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.btn_save_db = QPushButton("SAVE TEST")
        self.btn_save_db.setObjectName("btnPrimary")
        self.btn_save_db.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.btn_history = QPushButton("HISTORY")
        self.btn_history.setObjectName("btnHistory")
        self.btn_history.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        action_layout.addWidget(self.btn_pdf)
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_save_db)
        action_layout.addWidget(self.btn_history)
        
        main_content.addWidget(action_bar)
        
        workspace_layout.addLayout(main_content, 1)
        root_layout.addLayout(workspace_layout, 1)

    def _create_kpi_card(self, title, default_val, unit, accent_color, layout, row, col, tag=None):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            #card {{
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: 3px solid {accent_color};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 4, 10, 4)
        card_layout.setSpacing(1)
        
        header_row = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #475569; letter-spacing: 0.5px;")
        header_row.addWidget(lbl_title)
        
        if tag:
            lbl_tag = QLabel(tag)
            lbl_tag.setStyleSheet(f"""
                background-color: {accent_color};
                color: #ffffff;
                font-size: 8px;
                font-weight: 800;
                border-radius: 3px;
                padding: 1px 4px;
            """)
            header_row.addStretch()
            header_row.addWidget(lbl_tag)
        else:
            header_row.addStretch()
            
        card_layout.addLayout(header_row)
        
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        lbl_val = QLabel(default_val)
        lbl_val.setStyleSheet(f"font-family: 'Consolas', monospace; font-size: 20px; font-weight: 800; color: {accent_color};")
        lbl_val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; padding-bottom: 2px;")
        lbl_unit.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        
        val_row.addWidget(lbl_val)
        val_row.addWidget(lbl_unit)
        val_row.addStretch()
        
        card_layout.addLayout(val_row)
        layout.addWidget(card, row, col)
        
        return lbl_val

    def _connect_signals(self):
        self.btn_connect.clicked.connect(self._toggle_connection)
        self.btn_start.clicked.connect(self._start_test)
        self.btn_stop.clicked.connect(self._stop_test)
        self.btn_tare.clicked.connect(self.controller.tare)
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_pdf.clicked.connect(self._generate_pdf_report)
        self.btn_save_db.clicked.connect(self._save_test_to_db)
        self.btn_history.clicked.connect(self._view_history)
        
        self.controller.state_changed.connect(self._update_state_ui)
        self.controller.data_updated.connect(self._update_live_data)
        self.controller.serial_manager.connection_status_changed.connect(self._on_connection_changed)
        self.controller.alarm_triggered.connect(self._show_alarm)
        
        self.camera_manager.recording_started.connect(self._on_cam_recording_started)
        self.camera_manager.recording_stopped.connect(self._on_cam_recording_stopped)
        
        self.in_width.textChanged.connect(self._update_dimensions)
        self.in_thickness.textChanged.connect(self._update_dimensions)
        self.in_gauge.textChanged.connect(self._update_dimensions)
        self.chk_autobreak.toggled.connect(self._on_autobreak_toggled)
        self.cb_baud.currentTextChanged.connect(self._on_baud_changed)

    def _refresh_ports(self):
        current = self.cb_ports.currentText()
        self.cb_ports.clear()
        ports = self.controller.serial_manager.get_available_ports()
        self.cb_ports.addItems(ports)
        if current in ports:
            self.cb_ports.setCurrentText(current)
        elif "COM3" in ports:
            self.cb_ports.setCurrentText("COM3")
        elif ports:
            self.cb_ports.setCurrentIndex(0)

    def _on_mock_toggled(self, checked: bool):
        self.controller.enable_mock_mode(checked)
        self.chk_mock.setChecked(checked)
        self.mock_action.setChecked(checked)
        if checked:
            self.lbl_conn_dot.setStyleSheet("color: #0284c7; font-size: 14px;")
            self.lbl_conn_status.setText("Simulation Active")
            self.lbl_conn_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #0284c7;")
        else:
            is_conn = self.controller.serial_manager.is_connected
            self._on_connection_changed(is_conn, self.cb_ports.currentText())

    def _on_autobreak_toggled(self, checked: bool):
        self.controller.auto_break_enabled = checked

    def _open_diagnostic_dialog(self):
        dlg = DiagnosticDialog(self.controller.serial_manager, self)
        dlg.exec()

    def _update_dimensions(self):
        try:
            w = float(self.in_width.text() or 0)
            t = float(self.in_thickness.text() or 0)
            g = float(self.in_gauge.text() or 0)
            area = w * t
            self.lbl_area_val.setText(f"{area:.2f} mm²")
            self.controller.set_sample_dimensions(w, t, g)
        except ValueError:
            self.lbl_area_val.setText("Invalid mm²")

    def _get_ui_metadata(self):
        return {
            "operator": self.in_operator.text(),
            "customer": self.in_customer.text(),
            "sample": self.in_sample.text(),
            "material": self.in_material.text(),
            "standard": self.in_standard.text(),
            "width": float(self.in_width.text() or 0),
            "thickness": float(self.in_thickness.text() or 0),
            "gauge_length": float(self.in_gauge.text() or 0)
        }

    def _save_test_to_db(self):
        if len(self.graph.data["Time (s)"]) == 0:
            QMessageBox.information(self, "No Data", "No test data available to save.")
            return
            
        meta = self._get_ui_metadata()
        meta["video_path"] = getattr(self.camera_manager, 'last_recorded_video', '')
        meta["snapshot_path"] = getattr(self.camera_manager.worker, '_latest_snapshot_path', '')
        res = {
            "peak_load": self.controller.peak_load,
            "peak_stress": self.controller.peak_stress
        }
        arrays = {
            "time": self.graph.data["Time (s)"],
            "load": self.graph.data["Load (kN)"],
            "ext": self.graph.data["Extension (mm)"]
        }
        
        record_id = self.db_manager.save_test(meta, res, arrays)
        if record_id:
            QMessageBox.information(self, "Test Saved", f"Test record successfully saved to local database!\nRecord ID: #{record_id}")
        else:
            QMessageBox.critical(self, "Error", "Failed to save test to database.")

    def _export_csv(self):
        has_controller_data = bool(self.controller.test_data and len(self.controller.test_data) > 0)
        has_graph_data = bool(len(self.graph.data["Time (s)"]) > 0)
        
        if not has_controller_data and not has_graph_data:
            QMessageBox.warning(self, "No Test Data", "There is no test data available to export.\nPlease run a test first.")
            return

        from datetime import datetime
        output_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(output_dir, exist_ok=True)
        
        sample_id = self.in_sample.text().strip().replace(" ", "_") or "SMP-001"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = os.path.join(output_dir, f"UTM_Data_{sample_id}_{timestamp}.csv")
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Test Data to CSV / Excel", 
            default_filename, 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filepath:
            return  # User dismissed or cancelled
            
        if not filepath.endswith('.csv'):
            filepath += '.csv'
            
        meta = self._get_ui_metadata()
        res = {
            "peak_load": self.controller.peak_load,
            "peak_stress": self.controller.peak_stress
        }
        arrays = {
            "time": self.graph.data["Time (s)"],
            "load": self.graph.data["Load (kN)"],
            "ext": self.graph.data["Extension (mm)"],
            "stress": self.graph.data["Stress (MPa)"],
            "strain": self.graph.data["Strain (%)"]
        }
        
        try:
            saved_file = DataExporter.export_csv(
                metadata=meta,
                results=res,
                data_points=self.controller.test_data,
                arrays=arrays,
                filepath=filepath
            )
            
            if saved_file and os.path.exists(saved_file):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Export Successful")
                msg_box.setText(f"Data successfully exported to:\n{saved_file}")
                
                btn_open_file = msg_box.addButton("Open CSV in Excel", QMessageBox.ActionRole)
                btn_open_folder = msg_box.addButton("Open Folder", QMessageBox.ActionRole)
                msg_box.addButton(QMessageBox.Ok)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == btn_open_file:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(saved_file))
                elif msg_box.clickedButton() == btn_open_folder:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(saved_file)))
            else:
                QMessageBox.critical(self, "Export Error", "Failed to write CSV file.")
        except PermissionError:
            QMessageBox.critical(
                self, 
                "File Locked", 
                f"Cannot save to:\n{filepath}\n\nThe file is currently open in Excel or another program. Please close it and try again."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred while exporting:\n{str(e)}")

    def _generate_pdf_report(self):
        if len(self.graph.data["Time (s)"]) == 0:
            QMessageBox.information(self, "No Data", "Run a test first to generate a report.")
            return
            
        img_path = os.path.join(os.getcwd(), "temp_graph.png")
        self.graph.export_image(img_path)
        
        meta = self._get_ui_metadata()
        meta["video_path"] = getattr(self.camera_manager, 'last_recorded_video', '')
        snap_path = getattr(self.camera_manager.worker, '_latest_snapshot_path', None)
        res = {
            "peak_load": self.controller.peak_load,
            "peak_stress": self.controller.peak_stress
        }
        
        try:
            pdf_file = self.report_generator.generate_pdf(meta, res, img_path, snapshot_path=snap_path)
            if os.path.exists(img_path):
                os.remove(img_path)
                
            QMessageBox.information(self, "Report Generated", f"Official PDF report created at:\n{pdf_file}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_file))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {e}")

    def _view_history(self):
        dialog = HistoryDialog(self.db_manager, self)
        dialog.exec()

    def _toggle_connection(self):
        if not self.controller.serial_manager.is_connected:
            port = self.cb_ports.currentText()
            try:
                baud = int(self.cb_baud.currentText())
            except ValueError:
                baud = 9600
                
            dtr = self.chk_dtr.isChecked()
            rts = self.chk_rts.isChecked()
            
            if port:
                self.controller.serial_manager.baudrate = baud
                self.controller.serial_manager.dtr_state = dtr
                self.controller.serial_manager.rts_state = rts
                self.controller.serial_manager.connect(port)
        else:
            self.controller.serial_manager.disconnect()

    def _on_baud_changed(self, new_baud_str):
        try:
            baud = int(new_baud_str)
            self.controller.serial_manager.baudrate = baud
            if self.controller.serial_manager.is_connected and self.controller.serial_manager.serial_conn:
                self.controller.serial_manager.serial_conn.baudrate = baud
                self.lbl_conn_status.setText(f"{self.cb_ports.currentText()} @ {baud}")
        except Exception as e:
            pass

    def _on_connection_changed(self, connected: bool, port: str):
        if connected:
            self.btn_connect.setText("DISCONNECT")
            self.btn_connect.setStyleSheet("background-color: #dc2626; color: white; border: 1px solid #b91c1c;")
            self.lbl_conn_dot.setStyleSheet("color: #16a34a; font-size: 14px;")
            self.lbl_conn_status.setText(f"{port} @ {self.controller.serial_manager.baudrate}")
            self.lbl_conn_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #16a34a;")
            self.cb_ports.setEnabled(False)
            # Baud rate and Refresh remain enabled so the user can easily re-scan or switch baud rates!
        else:
            self.btn_connect.setText("CONNECT TO MACHINE")
            self.btn_connect.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 6px; border: 1px solid #0369a1;")
            self.lbl_conn_dot.setStyleSheet("color: #dc2626; font-size: 14px;")
            self.lbl_conn_status.setText("Disconnected")
            self.lbl_conn_status.setStyleSheet("font-weight: 600; font-size: 12px; color: #dc2626;")
            self.cb_ports.setEnabled(True)
            self.cb_baud.setEnabled(True)
            self.chk_dtr.setEnabled(True)
            self.chk_rts.setEnabled(True)
            self.btn_refresh_ports.setEnabled(True)

    def _show_alarm(self, msg: str):
        if "Raw Machine Data" in msg or "Protocol Decode Error" in msg:
            print(f"[Warning Suppressed]: {msg}")
        else:
            QMessageBox.warning(self, "Machine Alarm", msg)

    def _update_state_ui(self, state: MachineState):
        self.lbl_state_val.setText(state.name)
        
        if state == MachineState.RUNNING:
            self.lbl_state_val.setStyleSheet("color: #16a34a; font-weight: 800; font-size: 12px;")
            self.test_time = QTime(0, 0, 0)
            self.timer.start(1000)
            # Synchronized Auto-Recording on Test Start
            if hasattr(self, 'camera_widget') and self.camera_widget.chk_auto_rec.isChecked():
                sample_id = self.in_sample.text().strip() or "SMP-001"
                self.camera_manager.start_recording(sample_id)
        elif state == MachineState.COMPLETED:
            self.lbl_state_val.setStyleSheet("color: #0284c7; font-weight: 800; font-size: 12px;")
            self.timer.stop()
            # Capture specimen fracture surface snapshot upon test completion
            if hasattr(self, 'camera_manager'):
                try:
                    self.camera_manager.take_snapshot()
                except Exception:
                    pass
                if self.camera_manager.is_recording():
                    self.camera_manager.stop_recording()
        elif state in [MachineState.EMERGENCY_STOP, MachineState.COMMUNICATION_LOST]:
            self.lbl_state_val.setStyleSheet("color: #dc2626; font-weight: 800; font-size: 12px;")
            self.timer.stop()
            if hasattr(self, 'camera_manager') and self.camera_manager.is_recording():
                self.camera_manager.stop_recording()
        else:
            self.lbl_state_val.setStyleSheet("color: #0f172a; font-weight: 700; font-size: 12px;")
            self.timer.stop()
            if hasattr(self, 'camera_manager') and self.camera_manager.is_recording():
                self.camera_manager.stop_recording()

    def _start_test(self):
        if self.controller.mock_mode or self.controller.serial_manager.is_connected:
            self.graph.clear_graph()
            self.test_time = QTime(0, 0, 0)
            self.lbl_time.setText("00:00:00")
            self.controller.start_test()
        else:
            res = QMessageBox.question(
                self, 
                "Machine Hardware Offline", 
                "Physical UTM machine is not connected to a COM port.\n\n"
                "Would you like to start the test in Simulation Mode\n"
                "(with live curve generation and synchronized camera recording)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if res == QMessageBox.Yes:
                self.chk_mock.setChecked(True)
                self.controller.enable_mock_mode(True)
                self.graph.clear_graph()
                self.test_time = QTime(0, 0, 0)
                self.lbl_time.setText("00:00:00")
                self.controller.start_test()

    def _stop_test(self):
        # 1. Stop hardware / simulation controller
        if hasattr(self, 'controller'):
            self.controller.stop_test()
            
        # 2. Stop UI timer
        self.timer.stop()
        
        # 3. Always guarantee video recording is stopped and saved!
        if hasattr(self, 'camera_manager') and self.camera_manager.is_recording():
            self.camera_manager.stop_recording()

    def _update_time(self):
        self.test_time = self.test_time.addSecs(1)
        self.lbl_time.setText(self.test_time.toString("hh:mm:ss"))

    def _update_live_data(self, data: dict):
        self.latest_data = data
        if not hasattr(self, 'ui_update_timer'):
            self.ui_update_timer = QTimer()
            self.ui_update_timer.timeout.connect(self._safe_update_labels)
            self.ui_update_timer.start(100) # Throttled UI refresh to 10 Hz

    def _safe_update_labels(self):
        if not hasattr(self, 'latest_data') or not self.latest_data:
            return
            
        data = self.latest_data
        load_kN = data.get('LOAD_kN', 0.0)
        stress = data.get('STRESS', 0.0)
        ext = data.get('EXT', 0.0)
        strain = data.get('STRAIN', 0.0)
        p_load = data.get('PEAK_LOAD', 0.0)
        p_stress = data.get('PEAK_STRESS', 0.0)
        time_s = data.get('time', 0.0)
        
        self.lbl_load.setText(f"{load_kN:.2f}")
        self.lbl_stress.setText(f"{stress:.2f}")
        self.lbl_ext.setText(f"{ext:.2f}")
        self.lbl_strain.setText(f"{strain:.2f}")
        self.lbl_peak_load.setText(f"{p_load:.2f}")
        self.lbl_peak_stress.setText(f"{p_stress:.2f}")
        
        self.graph.add_point(time_s, load_kN, ext, stress, strain)
        
        # Stamped Live Machine Telemetry into Camera Recording HUD
        if hasattr(self, 'camera_manager'):
            self.camera_manager.update_telemetry({
                "load_kN": load_kN,
                "stress_MPa": stress,
                "ext_mm": ext,
                "strain_pct": strain,
                "time_str": self.lbl_time.text(),
                "state_str": self.lbl_state_val.text(),
                "sample_id": self.in_sample.text(),
                "material": self.in_material.text(),
                "standard": self.in_standard.text()
            })

    def _on_cam_recording_started(self, path: str):
        self.lbl_cam_indicator.setText("● REC ACTIVE")
        self.lbl_cam_indicator.setStyleSheet("font-size: 11px; font-weight: 700; color: #dc2626; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 2px 10px;")

    def _on_cam_recording_stopped(self, path: str, duration: float):
        self.lbl_cam_indicator.setText("● Vision Ready")
        self.lbl_cam_indicator.setStyleSheet("font-size: 11px; font-weight: 700; color: #16a34a; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 2px 10px;")
        
        if path and os.path.exists(path) and os.path.getsize(path) > 2048:
            file_size_mb = os.path.getsize(path) / (1024 * 1024)
            size_str = f"{file_size_mb:.2f} MB" if file_size_mb >= 1.0 else f"{os.path.getsize(path)/1024:.0f} KB"
            fname = os.path.basename(path)
            self._show_video_saved_dialog(path, fname, size_str, duration)

    def _show_video_saved_dialog(self, path: str, fname: str, size_str: str, duration: float):
        msg = QMessageBox(self)
        msg.setWindowTitle("Video Recording Saved - UTM Professional")
        msg.setIcon(QMessageBox.Information)
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            f"<h3 style='color: #16a34a; margin-bottom: 6px;'>✔ Video Recording Saved Successfully!</h3>"
            f"<p style='font-size: 12px; color: #1e293b; margin: 4px 0;'>"
            f"<b>File:</b> <code>{fname}</code><br>"
            f"<b>Size:</b> {size_str} &nbsp;|&nbsp; <b>Duration:</b> {duration:.1f}s<br>"
            f"<b>Location:</b> <span style='color: #0284c7;'>{os.path.dirname(path)}</span>"
            f"</p>"
            f"<p style='font-size: 11px; color: #64748b; margin-top: 6px;'>"
            f"Machine telemetry (Load, Stress, Strain, Ext) and specimen tracking overlays have been permanently stamped onto this video."
            f"</p>"
        )
        btn_play = msg.addButton("▶ Play Video", QMessageBox.ActionRole)
        btn_open = msg.addButton("📁 Open Folder", QMessageBox.ActionRole)
        btn_ok = msg.addButton("OK", QMessageBox.AcceptRole)
        msg.setDefaultButton(btn_play)
        
        btn_play.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; font-size: 11px;")
        btn_open.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; font-size: 11px;")
        btn_ok.setStyleSheet("background-color: #f1f5f9; color: #334155; font-weight: bold; padding: 6px 14px; border-radius: 4px; font-size: 11px;")
        
        msg.exec()
        
        if msg.clickedButton() == btn_play:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif msg.clickedButton() == btn_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _set_active_view(self, mode: str):
        self.active_view = mode
        
        for btn, btn_mode in [(self.btn_view_dual, "dual"), 
                              (self.btn_view_graph, "graph"), 
                              (self.btn_view_camera, "camera")]:
            if mode == btn_mode:
                btn.setStyleSheet("""
                    background-color: #0284c7;
                    color: #ffffff;
                    border: 1px solid #0369a1;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 14px;
                """)
            else:
                btn.setStyleSheet("""
                    background-color: #f1f5f9;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 14px;
                """)

        if mode == "graph":
            self.graph_card.setVisible(True)
            self.camera_card.setVisible(False)
        elif mode == "camera":
            self.graph_card.setVisible(False)
            self.camera_card.setVisible(True)
        elif mode == "dual":
            self.graph_card.setVisible(True)
            self.camera_card.setVisible(True)
            total_w = self.view_splitter.width() or 800
            self.view_splitter.setSizes([total_w // 2, total_w // 2])

    def closeEvent(self, event):
        if hasattr(self, 'camera_manager'):
            self.camera_manager.stop_camera()
        if hasattr(self, 'controller') and self.controller.state == MachineState.RUNNING:
            self.controller.stop_test()
        event.accept()
