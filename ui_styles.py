# UI 样式常量，供 desktop_app.py 使用
DIALOG_STYLE = """
QDialog { background-color: #f8f9fa; }
"""

BTN_PRIMARY_STYLE = """
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover { background-color: #346edb; }
QPushButton:pressed { background-color: #3445db; }
"""

BTN_ACCENT_STYLE = """
QPushButton {
    background-color: #51cf66;
    color: white;
    border: none;
    border-radius: 3px;
    padding: 6px 8px;
    font-weight: bold;
    font-size: 10px;
}
QPushButton:hover { background-color: #37b24d; }
QPushButton:pressed { background-color: #2f8a3d; }
"""

INPUT_STYLE = """
QLineEdit {
    border: 1px solid #3498db;
    border-radius: 3px;
    padding: 6px;
    font-size: 11px;
    background-color: white;
    color: #333;
}
QLineEdit:focus { border: 2px solid #3445db; background-color: white; color: #333; }
"""

TABLE_HEADER_STYLE = """
QHeaderView::section {
    background-color: #3445db;
    color: white;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #3445db;
}
"""

TABLE_STYLE = """
QTableWidget {
    gridline-color: #e0e0e0;
    background-color: #f8f9fa;
}
QTableWidget::item { padding: 6px; border: 1px solid #e8e8e8; background-color: white; color: #333; }
QTableWidget::item:selected { background-color: #3498db; color: white; }
QTableWidget::indicator:unchecked { background-color: white; border: 3px solid #d0d0d0; width: 20px; height: 20px; margin: 1px; }
QTableWidget::indicator:checked { background-color: #e74c3c; border: 3px solid #c0392b; width: 20px; height: 20px; margin: 1px; image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBkPSJNMTMuNzEgMy43MWwtNy43MSA3LjcxTC4yOSA4LjI5YS45OTkuOTk5IDAgMDAtMS40MTQgMS40MTRMNC41NjkgMTMuNDMxYy4zOTMuMzkyIDEuMDI4LjM5MiAxLjQyIDAgMDAwIDAgLjAwMiAwbDkuMTkyLTkuMTkyYTEgMSAwIDAwLTEuNDEzLTEuNDEyeiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=); }
QScrollBar:vertical { background-color: #f0f0f0; width: 12px; margin: 0px; border: none; }
QScrollBar::handle:vertical { background-color: #3498db; min-height: 20px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background-color: #346edb; }
QScrollBar::handle:vertical:pressed { background-color: #3445db; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background-color: #f0f0f0; height: 12px; margin: 0px; border: none; }
QScrollBar::handle:horizontal { background-color: #3498db; min-width: 20px; border-radius: 6px; }
QScrollBar::handle:horizontal:hover { background-color: #346edb; }
QScrollBar::handle:horizontal:pressed { background-color: #3445db; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""
