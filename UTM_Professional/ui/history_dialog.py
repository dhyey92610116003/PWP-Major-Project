from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, 
                                 QTableWidgetItem, QPushButton, QHBoxLayout, 
                                 QHeaderView, QLabel, QLineEdit, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt
from ui.theme import Theme

class HistoryDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Test History & Archives")
        self.setMinimumSize(950, 520)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)
        
        # Header and Search Filter
        header_layout = QHBoxLayout()
        
        lbl_title = QLabel("Archived Test Records")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        header_layout.addWidget(lbl_title)
        
        header_layout.addStretch()
        
        self.in_search = QLineEdit()
        self.in_search.setPlaceholderText("🔍 Filter by Operator, Material, or ID...")
        self.in_search.setFixedWidth(280)
        self.in_search.textChanged.connect(self._filter_table)
        header_layout.addWidget(self.in_search)
        
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Test ID", "Timestamp", "Operator", "Material", "Standard", "Peak Load (kN)", "Peak Stress (MPa)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
            
            item_op = QTableWidgetItem(str(record.operator or "N/A"))
            item_mat = QTableWidgetItem(str(record.material or "N/A"))
            item_std = QTableWidgetItem(str(getattr(record, 'standard', 'N/A') or "N/A"))
            
            item_load = QTableWidgetItem(f"{record.peak_load:.2f}")
            item_load.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            item_stress = QTableWidgetItem(f"{record.peak_stress:.2f}")
            item_stress.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.table.setItem(row_idx, 0, item_id)
            self.table.setItem(row_idx, 1, item_time)
            self.table.setItem(row_idx, 2, item_op)
            self.table.setItem(row_idx, 3, item_mat)
            self.table.setItem(row_idx, 4, item_std)
            self.table.setItem(row_idx, 5, item_load)
            self.table.setItem(row_idx, 6, item_stress)

    def _filter_table(self, query: str):
        query = query.strip().lower()
        if not query:
            self._populate_table(self.records)
            return
            
        filtered = []
        for r in self.records:
            op = str(r.operator or "").lower()
            mat = str(r.material or "").lower()
            rec_id = str(r.id)
            if query in op or query in mat or query in rec_id:
                filtered.append(r)
        self._populate_table(filtered)
