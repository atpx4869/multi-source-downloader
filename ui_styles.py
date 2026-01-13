# -*- coding: utf-8 -*-
"""
UI 样式定义模块
所有样式常量及颜色配置
"""

# ==================== 颜色定义 ====================
PRIMARY_COLOR = "#34c2db"      # 主色（蓝色）
PRIMARY_HOVER = "#2ba8c1"      # 主色悬停
PRIMARY_PRESS = "#219aa6"      # 主色按下
SECONDARY_COLOR = "#eee"       # 次色（浅灰）
BORDER_COLOR = "#ddd"          # 边框色（中灰）
BG_COLOR = "#f5f5f5"           # 背景色（极浅灰）
TEXT_COLOR = "#333"            # 文字色（深灰/黑）
TEXT_LIGHT = "#666"            # 浅文字色
TEXT_DISABLED = "#aaa"         # 禁用文字色
WHITE = "#ffffff"              # 白色
BLACK = "#000000"              # 黑色
SUCCESS_COLOR = "#27ae60"       # 成功色（绿）
ERROR_COLOR = "#e74c3c"        # 错误色（红）
WARNING_COLOR = "#f39c12"      # 警告色（橙）
DARK_BG = "#1e1e1e"            # 暗色背景（日志窗口）
DARK_TEXT = "#e8e8e8"          # 暗色文字

# ==================== 按钮样式 ====================
BTN_PRIMARY_STYLE = f"""
    QPushButton {{
        background-color: {PRIMARY_COLOR};
        color: {WHITE};
        border: none;
        border-radius: 4px;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {PRIMARY_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {PRIMARY_PRESS};
    }}
    QPushButton:disabled {{
        background-color: {BORDER_COLOR};
        color: {TEXT_DISABLED};
    }}
"""

BTN_SECONDARY_STYLE = f"""
    QPushButton {{
        background-color: {SECONDARY_COLOR};
        color: {TEXT_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        font-weight: normal;
        padding: 8px 16px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {BORDER_COLOR};
    }}
    QPushButton:pressed {{
        background-color: #ccc;
    }}
"""

# ==================== 输入框样式 ====================
INPUT_STYLE = f"""
    QLineEdit {{
        background-color: {WHITE};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 12px;
        color: {TEXT_COLOR};
    }}
    QLineEdit:focus {{
        border: 2px solid {PRIMARY_COLOR};
        background-color: {WHITE};
    }}
"""

SEARCH_STYLE = f"""
    QLineEdit {{
        background-color: {WHITE};
        border: 2px solid {PRIMARY_COLOR};
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 13px;
        color: {TEXT_COLOR};
        selection-background-color: {PRIMARY_COLOR};
    }}
    QLineEdit:focus {{
        border: 2px solid {PRIMARY_HOVER};
    }}
"""

# ==================== 表格样式 ====================
TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {WHITE};
        gridline-color: #eee;
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
    }}
    QTableWidget::item {{
        padding: 5px 10px;
        color: {TEXT_COLOR};
        background-color: {WHITE};
    }}
    QTableWidget::item:selected {{
        background-color: {PRIMARY_COLOR};
        color: {WHITE};
    }}
    QTableWidget::item:alternate {{
        background-color: #fafafa;
    }}
"""

TABLE_HEADER_STYLE = f"""
    QHeaderView::section {{
        background-color: #e8e8e8;
        color: {TEXT_COLOR};
        padding: 5px 10px;
        border: none;
        border-right: 1px solid {BORDER_COLOR};
        border-bottom: 1px solid {BORDER_COLOR};
        font-weight: bold;
    }}
"""

# ==================== 对话框样式 ====================
DIALOG_STYLE = f"""
    QDialog {{
        background-color: {BG_COLOR};
    }}
    QLabel {{
        color: {TEXT_COLOR};
    }}
    QPushButton {{
        color: {WHITE};
    }}
    QLineEdit {{
        background-color: {WHITE};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 5px;
        font-size: 12px;
        color: {TEXT_COLOR};
    }}
    QLineEdit:focus {{
        border: 2px solid {PRIMARY_COLOR};
    }}
"""

# ==================== 日志框样式 ====================
LOG_STYLE = f"""
    QTextEdit {{
        background-color: {DARK_BG};
        color: {DARK_TEXT};
        font-family: 'Courier New', 'Consolas', monospace;
        font-size: 11px;
        padding: 8px;
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
    }}
"""

# ==================== 进度条样式 ====================
PROGRESS_STYLE = f"""
    QProgressBar {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        text-align: center;
        background-color: {WHITE};
        color: {TEXT_COLOR};
    }}
    QProgressBar::chunk {{
        background-color: {PRIMARY_COLOR};
        border-radius: 3px;
    }}
"""

# ==================== 复选框样式 ====================
CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {TEXT_COLOR};
        spacing: 5px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
    }}
    QCheckBox::indicator:unchecked {{
        background-color: {WHITE};
        border: 1px solid {BORDER_COLOR};
        border-radius: 2px;
    }}
    QCheckBox::indicator:checked {{
        background-color: {PRIMARY_COLOR};
        border: 1px solid {PRIMARY_COLOR};
        border-radius: 2px;
        color: {WHITE};
    }}
"""

# ==================== 主窗口样式 ====================
MAIN_WINDOW_STYLE = f"""
    QMainWindow {{
        background-color: {BG_COLOR};
    }}
"""

# ==================== 标签页样式 ====================
TAB_STYLE = f"""
    QTabWidget::pane {{
        border: 1px solid {BORDER_COLOR};
    }}
    QTabBar::tab {{
        background-color: {SECONDARY_COLOR};
        border: 1px solid {BORDER_COLOR};
        padding: 8px 20px;
        margin-right: 2px;
        color: {TEXT_COLOR};
    }}
    QTabBar::tab:selected {{
        background-color: {PRIMARY_COLOR};
        color: {WHITE};
        border: 1px solid {PRIMARY_COLOR};
    }}
    QTabBar::tab:hover {{
        background-color: {BORDER_COLOR};
    }}
"""

# ==================== 分组框样式 ====================
BUTTON_GROUP_STYLE = f"""
    QGroupBox {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        margin-top: 10px;
        padding-top: 10px;
        color: {TEXT_COLOR};
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px 0 3px;
    }}
"""

# ==================== 下拉框样式 ====================
COMBO_STYLE = f"""
    QComboBox {{
        background-color: {WHITE};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 5px 10px;
        color: {TEXT_COLOR};
    }}
    QComboBox:hover {{
        border: 1px solid {PRIMARY_COLOR};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
    }}
"""

# ==================== 滚动条样式 ====================
SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        border: none;
        background: {BG_COLOR};
        width: 12px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_COLOR};
        border-radius: 6px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #bbb;
    }}
    QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
        border: none;
        background: none;
    }}
"""
