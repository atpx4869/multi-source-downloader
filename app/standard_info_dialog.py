# -*- coding: utf-8 -*-
"""
标准查新对话框
用户上传标准号列表，自动查询发布日期、实施日期、状态等元数据信息
"""
import sys
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.aggregated_downloader import AggregatedDownloader

try:
    from PySide6 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 2


class StandardInfoDialog(QtWidgets.QDialog):
    """标准查新对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标准查新 - 批量查询元数据")
        self.setGeometry(100, 100, 1000, 700)
        self.setModal(True)
        
        # 设置对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
            }
            QGroupBox {
                color: #333333;
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #2196F3;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
            }
            QTableWidget {
                background-color: white;
                color: #333333;
                gridline-color: #ddd;
                selection-background-color: #2196F3;
                selection-color: white;
            }
            QTableWidget::item {
                color: #333333;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                color: #333333;
                padding: 5px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        self.downloader = None
        self.result_df = None
        self.file_path = None
        self.processing = False
        
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # ========== 1. 文件选择区 ==========
        file_group = QtWidgets.QGroupBox("1. 选择标准号文件")
        file_layout = QtWidgets.QHBoxLayout()
        
        self.label_file = QtWidgets.QLabel("未选择文件")
        self.label_file.setStyleSheet("color: #666666; padding: 5px;")
        
        self.btn_select = QtWidgets.QPushButton("选择文件 (Excel/CSV/TXT)")
        self.btn_select.setMaximumWidth(160)
        self.btn_select.clicked.connect(self.select_file)
        self.btn_select.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        file_layout.addWidget(self.label_file, 1)
        file_layout.addWidget(self.btn_select)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # ========== 2. 配置区 ==========
        config_group = QtWidgets.QGroupBox("2. 配置查询参数")
        config_layout = QtWidgets.QFormLayout()
        
        # 数据源选择
        source_layout = QtWidgets.QHBoxLayout()
        self.cb_zby = QtWidgets.QCheckBox("ZBY")
        self.cb_zby.setChecked(True)
        self.cb_by = QtWidgets.QCheckBox("BY")
        self.cb_by.setChecked(False)
        self.cb_gbw = QtWidgets.QCheckBox("GBW")
        self.cb_gbw.setChecked(False)
        source_layout.addWidget(self.cb_zby)
        source_layout.addWidget(self.cb_by)
        source_layout.addWidget(self.cb_gbw)
        source_layout.addStretch()
        config_layout.addRow("数据源:", source_layout)
        
        # 列名称配置
        self.input_column = QtWidgets.QLineEdit()
        self.input_column.setPlaceholderText("例如: 标准号, std_no, 标准编号 (留空则自动识别)")
        config_layout.addRow("标准号列名:", self.input_column)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # ========== 3. 处理按钮 ==========
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_process = QtWidgets.QPushButton("🔍 开始查询")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.process_file)
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_process)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        # ========== 4. 进度显示 ==========
        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: white;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
            }
        """)
        main_layout.addWidget(self.progress)
        
        self.label_status = QtWidgets.QLabel("")
        self.label_status.setStyleSheet("color: #666666; padding: 5px;")
        self.label_status.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.label_status)
        
        # ========== 5. 结果显示表格 ==========
        result_group = QtWidgets.QGroupBox("3. 查询结果")
        result_layout = QtWidgets.QVBoxLayout()
        
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            '原始标准号', '规范标准号', '标准名称', 
            '发布日期', '实施日期', '状态', '替代标准', '来源'
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        result_layout.addWidget(self.table)
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group, 1)
        
        # ========== 6. 底部按钮 ==========
        bottom_layout = QtWidgets.QHBoxLayout()
        
        self.btn_export_excel = QtWidgets.QPushButton("导出 Excel")
        self.btn_export_excel.setMaximumWidth(100)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.clicked.connect(self.export_excel)
        self.btn_export_excel.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.btn_export_csv = QtWidgets.QPushButton("导出 CSV")
        self.btn_export_csv.setMaximumWidth(100)
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_csv.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.btn_close = QtWidgets.QPushButton("关闭")
        self.btn_close.setMaximumWidth(80)
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_export_excel)
        bottom_layout.addWidget(self.btn_export_csv)
        bottom_layout.addWidget(self.btn_close)
        
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)
    
    def select_file(self):
        """选择文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择标准号文件",
            "",
            "所有支持的文件 (*.xlsx *.xls *.csv *.txt);;Excel文件 (*.xlsx *.xls);;CSV文件 (*.csv);;文本文件 (*.txt)"
        )
        
        if file_path:
            self.file_path = file_path
            self.label_file.setText(f"已选择: {Path(file_path).name}")
            self.label_file.setStyleSheet("color: #4CAF50; padding: 5px; font-weight: bold;")
            self.btn_process.setEnabled(True)
    
    def get_enabled_sources(self):
        """获取启用的数据源"""
        sources = []
        if self.cb_zby.isChecked():
            sources.append("ZBY")
        if self.cb_by.isChecked():
            sources.append("BY")
        if self.cb_gbw.isChecked():
            sources.append("GBW")
        return sources if sources else ["ZBY"]
    
    def process_file(self):
        """处理文件"""
        if self.processing:
            QtWidgets.QMessageBox.warning(self, "提示", "正在处理中，请稍候...")
            return
        
        if not self.file_path:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择文件！")
            return
        
        self.processing = True
        self.btn_process.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.label_status.setText("正在读取文件...")
        
        # 在后台线程处理
        thread = threading.Thread(target=self._process_in_background)
        thread.daemon = True
        thread.start()
    
    def _process_in_background(self):
        """后台处理线程"""
        try:
            # 1. 读取文件
            self.update_status("正在读取文件...", 10)
            df = self._read_file()
            
            if df is None or df.empty:
                self.update_status("文件读取失败或为空！", 0)
                self.processing = False
                return
            
            # 2. 识别标准号列
            self.update_status("正在识别标准号列...", 20)
            std_column = self._identify_std_column(df)
            
            if not std_column:
                self.update_status("未找到标准号列！", 0)
                self.processing = False
                return
            
            # 3. 提取标准号
            std_list = df[std_column].dropna().astype(str).tolist()
            self.update_status(f"找到 {len(std_list)} 个标准号", 30)
            
            # 4. 初始化下载器
            sources = self.get_enabled_sources()
            self.update_status(f"初始化数据源: {', '.join(sources)}", 40)
            self.downloader = AggregatedDownloader(enable_sources=sources, output_dir="downloads")
            
            # 5. 批量查询
            results = []
            total = len(std_list)
            for i, std_no in enumerate(std_list, 1):
                progress = 40 + int((i / total) * 50)
                self.update_status(f"查询中 ({i}/{total}): {std_no}", progress)
                
                # 搜索标准
                search_results = self.downloader.search(std_no, limit=1)
                
                if search_results:
                    result = search_results[0]
                    results.append({
                        '原始标准号': std_no,
                        '规范标准号': result.std_no,
                        '标准名称': result.name,
                        '发布日期': result.publish or '',
                        '实施日期': result.implement or '',
                        '状态': result.status or '',
                        '替代标准': result.replace_std or '',
                        '来源': ', '.join(result.sources) if hasattr(result, 'sources') and result.sources else 'ZBY'
                    })
                else:
                    results.append({
                        '原始标准号': std_no,
                        '规范标准号': '',
                        '标准名称': '未找到',
                        '发布日期': '',
                        '实施日期': '',
                        '状态': '',
                        '替代标准': '',
                        '来源': ''
                    })
            
            # 6. 显示结果
            self.result_df = pd.DataFrame(results)
            self.update_status(f"查询完成！找到 {len(results)} 条结果", 100)
            self._display_results()
            
        except Exception as e:
            self.update_status(f"处理失败: {str(e)}", 0)
            QtWidgets.QMessageBox.critical(self, "错误", f"处理失败:\n{str(e)}")
        
        finally:
            self.processing = False
            self.btn_process.setEnabled(True)
    
    def _read_file(self):
        """读取文件"""
        try:
            file_ext = Path(self.file_path).suffix.lower()
            
            if file_ext in ['.xlsx', '.xls']:
                return pd.read_excel(self.file_path)
            elif file_ext == '.csv':
                # 尝试不同编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                    try:
                        return pd.read_csv(self.file_path, encoding=encoding)
                    except:
                        continue
                return None
            elif file_ext == '.txt':
                # 读取为单列
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                return pd.DataFrame({'标准号': lines})
            else:
                return None
        except Exception as e:
            print(f"读取文件失败: {e}")
            return None
    
    def _identify_std_column(self, df):
        """识别标准号列"""
        # 用户指定的列名
        user_column = self.input_column.text().strip()
        if user_column and user_column in df.columns:
            return user_column
        
        # 自动识别
        possible_names = ['标准号', 'std_no', '标准编号', '编号', 'number', 'code', '标准代号']
        for col in df.columns:
            if any(name in str(col).lower() for name in possible_names):
                return col
        
        # 默认使用第一列
        return df.columns[0] if len(df.columns) > 0 else None
    
    def _display_results(self):
        """显示结果"""
        if self.result_df is None or self.result_df.empty:
            return
        
        self.table.setRowCount(0)
        for idx, row in self.result_df.iterrows():
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            
            for col_idx, col_name in enumerate(self.result_df.columns):
                value = str(row[col_name])
                item = QtWidgets.QTableWidgetItem(value)
                
                # 状态列颜色
                if col_name == '状态' and value:
                    if '现行' in value or 'active' in value.lower():
                        item.setBackground(QtGui.QColor("#d4edda"))
                        item.setForeground(QtGui.QColor("#155724"))
                    elif '废止' in value or 'supersede' in value.lower():
                        item.setBackground(QtGui.QColor("#f8d7da"))
                        item.setForeground(QtGui.QColor("#721c24"))
                
                self.table.setItem(row_pos, col_idx, item)
        
        self.btn_export_excel.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
    
    def update_status(self, message, progress):
        """更新状态（线程安全）"""
        QtCore.QMetaObject.invokeMethod(
            self.label_status,
            "setText",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, message)
        )
        QtCore.QMetaObject.invokeMethod(
            self.progress,
            "setValue",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(int, progress)
        )
    
    def export_excel(self):
        """导出为 Excel"""
        if self.result_df is None or self.result_df.empty:
            QtWidgets.QMessageBox.warning(self, "提示", "暂无结果可导出！")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"标准查新结果_{timestamp}.xlsx"
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 Excel", default_name, "Excel 文件 (*.xlsx)"
        )
        
        if file_path:
            try:
                self.result_df.to_excel(file_path, index=False, engine='openpyxl')
                QtWidgets.QMessageBox.information(
                    self, "成功", f"已成功导出到:\n{file_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")
    
    def export_csv(self):
        """导出为 CSV"""
        if self.result_df is None or self.result_df.empty:
            QtWidgets.QMessageBox.warning(self, "提示", "暂无结果可导出！")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"标准查新结果_{timestamp}.csv"
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 CSV", default_name, "CSV 文件 (*.csv)"
        )
        
        if file_path:
            try:
                self.result_df.to_csv(file_path, index=False, encoding='utf-8-sig')
                QtWidgets.QMessageBox.information(
                    self, "成功", f"已成功导出到:\n{file_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dialog = StandardInfoDialog()
    dialog.show()
    sys.exit(app.exec())
