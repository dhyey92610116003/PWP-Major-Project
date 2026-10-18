"""
UTM Professional - Enterprise Light Theme Design System
Tailored for laboratory and industrial testing workstations (Instron / Shimadzu style).
Crisp, high-contrast, professional, and easy to read under lab lighting.
Uses native Windows dropdown arrows and controls to avoid rasterization artifacts.
"""

class Theme:
    # Enterprise Light Palette
    PALETTE = {
        "bg_root": "#f8fafc",         # Clean light slate
        "bg_card": "#ffffff",         # Crisp pure white
        "bg_card_alt": "#f1f5f9",     # Light gray for headers / inputs
        "bg_hover": "#e2e8f0",        # Hover state
        "border": "#cbd5e1",          # Structural border
        "border_light": "#e2e8f0",    # Subtle border
        "border_focus": "#0284c7",    # Primary blue focus
        "text_primary": "#0f172a",    # Deep charcoal/navy for high contrast
        "text_secondary": "#475569",  # Slate gray for descriptions & labels
        "text_muted": "#64748b",      # Muted labels
        
        # Semantic Accents (Refined Lab Grade)
        "accent_blue": "#0284c7",     # Corporate Lab Blue
        "accent_green": "#16a34a",    # Safety Green (Start)
        "accent_red": "#dc2626",      # Emergency Red (Stop)
        "accent_amber": "#d97706",    # Calibration Amber (Tare)
        "accent_purple": "#7c3aed",   # Document Violet (PDF)
        "accent_teal": "#0d9488",     # Data Teal (CSV)
        "accent_slate": "#475569",    # History Slate
        
        # Graph Colors
        "plot_bg": "#ffffff",
        "plot_fg": "#1e293b",
        "plot_grid": "#e2e8f0",
        "plot_curve": "#0284c7"
    }

    @classmethod
    def get_stylesheet(cls):
        c = cls.PALETTE
        
        return f"""
        /* Global Base Settings */
        QMainWindow, QDialog, QWidget#centralWidget {{
            background-color: {c['bg_root']};
            color: {c['text_primary']};
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            font-size: 13px;
        }}

        QWidget {{
            color: {c['text_primary']};
        }}

        /* Menubar */
        QMenuBar {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border-bottom: 1px solid {c['border']};
            padding: 4px 8px;
            font-weight: 500;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 6px 12px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background-color: {c['bg_hover']};
        }}
        QMenu {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {c['accent_blue']};
            color: #ffffff;
        }}

        /* Card Panels */
        QFrame.card, QWidget.card {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}

        QGroupBox {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            margin-top: 10px;
            font-weight: 700;
            font-size: 12px;
            padding: 8px 6px 6px 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: 2px;
            padding: 0 4px;
            color: {c['accent_blue']};
            background-color: {c['bg_card']};
        }}

        /* Inputs and Text Boxes */
        QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 3px 6px;
            font-size: 12px;
            min-height: 20px;
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {c['border_focus']};
            background-color: #ffffff;
        }}
        QLineEdit:read-only, QLineEdit:disabled {{
            background-color: {c['bg_card_alt']};
            color: {c['text_muted']};
            border: 1px solid {c['border_light']};
        }}

        /* Clean Native Dropdowns (QComboBox) - No SVG black box */
        QComboBox {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 3px 6px;
            font-size: 12px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {c['border_focus']};
        }}
        QComboBox:focus {{
            border: 1px solid {c['border_focus']};
        }}
        QComboBox:disabled {{
            background-color: {c['bg_card_alt']};
            color: {c['text_secondary']};
            border: 1px solid {c['border_light']};
        }}
        QComboBox QAbstractItemView {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            selection-background-color: {c['accent_blue']};
            selection-color: #ffffff;
            outline: none;
            padding: 4px;
        }}

        /* Checkboxes */
        QCheckBox {{
            color: {c['text_primary']};
            font-weight: 500;
            spacing: 6px;
        }}
        QCheckBox:disabled {{
            color: {c['text_muted']};
        }}

        /* General Buttons */
        QPushButton {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 7px 14px;
            font-weight: 600;
            font-size: 12px;
            min-height: 26px;
        }}
        QPushButton:hover {{
            background-color: {c['bg_hover']};
            border-color: {c['border_focus']};
        }}
        QPushButton:pressed {{
            background-color: {c['bg_card_alt']};
        }}
        QPushButton:disabled {{
            background-color: {c['bg_card_alt']};
            color: {c['text_muted']};
            border-color: {c['border_light']};
        }}

        /* Styled Action Buttons */
        QPushButton#btnStart {{
            background-color: {c['accent_green']};
            color: #ffffff;
            border: 1px solid #15803d;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnStart:hover {{
            background-color: #15803d;
        }}
        QPushButton#btnStart:pressed {{
            background-color: #166534;
        }}

        QPushButton#btnStop {{
            background-color: {c['accent_red']};
            color: #ffffff;
            border: 1px solid #b91c1c;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnStop:hover {{
            background-color: #b91c1c;
        }}
        QPushButton#btnStop:pressed {{
            background-color: #991b1b;
        }}

        QPushButton#btnTare {{
            background-color: {c['accent_amber']};
            color: #ffffff;
            border: 1px solid #b45309;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnTare:hover {{
            background-color: #b45309;
        }}

        QPushButton#btnPdf {{
            background-color: {c['accent_purple']};
            color: #ffffff;
            border: 1px solid #6d28d9;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnPdf:hover {{
            background-color: #6d28d9;
        }}

        QPushButton#btnExport {{
            background-color: {c['accent_teal']};
            color: #ffffff;
            border: 1px solid #0f766e;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnExport:hover {{
            background-color: #0f766e;
        }}

        QPushButton#btnPrimary {{
            background-color: {c['accent_blue']};
            color: #ffffff;
            border: 1px solid #0369a1;
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnPrimary:hover {{
            background-color: #0369a1;
        }}

        QPushButton#btnHistory {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            font-size: 11px;
            font-weight: 700;
            padding: 7px 12px;
            border-radius: 6px;
            min-height: 26px;
        }}
        QPushButton#btnHistory:hover {{
            background-color: {c['bg_hover']};
        }}

        /* Table Widget */
        QTableWidget {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            gridline-color: {c['border_light']};
            border-radius: 6px;
            selection-background-color: {c['accent_blue']};
            selection-color: #ffffff;
        }}
        QHeaderView::section {{
            background-color: {c['bg_card_alt']};
            color: {c['text_primary']};
            padding: 8px;
            border: 1px solid {c['border']};
            font-weight: 600;
        }}

        /* Scroll Area */
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {c['bg_card_alt']};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {c['border']};
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['text_muted']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            height: 0px;
        }}

        /* Tooltip */
        QToolTip {{
            background-color: #ffffff;
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            padding: 6px;
            border-radius: 4px;
        }}
        """
