# -*- coding: utf-8 -*-
"""
桌面原型 - PySide6

功能：
- 左侧：搜索输入、结果表（可选择行）
- 右侧：实时日志（自动滚动）
- 后台线程执行搜索与下载，使用信号回写 UI
- 优化：先搜索ZBY快速返回，后台补充GBW/BY

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
import os
import json
from pathlib import Path
from datetime import datetime
import re
from typing import List, Dict, Optional, Any
import queue
import threading
import time

project_root = Path(__file__).parent.parent  # 项目根目录（上两级）
sys.path.insert(0, str(project_root))

# Add ppllocr path for development mode
ppllocr_path = project_root / "ppllocr" / "ppllocr-main"
if ppllocr_path.exists():
    sys.path.insert(0, str(ppllocr_path))

# Ensure the local "sources" package is discovered by PyInstaller
# Some imports are dynamic in the codebase; this explicit import helps
# PyInstaller include the package into the frozen bundle.
try:
    import sources  # type: ignore
    # also import common submodules so PyInstaller includes them
    try:
        import sources.gbw  # type: ignore
    except Exception:
        pass
    try:
        import sources.by  # type: ignore
    except Exception:
        pass
    try:
        import sources.zby  # type: ignore
    except Exception:
        pass
except Exception:
    pass

import traceback
import pandas as pd

# 导入 API 配置
from core.api_config import get_api_config
from core.cache_manager import get_cache_manager

try:
    from PySide6 import QtCore, QtWidgets, QtGui
    PYSIDE_VER = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtWidgets, QtGui
        PYSIDE_VER = 2
    except ImportError:
        raise ImportError("Neither PySide6 nor PySide2 is installed.")

# 兼容性处理：Qt5 使用 exec_()，Qt6 使用 exec()
if PYSIDE_VER == 2:
    if not hasattr(QtWidgets.QApplication, 'exec'):
        QtWidgets.QApplication.exec = QtWidgets.QApplication.exec_
    if not hasattr(QtWidgets.QDialog, 'exec'):
        QtWidgets.QDialog.exec = QtWidgets.QDialog.exec_
    if not hasattr(QtCore.QCoreApplication, 'exec'):
        QtCore.QCoreApplication.exec = QtCore.QCoreApplication.exec_


def _ensure_qt_platform_plugin_path():
    """在某些环境（尤其路径包含中文/打包环境）下，Qt 可能找不到 windows 平台插件。

    显式设置 QT_QPA_PLATFORM_PLUGIN_PATH / QT_PLUGIN_PATH 并追加 library path，
    以避免报错：Could not find the Qt platform plugin "windows".
    """
    try:
        # 不要在模块顶层强依赖某个 PySide 版本
        if PYSIDE_VER == 2:
            import PySide2 as _pyside  # type: ignore
        else:
            import PySide6 as _pyside  # type: ignore
        pyside_dir = Path(_pyside.__file__).resolve().parent
        plugins_dir = pyside_dir / "plugins"
        platforms_dir = plugins_dir / "platforms"
        if not platforms_dir.exists():
            return

        # 若环境变量未设置或指向无效路径，则覆盖
        cur_platforms = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH")
        if not cur_platforms or not Path(cur_platforms).exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)

        cur_plugins = os.environ.get("QT_PLUGIN_PATH")
        if not cur_plugins or not Path(cur_plugins).exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)

        # 追加到 Qt 的 libraryPaths（需要在创建 QApplication 之前调用）
        try:
            QtCore.QCoreApplication.addLibraryPath(str(plugins_dir))
        except Exception:
            pass
    except Exception:
        return


_ensure_qt_platform_plugin_path()

import ui_styles

# 规范号规范化正则（复用以避免在循环中重复编译）
_STD_NO_RE = re.compile(r"[\s/\-–—_:：]+")
import threading

# 缓存 AggregatedDownloader 实例以减少重复初始化开销
_AD_CACHE: dict = {}
_AD_CACHE_LOCK = threading.Lock()

def get_aggregated_downloader(enable_sources=None, output_dir=None):
    """返回一个复用的 AggregatedDownloader 实例（按 enable_sources+output_dir 缓存）。
    如果 AggregatedDownloader 未导入或无法实例化，则返回 None 或抛出原始异常。
    """
    if output_dir is None:
        output_dir = "downloads"
    key = (tuple(enable_sources) if enable_sources else None, output_dir)
    with _AD_CACHE_LOCK:
        inst = _AD_CACHE.get(key)
        if inst is not None:
            return inst

        # 延迟导入 core.AggregatedDownloader，若不可用则返回 None
        try:
            from core import AggregatedDownloader
        
            try:
                inst = AggregatedDownloader(enable_sources=enable_sources, output_dir=output_dir)
            except Exception:
                # 打印详细 traceback 以便诊断初始化失败原因
                print("[get_aggregated_downloader] AggregatedDownloader init failed:")
                traceback.print_exc()
                return None
        except Exception:
            print("[get_aggregated_downloader] import/core failure:")
            traceback.print_exc()
            return None

        _AD_CACHE[key] = inst
        return inst

try:
    from core import AggregatedDownloader
    from core import natural_key
    from core.models import Standard
except Exception:
    AggregatedDownloader = None
    Standard = None


# ==================== 密码验证模块 ====================

def get_today_password() -> str:
    """获取今日密码：日期反转后取6位"""
    today = datetime.now().strftime("%Y%m%d")  # 如 20251216
    return today[::-1][:6]  # 反转后取前6位: 61215202 -> 612152


def get_auth_file() -> Path:
    """获取验证记录文件路径"""
    return Path(__file__).parent / ".auth_cache"


def is_authenticated_today() -> bool:
    """检查今天是否已验证过"""
    auth_file = get_auth_file()
    if not auth_file.exists():
        return False
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        last_auth_date = data.get("date", "")
        today = datetime.now().strftime("%Y%m%d")
        return last_auth_date == today
    except Exception:
        return False


def save_auth_record():
    """保存今日验证记录"""
    auth_file = get_auth_file()
    today = datetime.now().strftime("%Y%m%d")
    auth_file.write_text(json.dumps({"date": today}), encoding="utf-8")


class PasswordDialog(QtWidgets.QDialog):
    """密码验证对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安全验证")
        self.setFixedSize(360, 260)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setup_ui()
        self.attempts = 0
        self.max_attempts = 5
        # 设置对话框为模态且置顶
        self.setModal(True)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        
    def setup_ui(self):
        self.setStyleSheet(ui_styles.DIALOG_STYLE)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 20, 30, 20)
        
        # 顶部标题栏 - 居中布局
        header = QtWidgets.QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #34c2db;
                border-radius: 8px;
            }
        """)
        header.setFixedHeight(55)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # 居中容器
        center_widget = QtWidgets.QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QtWidgets.QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)
        
        icon_label = QtWidgets.QLabel("🔐")
        icon_label.setStyleSheet("font-size: 24px; background: transparent;")
        center_layout.addWidget(icon_label)
        
        title = QtWidgets.QLabel("标准文献检索系统")
        title.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: white;
            background: transparent;
        """)
        center_layout.addWidget(title)
        
        header_layout.addStretch()
        header_layout.addWidget(center_widget)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # 提示文字 - 确保完整显示
        subtitle = QtWidgets.QLabel("请输入6位数字密码以继续使用")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setFixedHeight(30)
        subtitle.setStyleSheet("""
            font-size: 12px;
            color: #666;
        """)
        layout.addWidget(subtitle)
        
        # 密码输入框 - 使用星号显示
        self.pwd_input = QtWidgets.QLineEdit()
        self.pwd_input.setPlaceholderText("******")
        self.pwd_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pwd_input.setMaxLength(6)
        self.pwd_input.setAlignment(QtCore.Qt.AlignCenter)
        self.pwd_input.setFixedHeight(50)
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 2px solid #34c2db;
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 18px;
                font-weight: bold;
                font-family: Arial;
                letter-spacing: 10px;
                color: #333;
                lineedit-password-character: 42;
            }
            QLineEdit:focus {
                border-color: #346edb;
            }
        """)
        self.pwd_input.returnPressed.connect(self.verify_password)
        layout.addWidget(self.pwd_input)
        
        # 提示信息
        self.msg_label = QtWidgets.QLabel("")
        self.msg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.msg_label.setStyleSheet("""
            font-size: 11px;
            color: #e74c3c;
            min-height: 16px;
        """)
        layout.addWidget(self.msg_label)
        
        # 确认按钮
        self.btn_confirm = QtWidgets.QPushButton("确 认")
        self.btn_confirm.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_confirm.setFixedHeight(38)
        self.btn_confirm.setStyleSheet(ui_styles.BTN_PRIMARY_STYLE)
        self.btn_confirm.clicked.connect(self.verify_password)
        layout.addWidget(self.btn_confirm)
        
        # 底部提示
        hint = QtWidgets.QLabel("仅限内部使用 · 密码每日更新")
        hint.setAlignment(QtCore.Qt.AlignCenter)
        hint.setStyleSheet("""
            font-size: 10px;
            color: #aaa;
            padding-top: 5px;
        """)
        layout.addWidget(hint)
    
    def showEvent(self, event):
        """窗口显示时自动焦点到输入框"""
        try:
            super().showEvent(event)
            # 延迟设置焦点，确保窗口完全显示
            QtCore.QTimer.singleShot(100, self._set_focus)
        except Exception as e:
            print(f"❌ showEvent 错误: {e}")
    
    def _set_focus(self):
        """设置焦点到输入框"""
        try:
            self.pwd_input.setFocus()
            self.pwd_input.selectAll()
            print("[DEBUG] 焦点已设置到输入框")
        except Exception as e:
            print(f"❌ 设置焦点失败: {e}")
    
    def verify_password(self):
        """验证密码"""
        try:
            entered = self.pwd_input.text().strip()
            correct = get_today_password()
            
            print(f"[DEBUG] 输入长度: {len(entered)}, 期望长度: {len(correct)}")  # 调试
            
            if entered == correct:
                save_auth_record()
                self.accept()
            else:
                self.attempts += 1
                remaining = self.max_attempts - self.attempts
                
                if remaining <= 0:
                    QtWidgets.QMessageBox.critical(self, "验证失败", "密码错误次数过多，程序将退出。")
                    self.reject()
                else:
                    self.msg_label.setText(f"❌ 密码错误，还剩 {remaining} 次机会")
                    self.pwd_input.clear()
                    self.pwd_input.setFocus()
        except Exception as e:
            print(f"❌ 密码验证错误: {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self, "错误", f"验证过程出错：{str(e)}")
            self.reject()
    
    def shake_animation(self):
        """窗口抖动效果"""
        original_pos = self.pos()
        
        animation = QtCore.QPropertyAnimation(self, b"pos")
        animation.setDuration(300)
        animation.setLoopCount(1)
        
        animation.setKeyValueAt(0, original_pos)
        animation.setKeyValueAt(0.1, original_pos + QtCore.QPoint(10, 0))
        animation.setKeyValueAt(0.2, original_pos + QtCore.QPoint(-10, 0))
        animation.setKeyValueAt(0.3, original_pos + QtCore.QPoint(8, 0))
        animation.setKeyValueAt(0.4, original_pos + QtCore.QPoint(-8, 0))
        animation.setKeyValueAt(0.5, original_pos + QtCore.QPoint(5, 0))
        animation.setKeyValueAt(0.6, original_pos + QtCore.QPoint(-5, 0))
        animation.setKeyValueAt(0.7, original_pos + QtCore.QPoint(3, 0))
        animation.setKeyValueAt(0.8, original_pos + QtCore.QPoint(-3, 0))
        animation.setKeyValueAt(1, original_pos)
        
        animation.start()
        # 保持动画对象引用
        self._shake_anim = animation


def check_password() -> bool:
    """检查密码验证，返回是否通过"""
    try:
        print("[DEBUG] 开始密码验证...")
        
        if is_authenticated_today():
            print("[DEBUG] 今日已验证过，跳过密码验证")
            return True
        
        print("[DEBUG] 创建密码对话框...")
        dialog = PasswordDialog()
        
        print("[DEBUG] 显示密码对话框...")
        result = dialog.exec()
        
        print(f"[DEBUG] 对话框返回结果: {result}")
        success = result == QtWidgets.QDialog.Accepted
        print(f"[DEBUG] 密码验证{'成功' if success else '失败'}")
        return success
    except Exception as e:
        print(f"❌ check_password 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 搜索下载模块 ====================


class SearchThread(QtCore.QThread):
    """渐进式搜索线程 - 并行搜索所有源，先搜出来的先显示"""
    partial_results = QtCore.Signal(str, list)  # source_name, rows - 单个源的结果
    all_completed = QtCore.Signal()  # 所有源搜索完成
    log = QtCore.Signal(str)
    error = QtCore.Signal(str)
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, keyword: str, sources: Optional[List[str]] = None, page: int = 1, page_size: int = 20, output_dir: str = "downloads"):
        super().__init__()
        self.keyword = keyword
        self.sources = sources or ["GBW", "BY", "ZBY"]
        self.page = page
        self.page_size = page_size
        self.output_dir = output_dir

    def run(self):
        try:
            if AggregatedDownloader is None:
                self.log.emit("AggregatedDownloader 未找到，无法执行搜索（请确认项目结构）")
                self.all_completed.emit()
                return
            
            self.log.emit(f"🔍 开始并行搜索: {self.keyword}，来源: {', '.join(self.sources)}")
            self.progress.emit(0, 100, f"正在搜索 {len(self.sources)} 个数据源...")
            
            import concurrent.futures
            import threading
            
            completed_count = 0
            total_sources = len(self.sources)
            lock = threading.Lock()
            
            def search_single_source(source_name: str):
                """搜索单个源"""
                try:
                    self.log.emit(f"   ↳ {source_name} 开始搜索...")
                    
                    # 创建单源客户端
                    client = get_aggregated_downloader(enable_sources=[source_name], output_dir=self.output_dir)
                    if client is None:
                        self.log.emit(f"   ✗ {source_name} 客户端创建失败")
                        return source_name, []
                    
                    # 搜索（注意：这里不使用parallel，因为单源搜索不需要并行）
                    items = client.search(self.keyword, parallel=False, page=int(self.page), page_size=int(self.page_size))
                    
                    # 转换为显示格式
                    rows = []
                    for it in items:
                        rows.append({
                            "std_no": it.std_no,
                            "name": it.name,
                            "publish": it.publish or "",
                            "implement": it.implement or "",
                            "status": it.status or "",
                            "has_pdf": bool(it.has_pdf),
                            "obj": it,
                        })
                    
                    self.log.emit(f"   ✅ {source_name} 完成: {len(rows)} 条")
                    return source_name, rows
                    
                except Exception as e:
                    self.log.emit(f"   ✗ {source_name} 失败: {str(e)[:50]}")
                    return source_name, []
            
            # 使用线程池并行搜索所有源
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.sources)) as executor:
                # 提交所有任务
                future_to_source = {executor.submit(search_single_source, src): src for src in self.sources}
                
                # 按完成顺序处理结果
                for future in concurrent.futures.as_completed(future_to_source):
                    try:
                        source_name, rows = future.result()
                        
                        # 立即发送这个源的结果（渐进式显示）
                        if rows:
                            self.partial_results.emit(source_name, rows)
                        
                        # 更新进度
                        with lock:
                            completed_count += 1
                            progress = int((completed_count / total_sources) * 100)
                            self.progress.emit(progress, 100, f"已完成 {completed_count}/{total_sources} 个数据源")
                        
                    except Exception as e:
                        self.log.emit(f"❌ 处理搜索结果时出错: {e}")
            
            self.progress.emit(100, 100, "所有数据源搜索完成")
            self.log.emit(f"✅ 搜索完成: 共查询 {total_sources} 个数据源")
            self.all_completed.emit()
            
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"❌ 搜索出错: {e}")
            self.log.emit(tb)
            self.error.emit(tb)
            self.progress.emit(0, 100, "搜索失败")
            self.all_completed.emit()


class BackgroundSearchThread(QtCore.QThread):
    """后台搜索线程 - 静默搜索GBW/BY，补充数据"""
    log = QtCore.Signal(str)
    finished = QtCore.Signal(dict)  # 返回 {std_no_normalized: Standard} 缓存
    progress = QtCore.Signal(str)  # 状态文本

    def __init__(self, keyword: str, sources: List[str], page: int = 1, page_size: int = 20, output_dir: str = "downloads"):
        super().__init__()
        self.keyword = keyword
        self.sources = sources  # 要搜索的源，如 ["GBW", "BY"]
        self.page = page
        self.page_size = page_size
        self.output_dir = output_dir

    def run(self):
        cache = {}
        try:
            if AggregatedDownloader is None or not self.sources:
                self.finished.emit(cache)
                return

            self.progress.emit(f"后台加载中: {', '.join(self.sources)}...")
            self.log.emit(f"🔄 后台开始搜索: {', '.join(self.sources)}")

            for src_name in self.sources:
                try:
                    self.log.emit(f"   ↳ 正在搜索 {src_name}...")
                    try:
                        client = get_aggregated_downloader(enable_sources=[src_name], output_dir=self.output_dir)
                    except Exception as e:
                        self.log.emit(f"   ✗ 创建 AggregatedDownloader 失败: {e}")
                        continue
                    if client is None:
                        self.log.emit(f"   ✗ AggregatedDownloader 未就绪: {src_name}")
                        continue
                    config = get_api_config()
                    items = client.search(self.keyword, parallel=config.parallel_search, page=int(self.page), page_size=int(self.page_size))
                    
                    for it in items:
                        # 标准化 std_no 作为 key
                        key = _STD_NO_RE.sub("", it.std_no or "").lower()
                        if key not in cache:
                            cache[key] = {}
                        
                        # 按源存储 Standard 对象，便于后续精确合并与优先级判断
                        s_name = it.sources[0] if it.sources else src_name
                        cache[key][s_name] = it
                    
                    self.log.emit(f"   ✅ {src_name} 完成: {len(items)} 条")
                except Exception as e:
                    self.log.emit(f"   ✗ {src_name} 失败: {str(e)[:50]}")

            self.progress.emit("后台加载完成")
            self.log.emit(f"✅ 后台搜索完成: 共缓存 {len(cache)} 条补充数据")
            
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"❌ 后台搜索出错: {e}")
            self.log.emit(tb)
            self.progress.emit("后台加载失败")
        
        self.finished.emit(cache)


class SearchWorker(threading.Thread):
    """后台搜索worker线程，从队列中取关键词并执行搜索"""
    
    def __init__(self, search_queue: queue.Queue, result_queue: queue.Queue, worker_id: int, 
                 enable_sources: List[str] = None, log_signal=None):
        super().__init__(daemon=True)
        self.search_queue = search_queue
        self.result_queue = result_queue
        self.worker_id = worker_id
        self.enable_sources = enable_sources
        self.log_signal = log_signal  # QtCore.Signal(str)

    def _emit_log(self, msg: str):
        """发送日志信号"""
        if self.log_signal:
            self.log_signal.emit(msg)

    def run(self):
        """从队列中取关键词并搜索"""
        try:
            client = get_aggregated_downloader(enable_sources=self.enable_sources, output_dir="downloads")
        except Exception as e:
            self._emit_log(f"❌ [SearchWorker-{self.worker_id}] 初始化失败: {e}")
            return

        while True:
            try:
                # 从队列中取任务，超时5秒
                task = self.search_queue.get(timeout=5)
                
                # 如果收到哨兵值（None），表示搜索完成
                if task is None:
                    break
                
                std_id, idx = task
                
                try:
                    config = get_api_config()
                    # 清理关键词
                    search_key = re.sub(r'\s+', ' ', std_id)
                    
                    # 优先级搜索策略（方案D）：BY > GBW > ZBY
                    # 在搜索时优先级搜索，找到就返回，不等其他源
                    results = None
                    
                    # 尝试按优先级搜索
                    for source_name in ["BY", "GBW", "ZBY"]:
                        try:
                            # 调用聚合下载器的搜索，指定只用某个源
                            # 注意：这里需要改造一下，直接调用单个源
                            results = client.search(search_key, parallel=config.parallel_search)
                            
                            if results:
                                self._emit_log(f"   ✅ [SearchWorker-{self.worker_id}] 搜索成功: {std_id}")
                                break
                        except Exception:
                            continue
                    
                    # 如果主搜索没找到，尝试部分关键词
                    if not results and '-' in search_key:
                        try:
                            short_key = search_key.split('-')[0].strip()
                            results = client.search(short_key, parallel=config.parallel_search)
                        except Exception:
                            pass
                    
                    # 放入结果队列
                    self.result_queue.put((std_id, idx, results))
                    
                except Exception as e:
                    self._emit_log(f"   ❌ [SearchWorker-{self.worker_id}] 搜索失败: {std_id} - {str(e)[:50]}")
                    self.result_queue.put((std_id, idx, None))
                finally:
                    self.search_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                self._emit_log(f"❌ [SearchWorker-{self.worker_id}] 异常: {str(e)[:80]}")
                break


class DownloadWorker(threading.Thread):
    """后台下载worker线程，从队列中取任务并执行下载"""
    
    def __init__(self, download_queue: queue.Queue, worker_id: int, output_dir: str = "downloads", 
                 enable_sources: List[str] = None, log_signal=None, progress_signal=None, prefer_order: List[str] = None):
        super().__init__(daemon=True)
        self.download_queue = download_queue
        self.worker_id = worker_id
        self.output_dir = output_dir
        self.enable_sources = enable_sources
        self.log_signal = log_signal  # QtCore.Signal(str)
        self.progress_signal = progress_signal  # QtCore.Signal(int, int, str)
        self.prefer_order = prefer_order  # 下载源优先级
        self.download_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.cache_manager = get_cache_manager()

    def _emit_log(self, msg: str):
        """发送日志信号"""
        if self.log_signal:
            self.log_signal.emit(msg)

    def _emit_progress(self, success: int, fail: int, msg: str):
        """发送进度信号"""
        if self.progress_signal:
            self.progress_signal.emit(success, fail, msg)

    def run(self):
        """从队列中取任务并下载"""
        try:
            client = get_aggregated_downloader(enable_sources=self.enable_sources, output_dir=self.output_dir)
        except Exception as e:
            self._emit_log(f"❌ [Worker-{self.worker_id}] 初始化下载器失败: {e}")
            return

        while True:
            try:
                # 从队列中取任务，超时5秒
                task = self.download_queue.get(timeout=5)
                
                # 如果收到哨兵值（None），表示下载完成
                if task is None:
                    summary = f"✅ [Worker-{self.worker_id}] 完成"
                    if self.success_count > 0:
                        summary += f" 成功{self.success_count}个"
                    if self.fail_count > 0:
                        summary += f" 失败{self.fail_count}个"
                    self._emit_log(summary)
                    break
                
                std_id, best_match = task
                self.download_count += 1
                
                # 智能重试策略：区分错误类型
                self._download_with_retry(best_match)
                
                self.download_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                self._emit_log(f"❌ [Worker-{self.worker_id}] 异常: {str(e)[:80]}")
                break

    def _classify_error(self, error_msg: str, logs: list) -> str:
        """
        错误分类：区分网络错误(重试)、源不可用(跳过)、无标准(记录)
        返回: "network" | "source_unavailable" | "not_found" | "corrupted" | "unknown"
        """
        error_msg_lower = error_msg.lower()
        logs_str = " ".join(logs or []).lower() if logs else ""
        
        # 网络错误：连接超时、临时故障、DNS等
        if any(k in error_msg_lower or k in logs_str for k in 
               ["timeout", "connection", "连接", "网络", "dns", "unreachable", "refused", "temporarily", "临时"]):
            return "network"
        
        # 源不可用：404、503、服务不可用等
        if any(k in error_msg_lower or k in logs_str for k in 
               ["404", "503", "502", "不可用", "unavailable", "forbidden", "403"]):
            return "source_unavailable"
        
        # 文件不存在或格式错误
        if any(k in error_msg_lower or k in logs_str for k in 
               ["未找到", "not found", "no such file", "无效", "corrupt", "损坏"]):
            return "not_found"
        
        # 文件损坏
        if any(k in error_msg_lower or k in logs_str for k in 
               ["损坏", "corrupt", "checksum", "crc"]):
            return "corrupted"
        
        return "unknown"

    def _download_with_retry(self, best_match):
        """
        带智能重试的下载逻辑
        - 网络错误：重试2次
        - 源不可用：跳过该源
        - 无标准：直接记录失败
        """
        import time
        
        self._emit_log(f"⬇️  [Worker-{self.worker_id}] 处理: {best_match.std_no}")
        
        max_retries = 2
        retry_delay = 2
        download_success = False
        last_error = None
        
        # 获取client实例
        try:
            client = get_aggregated_downloader(enable_sources=self.enable_sources, output_dir=self.output_dir)
        except Exception as e:
            self._emit_log(f"[ERROR] [Worker-{self.worker_id}] 获取下载器失败: {str(e)[:60]}")
            self.fail_count += 1
            return
        
        for attempt in range(1, max_retries + 1):
            try:
                # 执行下载，指定源优先级
                path, logs = client.download(best_match, prefer_order=self.prefer_order)
                
                if path:
                    # 成功下载
                    is_cached = "[OK] 缓存命中" in " ".join(logs or [])
                    success_src = "缓存"
                    
                    if not is_cached:
                        # 从logs中提取源名称
                        for line in reversed(logs or []):
                            if "成功 ->" in line:
                                success_src = line.split(":")[0].strip()
                                break
                    
                    if is_cached:
                        self._emit_log(f"   💾 [Worker-{self.worker_id}] 缓存命中 -> {path}")
                    else:
                        self._emit_log(f"   [OK] [Worker-{self.worker_id}] 下载成功 [{success_src}]")
                        # 写入下载历史
                        try:
                            size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
                            self.cache_manager.save_download_record(
                                std_no=getattr(best_match, "std_no", ""),
                                std_name=getattr(best_match, "name", getattr(best_match, "std_name", "")) or "",
                                source=success_src,
                                file_path=path,
                                file_size=size_bytes
                            )
                        except Exception as e:
                            self._emit_log(f"      ⚠️  记录下载历史失败: {str(e)[:60]}")

                    self.success_count += 1
                    download_success = True
                    return
                else:
                    # 下载返回None，判断错误类型
                    error_msg = " ".join(logs[-3:]) if logs else "未知错误"
                    error_type = self._classify_error(error_msg, logs)
                    
                    if error_type == "network" and attempt < max_retries:
                        # 网络错误 → 重试
                        self._emit_log(f"   ⚠️  [Worker-{self.worker_id}] 第{attempt}次网络错误，{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                        continue
                    elif error_type == "source_unavailable":
                        # 源不可用 → 跳过，标记失败
                        self._emit_log(f"   ❌ [Worker-{self.worker_id}] 源不可用或限制访问，放弃")
                        last_error = error_msg
                        break
                    elif error_type == "not_found":
                        # 无此标准 → 直接失败，不重试
                        # 如果来自GBW且标记为有PDF，执行"延迟验证"
                        self._emit_log(f"   ❌ [Worker-{self.worker_id}] 标准不存在或已删除，放弃")
                        
                        # 尝试回溯并更新GBW缓存（延迟验证）
                        if "GBW" in error_msg or "GBW" in str(logs):
                            self._emit_log(f"   🔄 [Worker-{self.worker_id}] 执行延迟验证：标记GBW中的此项为误判")
                            try:
                                # 直接访问类变量更新缓存（所有实例共享）
                                from sources.gbw import GBWSource
                                # 尝试多种方式获取item_id
                                item_id = None
                                if hasattr(best_match, 'source_meta') and best_match.source_meta:
                                    item_id = best_match.source_meta.get('id')
                                if not item_id:
                                    item_id = getattr(best_match, 'gb_id', None) or getattr(best_match, 'id', None)
                                
                                if item_id:
                                    GBWSource._pdf_check_cache[item_id] = False
                                    self._emit_log(f"      ✓ 缓存已更新: {item_id[:16]}...")
                                else:
                                    self._emit_log(f"      ⚠️  无法获取item_id，跳过缓存更新")
                            except Exception as e:
                                self._emit_log(f"      ⚠️  缓存更新失败: {str(e)[:50]}")
                        
                        last_error = error_msg
                        break
                    elif error_type == "corrupted":
                        # 文件损坏 → 删除后重试
                        if attempt < max_retries:
                            self._emit_log(f"   ⚠️  [Worker-{self.worker_id}] 文件损坏，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            continue
                    else:
                        # 未知错误 → 重试
                        if attempt < max_retries:
                            self._emit_log(f"   ⚠️  [Worker-{self.worker_id}] 第{attempt}次下载失败，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            last_error = error_msg
                            break
                    
            except Exception as e:
                error_type = self._classify_error(str(e), [])
                
                if error_type == "network" and attempt < max_retries:
                    self._emit_log(f"   ⚠️  [Worker-{self.worker_id}] 第{attempt}次异常（网络），{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    continue
                else:
                    self._emit_log(f"   ❌ [Worker-{self.worker_id}] 下载异常: {str(e)[:60]}")
                    last_error = str(e)[:100]
                    break
        
        # 所有尝试都失败
        if not download_success:
            self._emit_log(f"   ❌ [Worker-{self.worker_id}] 下载失败: {last_error or '未知原因'}")
            self.fail_count += 1


class BatchDownloadThread(QtCore.QThread):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(int, int, list)  # success, fail, failed_list
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, std_ids: List[str], output_dir: str = "downloads", enable_sources: List[str] = None, 
                 num_workers: int = 3):
        super().__init__()
        self.std_ids = std_ids
        self.output_dir = output_dir
        self.enable_sources = enable_sources
        self.num_workers = num_workers  # 下载worker线程数
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        """
        改造为方案1+3：流水线优化 + 智能重试策略
        - 搜索和下载并行进行：边搜边下（不等搜索全部完成）
        - 智能重试：区分错误类型，网络错误重试，源不可用跳过
        - 性能提升：15-20% 加速，关键路径优化
        """
        total = len(self.std_ids)
        failed_list = []
        
        # 创建搜索队列和结果队列
        search_queue = queue.Queue()
        result_queue = queue.Queue()
        
        # 创建下载队列
        download_queue = queue.Queue(maxsize=100)
        
        # ─────────────── 启动搜索worker线程 ───────────────
        num_search_workers = 3
        search_workers = []
        for i in range(num_search_workers):
            worker = SearchWorker(
                search_queue=search_queue,
                result_queue=result_queue,
                worker_id=i + 1,
                enable_sources=self.enable_sources,
                log_signal=self.log
            )
            worker.start()
            search_workers.append(worker)
        
        # ─────────────── 启动下载worker线程 ───────────────
        # 设置下载源优先级: BY > GBW > ZBY
        prefer_order = ["BY", "GBW", "ZBY"]
        
        download_workers = []
        for i in range(self.num_workers):
            worker = DownloadWorker(
                download_queue=download_queue,
                worker_id=i + 1,
                output_dir=self.output_dir,
                enable_sources=self.enable_sources,
                log_signal=self.log,
                progress_signal=None,
                prefer_order=prefer_order
            )
            worker.start()
            download_workers.append(worker)
        
        # ─────────────── 流水线：放入搜索任务并实时收集+下载 ───────────────
        self.log.emit("🚀 [方案1+3] 启动流水线：边搜边下，智能重试")
        self.log.emit(f"   🔍 搜索线程数: 3   ⬇️  下载线程数: {self.num_workers}")
        
        search_count = 0
        search_fail = 0
        total_success = 0
        total_fail = 0
        processed = 0
        
        # 使用线程来并行处理：放入搜索任务 + 收集结果 + 入队下载
        import threading
        import time
        
        # 线程1：持续放入搜索任务
        def enqueue_searches():
            for idx, std_id in enumerate(self.std_ids, start=1):
                if self._stop_requested:
                    self.log.emit("🛑 用户取消了批量下载任务")
                    break

                # 清理标准号
                std_id = std_id.strip().replace('\xa0', ' ').replace('\u3000', ' ')
                if not std_id:
                    continue

                self.progress.emit(idx, total, f"[入队] ({idx}/{total}): {std_id}")
                
                try:
                    search_queue.put((std_id, idx), timeout=5)
                except queue.Full:
                    self.log.emit(f"⚠️ 搜索队列已满，等待...")
                    search_queue.put((std_id, idx))
            
            # 通知搜索worker停止
            for _ in range(num_search_workers):
                search_queue.put(None)
        
        # 线程2：实时收集结果并入队下载（流水线优化！）
        def collect_and_enqueue():
            nonlocal search_count, search_fail, total_success, total_fail, processed
            
            remaining = len([s for s in self.std_ids if s.strip()])
            collected = 0
            
            while collected < remaining:
                try:
                    dynamic_timeout = max(60, remaining * 5)
                    std_id, idx, results = result_queue.get(timeout=dynamic_timeout)
                    collected += 1
                    processed = collected
                    
                    # 更新进度：搜索进度从 0-50%
                    progress = int(collected / remaining * 50)
                    self.progress.emit(progress, 100, f"[搜索中] ({collected}/{remaining}): {std_id}")
                    
                    if not results:
                        self.log.emit(f"❌ [{collected}/{remaining}] 未找到: {std_id}")
                        search_fail += 1
                        failed_list.append(f"{std_id} (未找到标准)")
                        result_queue.task_done()
                        continue
                    
                    search_count += 1
                    
                    # 寻找最匹配的项
                    best_match = results[0]
                    clean_id = std_id.replace(" ", "").upper()
                    for r in results:
                        if r.std_no.replace(" ", "").upper() == clean_id:
                            best_match = r
                            break
                    
                    self.log.emit(f"✅ [{collected}/{remaining}] {best_match.std_no}")
                    
                    # 🚀 立即放入下载队列（流水线！边搜边下）
                    try:
                        download_queue.put((std_id, best_match), timeout=5)
                    except queue.Full:
                        self.log.emit(f"   ⚠️ 下载队列已满...")
                        download_queue.put((std_id, best_match))
                    
                    result_queue.task_done()
                        
                except queue.Empty:
                    self.log.emit(f"⚠️ 搜索超时 ({dynamic_timeout}秒)，已收集 {collected}/{remaining}")
                    break
                except Exception as e:
                    self.log.emit(f"❌ 收集结果出错: {str(e)[:80]}")
        
        # 并行运行两个线程
        enqueue_thread = threading.Thread(target=enqueue_searches, daemon=True)
        collect_thread = threading.Thread(target=collect_and_enqueue, daemon=True)
        
        enqueue_thread.start()
        collect_thread.start()
        
        # 等待搜索线程完成
        enqueue_thread.join()
        collect_thread.join()
        
        # ─────────────── 等待下载完成 ───────────────
        self.log.emit(f"──────────────────────────────────────")
        self.log.emit(f"🔍 搜索阶段完成！共找到 {search_count} 个标准")
        self.log.emit(f"⏳ 正在下载 {search_count} 个文件（{self.num_workers} 线程并发）...")
        
        # 通知下载worker停止
        for _ in range(self.num_workers):
            download_queue.put(None)
        
        # 等待所有下载worker完成，并实时更新进度
        start_time = time.time()
        while any(w.is_alive() for w in download_workers):
            current_downloaded = sum(w.success_count + w.fail_count for w in download_workers)
            download_total = search_count
            
            if download_total > 0:
                download_progress = int(50 + (current_downloaded / max(1, download_total) * 50))
                msg = f"[下载中] ({current_downloaded}/{download_total}) - "
                msg += "█" * (current_downloaded % 10) + "░" * (10 - (current_downloaded % 10))
                self.progress.emit(download_progress, 100, msg)
            
            time.sleep(0.5)
        
        # 最后等待所有worker完全结束
        worker_stats = []
        for worker in download_workers:
            worker.join()
            total_success += worker.success_count
            total_fail += worker.fail_count
            worker_stats.append((worker.worker_id, worker.success_count, worker.fail_count))
        
        elapsed = time.time() - start_time
        self.progress.emit(100, 100, f"[完成] 耗时: {elapsed:.1f}秒")
        
        # ─────────────── 汇总结果 ───────────────
        self.log.emit(f"──────────────────────────────────────")
        self.log.emit(f"📊 📊 📊 批量下载完成统计 📊 📊 📊")
        self.log.emit(f"──────────────────────────────────────")
        self.log.emit(f"🔍 搜索阶段: {search_count}/{total} 成功，{search_fail} 失败")
        self.log.emit(f"⬇️  下载阶段: {total_success} 成功，{total_fail} 失败")
        self.log.emit(f"📈 总成功率: {total_success/(max(1, total_success+total_fail))*100:.1f}%")
        self.log.emit(f"⏱️  总耗时: {elapsed:.1f}秒")
        self.log.emit(f"👷 Worker详情:")
        for worker_id, success, fail in worker_stats:
            rate = success / max(1, success + fail) * 100
            self.log.emit(f"   Worker-{worker_id}: ✅ {success} | ❌ {fail} ({rate:.0f}%)")
        
        if failed_list:
            self.log.emit(f"📋 失败的标准:")
            for item in failed_list[:10]:  # 只显示前10个
                self.log.emit(f"   • {item}")
            if len(failed_list) > 10:
                self.log.emit(f"   ... 还有 {len(failed_list) - 10} 个失败")
        
        self.log.emit(f"──────────────────────────────────────")
        self.finished.emit(total_success, total_fail, failed_list)




class DownloadThread(QtCore.QThread):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(int, int)
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, items: List[dict], output_dir: str = "downloads", background_cache: dict = None, parallel: bool = False, max_workers: int = 3, prefer_order: Optional[List[str]] = None):
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self.background_cache = background_cache or {}
        self.parallel = parallel  # 是否并行下载
        self.max_workers = max_workers  # 并行下载的线程数
        self.prefer_order = prefer_order  # 手动指定下载优先级
        self._lock = None  # 线程锁（并行模式使用）
        self._stop_requested = False

    def stop(self):
        """停止下载"""
        self._stop_requested = True

    def _download_single(self, idx: int, it: dict, total: int) -> Tuple[bool, str, Optional[str]]:
        """
        下载单个文件
        
        Returns:
            (success, std_no, error_msg)
        """
        std_no = it.get("std_no")
        
        try:
            # 获取原始对象
            obj = it.get("obj")

            # 使用复用的 AggregatedDownloader 实例以提升性能
            try:
                client = get_aggregated_downloader(enable_sources=None, output_dir=self.output_dir)
            except Exception as e:
                return False, std_no, f"创建下载器失败: {str(e)[:100]}"

            try:
                path, logs = client.download(obj, prefer_order=self.prefer_order)
            except Exception as e:
                tb = traceback.format_exc()
                return False, std_no, f"{str(e)[:100]}"

            if path:
                success_src = "未知"
                try:
                    for line in reversed(logs or []):
                        if "成功 ->" in line:
                            success_src = line.split(":")[0].strip()
                            break
                except Exception:
                    pass
                return True, std_no, f"✅ [{success_src}] -> {path}"
            else:
                return False, std_no, "所有来源均未成功"
                
        except Exception as e:
            return False, std_no, f"异常: {str(e)[:100]}"

    def run(self):
        success = 0
        fail = 0
        total = len(self.items)
        
        if not self.parallel:
            # 串行下载（原逻辑，安全但慢）
            for idx, it in enumerate(self.items, start=1):
                if self._stop_requested:
                    self.log.emit("🛑 用户取消下载")
                    break
                
                std_no = it.get("std_no")
                self.progress.emit(idx, total, f"正在下载: {std_no}")
                self.log.emit(f"📥 [{idx}/{total}] 开始下载: {std_no}")
                
                ok, _, msg = self._download_single(idx, it, total)
                if ok:
                    self.log.emit(f"   {msg}")
                    success += 1
                else:
                    self.log.emit(f"   ❌ 下载失败: {std_no} - {msg}")
                    fail += 1
        else:
            # 并行下载（推荐，性能提升 2-3 倍）
            import concurrent.futures
            import threading
            
            self._lock = threading.Lock()
            completed = 0
            
            def download_task(idx_item):
                """并行下载任务"""
                idx, it = idx_item
                if self._stop_requested:
                    return False, it.get("std_no"), "用户取消"
                
                std_no = it.get("std_no")
                
                # 线程安全地更新进度
                with self._lock:
                    nonlocal completed
                    completed += 1
                    self.progress.emit(completed, total, f"正在下载: {std_no}")
                    self.log.emit(f"📥 [{completed}/{total}] 开始下载: {std_no}")
                
                return self._download_single(idx, it, total)
            
            # 使用线程池并行下载
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(download_task, (i+1, item)) for i, item in enumerate(self.items)]
                
                # 等待所有任务完成
                for future in concurrent.futures.as_completed(futures):
                    try:
                        ok, std_no, msg = future.result()
                        with self._lock:
                            if ok:
                                self.log.emit(f"   {msg}")
                                success += 1
                            else:
                                self.log.emit(f"   ❌ 下载失败: {std_no} - {msg}")
                                fail += 1
                    except Exception as exc:
                        with self._lock:
                            self.log.emit(f"   ❌ 下载任务异常: {exc}")
                            fail += 1

        self.progress.emit(total, total, "下载完成")
        self.finished.emit(success, fail)


class SourceHealthThread(QtCore.QThread):
    """在后台检查数据源连通性并通过信号返回结果"""
    finished = QtCore.Signal(dict)
    error = QtCore.Signal(str)

    def __init__(self, force: bool = False, parent=None):
        super().__init__(parent)
        self.force = force

    def run(self):
        try:
            try:
                client = get_aggregated_downloader(enable_sources=["GBW", "BY", "ZBY"], output_dir=None)
            except Exception:
                import traceback as _tb
                self.error.emit(_tb.format_exc())
                return
            if client is None:
                self.error.emit("AggregatedDownloader 未就绪")
                return
            health_status = client.check_source_health(force=self.force)
            self.finished.emit(health_status)
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())


class StandardTableModel(QtCore.QAbstractTableModel):
    """简单的表格模型，替代 QTableWidget 用于更高效渲染和批量操作"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[dict] = []
        # 调整列顺序：来源放到状态后面，文本前面
        self._headers = ["选中", "序号", "标准号", "名称", "发布日期", "实施日期", "状态", "来源", "文本"]

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._headers)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        r = index.row(); c = index.column()
        item = self._items[r]
        if role == QtCore.Qt.DisplayRole:
            if c == 0:
                return "●" if item.get("_selected") else ""
            if c == 1:
                return str(item.get("_display_idx", r + 1))
            if c == 2:
                return item.get("std_no", "")
            if c == 3:
                return item.get("name", "")
            if c == 4:
                return item.get("publish", "")
            if c == 5:
                return item.get("implement", "")
            if c == 6:
                return item.get("status", "")
            if c == 7:
                # 显示来源（优先使用合并后的 _display_source）
                disp = item.get('_display_source') or (item.get('sources')[0] if item.get('sources') else None)
                return disp or ""
            if c == 8:
                return "✓" if item.get("has_pdf") else "-"
        # 背景色：选中项用蓝色，未选中用白色
        if role == QtCore.Qt.BackgroundRole:
            if c == 0 and item.get("_selected"):
                return QtGui.QBrush(QtGui.QColor("#3498db"))
            else:
                return QtGui.QBrush(QtGui.QColor("#ffffff"))
        
        # 文字色：选中项用白色，未选中用黑色
        if role == QtCore.Qt.ForegroundRole:
            if c == 0 and item.get("_selected"):
                return QtGui.QBrush(QtGui.QColor("#ffffff"))
            else:
                return QtGui.QBrush(QtGui.QColor("#333333"))  # 黑色文字
        
        # 对齐方式
        if role == QtCore.Qt.TextAlignmentRole and c == 0:
            return QtCore.Qt.AlignCenter
        
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        return flags

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return False
        return False
        return False

    def set_items(self, items: List[dict]):
        self.beginResetModel()
        self._items = []
        for i, it in enumerate(items, start=1):
            copy = dict(it)
            copy.setdefault("_selected", False)
            copy.setdefault("_display_idx", i)
            self._items.append(copy)
        self.endResetModel()

    def get_selected_items(self) -> List[dict]:
        return [it for it in self._items if it.get("_selected")]

    def set_all_selected(self, selected: bool):
        for it in self._items:
            it["_selected"] = bool(selected)
        if self._items:
            top = self.index(0, 0)
            bottom = self.index(len(self._items) - 1, 0)
            self.dataChanged.emit(top, bottom, [QtCore.Qt.BackgroundRole, QtCore.Qt.DisplayRole])


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置")
        self.setModal(True)
        self.resize(700, 600)
        self.setStyleSheet(ui_styles.DIALOG_STYLE + ui_styles.SCROLLBAR_STYLE)
        
        self.api_config = get_api_config()

        # 主布局
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 创建滚动区域以容纳所有内容
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        
        # ========== API 模式配置 ==========
        scroll_layout.addWidget(self._create_api_section())
        
        # ========== 数据源配置 ==========
        scroll_layout.addWidget(self._create_sources_section())
        
        # ========== 搜索配置 ==========
        scroll_layout.addWidget(self._create_search_section())
        
        # ========== 性能优化 ==========
        scroll_layout.addWidget(self._create_performance_section())
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # ========== 底部按钮 ==========
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_reset = QtWidgets.QPushButton("🔄 重置默认")
        btn_reset.setMinimumWidth(100)
        btn_reset.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
        btn_reset.setCursor(QtCore.Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.on_reset_defaults)
        
        btn_ok = QtWidgets.QPushButton("✓ 保存")
        btn_ok.setMinimumWidth(100)
        btn_ok.setStyleSheet(ui_styles.BTN_PRIMARY_STYLE)
        btn_ok.setCursor(QtCore.Qt.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)
        
        btn_cancel = QtWidgets.QPushButton("✕ 取消")
        btn_cancel.setMinimumWidth(100)
        btn_cancel.setStyleSheet(ui_styles.BTN_SECONDARY_STYLE)
        btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
    
    def _create_section_header(self, title: str) -> QtWidgets.QWidget:
        """创建段落标题"""
        header = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(0, 10, 0, 5)
        
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px;")
        
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("color: #bdc3c7;")
        
        layout.addWidget(lbl, 0)
        layout.addWidget(line, 1)
        return header
    
    def _create_form_row(self, label: str, widget) -> QtWidgets.QWidget:
        """创建表单行"""
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        lbl = QtWidgets.QLabel(label)
        lbl.setMinimumWidth(120)
        lbl.setStyleSheet("color: #34495e;")
        
        layout.addWidget(lbl, 0)
        layout.addWidget(widget, 1)
        return row
    
    def _create_api_section(self) -> QtWidgets.QGroupBox:
        """API模式配置段"""
        group = QtWidgets.QGroupBox()
        group.setStyleSheet(ui_styles.BUTTON_GROUP_STYLE + """
            QGroupBox { background-color: #f8f9fa; }
            QLabel { color: #333333; }
            QRadioButton { color: #333333; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(12)
        
        layout.addWidget(self._create_section_header("⚙️ API 模式"))
        
        # 模式选择
        mode_layout = QtWidgets.QHBoxLayout()
        self.rb_local = QtWidgets.QRadioButton("📍 本地模式")
        self.rb_remote = QtWidgets.QRadioButton("🌐 远程模式")
        self.rb_local.setChecked(self.api_config.is_local_mode())
        self.rb_remote.setChecked(self.api_config.is_remote_mode())
        self.rb_local.setStyleSheet("color: #34495e;")
        self.rb_remote.setStyleSheet("color: #34495e;")
        self.rb_local.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.rb_local)
        mode_layout.addWidget(self.rb_remote)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # 本地模式设置
        self.local_group = QtWidgets.QWidget()
        local_layout = QtWidgets.QVBoxLayout(self.local_group)
        local_layout.setContentsMargins(10, 0, 0, 0)
        local_layout.setSpacing(8)
        
        self.spin_local_timeout = QtWidgets.QSpinBox()
        self.spin_local_timeout.setValue(self.api_config.local_timeout)
        self.spin_local_timeout.setMinimum(5)
        self.spin_local_timeout.setMaximum(300)
        self.spin_local_timeout.setSuffix(" 秒")
        self.spin_local_timeout.setStyleSheet(self._get_input_style())
        local_layout.addWidget(self._create_form_row("请求超时:", self.spin_local_timeout))
        
        layout.addWidget(self.local_group)
        
        # 远程模式设置
        self.remote_group = QtWidgets.QWidget()
        remote_layout = QtWidgets.QVBoxLayout(self.remote_group)
        remote_layout.setContentsMargins(10, 0, 0, 0)
        remote_layout.setSpacing(8)
        
        self.input_remote_url = QtWidgets.QLineEdit(self.api_config.remote_base_url)
        self.input_remote_url.setPlaceholderText("http://127.0.0.1:8000")
        self.input_remote_url.setStyleSheet(self._get_input_style())
        remote_layout.addWidget(self._create_form_row("API 地址:", self.input_remote_url))
        
        self.spin_remote_timeout = QtWidgets.QSpinBox()
        self.spin_remote_timeout.setValue(self.api_config.remote_timeout)
        self.spin_remote_timeout.setMinimum(10)
        self.spin_remote_timeout.setMaximum(600)
        self.spin_remote_timeout.setSuffix(" 秒")
        self.spin_remote_timeout.setStyleSheet(self._get_input_style())
        remote_layout.addWidget(self._create_form_row("请求超时:", self.spin_remote_timeout))
        
        self.chk_verify_ssl = QtWidgets.QCheckBox("启用 SSL 验证 (HTTPS 推荐)")
        self.chk_verify_ssl.setChecked(self.api_config.verify_ssl)
        self.chk_verify_ssl.setStyleSheet("color: #34495e;")
        remote_layout.addWidget(self.chk_verify_ssl)
        
        layout.addWidget(self.remote_group)
        
        self.on_mode_changed()
        return group
    
    def _create_sources_section(self) -> QtWidgets.QGroupBox:
        """数据源配置段"""
        group = QtWidgets.QGroupBox()
        group.setStyleSheet(ui_styles.BUTTON_GROUP_STYLE + """
            QGroupBox { background-color: #f8f9fa; }
            QLabel { color: #333333; }
            QCheckBox { color: #333333; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(self._create_section_header("📡 启用的数据源"))
        
        self.chk_gbw = QtWidgets.QCheckBox("✓ GBW (国家标准平台)")
        self.chk_by = QtWidgets.QCheckBox("✓ BY (内部系统)")
        self.chk_zby = QtWidgets.QCheckBox("✓ ZBY (标准云)")
        
        self.chk_gbw.setChecked("gbw" in self.api_config.enable_sources)
        self.chk_by.setChecked("by" in self.api_config.enable_sources)
        self.chk_zby.setChecked("zby" in self.api_config.enable_sources)
        
        for chk in [self.chk_gbw, self.chk_by, self.chk_zby]:
            chk.setStyleSheet("color: #34495e;")
            layout.addWidget(chk)
        
        return group
    
    def _create_search_section(self) -> QtWidgets.QGroupBox:
        """搜索配置段"""
        group = QtWidgets.QGroupBox()
        group.setStyleSheet(ui_styles.BUTTON_GROUP_STYLE + """
            QGroupBox { background-color: #f8f9fa; }
            QLabel { color: #333333; }
            QCheckBox { color: #333333; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(self._create_section_header("🔍 搜索配置"))
        
        self.spin_search_limit = QtWidgets.QSpinBox()
        self.spin_search_limit.setValue(self.api_config.search_limit)
        self.spin_search_limit.setMinimum(10)
        self.spin_search_limit.setMaximum(500)
        self.spin_search_limit.setStyleSheet(self._get_input_style())
        layout.addWidget(self._create_form_row("返回结果数:", self.spin_search_limit))
        
        self.spin_max_retries = QtWidgets.QSpinBox()
        self.spin_max_retries.setValue(self.api_config.max_retries)
        self.spin_max_retries.setMinimum(1)
        self.spin_max_retries.setMaximum(10)
        self.spin_max_retries.setStyleSheet(self._get_input_style())
        layout.addWidget(self._create_form_row("最大重试次数:", self.spin_max_retries))
        
        self.spin_retry_delay = QtWidgets.QSpinBox()
        self.spin_retry_delay.setValue(self.api_config.retry_delay)
        self.spin_retry_delay.setMinimum(1)
        self.spin_retry_delay.setMaximum(30)
        self.spin_retry_delay.setSuffix(" 秒")
        self.spin_retry_delay.setStyleSheet(self._get_input_style())
        layout.addWidget(self._create_form_row("重试延迟:", self.spin_retry_delay))
        
        return group
    
    def _create_performance_section(self) -> QtWidgets.QGroupBox:
        """性能优化段"""
        group = QtWidgets.QGroupBox()
        group.setStyleSheet(ui_styles.BUTTON_GROUP_STYLE + """
            QGroupBox { background-color: #f8f9fa; }
            QLabel { color: #333333; }
            QCheckBox { color: #333333; }
        """)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(10)
        
        layout.addWidget(self._create_section_header("⚡ 性能优化"))
        
        self.chk_parallel_search = QtWidgets.QCheckBox("✓ 启用并行搜索 (3-5倍速提升)")
        self.chk_parallel_search.setChecked(self.api_config.parallel_search)
        self.chk_parallel_search.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.chk_parallel_search)
        
        # 下载并行配置
        download_layout = QtWidgets.QHBoxLayout()
        self.chk_parallel_download = QtWidgets.QCheckBox("✓ 启用并行下载")
        self.chk_parallel_download.setChecked(self.api_config.parallel_download)
        self.chk_parallel_download.setStyleSheet("color: #34495e;")
        download_layout.addWidget(self.chk_parallel_download)
        
        download_layout.addSpacing(20)
        
        lbl_workers = QtWidgets.QLabel("下载线程数:")
        lbl_workers.setStyleSheet("color: #34495e;")
        download_layout.addWidget(lbl_workers)
        
        self.spin_download_workers = QtWidgets.QSpinBox()
        self.spin_download_workers.setValue(self.api_config.download_workers)
        self.spin_download_workers.setMinimum(2)
        self.spin_download_workers.setMaximum(5)
        self.spin_download_workers.setStyleSheet(self._get_input_style())
        self.spin_download_workers.setMaximumWidth(80)
        download_layout.addWidget(self.spin_download_workers)
        download_layout.addStretch()
        
        layout.addLayout(download_layout)
        
        self.chk_parallel_download.toggled.connect(self.spin_download_workers.setEnabled)
        
        return group
    
    def _get_input_style(self) -> str:
        """获取输入框样式"""
        return """
            QLineEdit, QSpinBox {
                background-color: white;
                color: #333333;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 2px solid #3498db;
                background-color: white;
            }
        """
    
    def on_mode_changed(self):
        """切换 API 模式时更新 UI"""
        is_local = self.rb_local.isChecked()
        self.local_group.setEnabled(is_local)
        self.remote_group.setEnabled(not is_local)
    
    def on_reset_defaults(self):
        """重置为默认配置"""
        reply = QtWidgets.QMessageBox.question(
            self, "重置确认",
            "确定要重置所有配置为默认值吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            from core.api_config import APIConfig, APIMode
            default = APIConfig()
            
            self.rb_local.setChecked(default.is_local_mode())
            self.rb_remote.setChecked(default.is_remote_mode())
            self.input_local_dir.setText(default.local_output_dir)
            self.spin_local_timeout.setValue(default.local_timeout)
            self.input_remote_url.setText(default.remote_base_url)
            self.spin_remote_timeout.setValue(default.remote_timeout)
            self.chk_verify_ssl.setChecked(default.verify_ssl)
            self.chk_gbw.setChecked("gbw" in default.enable_sources)
            self.chk_by.setChecked("by" in default.enable_sources)
            self.chk_zby.setChecked("zby" in default.enable_sources)
            self.spin_search_limit.setValue(default.search_limit)
            self.spin_max_retries.setValue(default.max_retries)
            self.spin_retry_delay.setValue(default.retry_delay)
            self.chk_parallel_search.setChecked(default.parallel_search)
            self.chk_parallel_download.setChecked(default.parallel_download)
            self.spin_download_workers.setValue(default.download_workers)
            self.on_mode_changed()
            QtWidgets.QMessageBox.information(self, "成功", "已重置为默认配置")

    def get_settings(self):
        """获取用户配置并保存到 API 配置"""
        from core.api_config import APIMode
        
        # 构建数据源列表
        sources = []
        if self.chk_gbw.isChecked():
            sources.append("gbw")
        if self.chk_by.isChecked():
            sources.append("by")
        if self.chk_zby.isChecked():
            sources.append("zby")
        
        # 更新全局 API 配置
        config = get_api_config()
        config.mode = APIMode.LOCAL if self.rb_local.isChecked() else APIMode.REMOTE
        # 下载目录统一由主界面选择，这里不再保存输入框
        if hasattr(self.parent(), "settings"):
            config.local_output_dir = self.parent().settings.get("output_dir", "downloads")
        else:
            config.local_output_dir = self.input_local_dir.text().strip() or "downloads"
        config.local_timeout = self.spin_local_timeout.value()
        config.remote_base_url = self.input_remote_url.text().strip() or "http://127.0.0.1:8000"
        config.remote_timeout = self.spin_remote_timeout.value()
        config.verify_ssl = self.chk_verify_ssl.isChecked()
        config.enable_sources = sources or ["gbw", "by", "zby"]
        config.search_limit = self.spin_search_limit.value()
        config.max_retries = self.spin_max_retries.value()
        config.retry_delay = self.spin_retry_delay.value()
        config.parallel_search = self.chk_parallel_search.isChecked()
        config.parallel_download = self.chk_parallel_download.isChecked()
        config.download_workers = self.spin_download_workers.value()
        
        # 保存到文件
        config.save()
        
        # 返回兼容旧代码的结果
        return {
            "sources": [s.upper() for s in sources] or ["GBW", "BY", "ZBY"],
            "output_dir": config.local_output_dir,
            "page_size": self.spin_search_limit.value(),
        }


class BatchDownloadDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量下载")
        self.resize(500, 400)
        self.setModal(True)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        lbl_hint = QtWidgets.QLabel("请输入标准号（每行一个，或使用逗号、空格分隔）：")
        lbl_hint.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(lbl_hint)
        
        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setPlaceholderText("例如：\nGB/T 3324-2024\nGB/T 3325-2024\nGB/T 10357.1-2013")
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #3498db;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New';
                font-size: 12px;
                background-color: white;
                color: #333333;
            }
            QPlainTextEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        layout.addWidget(self.text_edit)
        
        lbl_note = QtWidgets.QLabel("注：程序将自动搜索每个标准号并下载第一个匹配项。")
        lbl_note.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        layout.addWidget(lbl_note)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_ok = QtWidgets.QPushButton("🚀 开始批量下载")
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #51cf66;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #37b24d; }
            QPushButton:pressed { background-color: #2f8a3d; }
        """)
        self.btn_ok.clicked.connect(self.accept)
        
        self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #eee;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #ddd; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def get_ids(self) -> List[str]:
        text = self.text_edit.toPlainText()
        # 修改正则：不再使用 \s 分割，只使用换行、逗号、分号、顿号分割
        # 这样可以保留 "GB 18584-2024" 这种中间带空格的标准号
        raw_ids = re.split(r'[\n\r,，;；、]+', text)
        # 过滤空字符串并去重
        ids = []
        seen = set()
        for i in raw_ids:
            i = i.strip()
            if i and i not in seen:
                ids.append(i)
                seen.add(i)
        return ids


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("标准下载 - 桌面版 V2.0.0")
        self.resize(1200, 750)
        # 应用全局样式（包含对话框样式与统一的复选框样式）
        try:
            self.setStyleSheet(ui_styles.DIALOG_STYLE + getattr(ui_styles, 'CHECKBOX_STYLE', ''))
        except Exception:
            # 如果样式拼接失败，降级为仅应用对话框样式
            try:
                self.setStyleSheet(ui_styles.DIALOG_STYLE)
            except Exception:
                pass

        # 配置存储（默认值；会被持久化配置覆盖）
        self.settings = {
            "sources": ["GBW", "BY", "ZBY"],
            "output_dir": "downloads",
            "page_size": 30,  # 默认每页30条
        }

        # 缓存与历史管理器（用于搜索/下载历史记录）
        self.cache_manager = get_cache_manager()

        # 持久化配置（Win7 兼容）：使用 QSettings（Windows 下为注册表；无需额外文件权限）
        self._load_persistent_settings()
        
        # 分页状态
        self.current_page = 1
        self.total_pages = 1
        # pending search rows (避免在搜索未完全结束前就更新显示)
        self._pending_search_rows = None

        # Web应用线程
        self.web_thread = None
        self.web_server_running = False
        self.web_server_event = threading.Event()  # 用于线程间信号

        # 创建菜单栏
        menubar = self.menuBar()

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
        self.input_keyword.setStyleSheet(ui_styles.INPUT_STYLE)
        self.input_keyword.returnPressed.connect(self.on_search)
        self.btn_search = QtWidgets.QPushButton("🔍 检索")
        self.btn_search.setMinimumWidth(80)
        self.btn_search.setStyleSheet(ui_styles.BTN_PRIMARY_STYLE)
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
        
        # Web应用按钮 - 改为 Excel 补全
        self.btn_web_app = QtWidgets.QPushButton("📊 标准补全")
        self.btn_web_app.setMaximumWidth(70)
        self.btn_web_app.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.btn_web_app.clicked.connect(self.open_excel_dialog)
        path_op_layout.addWidget(self.btn_web_app)
        
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

        # 下载源选择由右侧复选框控制（移除下拉框）
        
        # 队列管理按钮
        self.btn_queue = QtWidgets.QPushButton("📥 队列")
        self.btn_queue.setMaximumWidth(70)
        self.btn_queue.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.btn_queue.clicked.connect(self.open_queue_dialog)
        path_op_layout.addWidget(self.btn_queue)
        
        # 历史记录按钮
        self.btn_history = QtWidgets.QPushButton("🕒 历史")
        self.btn_history.setMaximumWidth(70)
        self.btn_history.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
            QPushButton:pressed {
                background-color: #117864;
            }
        """)
        self.btn_history.clicked.connect(self.open_history_dialog)
        path_op_layout.addWidget(self.btn_history)
        
        # 设置按钮
        self.btn_settings = QtWidgets.QPushButton("⚙️ 设置")
        self.btn_settings.setMaximumWidth(70)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
            }
        """)
        self.btn_settings.clicked.connect(self.on_settings)
        path_op_layout.addWidget(self.btn_settings)
        
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
        
        # 批量下载按钮
        self.btn_batch_download = QtWidgets.QPushButton("🚀 批量下载")
        self.btn_batch_download.setMaximumWidth(85)
        self.btn_batch_download.setStyleSheet("""
            QPushButton {
                background-color: #00b894;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #00a383;
            }
            QPushButton:pressed {
                background-color: #008f72;
            }
        """)
        self.btn_batch_download.clicked.connect(self.on_batch_download)
        path_op_layout.addWidget(self.btn_batch_download)

        # 创建源复选框（右侧区域显示）
        self.chk_gbw = QtWidgets.QCheckBox("GBW")
        self.chk_gbw.setChecked(True)
        self.chk_gbw.setStyleSheet("color: #333; font-weight: bold;")
        self.chk_by = QtWidgets.QCheckBox("BY")
        self.chk_by.setChecked(True)
        self.chk_by.setStyleSheet("color: #333; font-weight: bold;")
        self.chk_zby = QtWidgets.QCheckBox("ZBY")
        self.chk_zby.setChecked(True)
        self.chk_zby.setStyleSheet("color: #333; font-weight: bold;")

        left_layout.addWidget(path_op_row)
        
        # 初始化时根据连通性设置状态
        self.update_source_checkboxes()

        # 表格操作行：全选、筛选
        table_op_row = QtWidgets.QWidget()
        table_op_layout = QtWidgets.QHBoxLayout(table_op_row)
        table_op_layout.setContentsMargins(0, 4, 0, 4)
        table_op_layout.setSpacing(8)
        
        # 全选按钮
        self.btn_select_all = QtWidgets.QPushButton("☑ 全选")
        self.btn_select_all.setMaximumWidth(80)
        self.btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #6c5ce7;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5b4cdb;
            }
        """)
        self.btn_select_all.clicked.connect(self.on_select_all)
        table_op_layout.addWidget(self.btn_select_all)
        
        # 取消全选按钮
        self.btn_deselect_all = QtWidgets.QPushButton("☐ 取消")
        self.btn_deselect_all.setMaximumWidth(80)
        self.btn_deselect_all.setStyleSheet("""
            QPushButton {
                background-color: #636e72;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #535c5f;
            }
        """)
        self.btn_deselect_all.clicked.connect(self.on_deselect_all)
        table_op_layout.addWidget(self.btn_deselect_all)
        
        # 分隔线
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: #ccc;")
        table_op_layout.addWidget(sep)
        
        # 筛选：仅显示有PDF
        self.chk_filter_pdf = QtWidgets.QCheckBox("仅显示有PDF")
        self.chk_filter_pdf.setStyleSheet("color: #333; font-weight: bold;")
        self.chk_filter_pdf.stateChanged.connect(self.on_filter_changed)
        table_op_layout.addWidget(self.chk_filter_pdf)
        
        # 分隔线
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.VLine)
        sep2.setStyleSheet("color: #ccc;")
        table_op_layout.addWidget(sep2)
        
        # 状态筛选下拉框
        self.combo_status_filter = QtWidgets.QComboBox()
        self.combo_status_filter.addItems(["📋 全部状态", "✅ 现行有效", "📅 即将实施", "❌ 已废止", "📄 其他"])
        self.combo_status_filter.setStyleSheet("""
            QComboBox {
                background-color: #a29bfe;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 10px;
                min-width: 100px;
            }
            QComboBox:hover {
                background-color: #6c5ce7;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid white;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333;
                selection-background-color: #a29bfe;
                selection-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 4px;
            }
        """)
        self.combo_status_filter.currentIndexChanged.connect(self.on_filter_changed)
        table_op_layout.addWidget(self.combo_status_filter)
        
        # 选中数量显示
        self.lbl_selection_count = QtWidgets.QLabel("已选: 0")
        self.lbl_selection_count.setStyleSheet("color: #666; font-size: 10px;")
        table_op_layout.addStretch()
        table_op_layout.addWidget(self.lbl_selection_count)
        
        left_layout.addWidget(table_op_row)

        # 结果表 - 使用 QTableView + StandardTableModel 提升性能与可扩展性
        self.table = QtWidgets.QTableView()
        self.table_model = StandardTableModel(self)
        self.table.setModel(self.table_model)
        self.table.verticalHeader().setVisible(False)
        # 允许编辑触发（确保复选框点击可被处理）
        # 保持表格不可编辑，使用行选择来标记条目
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        
        # 设置列宽模式
        header = self.table.horizontalHeader()
        # 0:选中 - 固定宽度
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(0, 45)
        # 1:序号 - 固定宽度
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(1, 50)
        # 2:标准号 - 内容自适应
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        # 3:名称 - 自动伸缩填充剩余空间
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        # 4:来源 - 内容自适应
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        # 5:发布日期 - 内容自适应
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        # 6:实施日期 - 内容自适应
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        # 7:状态 - 内容自适应
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)
        # 8:文本 - 固定宽度
        header.setSectionResizeMode(8, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(8, 50)

        # 美化：专业配色（深蓝头、浅灰行）
        header = self.table.horizontalHeader()
        # 将 CHECKBOX_STYLE 追加到表头和表格样式，避免局部样式覆盖全局复选框样式
        header.setStyleSheet(ui_styles.TABLE_HEADER_STYLE + getattr(ui_styles, 'CHECKBOX_STYLE', ''))
        self.table.setStyleSheet(ui_styles.TABLE_STYLE + getattr(ui_styles, 'CHECKBOX_STYLE', ''))
        # 启用交替行颜色以增强可读性（交替颜色由 TABLE_STYLE 中的 alternate-background-color 控制）
        try:
            self.table.setAlternatingRowColors(True)
        except Exception:
            pass
        # 监听模型数据变化，更新已选数量
        self.table_model.dataChanged.connect(lambda *args, **kwargs: self.update_selection_count())
        # 当用户选择行时，同步模型的 _selected 标记并刷新指示列
        self.table.selectionModel().selectionChanged.connect(self.on_table_selection_changed)
        # 右键菜单用于下载等操作
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)
        left_layout.addWidget(self.table)
        
        # 分页控件行
        page_row = QtWidgets.QWidget()
        page_layout = QtWidgets.QHBoxLayout(page_row)
        page_layout.setContentsMargins(0, 4, 0, 4)
        page_layout.setSpacing(8)
        
        # 每页数量 - 使用下拉框替代SpinBox
        self.combo_page_size = QtWidgets.QComboBox()
        self.combo_page_size.addItems(["每页 10 条", "每页 20 条", "每页 30 条", "每页 50 条", "每页 100 条"])
        self.combo_page_size.setCurrentIndex(2)  # 默认30条
        self.combo_page_size.setStyleSheet("""
            QComboBox {
                background-color: #74b9ff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 10px;
                min-width: 90px;
            }
            QComboBox:hover {
                background-color: #0984e3;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid white;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333;
                selection-background-color: #74b9ff;
                selection-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 4px;
            }
        """)
        self.combo_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        page_layout.addWidget(self.combo_page_size)
        
        page_layout.addStretch()
        
        # 分页信息
        self.lbl_page_info = QtWidgets.QLabel("共 0 条")
        self.lbl_page_info.setStyleSheet("color: #666;")
        page_layout.addWidget(self.lbl_page_info)
        
        # 上一页
        self.btn_prev_page = QtWidgets.QPushButton("◀ 上一页")
        self.btn_prev_page.setMaximumWidth(80)
        self.btn_prev_page.setEnabled(False)
        self.btn_prev_page.setStyleSheet("""
            QPushButton {
                background-color: #74b9ff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #0984e3;
            }
            QPushButton:disabled {
                background-color: #ddd;
                color: #999;
            }
        """)
        self.btn_prev_page.clicked.connect(self.on_prev_page)
        page_layout.addWidget(self.btn_prev_page)
        
        # 当前页/总页
        self.lbl_page_num = QtWidgets.QLabel("1 / 1")
        self.lbl_page_num.setStyleSheet("color: #333; font-weight: bold; min-width: 60px;")
        self.lbl_page_num.setAlignment(QtCore.Qt.AlignCenter)
        page_layout.addWidget(self.lbl_page_num)
        
        # 下一页
        self.btn_next_page = QtWidgets.QPushButton("下一页 ▶")
        self.btn_next_page.setMaximumWidth(80)
        self.btn_next_page.setEnabled(False)
        self.btn_next_page.setStyleSheet("""
            QPushButton {
                background-color: #74b9ff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #0984e3;
            }
            QPushButton:disabled {
                background-color: #ddd;
                color: #999;
            }
        """)
        self.btn_next_page.clicked.connect(self.on_next_page)
        page_layout.addWidget(self.btn_next_page)
        
        left_layout.addWidget(page_row)

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
        self.lbl_source_status.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.lbl_source_status.setMinimumWidth(140)
        source_title_layout.addWidget(lbl_sources)
        source_title_layout.addWidget(self.lbl_source_status, 1)
        
        # 重新检测按钮
        self.btn_recheck_sources = QtWidgets.QPushButton("🔄 重新检测")
        self.btn_recheck_sources.setMaximumWidth(100)
        self.btn_recheck_sources.setStyleSheet("""
            QPushButton {
                background-color: #00b894;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #00a383;
            }
        """)
        self.btn_recheck_sources.clicked.connect(self.on_recheck_sources)
        source_title_layout.addWidget(self.btn_recheck_sources)
        source_title_layout.addStretch()
        source_hdr_layout.addLayout(source_title_layout)
        
        # 源选择复选框行（放在右侧顶部，紧贴连通性）
        source_checkbox_layout = QtWidgets.QHBoxLayout()
        source_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        source_checkbox_layout.setSpacing(10)
        lbl_select = QtWidgets.QLabel("源选择:")
        lbl_select.setStyleSheet("color: #333; font-weight: bold;")
        source_checkbox_layout.addWidget(lbl_select)
        source_checkbox_layout.addWidget(self.chk_gbw)
        source_checkbox_layout.addWidget(self.chk_by)
        source_checkbox_layout.addWidget(self.chk_zby)
        source_checkbox_layout.addStretch()
        source_hdr_layout.addLayout(source_checkbox_layout)

        # 简化样式，保持紧凑
        source_header.setStyleSheet("")
        source_header.setMinimumHeight(70)
        
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

        # 右侧设置最小宽度，避免分隔条初始挤压导致控件不可见
        right.setMinimumWidth(260)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 360])  # 默认给右侧留出空间，保证复选框可见

        # 状态栏和进度条
        self.status = self.statusBar()
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 8px;
                background-color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 7px;
            }
        """)
        self.progress_bar.hide()
        self.status.addPermanentWidget(self.progress_bar)
        
        # 停止按钮
        self.btn_stop_batch = QtWidgets.QPushButton("停止")
        self.btn_stop_batch.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #fa5252; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.btn_stop_batch.hide()
        self.btn_stop_batch.clicked.connect(self.on_stop_batch)
        self.status.addPermanentWidget(self.btn_stop_batch)
        
        # 后台状态标签
        self.lbl_bg_status = QtWidgets.QLabel("")
        self.lbl_bg_status.setStyleSheet("color: #666; font-size: 11px;")
        self.status.addPermanentWidget(self.lbl_bg_status)

        # 存储
        self.current_items: List[dict] = []
        self.all_items: List[dict] = []  # 完整列表，用于筛选
        self.filtered_items: List[dict] = []  # 筛选后的列表
        self.background_cache: dict = {}  # 后台搜索缓存 {std_no_normalized: Standard}
        self.last_keyword: str = ""  # 上次搜索关键词

        # 线程占位
        self.search_thread: Optional[SearchThread] = None
        self.download_thread: Optional[DownloadThread] = None
        self.bg_search_thread: Optional[BackgroundSearchThread] = None
        
        # 初始化显示
        self.update_path_display()
        self.update_source_checkboxes()
        self.check_source_health()

    def _qsettings(self) -> "QtCore.QSettings":
        # 固定组织/应用名，避免因脚本路径变化导致配置丢失
        return QtCore.QSettings("StandardDownloader", "StandardDownloader")

    def _load_persistent_settings(self):
        try:
            qs = self._qsettings()
            output_dir = qs.value("output_dir", self.settings.get("output_dir", "downloads"))
            if isinstance(output_dir, str) and output_dir.strip():
                self.settings["output_dir"] = output_dir.strip()

            page_size = qs.value("page_size", self.settings.get("page_size", 30), type=int)
            try:
                page_size = int(page_size)
            except Exception:
                page_size = self.settings.get("page_size", 30)
            if page_size > 0:
                self.settings["page_size"] = page_size

            sources_val = qs.value("sources", self.settings.get("sources", ["GBW", "BY", "ZBY"]))
            sources: List[str]
            if isinstance(sources_val, str):
                # 兼容被存成 "GBW,BY,ZBY" 的情况
                sources = [s for s in (x.strip() for x in sources_val.split(',')) if s]
            elif isinstance(sources_val, (list, tuple)):
                sources = [str(x) for x in sources_val if str(x)]
            else:
                sources = list(self.settings.get("sources", ["GBW", "BY", "ZBY"]))

            # 过滤无效源
            allowed = {"GBW", "BY", "ZBY"}
            sources = [s for s in sources if s in allowed]
            if sources:
                self.settings["sources"] = sources
        except Exception:
            # 读取失败则使用默认值
            return

    def _save_persistent_settings(self):
        try:
            qs = self._qsettings()
            qs.setValue("output_dir", self.settings.get("output_dir", "downloads"))
            qs.setValue("page_size", int(self.settings.get("page_size", 30)))
            qs.setValue("sources", self.settings.get("sources", ["GBW", "BY", "ZBY"]))
            qs.sync()
        except Exception:
            return

    def closeEvent(self, event):
        # 退出前尽量停止后台线程，避免 QThread 仍在运行时被析构导致崩溃/报错
        try:
            threads = []
            # 先收集显式字段引用的线程
            for attr in ("_source_health_thread", "search_thread", "download_thread", "bg_search_thread"):
                th = getattr(self, attr, None)
                if isinstance(th, QtCore.QThread):
                    threads.append(th)

            # 再收集所有子 QThread（避免覆盖引用导致漏停）
            try:
                for th in self.findChildren(QtCore.QThread):
                    threads.append(th)
            except Exception:
                pass

            # 去重
            uniq = []
            seen = set()
            for th in threads:
                try:
                    key = int(th.__hash__())
                except Exception:
                    key = id(th)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(th)

            for th in uniq:
                try:
                    if not isinstance(th, QtCore.QThread):
                        continue
                    if not th.isRunning():
                        continue
                    try:
                        th.requestInterruption()
                    except Exception:
                        pass
                    # 只有以事件循环为主的线程 quit() 才有效；仍然调用以覆盖该类线程
                    try:
                        th.quit()
                    except Exception:
                        pass
                    try:
                        th.wait(1500)
                    except Exception:
                        pass
                    # 某些线程的 run() 可能在阻塞网络 I/O，quit() 无效；为避免关闭时崩溃，必要时强制终止
                    try:
                        if th.isRunning():
                            th.terminate()
                            th.wait(1000)
                    except Exception:
                        pass
                except Exception:
                    continue
        except Exception:
            pass

        # 退出前持久化配置
        try:
            self._save_persistent_settings()
        except Exception:
            pass
        return super().closeEvent(event)

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
        if not text:
            return
        
        # 涉及保密，脱敏处理：隐藏所有网址
        text = re.sub(r'https?://[^\s<>"]+', '[URL]', text)
        
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
        # SettingsDialog 会自动从 api_config 加载配置，无需手动设置
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.settings = dialog.get_settings()
            self.append_log(f"设置已更新：{self.settings}")
            self.update_path_display()
            self.check_source_health()
            self._save_persistent_settings()

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
            tb = traceback.format_exc()
            self.append_log(tb)
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
            tb = traceback.format_exc()
            self.append_log(tb)
            QtWidgets.QMessageBox.warning(self, "提示", f"无法打开文件夹: {e}")

    def open_excel_dialog(self):
        """打开 Excel 补全对话框"""
        from app.excel_dialog import ExcelDialog
        
        dialog = ExcelDialog(self)
        # 兼容 PySide2 和 PySide6
        if hasattr(dialog, 'exec'):
            dialog.exec()
        else:
            dialog.exec_()
    
    def open_queue_dialog(self):
        """打开下载队列管理对话框"""
        try:
            from app.queue_dialog import QueueDialog
            
            dialog = QueueDialog(self)
            # 兼容 PySide2 和 PySide6
            if hasattr(dialog, 'exec'):
                dialog.exec()
            else:
                dialog.exec_()
        except Exception as e:
            import traceback
            self.append_log(f"❌ 打开队列管理失败: {e}")
            self.append_log(traceback.format_exc())
            QtWidgets.QMessageBox.warning(self, "错误", f"无法打开队列管理:\n{e}")
    
    def open_history_dialog(self):
        """打开历史记录对话框"""
        try:
            from app.history_dialog import HistoryDialog
            
            dialog = HistoryDialog(self)
            # 兼容 PySide2 和 PySide6
            if hasattr(dialog, 'exec'):
                dialog.exec()
            else:
                dialog.exec_()
        except Exception as e:
            import traceback
            self.append_log(f"❌ 打开历史记录失败: {e}")
            self.append_log(traceback.format_exc())
            QtWidgets.QMessageBox.warning(self, "错误", f"无法打开历史记录:\n{e}")

    def _run_web_server(self):
        """在后台线程中运行Flask web服务器"""
        try:
            from web_app.web_app import app
            self.append_log("🚀 Web服务器启动...")
            # 禁用Flask日志输出到控制台，避免干扰
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            self.web_server_running = True
            self.web_server_event.set()  # 信号：服务器已启动
            self.append_log("✓ Web服务器已启动在 http://127.0.0.1:5000")
            
            app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
        except Exception as e:
            self.append_log(f"❌ Web服务器启动失败: {e}")
            self.web_server_running = False
            if not self.web_server_event.is_set():
                self.web_server_event.set()  # 即使失败也要设置事件，避免主线程一直等待

    def update_path_display(self):
        """更新路径显示"""
        output_dir = self.settings.get("output_dir", "downloads")
        self.lbl_download_path.setText(output_dir)

    def update_source_checkboxes(self):
        """根据源的连通性更新复选框状态（在后台线程中执行）"""
        try:
            # 启动后台线程检查连通性，结果通过 `_on_source_health_result` 回调
            th = SourceHealthThread(force=False, parent=self)
            self._source_health_thread = th
            th.finished.connect(self._on_source_health_result)
            th.error.connect(lambda tb: self.append_log(f"更新源复选框失败: {tb.splitlines()[-1] if tb else '错误'}"))
            th.start()
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
            self._save_persistent_settings()

    def check_source_health(self):
        """检查源连通性"""
        # 使用后台线程执行检查（结果更新交由回调处理）
        try:
            th = SourceHealthThread(force=False, parent=self)
            self._source_health_thread = th
            th.finished.connect(self._on_check_source_health_result)
            th.error.connect(lambda tb: (self.lbl_source_status.setText("检测失败"), self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;"), self.append_log(tb.splitlines()[-1] if tb else "source health error")))
            th.start()
        except Exception as e:
            self.lbl_source_status.setText(f"检测失败: {str(e)[:20]}")
            self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")

    def on_search(self):
        keyword = self.input_keyword.text().strip()
        if not keyword:
            QtWidgets.QMessageBox.warning(self, "提示", "请输入关键词")
            return
        self.btn_search.setEnabled(False)
        self.last_keyword = keyword
        self.background_cache = {}  # 清空后台缓存
        
        # 清空之前的搜索结果
        self.all_items = []
        self.current_items = []
        self.filtered_items = []
        self.table_model.set_items([])
        
        # 显示进度条
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status.showMessage("正在搜索...")
        
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
            self.progress_bar.hide()
            return
        
        # 更新设置中的源列表
        self.settings["sources"] = sources
        
        # 使用UI上的每页数量设置
        page_size = self.get_page_size()
        self.search_thread = SearchThread(
            keyword=keyword, 
            sources=sources, 
            page=1, 
            page_size=page_size,
            output_dir=self.settings.get("output_dir", "downloads")
        )
        # 连接渐进式结果信号（新）
        self.search_thread.partial_results.connect(self.on_partial_search_results)
        self.search_thread.all_completed.connect(self.on_all_search_completed)
        self.search_thread.log.connect(self.append_log)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.error.connect(lambda tb: self.append_log(f"错误详情:\n{tb}"))
        self.search_thread.start()
    
    def on_search_progress(self, current: int, total: int, message: str):
        """更新搜索进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status.showMessage(message)
    
    def on_partial_search_results(self, source_name: str, rows: List[dict]):
        """处理单个源的搜索结果（渐进式显示）"""
        if not rows:
            return

        # 添加源标记
        for row in rows:
            row['_display_source'] = source_name

        # 合并到现有结果（去重）
        existing_keys = set()
        for item in self.all_items:
            std_no = item.get("std_no", "")
            key = _STD_NO_RE.sub("", std_no).lower()
            existing_keys.add(key)

        new_items = []
        updated_items = []

        for row in rows:
            std_no = row.get("std_no", "")
            key = _STD_NO_RE.sub("", std_no).lower()

            if key in existing_keys:
                # 已存在，更新信息（如果新源更优）
                for item in self.all_items:
                    item_key = _STD_NO_RE.sub("", item.get("std_no", "")).lower()
                    if item_key == key:
                        # 合并源信息
                        old_obj = item.get("obj")
                        new_obj = row.get("obj")
                        if old_obj and new_obj:
                            # 合并sources
                            all_sources = set(old_obj.sources + new_obj.sources)
                            old_obj.sources = list(all_sources)
                            new_obj.sources = list(all_sources)

                            # 统一 has_pdf：任意源有文本/附件即为 True
                            has_pdf_any = bool(old_obj.has_pdf or new_obj.has_pdf)
                            item["has_pdf"] = has_pdf_any
                            old_obj.has_pdf = has_pdf_any
                            new_obj.has_pdf = has_pdf_any

                            # 选择最优显示源：先看有无 PDF，其次 BY>GBW>ZBY
                            def score_source(src, obj):
                                score = 0
                                if obj.has_pdf:
                                    score += 100
                                if src == "BY":
                                    score += 3
                                elif src == "GBW":
                                    score += 2
                                elif src == "ZBY":
                                    score += 1
                                return score

                            current_src = item.get("_display_source", "") or (old_obj.sources[0] if old_obj.sources else "")
                            best = (current_src, old_obj)

                            for cand_src, cand_obj in [(source_name, new_obj)]:
                                if score_source(cand_src, cand_obj) > score_source(best[0], best[1]):
                                    best = (cand_src, cand_obj)

                            item["_display_source"] = best[0]

                        updated_items.append(item)
                        break
            else:
                # 新增
                new_items.append(row)
                existing_keys.add(key)

        # 添加新项目
        if new_items:
            self.all_items.extend(new_items)
            self.append_log(f"   📍 {source_name} 新增 {len(new_items)} 条独有结果")

        # 重新排序和显示
        def status_sort_key(item):
            status = item.get("status", "")
            if "现行" in status:
                return 0
            elif "即将实施" in status:
                return 1
            elif "废止" in status:
                return 3
            else:
                return 2

        self.all_items.sort(key=status_sort_key)
        self.current_page = 1
        self.apply_filter()

        self.status.showMessage(f"{source_name} 完成，当前共 {len(self.all_items)} 条结果", 2000)

    def on_all_search_completed(self):
        """所有源搜索完成"""
        self.btn_search.setEnabled(True)
        self.progress_bar.hide()
        self.status.showMessage(f"搜索完成，共找到 {len(self.all_items)} 条结果", 5000)
        self.append_log(f"✅ 所有数据源搜索完成，共 {len(self.all_items)} 条结果")

        # 缓存搜索结果并记录历史
        try:
            serialized = self._serialize_search_results_for_cache()
            self.cache_manager.save_search_cache(
                keyword=self.last_keyword,
                sources=self.settings.get("sources", []),
                page=1,
                results=serialized
            )
        except Exception as e:
            self.append_log(f"⚠️  缓存搜索结果失败: {str(e)[:80]}")
            try:
                self.cache_manager.db.add_search_history(
                    keyword=self.last_keyword,
                    sources=self.settings.get("sources", []),
                    result_count=len(self.all_items)
                )
            except Exception:
                pass

    
    def on_search_finished(self):
        """搜索线程结束（兼容旧版，已被 on_all_search_completed 替代）"""
        # 保留此方法以防万一，但主要逻辑已移到 on_all_search_completed
        pass

    def _serialize_search_results_for_cache(self) -> List[dict]:
        """将当前搜索结果转换为可缓存的纯数据结构"""
        serialized = []
        for item in self.all_items or []:
            obj = item.get("obj")
            sources = []
            try:
                if obj and getattr(obj, "sources", None):
                    sources = list(obj.sources)
            except Exception:
                sources = []

            if not sources:
                if isinstance(item.get("sources"), list):
                    sources = item.get("sources")
                elif isinstance(item.get("sources"), str):
                    sources = [item.get("sources")]

            serialized.append({
                "std_no": item.get("std_no", ""),
                "name": item.get("name", ""),
                "publish": item.get("publish", ""),
                "implement": item.get("implement", ""),
                "status": item.get("status", ""),
                "has_pdf": bool(item.get("has_pdf")),
                "sources": sources,
                "_display_source": item.get("_display_source", ""),
            })
        return serialized

    def on_bg_search_finished_legacy(self, cache: dict):
        """后台搜索完成（已废弃，保留以防兼容性问题）"""
        # 新版渐进式搜索已经在 on_partial_search_results 中实时合并数据
        # 此方法保留但不再使用
        pass

    def on_search_results(self, rows: List[dict]):
        # 按状态排序：现行有效 > 即将实施 > 其他
        def status_sort_key(item):
            status = item.get("status", "")
            if "现行" in status:
                return 0
            elif "即将实施" in status:
                return 1
            elif "废止" in status:
                return 3
            else:
                return 2
        
        rows.sort(key=status_sort_key)

        # 存为 pending，等待线程 finished 信号再更新界面，避免在搜索过程中部分/空结果被误显示
        self._pending_search_rows = rows
        self.status.showMessage(f"已接收 {len(rows)} 条结果，等待搜索完成...", 2000)

    def _on_source_health_result(self, health_status: dict):
        """用于 `update_source_checkboxes` 的回调，更新复选框状态"""
        try:
            for src_name, checkbox in [("GBW", self.chk_gbw), ("BY", self.chk_by), ("ZBY", self.chk_zby)]:
                health = health_status.get(src_name)
                # 默认保持可选，让用户可以手动勾选
                checkbox.setEnabled(True)
                if health is None:
                    # 无检测结果则不强制变更勾选状态
                    continue
                is_available = getattr(health, 'available', False)
                checkbox.setChecked(bool(is_available))
        except Exception as e:
            tb = traceback.format_exc()
            self.append_log(tb)

    def _on_check_source_health_result(self, health_status: dict):
        """用于 `check_source_health` 的回调，更新状态标签"""
        try:
            status_parts = []
            sources_enabled = self.settings.get("sources", ["GBW", "BY", "ZBY"])
            for src in ["GBW", "BY", "ZBY"]:
                health = health_status.get(src)
                if health:
                    is_available = getattr(health, 'available', False)
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
            tb = traceback.format_exc()
            self.append_log(tb)
            self.lbl_source_status.setText(f"检测失败: {str(e)[:20]}")
            self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")
    
    def apply_filter(self):
        """根据筛选条件显示数据"""
        items = self.all_items.copy()

        # PDF筛选
        if self.chk_filter_pdf.isChecked():
            items = [r for r in items if r.get("has_pdf")]

        # 状态筛选
        status_filter = self.combo_status_filter.currentText()
        if "全部" not in status_filter:
            if "现行有效" in status_filter:
                items = [r for r in items if "现行" in r.get("status", "")]
            elif "即将实施" in status_filter:
                items = [r for r in items if "即将实施" in r.get("status", "")]
            elif "已废止" in status_filter:
                items = [r for r in items if "废止" in r.get("status", "")]
            elif "其他" in status_filter:
                items = [r for r in items if not any(s in r.get("status", "") for s in ["现行", "即将实施", "废止"])]

        self.filtered_items = items

        # 计算分页
        page_size = self.get_page_size()
        total_count = len(items)
        self.total_pages = max(1, (total_count + page_size - 1) // page_size)

        # 确保当前页有效
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        if self.current_page < 1:
            self.current_page = 1

        # 获取当前页数据并交给模型展示
        start_idx = (self.current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        self.current_items = page_items

        # 将 page_items 传入模型（模型会触发刷新）
        if hasattr(self, 'table_model') and self.table_model:
            self.table_model.set_items(page_items)
        else:
            # 兼容回退到 QTableWidget（极少用）
            try:
                self.table.setRowCount(0)
                for idx, r in enumerate(page_items, start=start_idx + 1):
                    row = self.table.rowCount()
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
            except Exception:
                pass

        self.update_page_controls(total_count)
        self.update_selection_count()
    
    def update_page_controls(self, total_count: int):
        """更新分页控件状态"""
        self.lbl_page_info.setText(f"共 {total_count} 条")
        self.lbl_page_num.setText(f"{self.current_page} / {self.total_pages}")
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < self.total_pages)
    
    def on_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.apply_filter()
    
    def on_next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.apply_filter()
    
    def on_page_size_changed(self, index: int):
        """每页数量改变"""
        page_size = self.get_page_size()
        self.settings["page_size"] = page_size
        self.current_page = 1
        if hasattr(self, 'all_items') and self.all_items:
            self.apply_filter()
    
    def get_page_size(self) -> int:
        """从下拉框获取每页数量"""
        page_size_map = {0: 10, 1: 20, 2: 30, 3: 50, 4: 100}
        return page_size_map.get(self.combo_page_size.currentIndex(), 30)
    
    def on_filter_changed(self):
        """筛选条件改变时重新显示"""
        self.current_page = 1  # 重置到第一页
        if hasattr(self, 'all_items'):
            self.apply_filter()
    
    def on_select_all(self):
        """全选所有行"""
        if hasattr(self, 'table_model') and self.table_model:
            self.table_model.set_all_selected(True)
        else:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(QtCore.Qt.Checked)
        self.update_selection_count()
    
    def on_deselect_all(self):
        """取消全选"""
        if hasattr(self, 'table_model') and self.table_model:
            self.table_model.set_all_selected(False)
        else:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(QtCore.Qt.Unchecked)
        self.update_selection_count()

    def on_table_selection_changed(self, selected, deselected):
        """同步选择模型到项的 _selected 标记并刷新指示列"""
        try:
            sel_rows = {idx.row() for idx in self.table.selectionModel().selectedRows()}
            for i, it in enumerate(self.table_model._items):
                prev = bool(it.get("_selected"))
                now = i in sel_rows
                if prev != now:
                    it["_selected"] = now
                    idx = self.table_model.index(i, 0)
                    self.table_model.dataChanged.emit(idx, idx, [QtCore.Qt.BackgroundRole, QtCore.Qt.DisplayRole, QtCore.Qt.ForegroundRole])
        except Exception:
            pass
        self.update_selection_count()

    def on_table_context_menu(self, pos):
        """表格右键菜单：下载所选"""
        menu = QtWidgets.QMenu(self)
        act_download = menu.addAction("下载所选")
        act = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if act == act_download:
            self.on_download()
    
    def update_selection_count(self):
        """更新已选数量显示"""
        count = 0
        try:
            if hasattr(self, 'table_model') and self.table_model:
                count = len(self.table_model.get_selected_items())
            else:
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item and item.checkState() == QtCore.Qt.Checked:
                        count += 1
        except Exception:
            count = 0
        self.lbl_selection_count.setText(f"已选: {count}")
    
    def on_table_item_changed(self, item):
        """表格项变化时更新选中数量（仅监听第0列复选框）"""
        if item.column() == 0:
            self.update_selection_count()
    
    def on_recheck_sources(self):
        """重新检测数据源连通性"""
        self.append_log("正在重新检测数据源...")
        self.lbl_source_status.setText("检测中...")
        self.lbl_source_status.setStyleSheet("color: #ff9800; font-weight: bold;")
        self.btn_recheck_sources.setEnabled(False)
        
        # 使用 QTimer 延迟执行，避免界面卡顿
        QtCore.QTimer.singleShot(100, self._do_recheck_sources)
    
    def _do_recheck_sources(self):
        """执行源检测"""
        try:
            th = SourceHealthThread(force=True, parent=self)
            self._source_health_thread = th
            def _on_finished(status):
                for src_name, checkbox in [("GBW", self.chk_gbw), ("BY", self.chk_by), ("ZBY", self.chk_zby)]:
                    health = status.get(src_name)
                    if health and health.available:
                        checkbox.setChecked(True)
                        checkbox.setEnabled(True)
                        self.append_log(f"✅ {src_name} 源可用")
                    else:
                        checkbox.setChecked(False)
                        checkbox.setEnabled(False)
                        self.append_log(f"❌ {src_name} 源不可用")

                # 更新状态显示
                self._on_check_source_health_result(status)
                self.append_log("数据源检测完成")
                self.btn_recheck_sources.setEnabled(True)

            th.finished.connect(_on_finished)
            th.error.connect(lambda tb: (self.append_log(tb), self.lbl_source_status.setText("检测失败"), self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;"), setattr(self, 'btn_recheck_sources', self.btn_recheck_sources)))
            th.start()
        except Exception as e:
            self.append_log(f"检测失败: {str(e)}")
            self.lbl_source_status.setText("检测失败")
            self.lbl_source_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.btn_recheck_sources.setEnabled(True)

    def on_download(self):
        selected = []
        if hasattr(self, 'table_model') and self.table_model:
            selected = self.table_model.get_selected_items()
        else:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.checkState() == QtCore.Qt.Checked:
                    selected.append(self.current_items[row])

        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择要下载的行")
            return

        self.append_log(f"📥 准备下载 {len(selected)} 条")
        if self.background_cache:
            self.append_log(f"   ↳ 后台缓存可用: {len(self.background_cache)} 条补充数据")
        
        self.btn_download.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(selected))
        self.progress_bar.show()
        
        # 从配置获取并行下载设置
        config = get_api_config()
        output_dir = self.settings.get("output_dir", "downloads")

        # 下载源选择：由日志上方复选框决定，按 BY > GBW > ZBY 顺序
        prefer_order = []
        by_checked = getattr(self, 'chk_by', None)
        gbw_checked = getattr(self, 'chk_gbw', None)
        zby_checked = getattr(self, 'chk_zby', None)
        if by_checked and by_checked.isChecked():
            prefer_order.append("BY")
        if gbw_checked and gbw_checked.isChecked():
            prefer_order.append("GBW")
        if zby_checked and zby_checked.isChecked():
            prefer_order.append("ZBY")
        if not prefer_order:
            QtWidgets.QMessageBox.information(self, "提示", "请在日志上方勾选至少一个下载源")
            self.btn_download.setEnabled(True)
            self.progress_bar.hide()
            return
        
        self.download_thread = DownloadThread(
            selected, 
            output_dir=output_dir,
            background_cache=self.background_cache,
            parallel=config.parallel_download,
            max_workers=config.download_workers,
            prefer_order=prefer_order
        )
        self.download_thread.log.connect(self.append_log)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
    
    def on_download_progress(self, current: int, total: int, message: str):
        """更新下载进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status.showMessage(message)

    def on_download_finished(self, success: int, fail: int):
        self.append_log(f"📊 下载结果：{success} 成功，{fail} 失败")
        self.btn_download.setEnabled(True)
        self.progress_bar.hide()
        self.status.showMessage(f"下载完成: {success} 成功, {fail} 失败", 5000)

    def on_batch_download(self):
        """打开批量下载对话框"""
        dialog = BatchDownloadDialog(self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            ids = dialog.get_ids()
            if not ids:
                QtWidgets.QMessageBox.information(self, "提示", "请输入至少一个标准号")
                return
            
            self.append_log(f"🚀 开始批量下载任务，共 {len(ids)} 个标准号")
            self.btn_batch_download.setEnabled(False)
            
            # 显示进度条和停止按钮
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(len(ids))
            self.progress_bar.show()
            self.btn_stop_batch.setEnabled(True)
            self.btn_stop_batch.setText("停止")
            self.btn_stop_batch.show()
            
            output_dir = self.settings.get("output_dir", "downloads")
            enable_sources = self.settings.get("sources", ["GBW", "BY", "ZBY"])
            
            # 支持配置worker数量（默认3个）
            num_workers = self.settings.get("download_workers", 3)
            
            self.batch_thread = BatchDownloadThread(
                ids, 
                output_dir=output_dir,
                enable_sources=enable_sources,
                num_workers=num_workers
            )
            self.batch_thread.log.connect(self.append_log)
            self.batch_thread.progress.connect(self.on_download_progress)
            self.batch_thread.finished.connect(self.on_batch_download_finished)
            self.batch_thread.start()

    def on_stop_batch(self):
        """停止批量下载"""
        if hasattr(self, 'batch_thread') and self.batch_thread.isRunning():
            self.batch_thread.stop()
            self.btn_stop_batch.setEnabled(False)
            self.btn_stop_batch.setText("正在停止...")
            self.append_log("⏳ 正在请求停止批量下载任务...")

    def on_batch_download_finished(self, success: int, fail: int, failed_list: list):
        self.append_log(f"📊 批量下载任务结束")
        self.append_log(f"   ✅ 成功: {success}")
        self.append_log(f"   ❌ 失败: {fail}")
        
        if failed_list:
            self.append_log(f"📋 失败清单:")
            for item in failed_list:
                self.append_log(f"   - {item}")
        
        self.btn_batch_download.setEnabled(True)
        self.progress_bar.hide()
        self.btn_stop_batch.hide()
        self.status.showMessage(f"批量下载完成: {success} 成功, {fail} 失败", 5000)
        
        msg = f"批量下载任务已结束。\n\n成功: {success}\n失败: {fail}"
        if failed_list:
            msg += "\n\n失败清单:\n" + "\n".join(failed_list[:15])
            if len(failed_list) > 15:
                msg += f"\n... 等共 {len(failed_list)} 项"

        info_box = QtWidgets.QMessageBox(self)
        info_box.setWindowTitle("任务完成")
        info_box.setText(msg)
        info_box.setIcon(QtWidgets.QMessageBox.Information)
        info_box.setStyleSheet("""
            QMessageBox { background-color: #f5f5f5; }
            QLabel { color: #333333; font-size: 12px; }
            QPushButton { background-color: #eeeeee; color: #333333; border: 1px solid #dddddd; border-radius: 4px; padding: 6px 14px; }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        info_box.exec()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # 密码验证（必须在 QApplication 创建后执行）
    if not check_password():
        return 0
    
    # 提前预热 OCR 模型和下载器，避免第一次下载时卡顿
    def prewarm_all():
        try:
            from sources.gbw_download import prewarm_ocr
            prewarm_ocr()
        except Exception:
            pass
        try:
            # 预热全量下载器，建立连接池
            client = get_aggregated_downloader(enable_sources=None)
            if client:
                # 尝试对主要域名进行一次 HEAD 请求以预热 TCP/SSL 连接
                for src in client.sources:
                    if src.name == "GBW":
                        try:
                            # 预热 search 域名 (支持 HTTPS)
                            src.session.head("https://std.samr.gov.cn/gb/search/gbQueryPage", timeout=5, proxies={"http": None, "https": None})
                            # 预热 download 域名 (仅支持 HTTP)
                            src.session.head("http://c.gb688.cn/bzgk/gb/showGb", timeout=5, proxies={"http": None, "https": None})
                        except Exception:
                            pass
        except Exception:
            pass
            
    threading.Thread(target=prewarm_all, daemon=True).start()
    
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
