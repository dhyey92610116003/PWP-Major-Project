from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, 
                                 QTableWidgetItem, QPushButton, QHBoxLayout, 
                                 QHeaderView, QLabel, QLineEdit, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor
import os
from ui.theme import Theme

class HistoryDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Test History & Video Archives")
        self.setMinimumSize(1050, 540)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)
        
        # Header and Search Filter
        header_layout = QHBoxLayout()
        
        lbl_title = QLabel("Archived Test Records & Specimen Videos")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        header_layout.addWidget(lbl_title)
        
        header_layout.addStretch()
        
        self.in_search = QLineEdit()
        self.in_search.setPlaceholderText("🔍 Filter by Operator, Sample, Material, or ID...")
        self.in_search.setFixedWidth(280)
        self.in_search.textChanged.connect(self._filter_table)
        header_layout.addWidget(self.in_search)
        
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Test ID", "Timestamp", "Sample ID", "Material", "Standard", "Peak Load (kN)", "Peak Stress (MPa)", "Video Recording"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, 1)
        
        # Status & Action Buttons
        bottom_layout = QHBoxLayout()
        
        self.lbl_count = QLabel("Total Records: 0")
        self.lbl_count.setStyleSheet("color: #64748b; font-weight: 500;")
        bottom_layout.addWidget(self.lbl_count)
        
        bottom_layout.addStretch()
        
        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.load_data)
        bottom_layout.addWidget(btn_refresh)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        
        layout.addLayout(bottom_layout)
        
        self.records = []
        self.load_data()

    def load_data(self):
        self.records = self.db.get_all_tests()
        self._populate_table(self.records)

    def _populate_table(self, records):
        self.table.setRowCount(len(records))
        self.lbl_count.setText(f"Total Records: {len(records)}")
        
        for row_idx, record in enumerate(records):
            item_id = QTableWidgetItem(str(record.id))
            item_id.setTextAlignment(Qt.AlignCenter)
            
            time_str = record.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(record.timestamp, 'strftime') else str(record.timestamp)
            item_time = QTableWidgetItem(time_str)
            item_time.setTextAlignment(Qt.AlignCenter)
            
            sample_val = str(getattr(record, 'sample', None) or getattr(record, 'operator', 'N/A') or "SMP")
            item_sample = QTableWidgetItem(sample_val)
            item_sample.setTextAlignment(Qt.AlignCenter)
            
            item_mat = QTableWidgetItem(str(record.material or "N/A"))
            item_std = QTableWidgetItem(str(getattr(record, 'standard', 'N/A') or "ASTM E8"))
            
            item_load = QTableWidgetItem(f"{record.peak_load:.2f}")
            item_load.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            item_stress = QTableWidgetItem(f"{record.peak_stress:.2f}")
            item_stress.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.table.setItem(row_idx, 0, item_id)
            self.table.setItem(row_idx, 1, item_time)
            self.table.setItem(row_idx, 2, item_sample)
            self.table.setItem(row_idx, 3, item_mat)
            self.table.setItem(row_idx, 4, item_std)
            self.table.setItem(row_idx, 5, item_load)
            self.table.setItem(row_idx, 6, item_stress)
            
            # Column 7: Video Recording Button / Status
            vid_path = getattr(record, 'video_path', '')
            if vid_path and os.path.exists(vid_path):
                btn_play = QPushButton("▶ Play Video")
                btn_play.setStyleSheet("""
                    QPushButton {
                        background-color: #16a34a;
                        color: white;
                        font-weight: bold;
                        font-size: 10px;
                        border-radius: 4px;
                        padding: 3px 8px;
                        border: 1px solid #15803d;
                    }
                    QPushButton:hover {
                        background-color: #15803d;
                    }
                """)
                btn_play.clicked.connect(lambda _, p=vid_path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                self.table.setCellWidget(row_idx, 7, btn_play)
            else:
                item_vid = QTableWidgetItem("No Video")
                item_vid.setTextAlignment(Qt.AlignCenter)
                item_vid.setForeground(QColor("#94a3b8"))
                self.table.setItem(row_idx, 7, item_vid)

    def _filter_table(self, query: str):
        query = query.strip().lower()
        if not query:
            self._populate_table(self.records)
            return
            
        filtered = []
        for r in self.records:
            op = str(r.operator or "").lower()
            sample = str(getattr(r, 'sample', '') or "").lower()
            mat = str(r.material or "").lower()
            rec_id = str(r.id)
            if query in op or query in sample or query in mat or query in rec_id:
                filtered.append(r)
        self._populate_table(filtered)
