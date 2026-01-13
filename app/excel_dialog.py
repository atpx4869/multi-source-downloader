# -*- coding: utf-8 -*-
"""
Excel 标准号处理对话框
集成标准号补全功能，直接在桌面应用中处理 Excel
"""
import sys
import threading
import queue
from pathlib import Path
from typing import Optional, List
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web_app.excel_standard_processor import StandardProcessor

try:
    from PySide6 import QtCore, QtWidgets, QtGui
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui


class WorkerThread(QtCore.QThread):
    """后台处理线程"""
    
    # 信号定义
    progress_updated = QtCore.Signal(int, int)  # (current, total)
    result_ready = QtCore.Signal(pd.DataFrame)
    error_occurred = QtCore.Signal(str)
    status_changed = QtCore.Signal(str)
    
    def __init__(self, processor: StandardProcessor, excel_file: str):
        super().__init__()
        self.processor = processor
        self.excel_file = excel_file
        self.result_df = None
    
    def run(self):
        """在后台线程中执行处理"""
        try:
            self.status_changed.emit("正在读取 Excel 文件...")
            
            # 读取 Excel
            df = pd.read_excel(self.excel_file)
            if df.empty:
                self.error_occurred.emit("Excel 文件为空")
                return
            
            # 获取标准号列（第一列或名为 '标准号' 的列）
            std_col = None
            for col in df.columns:
                if '标准' in col or '号' in col:
                    std_col = col
                    break
            if std_col is None:
                std_col = df.columns[0]
            
            self.status_changed.emit(f"开始处理 {len(df)} 行标准号...")
            
            # 处理每一行
            results = []
            for idx, row in df.iterrows():
                std_no = str(row[std_col]).strip()
                if not std_no or std_no.lower() == 'nan':
                    results.append({
                        '原始标准号': std_no,
                        '补全标准号': '',
                        '标准名称': '',
                        '状态': '空值'
                    })
                else:
                    # 处理标准号
                    full_std_no, name, status = self.processor.process_standard(std_no)
                    results.append({
                        '原始标准号': std_no,
                        '补全标准号': full_std_no,
                        '标准名称': name,
                        '状态': status
                    })
                
                # 更新进度
                self.progress_updated.emit(idx + 1, len(df))
            
            # 创建结果 DataFrame
            self.result_df = pd.DataFrame(results)
            self.result_ready.emit(self.result_df)
            self.status_changed.emit(f"处理完成！共处理 {len(df)} 行")
            
        except Exception as e:
            self.error_occurred.emit(f"处理失败: {str(e)}")


class ExcelDialogSignals(QtCore.QObject):
    """信号代理（兼容 PySide2）"""
    progress_updated = QtCore.Signal(int, int)
    result_ready = QtCore.Signal(object)
    error_occurred = QtCore.Signal(str)
    status_changed = QtCore.Signal(str)


class ExcelDialog(QtWidgets.QDialog):
    """Excel 标准号处理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Excel 标准号补全处理")
        self.setGeometry(100, 100, 1000, 600)
        
        self.processor = StandardProcessor()
        self.worker_thread = None
        self.signals = ExcelDialogSignals()
        self.result_df = None
        
        # 连接信号
        self.signals.progress_updated.connect(self.on_progress_updated)
        self.signals.result_ready.connect(self.on_result_ready)
        self.signals.error_occurred.connect(self.on_error)
        self.signals.status_changed.connect(self.on_status_changed)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QtWidgets.QVBoxLayout()
        
        # ========== 顶部：文件选择区 ==========
        top_layout = QtWidgets.QHBoxLayout()
        
        self.label_file = QtWidgets.QLabel("未选择文件")
        self.label_file.setStyleSheet("color: #666; font-size: 12px;")
        
        self.btn_select = QtWidgets.QPushButton("选择 Excel 文件")
        self.btn_select.clicked.connect(self.select_file)
        self.btn_select.setMaximumWidth(120)
        
        self.btn_process = QtWidgets.QPushButton("开始处理")
        self.btn_process.clicked.connect(self.process_file)
        self.btn_process.setMaximumWidth(100)
        self.btn_process.setEnabled(False)
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666;
            }
        """)
        
        top_layout.addWidget(QtWidgets.QLabel("文件："))
        top_layout.addWidget(self.label_file, 1)
        top_layout.addWidget(self.btn_select)
        top_layout.addWidget(self.btn_process)
        
        layout.addLayout(top_layout)
        layout.addSpacing(10)
        
        # ========== 中部：进度条 ==========
        progress_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        
        self.label_progress = QtWidgets.QLabel("")
        self.label_progress.setVisible(False)
        self.label_progress.setStyleSheet("color: #666; font-size: 12px;")
        
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.label_progress)
        
        layout.addLayout(progress_layout)
        layout.addSpacing(10)
        
        # ========== 中部：结果表格 ==========
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['原始标准号', '补全标准号', '标准名称', '状态'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 100)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(QtWidgets.QLabel("处理结果："), 0)
        layout.addWidget(self.table, 1)
        
        # ========== 底部：日志和按钮 ==========
        bottom_layout = QtWidgets.QHBoxLayout()
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                font-family: Courier;
                font-size: 10px;
            }
        """)
        
        layout.addWidget(QtWidgets.QLabel("处理日志："), 0)
        layout.addWidget(self.log_text, 1)
        
        # 导出按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_export_excel = QtWidgets.QPushButton("导出为 Excel")
        self.btn_export_excel.clicked.connect(self.export_excel)
        self.btn_export_excel.setEnabled(False)
        
        self.btn_export_csv = QtWidgets.QPushButton("导出为 CSV")
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_csv.setEnabled(False)
        
        self.btn_close = QtWidgets.QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        
        button_layout.addStretch()
        button_layout.addWidget(self.btn_export_excel)
        button_layout.addWidget(self.btn_export_csv)
        button_layout.addWidget(self.btn_close)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def select_file(self):
        """选择 Excel 文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择 Excel 文件",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.excel_file = file_path
            file_name = Path(file_path).name
            self.label_file.setText(file_name)
            self.btn_process.setEnabled(True)
            self.append_log(f"选择文件: {file_name}")
    
    def process_file(self):
        """处理文件"""
        if not hasattr(self, 'excel_file'):
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择 Excel 文件")
            return
        
        # 禁用按钮
        self.btn_process.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        
        # 清空结果
        self.table.setRowCount(0)
        self.log_text.clear()
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.label_progress.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动后台线程
        self.append_log("开始处理...")
        
        class ProcessThread(threading.Thread):
            def __init__(self, parent):
                super().__init__(daemon=True)
                self.parent = parent
            
            def run(self):
                try:
                    df = pd.read_excel(self.parent.excel_file)
                    if df.empty:
                        self.parent.signals.error_occurred.emit("Excel 文件为空")
                        return
                    
                    # 获取标准号列
                    std_col = None
                    for col in df.columns:
                        if '标准' in col or '号' in col:
                            std_col = col
                            break
                    if std_col is None:
                        std_col = df.columns[0]
                    
                    self.parent.signals.status_changed.emit(f"开始处理 {len(df)} 行标准号...")
                    
                    # 处理每一行
                    results = []
                    for idx, row in df.iterrows():
                        std_no = str(row[std_col]).strip()
                        if not std_no or std_no.lower() == 'nan':
                            results.append({
                                '原始标准号': std_no,
                                '补全标准号': '',
                                '标准名称': '',
                                '状态': '空值'
                            })
                        else:
                            # 处理标准号
                            full_std_no, name, status = self.parent.processor.process_standard(std_no)
                            results.append({
                                '原始标准号': std_no,
                                '补全标准号': full_std_no,
                                '标准名称': name,
                                '状态': status
                            })
                        
                        # 更新进度
                        self.parent.signals.progress_updated.emit(idx + 1, len(df))
                    
                    # 创建结果 DataFrame
                    result_df = pd.DataFrame(results)
                    self.parent.signals.result_ready.emit(result_df)
                    self.parent.signals.status_changed.emit(f"处理完成！共处理 {len(df)} 行")
                    
                except Exception as e:
                    self.parent.signals.error_occurred.emit(f"处理失败: {str(e)}")
        
        self.worker_thread = ProcessThread(self)
        self.worker_thread.start()
    
    def on_progress_updated(self, current, total):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.label_progress.setText(f"{current}/{total}")
    
    def on_result_ready(self, result_df):
        """处理完成，显示结果"""
        self.result_df = result_df
        self.show_results(result_df)
        
        # 启用导出按钮
        self.btn_export_excel.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
    
    def on_error(self, error_msg):
        """处理错误"""
        self.append_log(f"❌ {error_msg}")
        QtWidgets.QMessageBox.warning(self, "处理出错", error_msg)
        
        # 恢复按钮状态
        self.btn_process.setEnabled(True)
        self.btn_select.setEnabled(True)
    
    def on_status_changed(self, status):
        """状态变化"""
        self.append_log(status)
    
    def show_results(self, df: pd.DataFrame):
        """显示结果表格"""
        self.table.setRowCount(len(df))
        
        for row_idx, row in df.iterrows():
            for col_idx, col_name in enumerate(df.columns):
                value = str(row[col_name])
                item = QtWidgets.QTableWidgetItem(value)
                
                # 根据状态着色
                if col_name == '状态':
                    if '成功' in value:
                        item.setBackground(QtGui.QColor('#d4edda'))
                    elif '未找到' in value:
                        item.setBackground(QtGui.QColor('#fff3cd'))
                    else:
                        item.setBackground(QtGui.QColor('#f8d7da'))
                
                self.table.setItem(row_idx, col_idx, item)
    
    def export_excel(self):
        """导出为 Excel"""
        if self.result_df is None:
            QtWidgets.QMessageBox.warning(self, "提示", "没有可导出的数据")
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存 Excel 文件",
            "标准号补全结果.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if file_path:
            try:
                self.result_df.to_excel(file_path, index=False)
                self.append_log(f"✓ 已导出: {file_path}")
                QtWidgets.QMessageBox.information(self, "成功", f"已导出到:\n{file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "导出失败", str(e))
    
    def export_csv(self):
        """导出为 CSV"""
        if self.result_df is None:
            QtWidgets.QMessageBox.warning(self, "提示", "没有可导出的数据")
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存 CSV 文件",
            "标准号补全结果.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                self.result_df.to_csv(file_path, index=False, encoding='utf-8-sig')
                self.append_log(f"✓ 已导出: {file_path}")
                QtWidgets.QMessageBox.information(self, "成功", f"已导出到:\n{file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "导出失败", str(e))
    
    def append_log(self, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
