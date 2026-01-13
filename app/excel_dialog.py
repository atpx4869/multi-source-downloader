# -*- coding: utf-8 -*-
"""
Excel 标准号处理对话框
集成标准号补全功能，直接在桌面应用中处理 Excel
"""
import sys
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web_app.excel_standard_processor import StandardProcessor

try:
    from PySide6 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 2


class ExcelDialog(QtWidgets.QDialog):
    """Excel 标准号处理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Excel 标准号补全处理")
        self.setGeometry(100, 100, 1000, 700)
        self.setModal(True)
        
        self.processor = StandardProcessor()
        self.result_df = None
        self.excel_file = None
        self.processing = False
        
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # ========== 1. 文件选择区 ==========
        file_group = QtWidgets.QGroupBox("1. 选择文件")
        file_layout = QtWidgets.QHBoxLayout()
        
        self.label_file = QtWidgets.QLabel("未选择文件")
        self.label_file.setStyleSheet("color: #666; padding: 5px;")
        
        self.btn_select = QtWidgets.QPushButton("选择 Excel 文件")
        self.btn_select.setMaximumWidth(120)
        self.btn_select.clicked.connect(self.select_file)
        self.btn_select.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        
        file_layout.addWidget(QtWidgets.QLabel("文件："))
        file_layout.addWidget(self.label_file, 1)
        file_layout.addWidget(self.btn_select)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # ========== 2. 处理区 ==========
        process_group = QtWidgets.QGroupBox("2. 开始处理")
        process_layout = QtWidgets.QHBoxLayout()
        
        self.btn_process = QtWidgets.QPushButton("开始处理")
        self.btn_process.setMaximumWidth(100)
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.process_file)
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
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
        
        # 进度显示
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(25)
        
        self.label_progress = QtWidgets.QLabel("")
        self.label_progress.setVisible(False)
        self.label_progress.setStyleSheet("color: #666; font-size: 11px; min-width: 50px;")
        
        process_layout.addWidget(self.btn_process)
        process_layout.addWidget(self.progress_bar, 1)
        process_layout.addWidget(self.label_progress)
        process_group.setLayout(process_layout)
        main_layout.addWidget(process_group)
        
        # ========== 3. 结果表格 ==========
        table_group = QtWidgets.QGroupBox("3. 处理结果")
        table_layout = QtWidgets.QVBoxLayout()
        
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['原始标准号', '补全标准号', '标准名称', '状态'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 100)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(200)
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        main_layout.addWidget(table_group, 1)
        
        # ========== 4. 日志 ==========
        log_group = QtWidgets.QGroupBox("4. 处理日志")
        log_layout = QtWidgets.QVBoxLayout()
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(80)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                font-family: Courier;
                font-size: 10px;
            }
        """)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # ========== 5. 底部按钮 ==========
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_export_excel = QtWidgets.QPushButton("导出 Excel")
        self.btn_export_excel.setMaximumWidth(100)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.clicked.connect(self.export_excel)
        
        self.btn_export_csv = QtWidgets.QPushButton("导出 CSV")
        self.btn_export_csv.setMaximumWidth(100)
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self.export_csv)
        
        self.btn_close = QtWidgets.QPushButton("关闭")
        self.btn_close.setMaximumWidth(100)
        self.btn_close.clicked.connect(self.accept)
        
        button_layout.addStretch()
        button_layout.addWidget(self.btn_export_excel)
        button_layout.addWidget(self.btn_export_csv)
        button_layout.addWidget(self.btn_close)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def append_log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
    
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
            self.append_log(f"已选择: {file_name}")
    
    def process_file(self):
        """处理文件"""
        if not self.excel_file:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择 Excel 文件")
            return
        
        # 禁用按钮
        self.btn_select.setEnabled(False)
        self.btn_process.setEnabled(False)
        self.processing = True
        
        # 清空之前的结果
        self.table.setRowCount(0)
        self.log_text.clear()
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.label_progress.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.append_log("开始处理...")
        
        # 在后台线程处理
        thread = threading.Thread(target=self._process_in_background, daemon=True)
        thread.start()
    
    def _process_in_background(self):
        """在后台线程中处理"""
        try:
            self.append_log("读取 Excel 文件...")
            df = pd.read_excel(self.excel_file)
            
            if df.empty:
                self.append_log("❌ Excel 文件为空")
                return
            
            # 获取标准号列
            std_col = None
            for col in df.columns:
                if '标准' in col or '号' in col:
                    std_col = col
                    break
            if std_col is None:
                std_col = df.columns[0]
            
            self.append_log(f"开始处理 {len(df)} 行标准号...")
            
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
                    try:
                        # 处理标准号
                        full_std_no, name, status = self.processor.process_standard(std_no)
                        results.append({
                            '原始标准号': std_no,
                            '补全标准号': full_std_no,
                            '标准名称': name,
                            '状态': status
                        })
                    except Exception as e:
                        results.append({
                            '原始标准号': std_no,
                            '补全标准号': '',
                            '标准名称': '',
                            '状态': f'错误: {str(e)[:20]}'
                        })
                
                # 更新进度
                self.progress_bar.setMaximum(len(df))
                self.progress_bar.setValue(idx + 1)
                self.label_progress.setText(f"{idx + 1}/{len(df)}")
                QtWidgets.QApplication.processEvents()
            
            # 显示结果
            self.result_df = pd.DataFrame(results)
            self.show_results(self.result_df)
            
            self.append_log(f"✓ 处理完成！共 {len(results)} 行")
            
            # 启用导出按钮
            self.btn_export_excel.setEnabled(True)
            self.btn_export_csv.setEnabled(True)
            
        except Exception as e:
            self.append_log(f"❌ 处理出错: {str(e)}")
            QtWidgets.QMessageBox.warning(self, "处理出错", f"发生错误:\n{str(e)}")
        
        finally:
            # 恢复按钮状态
            self.btn_select.setEnabled(True)
            self.btn_process.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.label_progress.setVisible(False)
            self.processing = False
    
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
