import pyqtgraph as pg
import pyqtgraph.exporters
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                                 QLabel, QPushButton, QFrame)
from PySide6.QtCore import Qt, QTimer
from ui.theme import Theme

class LiveGraph(QWidget):
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        
        # --- Top Graph Controls & Status Bar ---
        top_bar = QFrame()
        top_bar.setObjectName("graphTopBar")
        top_bar.setStyleSheet("""
            #graphTopBar {
                background-color: transparent;
                border: none;
            }
        """)
        bar_layout = QHBoxLayout(top_bar)
        bar_layout.setContentsMargins(6, 4, 6, 4)
        bar_layout.setSpacing(10)
        
        # Axis Selection
        lbl_x = QLabel("X:")
        lbl_x.setStyleSheet("font-weight: 600; color: #475569;")
        self.cb_xaxis = QComboBox()
        self.cb_xaxis.addItems(["Time (s)", "Extension (mm)", "Strain (%)"])
        
        lbl_y = QLabel("Y:")
        lbl_y.setStyleSheet("font-weight: 600; color: #475569;")
        self.cb_yaxis = QComboBox()
        self.cb_yaxis.addItems(["Load (kN)", "Stress (MPa)"])
        
        bar_layout.addWidget(lbl_x)
        bar_layout.addWidget(self.cb_xaxis)
        bar_layout.addWidget(lbl_y)
        bar_layout.addWidget(self.cb_yaxis)
        
        # Live Cursor Coordinate Readout
        self.lbl_cursor = QLabel("X: -- | Y: --")
        self.lbl_cursor.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px; color: #0284c7; font-weight: bold;")
        bar_layout.addWidget(self.lbl_cursor)
        
        bar_layout.addStretch()
        
        # Graph Toolbar Actions
        self.btn_autorange = QPushButton("⛶ Fit")
        self.btn_autorange.setToolTip("Auto-fit Graph to Data")
        self.btn_autorange.clicked.connect(self._auto_range)
        bar_layout.addWidget(self.btn_autorange)
        
        self.btn_grid = QPushButton("Grid")
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(True)
        self.btn_grid.setToolTip("Toggle Grid Lines")
        self.btn_grid.clicked.connect(self._toggle_grid)
        bar_layout.addWidget(self.btn_grid)
        
        main_layout.addWidget(top_bar)
        
        # --- High-Performance PyQtGraph Widget (Light Theme) ---
        pg.setConfigOptions(antialias=True)
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#ffffff")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.5)
        self.plot_widget.setMenuEnabled(True)
        self.plot_widget.addLegend(offset=(10, 10))
        
        # Configure axes for light mode
        axis_pen = pg.mkPen(color="#475569", width=1)
        for ax in ['left', 'bottom']:
            axis = self.plot_widget.getAxis(ax)
            axis.setPen(axis_pen)
            axis.setTextPen(axis_pen)
        
        self.curve = self.plot_widget.plot(
            name="Specimen Test Curve", 
            pen=pg.mkPen(color='#0284c7', width=2.5)
        )
        
        main_layout.addWidget(self.plot_widget, 1)
        
        # Data storage
        self.data = {
            "Time (s)": [],
            "Load (kN)": [],
            "Extension (mm)": [],
            "Stress (MPa)": [],
            "Strain (%)": []
        }
        
        self.current_x_key = "Time (s)"
        self.current_y_key = "Load (kN)"
        
        self._update_labels()
        
        # Connect signals
        self.cb_xaxis.currentTextChanged.connect(self._on_axis_changed)
        self.cb_yaxis.currentTextChanged.connect(self._on_axis_changed)
        
        # Cursor tracking proxy
        self.proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved, 
            rateLimit=30, 
            slot=self._on_mouse_moved
        )
        
        # Throttled graph refresh (~30 FPS)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_plot)
        self.update_timer.start(33)
        self._needs_update = False

    def _auto_range(self):
        self.plot_widget.autoRange()

    def _toggle_grid(self):
        show = self.btn_grid.isChecked()
        alpha = 0.5 if show else 0.0
        self.plot_widget.showGrid(x=show, y=show, alpha=alpha)

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            y_val = mouse_point.y()
            self.lbl_cursor.setText(f"X: {x_val:.2f} | Y: {y_val:.2f}")

    def _refresh_plot(self):
        if self._needs_update and len(self.data[self.current_x_key]) > 0:
            self.curve.setData(self.data[self.current_x_key], self.data[self.current_y_key])
            self._needs_update = False

    def _update_labels(self):
        title_color = "#0f172a"
        label_color = "#334155"
        
        self.plot_widget.setTitle(
            f"<span style='color:{title_color}; font-size:13pt; font-weight:700;'>{self.current_y_key} vs {self.current_x_key}</span>"
        )
        self.plot_widget.setLabel("left", self.current_y_key, **{'color': label_color, 'font-size': '11pt'})
        self.plot_widget.setLabel("bottom", self.current_x_key, **{'color': label_color, 'font-size': '11pt'})

    def _on_axis_changed(self, _=None):
        self.current_x_key = self.cb_xaxis.currentText()
        self.current_y_key = self.cb_yaxis.currentText()
        self._update_labels()
        
        if len(self.data[self.current_x_key]) > 0:
            self.curve.setData(self.data[self.current_x_key], self.data[self.current_y_key])
            self._auto_range()

    def add_point(self, time_s, load_kn, ext_mm, stress_mpa, strain_pct):
        self.data["Time (s)"].append(time_s)
        self.data["Load (kN)"].append(load_kn)
        self.data["Extension (mm)"].append(ext_mm)
        self.data["Stress (MPa)"].append(stress_mpa)
        self.data["Strain (%)"].append(strain_pct)
        self._needs_update = True

    def clear_graph(self):
        for key in self.data:
            self.data[key].clear()
        self.curve.setData([], [])
        self.lbl_cursor.setText("X: -- | Y: --")

    def export_image(self, file_path: str):
        try:
            self.plot_widget.repaint()
            exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
            exporter.parameters()['width'] = 1200
            exporter.export(file_path)
            return True
        except Exception as e:
            print(f"Graph Export Error: {e}")
            return False
