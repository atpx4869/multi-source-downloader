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

project_root = Path(__file__).parent
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
    
    def verify_password(self):
        """验证密码"""
        entered = self.pwd_input.text().strip()
        correct = get_today_password()
        
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
                
                # 抖动效果
                self.shake_animation()
    
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
    if is_authenticated_today():
        return True
    
    dialog = PasswordDialog()
    result = dialog.exec()
    return result == QtWidgets.QDialog.Accepted


# ==================== 搜索下载模块 ====================


class SearchThread(QtCore.QThread):
    """快速搜索线程 - 仅搜索ZBY，快速返回结果"""
    results = QtCore.Signal(list)
    log = QtCore.Signal(str)
    error = QtCore.Signal(str)
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, keyword: str, sources: Optional[List[str]] = None, page: int = 1, page_size: int = 20, output_dir: str = "downloads"):
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
            # 优先搜索 ZBY（最全的源）
            search_sources = self.sources or ["ZBY"]

            # 如果用户选择的源中包含 ZBY，优先只搜索 ZBY
            if "ZBY" in search_sources:
                primary_source = ["ZBY"]
                self.log.emit(f"🔍 开始快速搜索: {self.keyword}")
                self.progress.emit(0, 100, "正在连接 ZBY 数据源...")
            else:
                # 如果用户没选 ZBY，按用户选择搜索
                primary_source = search_sources
                self.log.emit(f"🔍 开始搜索: {self.keyword}，来源: {search_sources}")
                self.progress.emit(0, 100, f"正在搜索 {', '.join(search_sources)}...")

            self.progress.emit(20, 100, "正在加载搜索页面...")

            # 使用复用的 AggregatedDownloader 实例
            client = None
            try:
                client = get_aggregated_downloader(enable_sources=primary_source, output_dir=self.output_dir)
            except Exception as e:
                self.log.emit(f"无法创建 AggregatedDownloader: {e}")
                self.results.emit([])
                return
            if client is None:
                self.log.emit("AggregatedDownloader 未找到，无法执行搜索（请确认项目结构）")
                self.results.emit([])
                return
            
            self.progress.emit(40, 100, "正在解析搜索结果...")
            items = client.search(self.keyword, page=int(self.page), page_size=int(self.page_size))
            
            self.progress.emit(80, 100, "正在整理数据...")
            
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
            
            self.progress.emit(100, 100, "搜索完成")
            self.log.emit(f"✅ ZBY 搜索完成：找到 {len(rows)} 条结果")
            self.results.emit(rows)
            
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"❌ 搜索出错: {e}")
            self.log.emit(tb)
            self.error.emit(tb)
            self.progress.emit(0, 100, "搜索失败")


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
                    items = client.search(self.keyword, page=int(self.page), page_size=int(self.page_size))
                    
                    for it in items:
                        # 标准化 std_no 作为 key
                        key = _STD_NO_RE.sub("", it.std_no or "").lower()
                        if key not in cache:
                            cache[key] = {}
                        
                        # 按源存储 Standard 对象，便于后续精确合并与优先级判断
                        s_name = it.sources[0] if it.sources else src_name
                        cache[key][s_name] = it
                    
                    self.log.emit(f"   ✓ {src_name} 完成: {len(items)} 条")
                except Exception as e:
                    self.log.emit(f"   ✗ {src_name} 失败: {str(e)[:50]}")

            self.progress.emit("后台加载完成")
            self.log.emit(f"✅ 后台搜索完成，共缓存 {len(cache)} 条补充数据")
            
        except Exception as e:
            tb = traceback.format_exc()
            self.log.emit(f"❌ 后台搜索出错: {e}")
            self.log.emit(tb)
            self.progress.emit("后台加载失败")
        
        self.finished.emit(cache)


class BatchDownloadThread(QtCore.QThread):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(int, int, list)  # success, fail, failed_list
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, std_ids: List[str], output_dir: str = "downloads", enable_sources: List[str] = None):
        super().__init__()
        self.std_ids = std_ids
        self.output_dir = output_dir
        self.enable_sources = enable_sources
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        success = 0
        fail = 0
        failed_list = []
        total = len(self.std_ids)
        
        try:
            client = get_aggregated_downloader(enable_sources=self.enable_sources, output_dir=self.output_dir)
        except Exception as e:
            self.log.emit(f"❌ 初始化下载器失败: {e}")
            self.finished.emit(0, total, self.std_ids)
            return

        import time
        for idx, std_id in enumerate(self.std_ids, start=1):
            if self._stop_requested:
                self.log.emit("🛑 用户取消了批量下载任务")
                # 将剩余未处理的加入失败列表
                failed_list.extend(self.std_ids[idx-1:])
                fail = len(failed_list)
                break

            # 清理标准号：去除首尾空格、去除不可见字符（如 \xa0）
            std_id = std_id.strip().replace('\xa0', ' ').replace('\u3000', ' ')
            if not std_id:
                continue
                
            # 如果不是第一个，增加随机延迟，避免请求过快被封
            if idx > 1:
                time.sleep(1.5)

            self.progress.emit(idx, total, f"正在处理 ({idx}/{total}): {std_id}")
            self.log.emit(f"──────────────────────────────────────")
            self.log.emit(f"🔍 [{idx}/{total}] 正在搜索: {std_id}")
            
            try:
                # 搜索该标准号，增加重试逻辑
                results = []
                for retry in range(3):
                    try:
                        # 搜索时尝试稍微清理一下关键词，比如去掉多余空格
                        search_key = re.sub(r'\s+', ' ', std_id)
                        results = client.search(search_key)
                        if results:
                            break
                        
                        # 如果没搜到，尝试只搜标准号部分（去掉年份）
                        if '-' in search_key:
                            short_key = search_key.split('-')[0].strip()
                            results = client.search(short_key)
                            if results:
                                break

                        if retry < 2:
                            self.log.emit(f"   ⏳ 未找到结果，{retry+1}秒后重试...")
                            time.sleep(retry + 1)
                    except Exception as e:
                        if retry < 2:
                            time.sleep(retry + 1)
                        else:
                            raise e

                if not results:
                    self.log.emit(f"   ⚠️ 未找到标准: {std_id}")
                    fail += 1
                    failed_list.append(f"{std_id} (未找到标准)")
                    continue
                
                # 寻找最匹配的项（优先完全匹配标准号）
                best_match = results[0]
                # 尝试寻找标准号完全一致的项（忽略空格和大小写）
                clean_id = std_id.replace(" ", "").upper()
                for r in results:
                    if r.std_no.replace(" ", "").upper() == clean_id:
                        best_match = r
                        break
                
                self.log.emit(f"   ✅ 匹配到: {best_match.std_no}")
                self.log.emit(f"   📄 标准名称: {best_match.name}")
                self.log.emit(f"   📥 正在尝试下载...")
                
                # 成功时只输出一条摘要日志，避免底层重复日志刷屏；失败时再输出关键日志
                path, logs = client.download(best_match)
                if path:
                    # 尝试从 logs 中提取实际成功的源名称
                    success_src = "未知"
                    for line in reversed(logs):
                        if "成功 ->" in line:
                            success_src = line.split(":")[0].strip()
                            break
                    self.log.emit(f"   ✅ 下载成功 [{success_src}] -> {path}")
                    success += 1
                else:
                    try:
                        if logs:
                            important = []
                            keywords = ("成功", "失败", "下载完成", "获取到", "PDF生成成功", "requests 下载成功", "OCR", "耗时", "校验", "尝试")
                            for line in logs:
                                try:
                                    if any(k in line for k in keywords):
                                        important.append(line)
                                    if len(important) >= 20:
                                        break
                                except Exception:
                                    continue
                            for l in important:
                                self.log.emit(f"   ↳ {l}")
                    except Exception:
                        pass
                    self.log.emit(f"   ❌ 下载失败: 所有来源均未成功")
                    fail += 1
                    failed_list.append(f"{std_id} (下载失败)")
            except Exception as e:
                self.log.emit(f"   ❌ 处理出错: {e}")
                fail += 1
                failed_list.append(f"{std_id} (程序异常: {str(e)[:30]})")
                
        self.log.emit(f"──────────────────────────────────────")
        self.finished.emit(success, fail, failed_list)


class DownloadThread(QtCore.QThread):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(int, int)
    progress = QtCore.Signal(int, int, str)  # current, total, message

    def __init__(self, items: List[dict], output_dir: str = "downloads", background_cache: dict = None):
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self.background_cache = background_cache or {}

    def run(self):
        success = 0
        fail = 0
        total = len(self.items)
        
        # Note: create a fresh AggregatedDownloader per item to avoid reuse of
        # internal state across sequential downloads, which can cause intermittent
        # failures for some sources. Errors instantiating per-item clients are
        # handled per-item so other downloads can continue.

        for idx, it in enumerate(self.items, start=1):
            std_no = it.get("std_no")
            self.progress.emit(idx, total, f"正在下载: {std_no}")
            self.log.emit(f"📥 [{idx}/{total}] 开始下载: {std_no}")
            
            try:
                # 获取原始对象
                obj = it.get("obj")

                # (已移除旧的后台缓存合并逻辑，现在由 on_bg_search_finished 统一处理)

                # 在下载前记录对象的来源信息，便于排查失败时的来源
                    # 不再打印完整的 source/meta 调试信息，避免泄露冗长内容

                # 使用复用的 AggregatedDownloader 实例以提升性能
                try:
                    client = get_aggregated_downloader(enable_sources=None, output_dir=self.output_dir)
                except Exception:
                    tb = traceback.format_exc()
                    self.log.emit(f"   ✗ 为 {std_no} 创建 AggregatedDownloader 失败，跳过该条: {str(tb)[:200]}")
                    fail += 1
                    continue

                try:
                    path, logs = client.download(obj)
                except Exception as e:
                    # 在 download 抛出异常时记录 obj 的源信息与 traceback
                    try:
                        self.log.emit(f"   ↳ download 异常时 sources: {getattr(obj, 'sources', None)} | source_meta: {getattr(obj, 'source_meta', None)}")
                    except Exception:
                        pass
                    tb = traceback.format_exc()
                    self.log.emit(f"   ❌ 错误: {std_no} - {str(e)[:200]}")
                    self.log.emit(tb)
                    fail += 1
                    continue

                if path:
                    success_src = "未知"
                    try:
                        for line in reversed(logs or []):
                            if "成功 ->" in line:
                                success_src = line.split(":")[0].strip()
                                break
                    except Exception:
                        pass
                    self.log.emit(f"   ✅ 下载成功 [{success_src}] -> {path}")
                    success += 1
                else:
                    # 失败时再输出关键日志，便于排查
                    try:
                        if logs:
                            important = []
                            keywords = ("成功", "失败", "下载完成", "获取到", "PDF生成成功", "requests 下载成功", "OCR", "耗时", "校验", "尝试")
                            for line in logs:
                                try:
                                    if any(k in line for k in keywords):
                                        important.append(line)
                                    if len(important) >= 20:
                                        break
                                except Exception:
                                    continue
                            if important:
                                for l in important:
                                    self.log.emit(f"   ↳ {l}")
                            else:
                                self.log.emit(f"   ↳ download 日志: {len(logs)} 条")
                    except Exception:
                        pass
                    self.log.emit(f"   ❌ 下载失败: {std_no}")
                    fail += 1
            except Exception as e:
                tb = traceback.format_exc()
                self.log.emit(f"   ❌ 错误: {std_no} - {str(e)[:120]}")
                self.log.emit(tb)
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
        if role == QtCore.Qt.BackgroundRole and c == 0 and item.get("_selected"):
            return QtGui.QBrush(QtGui.QColor("#3498db"))
        if role == QtCore.Qt.ForegroundRole and c == 0 and item.get("_selected"):
            return QtGui.QBrush(QtGui.QColor("#ffffff"))
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
        dl_layout.addWidget(QtWidgets.QLabel("搜索返回数量:"), 1, 0)
        self.spin_pagesize = QtWidgets.QSpinBox()
        self.spin_pagesize.setValue(30)
        self.spin_pagesize.setMinimum(10)
        self.spin_pagesize.setMaximum(100)
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

        # 持久化配置（Win7 兼容）：使用 QSettings（Windows 下为注册表；无需额外文件权限）
        self._load_persistent_settings()
        
        # 分页状态
        self.current_page = 1
        self.total_pages = 1
        # pending search rows (避免在搜索未完全结束前就更新显示)
        self._pending_search_rows = None

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
        self.search_thread.results.connect(self.on_search_results)
        self.search_thread.log.connect(self.append_log)
        self.search_thread.progress.connect(self.on_search_progress)
        self.search_thread.error.connect(lambda tb: self.append_log(f"错误详情:\n{tb}"))
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.start()
    
    def on_search_progress(self, current: int, total: int, message: str):
        """更新搜索进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status.showMessage(message)
    
    def on_search_finished(self):
        """主搜索完成后，启动后台搜索"""
        # 在搜索线程结束后再把 pending rows 应用到界面，避免竞态
        if getattr(self, '_pending_search_rows', None) is not None:
            try:
                self.all_items = self._pending_search_rows.copy()
                self.current_page = 1
                self.apply_filter()
            finally:
                self._pending_search_rows = None

        self.btn_search.setEnabled(True)
        self.progress_bar.hide()
        self.status.showMessage("搜索完成", 3000)
        
        # 启动后台搜索补充 GBW/BY 数据
        sources = self.settings.get("sources", [])
        bg_sources = [s for s in sources if s != "ZBY"]  # 排除 ZBY
        
        if bg_sources and self.last_keyword and "ZBY" in sources:
            # 只有当用户选了 ZBY + 其他源时才启动后台搜索
            self.start_background_search(self.last_keyword, bg_sources)

    def start_background_search(self, keyword: str, sources: list[str]):
        """启动后台搜索"""
        if not sources:
            return
            
        # 使用UI上的每页数量设置
        page_size = self.get_page_size()
        self.bg_search_thread = BackgroundSearchThread(
            keyword=keyword,
            sources=sources,
            page=1,
            page_size=page_size,
            output_dir=self.settings.get("output_dir", "downloads")
        )
        self.bg_search_thread.log.connect(self.append_log)
        self.bg_search_thread.progress.connect(self.on_bg_search_progress)
        self.bg_search_thread.finished.connect(self.on_bg_search_finished)
        self.bg_search_thread.start()
    
    def on_bg_search_progress(self, message: str):
        """更新后台搜索状态"""
        self.lbl_bg_status.setText(message)
    
    def on_bg_search_finished(self, cache: dict):
        """后台搜索完成，合并数据并刷新界面"""
        self.background_cache = cache
        
        updated_count = 0
        
        # 遍历当前显示的列表（主要是 ZBY 结果）
        for item in self.current_items:
            std_no = item.get("std_no", "")
            key = _STD_NO_RE.sub("", std_no).lower()
            
            # 获取该标准的所有可用源数据
            candidates = []
            
            # 1. 当前项本身 (通常是 ZBY)
            if item.get("obj"):
                # 假设当前项主要是 ZBY，或者已有的源
                # 注意：item['obj'].sources 可能包含多个，但初始搜索通常只有一个
                srcs = item["obj"].sources
                main_src = srcs[0] if srcs else "ZBY"
                candidates.append((main_src, item["obj"]))
            
            # 2. 后台搜索结果 (GBW, BY)
            # cache 结构: { std_no_key: { 'GBW': obj, 'BY': obj } }
            bg_results = cache.get(key, {})
            for src, obj in bg_results.items():
                candidates.append((src, obj))
            
            if not candidates:
                continue
                
            # 确定最优源 (Best Source)
            # 优先级: GBW > BY > ZBY (如果有文本)
            # 如果都没有文本，也按此顺序
            
            def score_candidate(cand):
                src, obj = cand
                score = 0
                if obj.has_pdf:
                    score += 100
                
                if src == "GBW":
                    score += 3
                elif src == "BY":
                    score += 2
                elif src == "ZBY":
                    score += 1
                return score
            
            candidates.sort(key=score_candidate, reverse=True)
            best_src, best_obj = candidates[0]
            
            # 更新显示用的来源
            item['_display_source'] = best_src
            
            # 合并数据到 item['obj']
            target_obj = item["obj"]
            
            # 收集所有源
            all_sources = set(target_obj.sources)
            for src, obj in candidates:
                for s in obj.sources:
                    all_sources.add(s)
                # 合并 source_meta
                if obj.source_meta:
                    if not target_obj.source_meta:
                        target_obj.source_meta = {}
                    target_obj.source_meta.update(obj.source_meta)
            
            target_obj.sources = list(all_sources)
            
            # 更新状态 (如果 ZBY 状态为空或废止，而最优源状态更好，则更新)
            # 优先使用 best_obj 的状态，因为它通常是最准确的
            if best_obj.status:
                 # 仅当原状态为空，或原状态为废止但新状态为现行/即将实施时更新
                 # 或者直接信任 best_obj
                 item["status"] = best_obj.status
                 target_obj.status = best_obj.status
            
            # has_pdf 取并集
            has_pdf_any = any(obj.has_pdf for _, obj in candidates)
            item["has_pdf"] = has_pdf_any
            target_obj.has_pdf = has_pdf_any
            
            # 更新发布/实施日期 (如果缺失)
            if not item["publish"] and best_obj.publish:
                item["publish"] = best_obj.publish
                target_obj.publish = best_obj.publish
            if not item["implement"] and best_obj.implement:
                item["implement"] = best_obj.implement
                target_obj.implement = best_obj.implement
                
            updated_count += 1

        # 刷新表格
        if updated_count > 0:
            self.table_model.set_items(self.current_items)
            self.update_selection_count()
            # 仅在有更新时记录日志，避免刷屏
            if updated_count > 5:
                self.append_log(f"✅ 已根据后台数据优化 {updated_count} 条标准信息的来源与状态")

        self.lbl_bg_status.setText(f"✓ 后台数据已合并")
        QtCore.QTimer.singleShot(5000, lambda: self.lbl_bg_status.setText(""))

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
                if health and getattr(health, 'available', False):
                    checkbox.setChecked(True)
                    checkbox.setEnabled(True)
                else:
                    checkbox.setChecked(False)
                    checkbox.setEnabled(False)
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
        act = menu.exec(self.table.viewport().mapToGlobal(pos))
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
        
        output_dir = self.settings.get("output_dir", "downloads")
        self.download_thread = DownloadThread(
            selected, 
            output_dir=output_dir,
            background_cache=self.background_cache
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
            
            self.batch_thread = BatchDownloadThread(
                ids, 
                output_dir=output_dir,
                enable_sources=enable_sources
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
        
        QtWidgets.QMessageBox.information(self, "任务完成", msg)


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # 密码验证
    if not check_password():
        sys.exit(0)
    
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
