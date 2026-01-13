# -*- coding: utf-8 -*-
"""
历史记录与缓存管理界面
"""
import os
from pathlib import Path
from datetime import datetime

try:
    from PySide6 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 2

from core.cache_manager import get_cache_manager
import ui_styles


class HistoryDialog(QtWidgets.QDialog):
    """历史记录与缓存管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache_manager = get_cache_manager()
        
        self.setWindowTitle("🕒 历史记录")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(ui_styles.DIALOG_STYLE)
        
        self.setup_ui()
        self.load_history()
    
    def setup_ui(self):
        """构建界面"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题栏
        title = QtWidgets.QLabel("🕒 历史记录与缓存管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # 标签页
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addTab(self.create_search_history_tab(), "🔍 搜索历史")
        self.tab_widget.addTab(self.create_download_history_tab(), "📥 下载历史")
        self.tab_widget.addTab(self.create_cache_management_tab(), "💾 缓存管理")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def create_search_history_tab(self) -> QtWidgets.QWidget:
        """创建搜索历史标签页"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("搜索关键词...")
        self.search_input.returnPressed.connect(self.filter_search_history)
        toolbar.addWidget(self.search_input)
        
        search_btn = QtWidgets.QPushButton("🔍 搜索")
        search_btn.setFixedWidth(80)
        search_btn.clicked.connect(self.filter_search_history)
        toolbar.addWidget(search_btn)
        
        toolbar.addStretch()
        
        clear_search_btn = QtWidgets.QPushButton("🗑 清空历史")
        clear_search_btn.setFixedWidth(100)
        clear_search_btn.clicked.connect(self.clear_search_history)
        toolbar.addWidget(clear_search_btn)
        
        # 应用统一样式
        for i in range(toolbar.count()):
            btn = toolbar.itemAt(i).widget()
            if isinstance(btn, QtWidgets.QPushButton):
                btn.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
                btn.setFixedHeight(32)
                btn.setCursor(QtCore.Qt.PointingHandCursor)
        
        layout.addLayout(toolbar)
        
        # 搜索历史列表
        self.search_history_table = QtWidgets.QTableWidget()
        self.search_history_table.setColumnCount(4)
        self.search_history_table.setHorizontalHeaderLabels([
            "搜索关键词", "数据源", "结果数", "搜索时间"
        ])
        
        self.search_history_table.setColumnWidth(0, 300)
        self.search_history_table.setColumnWidth(1, 200)
        self.search_history_table.setColumnWidth(2, 100)
        self.search_history_table.setColumnWidth(3, 150)
        
        self.search_history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.search_history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.search_history_table.setAlternatingRowColors(True)
        self.search_history_table.verticalHeader().setVisible(False)
        self.search_history_table.doubleClicked.connect(self.on_search_history_double_click)
        
        layout.addWidget(self.search_history_table)
        
        return widget
    
    def create_download_history_tab(self) -> QtWidgets.QWidget:
        """创建下载历史标签页"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        
        refresh_btn = QtWidgets.QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.load_download_history)
        toolbar.addWidget(refresh_btn)
        
        toolbar.addStretch()
        
        # 应用统一样式
        for i in range(toolbar.count()):
            btn = toolbar.itemAt(i).widget()
            if isinstance(btn, QtWidgets.QPushButton):
                btn.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
                btn.setFixedHeight(32)
                btn.setCursor(QtCore.Qt.PointingHandCursor)
        
        layout.addLayout(toolbar)
        
        # 下载历史列表
        self.download_history_table = QtWidgets.QTableWidget()
        self.download_history_table.setColumnCount(6)
        self.download_history_table.setHorizontalHeaderLabels([
            "标准号", "标准名称", "来源", "文件大小", "下载时间", "操作"
        ])
        
        self.download_history_table.setColumnWidth(0, 140)
        self.download_history_table.setColumnWidth(1, 280)
        self.download_history_table.setColumnWidth(2, 80)
        self.download_history_table.setColumnWidth(3, 100)
        self.download_history_table.setColumnWidth(4, 140)
        self.download_history_table.setColumnWidth(5, 100)
        
        self.download_history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.download_history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.download_history_table.setAlternatingRowColors(True)
        self.download_history_table.verticalHeader().setVisible(False)
        # 统计信息栏
        self.download_stats_label = QtWidgets.QLabel()
        self.download_stats_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                font-size: 13px;
                color: #666;
            }
        """)
        layout.addWidget(self.download_stats_label)
        
        
        layout.addWidget(self.download_history_table)
        
        return widget
    
    def create_cache_management_tab(self) -> QtWidgets.QWidget:
        """创建缓存管理标签页"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(20)
        
        # 缓存统计
        stats_group = QtWidgets.QGroupBox("📊 缓存统计")
        stats_layout = QtWidgets.QFormLayout()
        
        self.cache_total_label = QtWidgets.QLabel("--")
        self.cache_with_file_label = QtWidgets.QLabel("--")
        self.search_cache_size_label = QtWidgets.QLabel("--")
        self.download_cache_size_label = QtWidgets.QLabel("--")
        self.total_cache_size_label = QtWidgets.QLabel("--")
        
        stats_layout.addRow("缓存总数:", self.cache_total_label)
        stats_layout.addRow("已下载文件:", self.cache_with_file_label)
        stats_layout.addRow("搜索缓存大小:", self.search_cache_size_label)
        stats_layout.addRow("下载缓存大小:", self.download_cache_size_label)
        stats_layout.addRow("总缓存大小:", self.total_cache_size_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 操作区
        actions_group = QtWidgets.QGroupBox("🛠 缓存操作")
        actions_layout = QtWidgets.QVBoxLayout()
        actions_layout.setSpacing(10)
        
        # 清空搜索缓存
        clear_search_cache_btn = QtWidgets.QPushButton("🗑 清空搜索缓存（保留近7天）")
        clear_search_cache_btn.clicked.connect(self.clear_search_cache)
        actions_layout.addWidget(clear_search_cache_btn)
        
        # 清空下载历史
        clear_download_history_btn = QtWidgets.QPushButton("🗑 清空下载历史记录（保留文件）")
        clear_download_history_btn.clicked.connect(self.clear_download_history)
        actions_layout.addWidget(clear_download_history_btn)
        
        # 清除无效缓存
        clear_invalid_btn = QtWidgets.QPushButton("🧹 清除无效缓存（文件不存在）")
        clear_invalid_btn.clicked.connect(self.clear_invalid_cache)
        actions_layout.addWidget(clear_invalid_btn)
        
        # 刷新统计
        refresh_stats_btn = QtWidgets.QPushButton("🔄 刷新统计信息")
        refresh_stats_btn.clicked.connect(self.refresh_cache_statistics)
        actions_layout.addWidget(refresh_stats_btn)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        layout.addStretch()
        
        # 应用统一样式
        for i in range(actions_layout.count()):
            widget_item = actions_layout.itemAt(i).widget()
            if isinstance(widget_item, QtWidgets.QPushButton):
                widget_item.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
                widget_item.setFixedHeight(32)
                widget_item.setCursor(QtCore.Qt.PointingHandCursor)
        
        # 初始加载统计
        self.refresh_cache_statistics()
        
        return widget
    
    def load_history(self):
        """加载历史记录"""
        self.load_search_history()
        self.load_download_history()
    
    def load_search_history(self):
        """加载搜索历史"""
        history = self.cache_manager.get_search_history(limit=100)
        
        self.search_history_table.setRowCount(0)
        
        for record in history:
            row = self.search_history_table.rowCount()
            self.search_history_table.insertRow(row)
            
            # 关键词
            keyword_item = QtWidgets.QTableWidgetItem(record['keyword'])
            self.search_history_table.setItem(row, 0, keyword_item)
            
            # 数据源
            sources = record['sources'] or ""
            self.search_history_table.setItem(row, 1, QtWidgets.QTableWidgetItem(sources))
            
            # 结果数
            count_item = QtWidgets.QTableWidgetItem(str(record['result_count'] or 0))
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.search_history_table.setItem(row, 2, count_item)
            
            # 时间
            try:
                search_time = datetime.fromisoformat(record['search_time'])
                time_str = search_time.strftime("%m-%d %H:%M:%S")
            except:
                time_str = record['search_time'][:16] if record['search_time'] else ""
            self.search_history_table.setItem(row, 3, QtWidgets.QTableWidgetItem(time_str))
    
    def filter_search_history(self):
        """过滤搜索历史"""
        keyword = self.search_input.text().strip()
        
        if not keyword:
            self.load_search_history()
            return
        
        history = self.cache_manager.search_history_by_keyword(keyword, limit=50)
        
        self.search_history_table.setRowCount(0)
        
        for record in history:
            row = self.search_history_table.rowCount()
            self.search_history_table.insertRow(row)
            
            self.search_history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(record['keyword']))
            self.search_history_table.setItem(row, 1, QtWidgets.QTableWidgetItem(record['sources'] or ""))
            
            count_item = QtWidgets.QTableWidgetItem(str(record['result_count'] or 0))
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.search_history_table.setItem(row, 2, count_item)
            
            try:
                search_time = datetime.fromisoformat(record['search_time'])
                time_str = search_time.strftime("%m-%d %H:%M:%S")
            except:
                time_str = record['search_time'][:16] if record['search_time'] else ""
            self.search_history_table.setItem(row, 3, QtWidgets.QTableWidgetItem(time_str))
    
    def on_search_history_double_click(self, index):
        """双击搜索历史项"""
        row = index.row()
        keyword = self.search_history_table.item(row, 0).text()
        # 统计信息
        total = len(history)
        total_size = sum(record['file_size'] or 0 for record in history)
        size_str = self.format_file_size(total_size)
        existing_files = sum(1 for r in history if r['file_path'] and Path(r['file_path']).exists())
        
        self.download_stats_label.setText(
            f"📊 总计: {total} 条记录  |  💾 总大小: {size_str}  |  ✅ 文件存在: {existing_files} 个"
        )
        
        
        # 显示提示
        QtWidgets.QMessageBox.information(
            self, "搜索历史",
            f"关键词: {keyword}\n\n您可以在主界面重新搜索此关键词"
        )
    
    def load_download_history(self):
        """加载下载历史"""
        history = self.cache_manager.get_download_history(limit=100)
        
        self.download_history_table.setRowCount(0)
        
        for record in history:
            row = self.download_history_table.rowCount()
            self.download_history_table.insertRow(row)
            
            # 标准号
            self.download_history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(record['std_no']))
            
            # 标准名称
            name_item = QtWidgets.QTableWidgetItem(record['std_name'] or "")
            name_item.setToolTip(record['std_name'] or "")
            self.download_history_table.setItem(row, 1, name_item)
            
            # 来源
            self.download_history_table.setItem(row, 2, QtWidgets.QTableWidgetItem(record['source'] or ""))
            
            # 文件大小
            file_size = record['file_size'] or 0
            size_str = self.format_file_size(file_size)
            size_item = QtWidgets.QTableWidgetItem(size_str)
            size_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.download_history_table.setItem(row, 3, size_item)
            
            # 下载时间
            try:
                download_time = datetime.fromisoformat(record['download_time'])
                time_str = download_time.strftime("%m-%d %H:%M:%S")
            except:
                time_str = record['download_time'][:16] if record['download_time'] else ""
            self.download_history_table.setItem(row, 4, QtWidgets.QTableWidgetItem(time_str))
            
            # 操作按钮
            action_widget = self.create_download_action_buttons(record)
            self.download_history_table.setCellWidget(row, 5, action_widget)
    
    def create_download_action_buttons(self, record: dict) -> QtWidgets.QWidget:
        """创建下载历史操作按钮"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        file_path = record['file_path']
        
        if file_path and Path(file_path).exists():
            # 打开文件
            open_btn = QtWidgets.QPushButton("📄")
            open_btn.setFixedSize(30, 26)
            open_btn.setToolTip("打开文件")
            open_btn.clicked.connect(lambda: self.open_file(file_path))
            layout.addWidget(open_btn)
            
            # 打开文件夹
            folder_btn = QtWidgets.QPushButton("📁")
            folder_btn.setFixedSize(30, 26)
            folder_btn.setToolTip("打开文件夹")
            folder_btn.clicked.connect(lambda: self.open_folder(file_path))
            layout.addWidget(folder_btn)
        
        layout.addStretch()
        
        # 应用样式
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QtWidgets.QPushButton):
                item.widget().setStyleSheet("""
                    QPushButton {
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 3px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #e9ecef;
                    }
                """)
                item.widget().setCursor(QtCore.Qt.PointingHandCursor)
        
        return widget
    
    def open_file(self, file_path: str):
        """打开文件"""
        try:
            os.startfile(file_path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"无法打开文件:\n{e}")
    
    def open_folder(self, file_path: str):
        """打开文件所在文件夹"""
        try:
            folder = str(Path(file_path).parent)
            os.startfile(folder)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"无法打开文件夹:\n{e}")
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / 1024 / 1024:.1f} MB"
    
    def clear_search_history(self):
        """清空搜索历史"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认清空",
            "确定要清空所有搜索历史吗？（保留近7天的记录）",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.cache_manager.clear_search_cache(days=7)
            self.load_search_history()
            QtWidgets.QMessageBox.information(self, "完成", "搜索历史已清空")
    
    def clear_search_cache(self):
        """清空搜索缓存"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认清空",
            "确定要清空搜索缓存吗？（保留近7天）\n这不会影响已下载的文件。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.cache_manager.clear_search_cache(days=7)
            self.refresh_cache_statistics()
            QtWidgets.QMessageBox.information(self, "完成", "搜索缓存已清空")
    
    def clear_download_history(self):
        """清空下载历史"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认清空",
            "确定要清空下载历史记录吗？\n这不会删除已下载的文件，只清空历史记录。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.cache_manager.db.clear_download_history(days=90)
            self.load_download_history()
            QtWidgets.QMessageBox.information(self, "完成", "下载历史已清空")
    
    def clear_invalid_cache(self):
        """清除无效缓存"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认清除",
            "确定要清除所有无效缓存吗？\n（文件已被删除的缓存记录）",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            count = self.cache_manager.clear_invalid_cache()
            self.refresh_cache_statistics()
            QtWidgets.QMessageBox.information(self, "完成", f"已清除 {count} 条无效缓存记录")
    
    def refresh_cache_statistics(self):
        """刷新缓存统计信息"""
        stats = self.cache_manager.get_statistics()
        
        self.cache_total_label.setText(f"{stats['cache_total']} 条")
        self.cache_with_file_label.setText(f"{stats['cache_with_file']} 个")
        self.search_cache_size_label.setText(f"{stats['search_cache_mb']} MB ({stats['search_file_count']} 个文件)")
        self.download_cache_size_label.setText(f"{stats['download_cache_mb']} MB ({stats['download_file_count']} 个文件)")
        self.total_cache_size_label.setText(f"{stats['total_mb']} MB")
