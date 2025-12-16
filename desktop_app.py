# -*- coding: utf-8 -*-
"""
桌面原型 - PySide6

功能：
- 左侧：搜索输入、结果表（可选择行）
- 右侧：实时日志（自动滚动）
- 后台线程执行搜索与下载，使用信号回写 UI

运行：
    pip install PySide6 pandas
    python desktop_app.py

打包（示例）：
    pip install pyinstaller
    pyinstaller --onefile desktop_app.py

说明：本文件复用仓库内 `core.AggregatedDownloader` 的接口（确保项目根路径已加入 sys.path）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import traceback
import pandas as pd

from PySide6 import QtCore, QtWidgets, QtGui

try:
    from core import AggregatedDownloader
    from core import natural_key
except Exception:
    AggregatedDownloader = None


class SearchThread(QtCore.QThread):
    results = QtCore.Signal(list)
    log = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, keyword: str, sources: list[str] | None = None, page: int = 1, page_size: int = 20, output_dir: str = "downloads"):
        super().__init__()
        self.keyword = keyword
        self.sources = sources
        self.page = page
        self.page_size = page_size
        self.output_dir = output_dir

    def run(self):
        try:
            if AggregatedDownloader is None:
                self.log.emit("AggregatedDownloader 未找到，无法执行搜索（请确认项目结构）")
                self.results.emit([])
                return

            client = AggregatedDownloader(output_dir=self.output_dir, enable_sources=self.sources)
            self.log.emit(f"开始搜索: {self.keyword}，来源: {self.sources}")
            items = client.search(self.keyword, page=int(self.page), page_size=int(self.page_size))
            rows = []
            for idx, it in enumerate(items, start=1):
                rows.append({
                    "std_no": it.std_no,
                    "name": it.name,
                    "publish": it.publish or "",
                    "implement": it.implement or "",
                    "status": it.status or "",
                    "has_pdf": bool(it.has_pdf),
                    "obj": it,
                })
            self.log.emit(f"搜索完成：{len(rows)} 条")
            self.results.emit(rows)
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"搜索出错: {e}")
            self.error.emit(tb)


class DownloadThread(QtCore.QThread):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(int, int)

    def __init__(self, items: list[dict], output_dir: str = "downloads"):
        super().__init__()
        self.items = items
        self.output_dir = output_dir

    def run(self):
        success = 0
        fail = 0
        try:
            client = AggregatedDownloader(output_dir=self.output_dir, enable_sources=None)
        except Exception:
            self.log.emit("AggregatedDownloader 无法实例化，跳过下载")
            self.finished.emit(0, len(self.items))
            return

        for it in self.items:
            std_no = it.get("std_no")
            self.log.emit(f"开始下载: {std_no}")
            try:
                path, logs = client.download(it.get("obj"))
                if path:
                    self.log.emit(f"✅ 下载完成: {std_no}")
                    success += 1
                else:
                    self.log.emit(f"❌ 下载失败: {std_no}")
                    fail += 1
            except Exception as e:
                self.log.emit(f"❌ 错误: {std_no} - {str(e)[:120]}")
                fail += 1

        self.finished.emit(success, fail)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(480, 280)

        layout = QtWidgets.QVBoxLayout()

        # 来源选择
        src_group = QtWidgets.QGroupBox("启用的数据源")
        src_layout = QtWidgets.QVBoxLayout()
        self.chk_gbw = QtWidgets.QCheckBox("GBW (国家标准)")
        self.chk_by = QtWidgets.QCheckBox("BY (内部系统)")
        self.chk_zby = QtWidgets.QCheckBox("ZBY (标准云)")
        self.chk_gbw.setChecked(True)
        self.chk_by.setChecked(True)
        self.chk_zby.setChecked(True)
        src_layout.addWidget(self.chk_gbw)
        src_layout.addWidget(self.chk_by)
        src_layout.addWidget(self.chk_zby)
        src_group.setLayout(src_layout)
        layout.addWidget(src_group)

        # 下载配置
        dl_group = QtWidgets.QGroupBox("下载配置")
        dl_layout = QtWidgets.QGridLayout()
        dl_layout.addWidget(QtWidgets.QLabel("下载目录:"), 0, 0)
        self.input_dir = QtWidgets.QLineEdit("downloads")
        dl_layout.addWidget(self.input_dir, 0, 1)
        dl_layout.addWidget(QtWidgets.QLabel("每页数量:"), 1, 0)
        self.spin_pagesize = QtWidgets.QSpinBox()
        self.spin_pagesize.setValue(50)
        self.spin_pagesize.setMinimum(5)
        self.spin_pagesize.setMaximum(200)
        dl_layout.addWidget(self.spin_pagesize, 1, 1)
        dl_group.setLayout(dl_layout)
        layout.addWidget(dl_group)

        layout.addStretch()

        # 按钮
        btn_layout = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton("确定")
        btn_cancel = QtWidgets.QPushButton("取消")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def get_settings(self):
        sources = []
        if self.chk_gbw.isChecked():
            sources.append("GBW")
        if self.chk_by.isChecked():
            sources.append("BY")
        if self.chk_zby.isChecked():
            sources.append("ZBY")
        return {
            "sources": sources,
            "output_dir": self.input_dir.text(),
            "page_size": self.spin_pagesize.value(),
        }


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("标准下载 - 桌面版")
        self.resize(1200, 750)

        # 配置存储
        self.settings = {
            "sources": ["GBW", "BY", "ZBY"],
            "output_dir": "downloads",
            "page_size": 50,
        }

        # 菜单栏已移除，功能集成到UI中

        central = QtWidgets.QWidget()
        central.setStyleSheet("background-color: #f8f9fa;")
        self.setCentralWidget(central)

        layout = QtWidgets.QHBoxLayout(central)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧主区（搜索 + 结果）
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

        # 搜索行
        search_row = QtWidgets.QWidget()
        sr_layout = QtWidgets.QHBoxLayout(search_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(8)
        self.input_keyword = QtWidgets.QLineEdit()
        self.input_keyword.setPlaceholderText("输入标准号或名称（例如 GB/T 3324）")
        self.input_keyword.setStyleSheet("""
            QLineEdit {
                border: 1px solid #3498db;
                border-radius: 3px;
                padding: 6px;
                font-size: 11px;
                background-color: white;
                color: #333;
            }
            QLineEdit:focus {
                border: 2px solid #3445db;
                background-color: white;
                color: #333;
            }
        """)
        self.input_keyword.returnPressed.connect(self.on_search)
        self.btn_search = QtWidgets.QPushButton("🔍 检索")
        self.btn_search.setMinimumWidth(80)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #346edb;
            }
            QPushButton:pressed {
                background-color: #3445db;
            }
        """)
        self.btn_search.clicked.connect(self.on_search)
        sr_layout.addWidget(self.input_keyword, 3)
        sr_layout.addWidget(self.btn_search, 1)
        left_layout.addWidget(search_row)

        # 路径和操作行（源选择已移到右侧）
        path_op_row = QtWidgets.QWidget()
        path_op_layout = QtWidgets.QHBoxLayout(path_op_row)
        path_op_layout.setContentsMargins(0, 0, 0, 0)
        path_op_layout.setSpacing(8)
        
        # 下载路径显示 - 放在最左边
        lbl_path = QtWidgets.QLabel("📍 路径:")
        lbl_path.setStyleSheet("font-weight: bold; color: #3498db;")
        self.lbl_download_path = QtWidgets.QLabel("downloads")
        self.lbl_download_path.setStyleSheet("color: #333; min-height: 18px;")
        self.lbl_download_path.setWordWrap(False)
        path_op_layout.addWidget(lbl_path)
        path_op_layout.addWidget(self.lbl_download_path, 1)
        
        # 路径选择按钮 - 宽度调小防止遮挡
        self.btn_select_path = QtWidgets.QPushButton("🔍 选路径")
        self.btn_select_path.setMaximumWidth(70)
        self.btn_select_path.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #346edb;
            }
            QPushButton:pressed {
                background-color: #3445db;
            }
        """)
        self.btn_select_path.clicked.connect(self.on_select_path)
        path_op_layout.addWidget(self.btn_select_path)
        
        # 打开文件夹按钮
        self.btn_open_folder = QtWidgets.QPushButton("📁 打开")
        self.btn_open_folder.setMaximumWidth(70)
        self.btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #346edb;
            }
            QPushButton:pressed {
                background-color: #3445db;
            }
        """)
        self.btn_open_folder.clicked.connect(self.on_open_folder)
        path_op_layout.addWidget(self.btn_open_folder)
        
        # 导出为 CSV 按钮
        self.btn_export = QtWidgets.QPushButton("💾 导出CSV")
        self.btn_export.setMaximumWidth(75)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #346edb;
            }
            QPushButton:pressed {
                background-color: #3445db;
            }
        """)
        self.btn_export.clicked.connect(self.on_export)
        path_op_layout.addWidget(self.btn_export)
        
        # 下载选中按钮
        self.btn_download = QtWidgets.QPushButton("📥 下载")
        self.btn_download.setMaximumWidth(65)
        self.btn_download.setStyleSheet("""
            QPushButton {
                background-color: #51cf66;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #37b24d;
            }
            QPushButton:pressed {
                background-color: #2f8a3d;
            }
        """)
        self.btn_download.clicked.connect(self.on_download)
        path_op_layout.addWidget(self.btn_download)
        
        left_layout.addWidget(path_op_row)
        
        # 创建源复选框（稍后添加到右侧）
        self.chk_gbw = QtWidgets.QCheckBox("GBW")
        self.chk_gbw.setChecked(True)
        self.chk_gbw.setStyleSheet("color: #333; font-weight: bold;")
        self.chk_by = QtWidgets.QCheckBox("BY")
        self.chk_by.setChecked(True)
        self.chk_by.setStyleSheet("color: #333; font-weight: bold;")
        self.chk_zby = QtWidgets.QCheckBox("ZBY")
        self.chk_zby.setChecked(True)
        self.chk_zby.setStyleSheet("color: #333; font-weight: bold;")
        
        # 初始化时根据连通性设置状态
        self.update_source_checkboxes()

        # 结果表 - 紧凑样式
        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["✓", "序号", "标准号", "名称", "发布日期", "实施日期", "状态", "文本"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 50)
        self.table.setRowHeight(0, 36)
        # 美化：专业配色（深蓝头、浅灰行）
        header = self.table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #3445db;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #3445db;
            }
        """)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 6px;
                border: 1px solid #e8e8e8;
                background-color: white;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTableWidget::indicator:unchecked {
                background-color: white;
                border: 3px solid #d0d0d0;
                width: 20px;
                height: 20px;
                margin: 1px;
            }
            QTableWidget::indicator:checked {
                background-color: #e74c3c;
                border: 3px solid #c0392b;
                width: 20px;
                height: 20px;
                margin: 1px;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBkPSJNMTMuNzEgMy43MWwtNy43MSA3LjcxTC4yOSA4LjI5YS45OTkuOTk5IDAgMDAtMS40MTQgMS40MTRMNC41NjkgMTMuNDMxYy4zOTMuMzkyIDEuMDI4LjM5MiAxLjQyIDAgMDAwIDAgLjAwMiAwbDkuMTkyLTkuMTkyYTEgMSAwIDAwLTEuNDEzLTEuNDEyeiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=);
            }            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                margin: 0px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #3498db;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #346edb;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #3445db;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #f0f0f0;
                height: 12px;
                margin: 0px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #3498db;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #346edb;
            }
            QScrollBar::handle:horizontal:pressed {
                background-color: #3445db;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }        """)
        left_layout.addWidget(self.table)

        splitter.addWidget(left)

        # 右侧日志区
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        
        # 源连通性指示（顶部）
        source_header = QtWidgets.QWidget()
        source_hdr_layout = QtWidgets.QVBoxLayout(source_header)
        source_hdr_layout.setContentsMargins(8, 8, 8, 4)
        source_hdr_layout.setSpacing(8)
        
        # 数据源连通性标签和状态
        source_title_layout = QtWidgets.QHBoxLayout()
        lbl_sources = QtWidgets.QLabel("📡 数据源连通性:")
        lbl_sources.setStyleSheet("font-weight: bold; color: #3498db; font-size: 12px;")
        self.lbl_source_status = QtWidgets.QLabel("检测中...")
        self.lbl_source_status.setStyleSheet("color: #ff9800; font-weight: bold;")
        source_title_layout.addWidget(lbl_sources)
        source_title_layout.addWidget(self.lbl_source_status, 1)
        source_title_layout.addStretch()
        source_hdr_layout.addLayout(source_title_layout)
        
        # 源选择复选框（在连通性下方，格式对齐）
        source_checkbox_layout = QtWidgets.QHBoxLayout()
        source_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        source_checkbox_layout.setSpacing(6)
        lbl_select = QtWidgets.QLabel("选择:")
        lbl_select.setStyleSheet("color: #333; font-weight: bold;")
        source_checkbox_layout.addWidget(lbl_select)
        source_checkbox_layout.addWidget(self.chk_gbw)
        source_checkbox_layout.addWidget(self.chk_by)
        source_checkbox_layout.addWidget(self.chk_zby)
        source_checkbox_layout.addStretch()
        source_hdr_layout.addLayout(source_checkbox_layout)
        
        right_layout.addWidget(source_header)
        
        # 日志标题与清空按钮
        log_header = QtWidgets.QWidget()
        log_hdr_layout = QtWidgets.QHBoxLayout(log_header)
        log_hdr_layout.setContentsMargins(8, 8, 8, 8)
        lbl = QtWidgets.QLabel("📋 实时日志")
        lbl.setStyleSheet("font-weight: bold; color: #3498db; font-size: 12px;")
        btn_clear = QtWidgets.QPushButton("🗑️ 清空")
        btn_clear.setMaximumWidth(80)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: 1px solid #346edb;
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3445db;
                color: white;
            }
        """)
        btn_clear.clicked.connect(self.on_clear_log)
        log_hdr_layout.addWidget(lbl)
        log_hdr_layout.addStretch()
        log_hdr_layout.addWidget(btn_clear)
        right_layout.addWidget(log_header)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        font = QtGui.QFont("Courier New", 9)
        self.log_view.setFont(font)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)
        right_layout.addWidget(self.log_view)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        # 状态
        self.status = self.statusBar()

        # 存储
        self.current_items: list[dict] = []

        # 线程占位
        self.search_thread: SearchThread | None = None
        self.download_thread: DownloadThread | None = None
        
        # 初始化显示
        self.update_path_display()
        self.update_source_checkboxes()
        self.check_source_health()

    def create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #34c2db;
                color: white;
                border-bottom: 1px solid #346edb;
            }
            QMenuBar::item:selected {
                background-color: #3445db;
            }
            QMenu {
                background-color: #34c2db;
                color: white;
            }
            QMenu::item:selected {
                background-color: #3445db;
                color: white;
            }
        """)
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        action_settings = file_menu.addAction("设置(&S)")
        action_settings.triggered.connect(self.on_settings)
        file_menu.addSeparator()
        action_exit = file_menu.addAction("退出(&Q)")
        action_exit.triggered.connect(self.close)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        action_about = help_menu.addAction("关于(&A)")
        action_about.triggered.connect(self.on_about)

    def append_log(self, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        # 根据日志内容选择颜色
        if "错误" in text or "失败" in text or "Error" in text:
            color = "#ff6b6b"  # 红色错误
        elif "完成" in text or "成功" in text or "Success" in text:
            color = "#51cf66"  # 绿色成功
        elif "搜索" in text or "下载" in text:
            color = "#4dabf7"  # 蓝色操作
        else:
            color = "#d4d4d4"  # 默认灰色
        
        log_text = f"<span style='color: #999;'>[{now}]</span> <span style='color: {color};'>{text}</span>"
        self.log_view.append(log_text)
        # 自动滚动到底部
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def on_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        dialog.chk_gbw.setChecked("GBW" in self.settings["sources"])
        dialog.chk_by.setChecked("BY" in self.settings["sources"])
        dialog.chk_zby.setChecked("ZBY" in self.settings["sources"])
        dialog.input_dir.setText(self.settings["output_dir"])
        dialog.spin_pagesize.setValue(self.settings["page_size"])
        
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.settings = dialog.get_settings()
            self.append_log(f"设置已更新：{self.settings}")
            self.update_path_display()
            self.check_source_health()

    def on_clear_log(self):
        """清空日志"""
        self.log_view.clear()
        self.append_log("日志已清空")

    def on_export(self):
        """导出结果为 CSV"""
        if not self.current_items:
            QtWidgets.QMessageBox.information(self, "提示", "暂无结果可导出")
            return
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出结果", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        
        try:
            data = []
            for r in self.current_items:
                data.append({
                    "标准号": r.get("std_no"),
                    "名称": r.get("name"),
                    "状态": r.get("status"),
                    "有文本": "是" if r.get("has_pdf") else "否",
                })
            df = pd.DataFrame(data)
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.append_log(f"已导出到: {path}")
            QtWidgets.QMessageBox.information(self, "成功", f"已导出 {len(data)} 条到:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出失败", str(e))

    def on_about(self):
        """关于对话框"""
        QtWidgets.QMessageBox.about(
            self,
            "关于",
            "标准下载 - 桌面版\n\n"
            "一个高效的标准文档聚合下载工具。\n\n"
            "功能：\n"
            "• 三源聚合搜索（GBW、BY、ZBY）\n"
            "• 实时日志与进度显示\n"
            "• 批量下载\n"
            "• 导出结果\n\n"
            "版本: 1.0.0"
        )

    def on_open_folder(self):
        """打开下载文件夹"""
        output_dir = self.settings.get("output_dir", "downloads")
        folder_path = Path(output_dir).resolve()
        
        # 如果文件夹不存在，创建它
        folder_path.mkdir(parents=True, exist_ok=True)
        
        try:
            if sys.platform == "win32":
                import os
                os.startfile(str(folder_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(folder_path)])
            else:
                import subprocess
                subprocess.run(["xdg-open", str(folder_path)])
            self.append_log(f"打开文件夹: {folder_path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "提示", f"无法打开文件夹: {e}")

    def update_path_display(self):
        """更新路径显示"""
        output_dir = self.settings.get("output_dir", "downloads")
        self.lbl_download_path.setText(output_dir)

    def update_source_checkboxes(self):
        """根据源的连通性更新复选框状态"""
        try:
            from core import AggregatedDownloader
            
            # 检查所有源的连通性
            client = AggregatedDownloader(enable_sources=["GBW", "BY", "ZBY"])
            health_status = client.check_source_health()
            
            # 根据连通性设置复选框
            for src_name, checkbox in [("GBW", self.chk_gbw), ("BY", self.chk_by), ("ZBY", self.chk_zby)]:
                health = health_status.get(src_name)
                if health and health.available:
                    checkbox.setChecked(True)
                    checkbox.setEnabled(True)
                else:
                    checkbox.setChecked(False)
                    checkbox.setEnabled(False)
        except Exception as e:
            self.append_log(f"更新源复选框失败: {str(e)[:40]}")

    def on_select_path(self):
        """打开文件夹选择对话框"""
        current_path = self.settings.get("output_dir", "downloads")
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择下载路径", current_path
        )
        if folder_path:
            self.settings["output_dir"] = folder_path
            self.update_path_display()
            self.append_log(f"下载路径已更改: {folder_path}")

    def check_source_health(self):
        """检查源连通性"""
        try:
            from core import AggregatedDownloader
            sources_enabled = self.settings.get("sources", ["GBW", "BY", "ZBY"])
            
            # 创建下载器获取源状态
            client = AggregatedDownloader(enable_sources=sources_enabled)
            health_status = client.check_source_health()
            
            status_parts = []
            for src in ["GBW", "BY", "ZBY"]:
                health = health_status.get(src)
                if health:
                    is_available = health.available
                    enabled = src in sources_enabled
                    if is_available:
                        icon = "🟢" if enabled else "⚪"
                    else:
                        icon = "🔴"
                    status_parts.append(f"{icon}{src}")
            
            status_text = " ".join(status_parts)
            self.lbl_source_status.setText(status_text)
            self.lbl_source_status.setStyleSheet("color: #34dbcb; font-weight: bold;")
        except Exception as e:
            self.lbl_source_status.setText(f"检测失败: {str(e)[:20]}")
            self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")

    def on_search(self):
        keyword = self.input_keyword.text().strip()
        if not keyword:
            QtWidgets.QMessageBox.warning(self, "提示", "请输入关键词")
            return
        self.btn_search.setEnabled(False)
        self.append_log(f"触发搜索: {keyword}")
        
        # 获取复选框中选中的源
        sources = []
        if self.chk_gbw.isChecked():
            sources.append("GBW")
        if self.chk_by.isChecked():
            sources.append("BY")
        if self.chk_zby.isChecked():
            sources.append("ZBY")
        
        if not sources:
            QtWidgets.QMessageBox.warning(self, "提示", "请至少选择一个数据源")
            self.btn_search.setEnabled(True)
            return
        
        # 更新设置中的源列表
        self.settings["sources"] = sources
        
        page_size = self.settings.get("page_size", 50)
        self.search_thread = SearchThread(
            keyword=keyword, 
            sources=sources, 
            page=1, 
            page_size=page_size,
            output_dir=self.settings.get("output_dir", "downloads")
        )
        self.search_thread.results.connect(self.on_search_results)
        self.search_thread.log.connect(self.append_log)
        self.search_thread.error.connect(lambda tb: self.append_log(f"错误详情:\n{tb}"))
        self.search_thread.finished.connect(lambda: self.btn_search.setEnabled(True))
        self.search_thread.start()

    def on_search_results(self, rows: list[dict]):
        self.current_items = rows
        self.table.setRowCount(0)
        for idx, r in enumerate(rows, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            # 复选框（使用可勾选的 QTableWidgetItem）
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chk.setCheckState(QtCore.Qt.Unchecked)
            self.table.setItem(row, 0, chk)
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(idx)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(r.get("std_no", "")))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(r.get("name", "")))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(r.get("publish", "")))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(r.get("implement", "")))
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(r.get("status", "")))
            self.table.setItem(row, 7, QtWidgets.QTableWidgetItem("✓" if r.get("has_pdf") else "-"))

    def on_download(self):
        selected = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == QtCore.Qt.Checked:
                selected.append(self.current_items[row])

        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择要下载的行")
            return

        self.append_log(f"准备下载 {len(selected)} 条")
        self.btn_download.setEnabled(False)
        output_dir = self.settings.get("output_dir", "downloads")
        self.download_thread = DownloadThread(selected, output_dir=output_dir)
        self.download_thread.log.connect(self.append_log)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def on_download_finished(self, success: int, fail: int):
        self.append_log(f"下载结果：{success} 成功，{fail} 失败")
        self.btn_download.setEnabled(True)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
