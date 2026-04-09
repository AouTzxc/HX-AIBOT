import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import (
    APP_DIR,
    APP_ICON_FILE,
    DEFAULT_ANALYSIS_PROMPT,
    DEFAULT_ENDPOINT,
    AIClient,
    AppConfig,
    WindowInfo,
    capture_window,
    click_at,
    find_next_question_btn,
    find_option_position,
    find_submit_btn,
    format_answer_items,
    format_offset_text,
    get_option_offset,
    get_ocr_status,
    get_root_window_from_point,
    get_window_rect,
    get_window_title,
    is_window_visible,
    load_config,
    normalize_point,
    normalize_theme_mode,
    normalize_ui_language,
    parse_ai_answers,
    point_in_rect,
    save_config,
)


def pil_to_pixmap(image: Image.Image, max_width: int, max_height: int) -> QPixmap:
    preview = image.copy()
    preview.thumbnail((max_width, max_height))
    rgba = preview.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    qimage = QImage(raw, rgba.width, rgba.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


UI_TEXTS: Dict[str, Dict[str, str]] = {
    "zh": {
        "app_title": "HX-AIBOT",
        "hero_subtitle": "macOS 26 风格的轻盈控制台，专注窗口捕获、答案分析与自动答题。",
        "select_window": "选择窗口",
        "analyze_once": "单次答题",
        "auto_start": "开始自动答题",
        "auto_stop": "停止自动答题",
        "button_locator": "按钮定位",
        "save_screenshot": "保存截图",
        "settings": "设置",
        "current_window_card": "当前目标窗口",
        "window_not_selected": "未选择目标窗口",
        "window_rect": "窗口范围：{left}, {top}, {right}, {bottom}",
        "window_rect_empty": "窗口范围：-",
        "preview_card": "最近截图预览",
        "preview_empty": "还没有截图",
        "result_card": "题目提取与解题思路",
        "result_placeholder": "模型返回的题目、答案和解析会显示在这里。",
        "log_card": "运行日志",
        "status_ready": "准备就绪",
        "footer_hint": "拖动轻量黄色准星到目标窗口或按钮上后松开鼠标即可记录位置。",
        "settings_title": "设置",
        "api_url": "API 地址",
        "api_key": "API Key",
        "model_id": "模型 ID / Endpoint ID",
        "timeout_seconds": "超时秒数",
        "auto_answer_check": "启用自动答题（选择答案并自动切题）",
        "auto_submit_check": "启用自动提交（全部题目完成后）",
        "analysis_prompt": "分析提示词",
        "reset_prompt": "恢复默认提示词",
        "locator_title": "按钮定位",
        "locator_hint": "用十字准星记录目标窗口里的可点击位置，保存的是相对窗口左上角的偏移。",
        "locator_window_none": "当前目标窗口：未选择",
        "locator_window_selected": "当前目标窗口：{title}",
        "option_a": "选项 A",
        "option_b": "选项 B",
        "option_c": "选项 C",
        "option_d": "选项 D",
        "next_button": "下一题按钮",
        "submit_button": "提交按钮",
        "set_a": "设置 A",
        "set_b": "设置 B",
        "set_c": "设置 C",
        "set_d": "设置 D",
        "set_next": "设置下一题",
        "set_submit": "设置提交",
        "clear_options": "清空 A-D",
        "clear_next": "清空下一题",
        "clear_submit": "清空提交",
        "close": "关闭",
        "not_set": "未设置",
        "offset_text": "窗口内偏移：({x}, {y})",
        "error_title": "执行失败",
        "info_title": "提示",
        "busy_msg": "当前正在处理，请稍候。",
        "missing_window_msg": "请先选择一个目标窗口。",
        "missing_api_msg": "请先在设置里填写 API Key 和模型 ID。",
        "theme_tooltip_light": "当前为明亮模式",
        "theme_tooltip_dark": "当前为黑暗模式",
        "language_tooltip": "切换中英界面",
        "language_button": "中",
        "settings_saved": "设置已保存。",
        "settings_updated": "设置已更新",
        "locator_opened": "按钮定位面板已打开",
        "screenshot_saved": "截图已保存",
        "screenshot_failed": "截图失败",
        "analysis_done": "分析完成",
        "analysis_failed": "分析失败",
        "auto_started": "自动答题已启动",
        "auto_stopped": "自动答题已停止",
        "program_started": "程序已启动。",
        "ocr_status": "OCR 状态：{status}",
        "theme_changed_light": "已切换到明亮主题",
        "theme_changed_dark": "已切换到黑暗主题",
        "language_changed": "界面语言已切换",
        "on": "开启",
        "off": "关闭",
        "auto_mode_log": "自动答题：{auto_answer} | 自动提交：{auto_submit}",
        "crosshair_pick_window_status": "请拖动十字准星到目标窗口后松开鼠标",
        "crosshair_pick_window_log": "十字准星已打开，请拖到目标窗口上后松开鼠标。",
        "window_pick_failed_log": "没有识别到目标窗口。",
        "window_pick_failed_status": "窗口选择失败",
        "window_invisible_log": "目标窗口当前不可见，请确认它没有被最小化。",
        "window_invisible_status": "目标窗口不可见",
        "window_selected_log": "已选择窗口：{title}，句柄 {hwnd}。",
        "window_selected_status": "目标窗口已选择",
        "button_position_failed_log": "{button_name}按钮定位失败：({x}, {y}) 不在目标窗口内。",
        "button_position_failed_status": "{button_name}按钮定位失败",
        "button_position_failed_error": "请把十字准星拖到目标窗口内部的按钮上再松开鼠标。",
        "button_position_saved_log": "{button_name}按钮定位已保存，屏幕坐标：({x}, {y})，窗口内偏移：{offset}",
        "button_position_saved_status": "{button_name}按钮定位已保存",
        "options_cleared_log": "已清空 A-D 选项的自定义定位。",
        "options_cleared_status": "已清空 A-D 选项定位",
        "next_cleared_log": "已清空“下一题”按钮的自定义定位。",
        "next_cleared_status": "已清空下一题按钮定位",
        "submit_cleared_log": "已清空“提交”按钮的自定义定位。",
        "submit_cleared_status": "已清空提交按钮定位",
        "auto_loop_started_log": "开始自动答题循环...",
        "auto_manual_stop_log": "自动答题已手动停止",
        "custom_position_source": "自定义定位",
        "default_position_source": "默认定位",
        "next_click_log": "点击下一题按钮（{source}），坐标：{pos}",
        "option_missing_auto_log": "未能定位到选项 {option}，自动答题已暂停，请先在“按钮定位”里标定 A-D 选项位置。",
        "option_missing_auto_status": "未定位到 {option} 选项，请先标定选项坐标",
        "option_missing_single_log": "未能定位到选项 {option}，请先在“按钮定位”里标定 A-D 选项位置。",
        "option_click_log": "点击选项 {option}（{source}），坐标：{pos}",
        "processing_question_status": "正在处理第 {number} 题...",
        "processing_question_log": "===== 处理第 {number} 题 =====",
        "capture_size_log": "截图完成，尺寸：{width} x {height}",
        "ai_analysis_complete_log": "AI 分析完成",
        "answer_parse_failed_log": "未能解析到有效答案，原始返回片段：{preview}",
        "answers_parsed_log": "解析到答案：{answers}",
        "last_question_log": "检测到最后一题，自动答题完成",
        "auto_submit_log": "执行自动提交...",
        "submit_click_log": "已点击提交按钮（{source}），坐标：{pos}",
        "auto_finished_status": "自动答题完成，共处理 {count} 题",
        "auto_finished_log": "自动答题循环结束，共处理 {count} 题",
        "auto_no_questions_status": "自动答题未处理任何题目",
        "auto_exception_log": "自动答题异常：{error}",
        "auto_exception_status": "自动答题异常终止",
        "saving_capture_status": "正在截图...",
        "capture_start_log": "开始截图目标窗口。",
        "capture_saved_log": "截图已保存到：{path}",
        "capture_failed_log": "截图失败：{error}",
        "analysis_running_status": "正在截图并调用模型...",
        "analysis_start_log": "开始截图目标窗口。",
        "analysis_capture_size_log": "截图完成，尺寸：{width} x {height}。",
        "analysis_call_model_log": "开始调用豆包兼容 API 分析截图。",
        "analysis_auto_select_log": "自动选择答案：{answers}",
        "analysis_no_answer_log": "单次答题未解析到答案，原始返回片段：{preview}",
        "analysis_complete_log": "模型分析完成。",
        "analysis_failed_log": "分析失败：{error}",
        "pick_option_status": "请拖动十字准星到“{option} 选项”后松开鼠标",
        "pick_option_log": "开始定位“{option} 选项”，请把十字准星拖到对应选项的可点击区域中心后松开鼠标。",
        "pick_next_status": "请拖动十字准星到“下一题”按钮后松开鼠标",
        "pick_next_log": "开始定位“下一题”按钮，请把十字准星拖到按钮中心后松开鼠标。",
        "pick_submit_status": "请拖动十字准星到“提交”按钮后松开鼠标",
        "pick_submit_log": "开始定位“提交”按钮，请把十字准星拖到按钮中心后松开鼠标。",
    },
    "en": {
        "app_title": "HX-AIBOT",
        "hero_subtitle": "A lightweight macOS 26-inspired console for window capture, answer analysis, and auto-solving.",
        "select_window": "Select Window",
        "analyze_once": "Analyze Once",
        "auto_start": "Start Auto",
        "auto_stop": "Stop Auto",
        "button_locator": "Locate Buttons",
        "save_screenshot": "Save Capture",
        "settings": "Settings",
        "current_window_card": "Target Window",
        "window_not_selected": "No target window selected",
        "window_rect": "Window Bounds: {left}, {top}, {right}, {bottom}",
        "window_rect_empty": "Window Bounds: -",
        "preview_card": "Latest Capture Preview",
        "preview_empty": "No screenshot yet",
        "result_card": "Question Extraction and Reasoning",
        "result_placeholder": "The model's extracted question, answer, and reasoning will appear here.",
        "log_card": "Runtime Log",
        "status_ready": "Ready",
        "footer_hint": "Drag the light yellow crosshair onto the target window or button, then release to save the position.",
        "settings_title": "Settings",
        "api_url": "API URL",
        "api_key": "API Key",
        "model_id": "Model ID / Endpoint ID",
        "timeout_seconds": "Timeout (seconds)",
        "auto_answer_check": "Enable auto-solving (pick answers and advance automatically)",
        "auto_submit_check": "Enable auto-submit (after all questions are finished)",
        "analysis_prompt": "Analysis Prompt",
        "reset_prompt": "Reset Default Prompt",
        "locator_title": "Button Locator",
        "locator_hint": "Use the crosshair to record clickable positions in the target window. Saved values are offsets from the top-left corner.",
        "locator_window_none": "Current target window: not selected",
        "locator_window_selected": "Current target window: {title}",
        "option_a": "Option A",
        "option_b": "Option B",
        "option_c": "Option C",
        "option_d": "Option D",
        "next_button": "Next Button",
        "submit_button": "Submit Button",
        "set_a": "Set A",
        "set_b": "Set B",
        "set_c": "Set C",
        "set_d": "Set D",
        "set_next": "Set Next",
        "set_submit": "Set Submit",
        "clear_options": "Clear A-D",
        "clear_next": "Clear Next",
        "clear_submit": "Clear Submit",
        "close": "Close",
        "not_set": "Not set",
        "offset_text": "Window offset: ({x}, {y})",
        "error_title": "Action Failed",
        "info_title": "Info",
        "busy_msg": "A task is already running. Please wait.",
        "missing_window_msg": "Please select a target window first.",
        "missing_api_msg": "Please fill in the API Key and Model ID in Settings first.",
        "theme_tooltip_light": "Light mode is active",
        "theme_tooltip_dark": "Dark mode is active",
        "language_tooltip": "Switch interface language",
        "language_button": "EN",
        "settings_saved": "Settings saved.",
        "settings_updated": "Settings updated",
        "locator_opened": "Button locator panel opened",
        "screenshot_saved": "Screenshot saved",
        "screenshot_failed": "Screenshot failed",
        "analysis_done": "Analysis completed",
        "analysis_failed": "Analysis failed",
        "auto_started": "Auto-solving started",
        "auto_stopped": "Auto-solving stopped",
        "program_started": "Application started.",
        "ocr_status": "OCR status: {status}",
        "theme_changed_light": "Switched to light theme",
        "theme_changed_dark": "Switched to dark theme",
        "language_changed": "Interface language switched",
        "on": "On",
        "off": "Off",
        "auto_mode_log": "Auto-solving: {auto_answer} | Auto-submit: {auto_submit}",
        "crosshair_pick_window_status": "Drag the crosshair onto the target window, then release the mouse",
        "crosshair_pick_window_log": "Crosshair opened. Drag it onto the target window and release the mouse.",
        "window_pick_failed_log": "No target window was detected.",
        "window_pick_failed_status": "Window selection failed",
        "window_invisible_log": "The target window is not visible. Make sure it is not minimized.",
        "window_invisible_status": "Target window is not visible",
        "window_selected_log": "Selected window: {title}, handle {hwnd}.",
        "window_selected_status": "Target window selected",
        "button_position_failed_log": "{button_name} positioning failed: ({x}, {y}) is outside the target window.",
        "button_position_failed_status": "{button_name} positioning failed",
        "button_position_failed_error": "Drag the crosshair onto a button inside the target window before releasing the mouse.",
        "button_position_saved_log": "{button_name} position saved. Screen: ({x}, {y}), window offset: {offset}",
        "button_position_saved_status": "{button_name} position saved",
        "options_cleared_log": "Cleared custom positions for options A-D.",
        "options_cleared_status": "Cleared A-D option positions",
        "next_cleared_log": "Cleared the custom position for the Next button.",
        "next_cleared_status": "Cleared Next button position",
        "submit_cleared_log": "Cleared the custom position for the Submit button.",
        "submit_cleared_status": "Cleared Submit button position",
        "auto_loop_started_log": "Started auto-solving loop...",
        "auto_manual_stop_log": "Auto-solving was stopped manually",
        "custom_position_source": "custom position",
        "default_position_source": "default position",
        "next_click_log": "Clicking Next button ({source}), coordinates: {pos}",
        "option_missing_auto_log": "Could not locate option {option}. Auto-solving has been paused. Please calibrate A-D positions in Button Locator first.",
        "option_missing_auto_status": "Option {option} was not found. Please calibrate option positions first",
        "option_missing_single_log": "Could not locate option {option}. Please calibrate A-D positions in Button Locator first.",
        "option_click_log": "Clicking option {option} ({source}), coordinates: {pos}",
        "processing_question_status": "Processing question {number}...",
        "processing_question_log": "===== Processing question {number} =====",
        "capture_size_log": "Capture finished. Size: {width} x {height}",
        "ai_analysis_complete_log": "AI analysis completed",
        "answer_parse_failed_log": "No valid answer was parsed. Raw response preview: {preview}",
        "answers_parsed_log": "Parsed answers: {answers}",
        "last_question_log": "Last question detected. Auto-solving completed",
        "auto_submit_log": "Submitting automatically...",
        "submit_click_log": "Clicked Submit button ({source}), coordinates: {pos}",
        "auto_finished_status": "Auto-solving completed. Processed {count} questions",
        "auto_finished_log": "Auto-solving loop finished after {count} questions",
        "auto_no_questions_status": "Auto-solving did not process any questions",
        "auto_exception_log": "Auto-solving error: {error}",
        "auto_exception_status": "Auto-solving terminated unexpectedly",
        "saving_capture_status": "Capturing screenshot...",
        "capture_start_log": "Starting target window capture.",
        "capture_saved_log": "Screenshot saved to: {path}",
        "capture_failed_log": "Screenshot failed: {error}",
        "analysis_running_status": "Capturing the window and calling the model...",
        "analysis_start_log": "Starting target window capture.",
        "analysis_capture_size_log": "Capture finished. Size: {width} x {height}.",
        "analysis_call_model_log": "Calling the Doubao-compatible API to analyze the screenshot.",
        "analysis_auto_select_log": "Auto-selecting answers: {answers}",
        "analysis_no_answer_log": "Analyze Once did not parse any answer. Raw response preview: {preview}",
        "analysis_complete_log": "Model analysis completed.",
        "analysis_failed_log": "Analysis failed: {error}",
        "pick_option_status": "Drag the crosshair onto option {option}, then release the mouse",
        "pick_option_log": "Locating option {option}. Drag the crosshair to the center of the clickable option area, then release the mouse.",
        "pick_next_status": "Drag the crosshair onto the Next button, then release the mouse",
        "pick_next_log": "Locating the Next button. Drag the crosshair to the center of the button, then release the mouse.",
        "pick_submit_status": "Drag the crosshair onto the Submit button, then release the mouse",
        "pick_submit_log": "Locating the Submit button. Drag the crosshair to the center of the button, then release the mouse.",
    },
}


class UiSignals(QObject):
    log = Signal(str)
    status = Signal(str)
    result = Signal(str)
    preview = Signal(object)
    error = Signal(str)
    busy = Signal(bool)
    auto_state = Signal(bool)
    locator_refresh = Signal()


class GlassCard(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 18)
        self.layout.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.layout.addWidget(self.title_label)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        self.layout.addWidget(self.body)


class CrosshairPicker(QWidget):
    def __init__(self, label: str, on_pick):
        super().__init__(None)
        self.label = label
        self.on_pick = on_pick
        self._drag_offset = QPoint()
        self.resize(52, 52)
        self.move(200, 200)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)
        self.show()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.setBrush(QColor(255, 219, 77, 48))
        painter.setPen(QPen(QColor(255, 217, 77, 225), 2))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(255, 217, 77, 235), 2))
        painter.drawLine(rect.center().x(), rect.top() + 3, rect.center().x(), rect.bottom() - 3)
        painter.drawLine(rect.left() + 3, rect.center().y(), rect.right() - 3, rect.center().y())
        painter.setBrush(QColor(255, 250, 205, 190))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect.center(), 4, 4)
        if self.label:
            text_rect = QRect(0, rect.bottom() - 4, self.width(), 16)
            painter.setPen(QColor(255, 248, 210, 230))
            font = painter.font()
            font.setPointSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, self.label)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            point = event.globalPosition().toPoint()
            self.close()
            self.on_pick(point.x(), point.y())


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, language: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.language = normalize_ui_language(language)
        self.source_config = config
        if APP_ICON_FILE.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_FILE)))
        self.resize(760, 620)
        self.setModal(True)

        self.api_url_edit = QLineEdit(config.api_url)
        self.api_key_edit = QLineEdit(config.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.model_edit = QLineEdit(config.model)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setValue(config.timeout_seconds)
        self.auto_answer_check = QCheckBox("启用自动答题（选择答案并自动切题）")
        self.auto_answer_check.setChecked(config.auto_answer)
        self.auto_submit_check = QCheckBox()
        self.auto_submit_check.setChecked(config.auto_submit)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(config.analysis_prompt)
        self.labels: Dict[str, QLabel] = {
            "api_url": QLabel(),
            "api_key": QLabel(),
            "model_id": QLabel(),
            "timeout_seconds": QLabel(),
            "analysis_prompt": QLabel(),
        }
        self.reset_button = QPushButton()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(self.labels["api_url"], 0, 0)
        form.addWidget(self.api_url_edit, 0, 1)
        form.addWidget(self.labels["api_key"], 1, 0)
        form.addWidget(self.api_key_edit, 1, 1)
        form.addWidget(self.labels["model_id"], 2, 0)
        form.addWidget(self.model_edit, 2, 1)
        form.addWidget(self.labels["timeout_seconds"], 3, 0)
        form.addWidget(self.timeout_spin, 3, 1)
        root.addLayout(form)
        root.addWidget(self.auto_answer_check)
        root.addWidget(self.auto_submit_check)
        root.addWidget(self.labels["analysis_prompt"])
        root.addWidget(self.prompt_edit, 1)

        actions = QHBoxLayout()
        self.reset_button.clicked.connect(self._reset_prompt)
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        actions.addWidget(self.buttons)
        root.addLayout(actions)
        self.apply_language(self.language)

    def _reset_prompt(self) -> None:
        self.prompt_edit.setPlainText(DEFAULT_ANALYSIS_PROMPT)

    def apply_language(self, language: str) -> None:
        self.language = normalize_ui_language(language)
        texts = UI_TEXTS[self.language]
        self.setWindowTitle(texts["settings_title"])
        self.labels["api_url"].setText(texts["api_url"])
        self.labels["api_key"].setText(texts["api_key"])
        self.labels["model_id"].setText(texts["model_id"])
        self.labels["timeout_seconds"].setText(texts["timeout_seconds"])
        self.labels["analysis_prompt"].setText(texts["analysis_prompt"])
        self.auto_answer_check.setText(texts["auto_answer_check"])
        self.auto_submit_check.setText(texts["auto_submit_check"])
        self.reset_button.setText(texts["reset_prompt"])
        save_button = self.buttons.button(QDialogButtonBox.Save)
        cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        if save_button is not None:
            save_button.setText("保存" if self.language == "zh" else "Save")
        if cancel_button is not None:
            cancel_button.setText("取消" if self.language == "zh" else "Cancel")

    def to_config(self, source_config: AppConfig) -> AppConfig:
        return AppConfig(
            api_url=self.api_url_edit.text().strip() or DEFAULT_ENDPOINT,
            api_key=self.api_key_edit.text().strip(),
            model=self.model_edit.text().strip(),
            timeout_seconds=int(self.timeout_spin.value()),
            analysis_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_ANALYSIS_PROMPT,
            auto_submit=self.auto_submit_check.isChecked(),
            auto_answer=self.auto_answer_check.isChecked(),
            ui_language=source_config.ui_language,
            theme_mode=source_config.theme_mode,
            option_a_offset=source_config.option_a_offset,
            option_b_offset=source_config.option_b_offset,
            option_c_offset=source_config.option_c_offset,
            option_d_offset=source_config.option_d_offset,
            next_button_offset=source_config.next_button_offset,
            submit_button_offset=source_config.submit_button_offset,
        )


class ButtonLocatorDialog(QDialog):
    def __init__(self, window: "QtMainWindow"):
        super().__init__(window)
        self.window = window
        if APP_ICON_FILE.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_FILE)))
        self.setModal(False)
        self.setMinimumWidth(420)

        self.intro_label = QLabel()
        self.window_label = QLabel()
        self.title_labels: Dict[str, QLabel] = {
            "option_a_offset": QLabel(),
            "option_b_offset": QLabel(),
            "option_c_offset": QLabel(),
            "option_d_offset": QLabel(),
            "next_button_offset": QLabel(),
            "submit_button_offset": QLabel(),
        }
        self.value_labels = {
            "option_a_offset": QLabel(),
            "option_b_offset": QLabel(),
            "option_c_offset": QLabel(),
            "option_d_offset": QLabel(),
            "next_button_offset": QLabel(),
            "submit_button_offset": QLabel(),
        }
        self.action_buttons: Dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(self.intro_label)
        root.addWidget(self.window_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        entries = [
            ("option_a_offset", lambda: self.window.pick_option_position("A"), "set_a"),
            ("option_b_offset", lambda: self.window.pick_option_position("B"), "set_b"),
            ("option_c_offset", lambda: self.window.pick_option_position("C"), "set_c"),
            ("option_d_offset", lambda: self.window.pick_option_position("D"), "set_d"),
            ("next_button_offset", self.window.pick_next_button_position, "set_next"),
            ("submit_button_offset", self.window.pick_submit_button_position, "set_submit"),
        ]
        for row, (key, callback, button_text_key) in enumerate(entries):
            grid.addWidget(self.title_labels[key], row, 0)
            grid.addWidget(self.value_labels[key], row, 1)
            button = QPushButton()
            button.clicked.connect(callback)
            grid.addWidget(button, row, 2)
            self.action_buttons[button_text_key] = button
        root.addLayout(grid)

        actions = QHBoxLayout()
        self.clear_options_button = QPushButton()
        self.clear_options_button.clicked.connect(self.window.clear_all_option_positions)
        self.clear_next_button = QPushButton()
        self.clear_next_button.clicked.connect(self.window.clear_next_button_position)
        self.clear_submit_button = QPushButton()
        self.clear_submit_button.clicked.connect(self.window.clear_submit_button_position)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.clear_options_button)
        actions.addWidget(self.clear_next_button)
        actions.addWidget(self.clear_submit_button)
        actions.addStretch(1)
        actions.addWidget(self.close_button)
        root.addLayout(actions)
        self.apply_language(self.window.ui_language)
        self.refresh()

    def apply_language(self, language: str) -> None:
        texts = UI_TEXTS[normalize_ui_language(language)]
        self.setWindowTitle(texts["locator_title"])
        self.intro_label.setText(texts["locator_hint"])
        self.title_labels["option_a_offset"].setText(texts["option_a"])
        self.title_labels["option_b_offset"].setText(texts["option_b"])
        self.title_labels["option_c_offset"].setText(texts["option_c"])
        self.title_labels["option_d_offset"].setText(texts["option_d"])
        self.title_labels["next_button_offset"].setText(texts["next_button"])
        self.title_labels["submit_button_offset"].setText(texts["submit_button"])
        self.action_buttons["set_a"].setText(texts["set_a"])
        self.action_buttons["set_b"].setText(texts["set_b"])
        self.action_buttons["set_c"].setText(texts["set_c"])
        self.action_buttons["set_d"].setText(texts["set_d"])
        self.action_buttons["set_next"].setText(texts["set_next"])
        self.action_buttons["set_submit"].setText(texts["set_submit"])
        self.clear_options_button.setText(texts["clear_options"])
        self.clear_next_button.setText(texts["clear_next"])
        self.clear_submit_button.setText(texts["clear_submit"])
        self.close_button.setText(texts["close"])
        self.refresh()

    def refresh(self) -> None:
        texts = UI_TEXTS[self.window.ui_language]
        title = texts["locator_window_none"]
        if self.window.selected_window is not None:
            title = texts["locator_window_selected"].format(title=self.window.selected_window.title)
        self.window_label.setText(title)
        for key, label in self.value_labels.items():
            offset = normalize_point(getattr(self.window.config_data, key))
            if offset is None:
                label.setText(texts["not_set"])
            else:
                label.setText(texts["offset_text"].format(x=offset[0], y=offset[1]))

    def closeEvent(self, event) -> None:
        self.window.button_locator_dialog = None
        super().closeEvent(event)


class QtMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        if APP_ICON_FILE.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_FILE)))
        self.resize(1240, 820)
        self.setMinimumSize(1040, 700)

        self.config_data = load_config()
        self.ui_language = normalize_ui_language(self.config_data.ui_language)
        self.theme_mode = normalize_theme_mode(self.config_data.theme_mode)
        self.config_data.ui_language = self.ui_language
        self.config_data.theme_mode = self.theme_mode
        self.selected_window: Optional[WindowInfo] = None
        self.current_picker: Optional[CrosshairPicker] = None
        self.button_locator_dialog: Optional[ButtonLocatorDialog] = None
        self.preview_pixmap: Optional[QPixmap] = None
        self.busy = False
        self.is_auto_running = False

        self.signals = UiSignals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status_text)
        self.signals.result.connect(self._set_result_text)
        self.signals.preview.connect(self._set_preview_image)
        self.signals.error.connect(self._show_error_dialog)
        self.signals.busy.connect(self._set_busy_state)
        self.signals.auto_state.connect(self._set_auto_running_state)
        self.signals.locator_refresh.connect(self._refresh_button_locator_dialog)

        self._build_ui()
        self._apply_texts()
        self._apply_styles()

        self._log_auto_mode()
        self.log(self.tr_text("program_started"))
        self.log(self.tr_text("ocr_status", status=get_ocr_status()))
        self.signals.status.emit(self.tr_text("status_ready"))
        QTimer.singleShot(450, self.open_window_picker)

    def tr_text(self, key: str, **kwargs) -> str:
        template = UI_TEXTS[self.ui_language].get(key, UI_TEXTS["zh"].get(key, key))
        return template.format(**kwargs)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QFrame()
        header.setObjectName("Hero")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        self.hero_title = QLabel()
        self.hero_title.setObjectName("HeroTitle")
        self.hero_subtitle = QLabel()
        self.hero_subtitle.setObjectName("HeroSubtitle")
        title_wrap.addWidget(self.hero_title)
        title_wrap.addWidget(self.hero_subtitle)
        top_row.addLayout(title_wrap, 1)

        utility_row = QHBoxLayout()
        utility_row.setSpacing(10)
        self.language_button = self._make_button("", self.toggle_language, compact=True)
        self.theme_button = self._make_button("", self.toggle_theme, compact=True)
        utility_row.addWidget(self.language_button)
        utility_row.addWidget(self.theme_button)
        top_row.addLayout(utility_row)
        header_layout.addLayout(top_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.select_window_button = self._make_button("", self.open_window_picker)
        self.analyze_button = self._make_button("", self.start_analysis)
        self.auto_button = self._make_button("", self.toggle_auto_answer, primary=True)
        self.locator_button = self._make_button("", self.open_button_locator)
        self.capture_button = self._make_button("", self.save_screenshot)
        self.settings_button = self._make_button("", self.open_settings)
        self.primary_header_buttons = [
            self.select_window_button,
            self.analyze_button,
            self.auto_button,
            self.locator_button,
            self.capture_button,
            self.settings_button,
        ]
        for button in (
            self.select_window_button,
            self.analyze_button,
            self.auto_button,
            self.locator_button,
            self.capture_button,
            self.settings_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        header_layout.addLayout(button_row)
        root.addWidget(header)

        content = QHBoxLayout()
        content.setSpacing(16)
        root.addLayout(content, 1)

        left_column = QVBoxLayout()
        left_column.setSpacing(16)
        content.addLayout(left_column, 3)

        self.window_card = GlassCard("")
        self.window_title_label = QLabel("")
        self.window_title_label.setObjectName("WindowTitle")
        self.window_rect_label = QLabel("")
        self.window_rect_label.setObjectName("Muted")
        self.window_card.body_layout.addWidget(self.window_title_label)
        self.window_card.body_layout.addWidget(self.window_rect_label)
        left_column.addWidget(self.window_card)

        self.preview_card = GlassCard("")
        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(280)
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_card.body_layout.addWidget(self.preview_label)
        left_column.addWidget(self.preview_card)

        self.result_card = GlassCard("")
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_card.body_layout.addWidget(self.result_text)
        left_column.addWidget(self.result_card, 1)

        right_column = QVBoxLayout()
        right_column.setSpacing(16)
        content.addLayout(right_column, 2)

        self.log_card = GlassCard("")
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(1200)
        self.log_card.body_layout.addWidget(self.log_text)
        right_column.addWidget(self.log_card, 1)

        footer = QFrame()
        footer.setObjectName("Footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(12)
        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusPill")
        self.footer_hint = QLabel("")
        self.footer_hint.setObjectName("Muted")
        footer_layout.addWidget(self.status_label)
        footer_layout.addWidget(self.footer_hint, 1)
        root.addWidget(footer)

    def _apply_styles(self) -> None:
        stylesheet = """
            QWidget {
                font-family: "SF Pro Display", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            #HeroTitle {
                font-size: 30px;
                font-weight: 700;
            }
            #CardTitle {
                font-size: 16px;
                font-weight: 600;
            }
            #WindowTitle {
                font-size: 20px;
                font-weight: 650;
            }
            QPushButton {
                border-radius: 16px;
                padding: 10px 16px;
            }
            QPushButton[compact="true"] {
                min-width: 44px;
                max-width: 44px;
                min-height: 44px;
                max-height: 44px;
                padding: 0;
                font-size: 18px;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
                border-radius: 16px;
                padding: 10px 12px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
            }
        """
        if self.theme_mode == "dark":
            stylesheet += """
            QWidget {
                background: #0b1220;
                color: #e5edf8;
            }
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #08101d, stop:1 #111a2e);
            }
            #Hero, #Footer, #GlassCard {
                background: rgba(15, 23, 42, 0.78);
                border: 1px solid rgba(71, 85, 105, 0.72);
                border-radius: 24px;
            }
            #HeroTitle, #CardTitle, #WindowTitle {
                color: #f8fafc;
            }
            #HeroSubtitle, #Muted {
                color: #94a3b8;
            }
            #PreviewLabel {
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(15,23,42,0.88), stop:1 rgba(30,41,59,0.9));
                border: 1px dashed rgba(148, 163, 184, 0.38);
            }
            #StatusPill {
                background: rgba(255, 216, 77, 0.14);
                border: 1px solid rgba(255, 216, 77, 0.48);
                border-radius: 999px;
                padding: 6px 12px;
                color: #ffe082;
                font-weight: 600;
            }
            QPushButton {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(71, 85, 105, 0.8);
                color: #e5edf8;
            }
            QPushButton:hover {
                background: rgba(30, 41, 59, 0.95);
                border-color: rgba(125, 211, 252, 0.42);
            }
            QPushButton:pressed {
                background: rgba(51, 65, 85, 0.98);
            }
            QPushButton[primary="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffd84d, stop:1 #ffbe3d);
                border: 1px solid rgba(255, 193, 56, 0.92);
                color: #493600;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
                background: rgba(15, 23, 42, 0.88);
                border: 1px solid rgba(71, 85, 105, 0.82);
                color: #e5edf8;
                selection-background-color: rgba(96, 165, 250, 0.3);
            }
            QCheckBox::indicator {
                border: 1px solid rgba(100, 116, 139, 0.95);
                background: rgba(15, 23, 42, 0.95);
            }
            QCheckBox::indicator:checked {
                background: #ffd84d;
                border-color: #ffbe3d;
            }
            """
        else:
            stylesheet += """
            QWidget {
                background: #eef2f7;
                color: #172033;
            }
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eff4fb, stop:1 #f8fafc);
            }
            #Hero, #Footer, #GlassCard {
                background: rgba(255, 255, 255, 0.78);
                border: 1px solid rgba(255, 255, 255, 0.95);
                border-radius: 24px;
            }
            #HeroTitle {
                font-size: 30px;
                font-weight: 700;
                color: #0f1728;
            }
            #HeroSubtitle, #Muted {
                color: #63708a;
            }
            #CardTitle {
                font-size: 16px;
                font-weight: 600;
                color: #111827;
            }
            #WindowTitle {
                font-size: 20px;
                font-weight: 650;
            }
            #PreviewLabel {
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.92), stop:1 rgba(241,245,249,0.92));
                border: 1px dashed rgba(148, 163, 184, 0.55);
            }
            #StatusPill {
                background: rgba(255, 216, 77, 0.18);
                border: 1px solid rgba(255, 216, 77, 0.55);
                border-radius: 999px;
                padding: 6px 12px;
                color: #735500;
                font-weight: 600;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.88);
                border: 1px solid rgba(203, 213, 225, 0.85);
                border-radius: 16px;
                padding: 10px 16px;
                color: #0f172a;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.98);
                border-color: rgba(96, 165, 250, 0.45);
            }
            QPushButton:pressed {
                background: rgba(226, 232, 240, 0.95);
            }
            QPushButton[primary="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffd84d, stop:1 #ffbe3d);
                border: 1px solid rgba(255, 193, 56, 0.92);
                color: #493600;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
                background: rgba(255, 255, 255, 0.88);
                border: 1px solid rgba(203, 213, 225, 0.9);
                border-radius: 16px;
                padding: 10px 12px;
                selection-background-color: rgba(96, 165, 250, 0.22);
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid rgba(148, 163, 184, 0.95);
                background: rgba(255,255,255,0.95);
            }
            QCheckBox::indicator:checked {
                background: #ffd84d;
                border-color: #ffbe3d;
            }
            """
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet(stylesheet)

    def _apply_texts(self) -> None:
        self.setWindowTitle(self.tr_text("app_title"))
        self.hero_title.setText(self.tr_text("app_title"))
        self.hero_subtitle.setText(self.tr_text("hero_subtitle"))
        self.select_window_button.setText(self.tr_text("select_window"))
        self.analyze_button.setText(self.tr_text("analyze_once"))
        self.auto_button.setText(self.tr_text("auto_stop") if self.is_auto_running else self.tr_text("auto_start"))
        self.locator_button.setText(self.tr_text("button_locator"))
        self.capture_button.setText(self.tr_text("save_screenshot"))
        self.settings_button.setText(self.tr_text("settings"))
        self.language_button.setText(self.tr_text("language_button"))
        self.language_button.setToolTip(self.tr_text("language_tooltip"))
        self.theme_button.setText("\u2600" if self.theme_mode == "light" else "\u263E")
        self.theme_button.setToolTip(
            self.tr_text("theme_tooltip_light") if self.theme_mode == "light" else self.tr_text("theme_tooltip_dark")
        )
        self._sync_header_button_widths()
        self.window_card.title_label.setText(self.tr_text("current_window_card"))
        self.preview_card.title_label.setText(self.tr_text("preview_card"))
        self.result_card.title_label.setText(self.tr_text("result_card"))
        self.log_card.title_label.setText(self.tr_text("log_card"))
        self.result_text.setPlaceholderText(self.tr_text("result_placeholder"))
        self.footer_hint.setText(self.tr_text("footer_hint"))
        self._refresh_window_summary()
        if self.preview_pixmap is None:
            self.preview_label.setText(self.tr_text("preview_empty"))
        if self.button_locator_dialog is not None:
            self.button_locator_dialog.apply_language(self.ui_language)

    def _sync_header_button_widths(self) -> None:
        for button in getattr(self, "primary_header_buttons", []):
            content_width = button.fontMetrics().horizontalAdvance(button.text()) + 40
            button.setMinimumWidth(max(116, content_width))

    def _refresh_window_summary(self) -> None:
        if self.selected_window is None:
            self.window_title_label.setText(self.tr_text("window_not_selected"))
            self.window_rect_label.setText(self.tr_text("window_rect_empty"))
            return
        rect = self.selected_window.rect
        self.window_title_label.setText(f"{self.selected_window.title}  (HWND: {self.selected_window.hwnd})")
        self.window_rect_label.setText(
            self.tr_text("window_rect", left=rect[0], top=rect[1], right=rect[2], bottom=rect[3])
        )

    def toggle_language(self) -> None:
        self.ui_language = "en" if self.ui_language == "zh" else "zh"
        self.config_data.ui_language = self.ui_language
        save_config(self.config_data)
        self._apply_texts()
        self.signals.status.emit(self.tr_text("status_ready"))
        self.log(self.tr_text("language_changed"))

    def toggle_theme(self) -> None:
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        self.config_data.theme_mode = self.theme_mode
        save_config(self.config_data)
        self._apply_styles()
        self._apply_texts()
        self.log(
            self.tr_text("theme_changed_dark") if self.theme_mode == "dark" else self.tr_text("theme_changed_light")
        )

    def _make_button(self, text: str, callback, primary: bool = False, compact: bool = False) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setProperty("primary", True)
        if compact:
            button.setProperty("compact", True)
        button.clicked.connect(callback)
        return button

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.signals.log.emit(f"[{timestamp}] {message}")

    def log_tr(self, key: str, **kwargs) -> None:
        self.log(self.tr_text(key, **kwargs))

    def status_tr(self, key: str, **kwargs) -> None:
        self.signals.status.emit(self.tr_text(key, **kwargs))

    def _append_log(self, line: str) -> None:
        self.log_text.appendPlainText(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _set_status_text(self, message: str) -> None:
        self.status_label.setText(message)

    def _set_result_text(self, content: str) -> None:
        self.result_text.setPlainText(content)

    def _set_preview_image(self, image: Image.Image) -> None:
        pixmap = pil_to_pixmap(image, 620, 300)
        self.preview_pixmap = pixmap
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")

    def _show_error_dialog(self, message: str) -> None:
        QMessageBox.critical(self, self.tr_text("error_title"), message)

    def _set_busy_state(self, busy: bool) -> None:
        self.busy = busy
        self.analyze_button.setEnabled(not busy and not self.is_auto_running)
        self.capture_button.setEnabled(not busy and not self.is_auto_running)
        self.select_window_button.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.locator_button.setEnabled(not busy)

    def _set_auto_running_state(self, running: bool) -> None:
        self.is_auto_running = running
        self.auto_button.setText(self.tr_text("auto_stop") if running else self.tr_text("auto_start"))
        self.analyze_button.setEnabled(not running and not self.busy)
        self.capture_button.setEnabled(not running and not self.busy)

    def _refresh_button_locator_dialog(self) -> None:
        if self.button_locator_dialog is not None:
            self.button_locator_dialog.refresh()

    def _log_auto_mode(self) -> None:
        auto_answer_status = self.tr_text("on") if self.config_data.auto_answer else self.tr_text("off")
        auto_submit_status = self.tr_text("on") if self.config_data.auto_submit else self.tr_text("off")
        self.log_tr("auto_mode_log", auto_answer=auto_answer_status, auto_submit=auto_submit_status)

    def _require_window(self) -> bool:
        if self.selected_window is not None:
            return True
        QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("missing_window_msg"))
        self.open_window_picker()
        return False

    def _refresh_selected_window_rect(self) -> Tuple[int, int, int, int]:
        if not self.selected_window:
            raise RuntimeError("还没有选择目标窗口。")
        self.selected_window.rect = get_window_rect(self.selected_window.hwnd)
        rect = self.selected_window.rect
        self._refresh_window_summary()
        return rect

    def _capture_selected_window(self) -> Image.Image:
        if not self.selected_window:
            raise RuntimeError("还没有选择目标窗口。")
        image = capture_window(self.selected_window.hwnd)
        self._refresh_selected_window_rect()
        self.signals.preview.emit(image)
        return image

    def _open_crosshair_picker(self, callback, status_message: str, log_message: str, label: str) -> None:
        if self.current_picker is not None:
            self.current_picker.close()
        self.current_picker = CrosshairPicker(label, callback)
        self.signals.status.emit(status_message)
        self.log(log_message)

    def open_window_picker(self) -> None:
        self._open_crosshair_picker(
            self._on_window_picked,
            self.tr_text("crosshair_pick_window_status"),
            self.tr_text("crosshair_pick_window_log"),
            "窗口",
        )

    def _on_window_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        hwnd = get_root_window_from_point(screen_x, screen_y)
        if not hwnd:
            self.log_tr("window_pick_failed_log")
            self.status_tr("window_pick_failed_status")
            return
        if not is_window_visible(hwnd):
            self.log_tr("window_invisible_log")
            self.status_tr("window_invisible_status")
            return
        title = get_window_title(hwnd) or "(无标题窗口)"
        rect = get_window_rect(hwnd)
        self.selected_window = WindowInfo(hwnd=hwnd, title=title, rect=rect)
        self._refresh_window_summary()
        self.log_tr("window_selected_log", title=title, hwnd=hwnd)
        self.status_tr("window_selected_status")
        self.signals.locator_refresh.emit()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config_data, self.ui_language, self)
        if dialog.exec() != QDialog.Accepted:
            return
        config = dialog.to_config(self.config_data)
        config.option_a_offset = normalize_point(config.option_a_offset)
        config.option_b_offset = normalize_point(config.option_b_offset)
        config.option_c_offset = normalize_point(config.option_c_offset)
        config.option_d_offset = normalize_point(config.option_d_offset)
        config.next_button_offset = normalize_point(config.next_button_offset)
        config.submit_button_offset = normalize_point(config.submit_button_offset)
        config.ui_language = self.ui_language
        config.theme_mode = self.theme_mode
        self.config_data = config
        save_config(config)
        self.log(self.tr_text("settings_saved"))
        self._log_auto_mode()
        self.signals.locator_refresh.emit()
        self.signals.status.emit(self.tr_text("settings_updated"))

    def open_button_locator(self) -> None:
        if not self._require_window():
            return
        if self.button_locator_dialog is None:
            self.button_locator_dialog = ButtonLocatorDialog(self)
        self.button_locator_dialog.show()
        self.button_locator_dialog.raise_()
        self.button_locator_dialog.activateWindow()
        self.button_locator_dialog.refresh()
        self.signals.status.emit(self.tr_text("locator_opened"))

    def pick_option_position(self, option_char: str) -> None:
        if not self._require_window():
            return
        option_key = option_char.upper()
        self._open_crosshair_picker(
            lambda x, y: self._on_option_picked(option_key, x, y),
            self.tr_text("pick_option_status", option=option_key),
            self.tr_text("pick_option_log", option=option_key),
            option_key,
        )

    def pick_next_button_position(self) -> None:
        if not self._require_window():
            return
        self._open_crosshair_picker(
            self._on_next_button_picked,
            self.tr_text("pick_next_status"),
            self.tr_text("pick_next_log"),
            "下一题",
        )

    def pick_submit_button_position(self) -> None:
        if not self._require_window():
            return
        self._open_crosshair_picker(
            self._on_submit_button_picked,
            self.tr_text("pick_submit_status"),
            self.tr_text("pick_submit_log"),
            "提交",
        )

    def _on_option_picked(self, option_char: str, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        button_name = {
            "A": self.tr_text("option_a"),
            "B": self.tr_text("option_b"),
            "C": self.tr_text("option_c"),
            "D": self.tr_text("option_d"),
        }.get(option_char, option_char)
        self._save_button_offset(f"option_{option_char.lower()}_offset", button_name, screen_x, screen_y)

    def _on_next_button_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        self._save_button_offset("next_button_offset", self.tr_text("next_button"), screen_x, screen_y)

    def _on_submit_button_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        self._save_button_offset("submit_button_offset", self.tr_text("submit_button"), screen_x, screen_y)

    def _save_button_offset(self, attr_name: str, button_name: str, screen_x: int, screen_y: int) -> None:
        if not self._require_window():
            return
        rect = self._refresh_selected_window_rect()
        if not point_in_rect(screen_x, screen_y, rect):
            self.log_tr("button_position_failed_log", button_name=button_name, x=screen_x, y=screen_y)
            self.status_tr("button_position_failed_status", button_name=button_name)
            self.signals.error.emit(self.tr_text("button_position_failed_error"))
            self.signals.locator_refresh.emit()
            return
        offset = (screen_x - rect[0], screen_y - rect[1])
        setattr(self.config_data, attr_name, offset)
        save_config(self.config_data)
        self.log_tr("button_position_saved_log", button_name=button_name, x=screen_x, y=screen_y, offset=offset)
        self.status_tr("button_position_saved_status", button_name=button_name)
        self.signals.locator_refresh.emit()

    def clear_all_option_positions(self) -> None:
        self.config_data.option_a_offset = None
        self.config_data.option_b_offset = None
        self.config_data.option_c_offset = None
        self.config_data.option_d_offset = None
        save_config(self.config_data)
        self.log_tr("options_cleared_log")
        self.status_tr("options_cleared_status")
        self.signals.locator_refresh.emit()

    def clear_next_button_position(self) -> None:
        self.config_data.next_button_offset = None
        save_config(self.config_data)
        self.log_tr("next_cleared_log")
        self.status_tr("next_cleared_status")
        self.signals.locator_refresh.emit()

    def clear_submit_button_position(self) -> None:
        self.config_data.submit_button_offset = None
        save_config(self.config_data)
        self.log_tr("submit_cleared_log")
        self.status_tr("submit_cleared_status")
        self.signals.locator_refresh.emit()

    def toggle_auto_answer(self) -> None:
        if self.is_auto_running:
            self.stop_auto_answer()
        else:
            self.start_auto_answer()

    def start_auto_answer(self) -> None:
        if self.busy:
            QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("busy_msg"))
            return
        if not self._require_window():
            return
        if not self.config_data.api_key.strip() or not self.config_data.model.strip():
            QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("missing_api_msg"))
            self.open_settings()
            return
        self.is_auto_running = True
        self.signals.auto_state.emit(True)
        self.signals.status.emit(self.tr_text("auto_started"))
        self.log_tr("auto_loop_started_log")
        threading.Thread(target=self._auto_answer_worker, daemon=True).start()

    def stop_auto_answer(self) -> None:
        self.is_auto_running = False
        self.signals.auto_state.emit(False)
        self.signals.status.emit(self.tr_text("auto_stopped"))
        self.log_tr("auto_manual_stop_log")

    def _click_next_question(self) -> None:
        next_pos = find_next_question_btn(self.selected_window.rect, self.config_data.next_button_offset)
        next_source = (
            self.tr_text("custom_position_source")
            if self.config_data.next_button_offset is not None
            else self.tr_text("default_position_source")
        )
        self.log_tr("next_click_log", source=next_source, pos=next_pos)
        click_at(*next_pos, settle_delay=0.35)

    def _check_if_last_question(self, _ai_response: str) -> bool:
        return False

    def _click_answer_options(self, image: Image.Image, answer_items: List[Tuple[str, str]], stop_on_missing: bool) -> bool:
        is_multi_select = len(answer_items) > 1
        for option_char, _option_content in answer_items:
            option_offset = get_option_offset(self.config_data, option_char)
            option_pos = find_option_position(self.selected_window.rect, image, option_char, option_offset)
            if not option_pos:
                if stop_on_missing:
                    self.log_tr("option_missing_auto_log", option=option_char)
                    self.is_auto_running = False
                    self.status_tr("option_missing_auto_status", option=option_char)
                else:
                    self.log_tr("option_missing_single_log", option=option_char)
                return False
            option_source = (
                self.tr_text("custom_position_source")
                if option_offset is not None
                else self.tr_text("default_position_source")
            )
            self.log_tr("option_click_log", option=option_char, source=option_source, pos=option_pos)
            click_at(*option_pos, settle_delay=0.18 if is_multi_select else 0.28)
            time.sleep(0.18 if is_multi_select else 0.38)
        if is_multi_select:
            time.sleep(0.35)
        return True

    def _auto_answer_worker(self) -> None:
        try:
            question_count = 0
            while self.is_auto_running and self.config_data.auto_answer:
                self.status_tr("processing_question_status", number=question_count + 1)
                self.log_tr("processing_question_log", number=question_count + 1)
                image = self._capture_selected_window()
                self.log_tr("capture_size_log", width=image.size[0], height=image.size[1])
                client = AIClient(self.config_data)
                ai_response = client.analyze_window_image(image)
                self.signals.result.emit(ai_response)
                self.log_tr("ai_analysis_complete_log")

                answer_items = parse_ai_answers(ai_response)
                if not answer_items:
                    preview_text = ai_response.strip().replace("\n", " ")
                    self.log_tr("answer_parse_failed_log", preview=preview_text[:120])
                    self._click_next_question()
                    continue

                self.log_tr("answers_parsed_log", answers=format_answer_items(answer_items))
                if not self._click_answer_options(image, answer_items, stop_on_missing=True):
                    break

                question_count += 1
                if self._check_if_last_question(ai_response):
                    self.log_tr("last_question_log")
                    if self.config_data.auto_submit:
                        self.log_tr("auto_submit_log")
                        submit_pos = find_submit_btn(self.selected_window.rect, self.config_data.submit_button_offset)
                        click_at(*submit_pos, settle_delay=0.4)
                        submit_source = (
                            self.tr_text("custom_position_source")
                            if self.config_data.submit_button_offset is not None
                            else self.tr_text("default_position_source")
                        )
                        self.log_tr("submit_click_log", source=submit_source, pos=submit_pos)
                    break

                self._click_next_question()
                time.sleep(1.2)

            self.is_auto_running = False
            self.signals.auto_state.emit(False)
            if question_count > 0:
                self.status_tr("auto_finished_status", count=question_count)
                self.log_tr("auto_finished_log", count=question_count)
            else:
                self.status_tr("auto_no_questions_status")
        except Exception as exc:
            self.is_auto_running = False
            self.signals.auto_state.emit(False)
            self.log_tr("auto_exception_log", error=exc)
            self.status_tr("auto_exception_status")
            self.signals.error.emit(str(exc))

    def save_screenshot(self) -> None:
        if self.busy:
            QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("busy_msg"))
            return
        if not self._require_window():
            return
        self.signals.busy.emit(True)
        threading.Thread(target=self._save_capture_worker, daemon=True).start()

    def _save_capture_worker(self) -> None:
        try:
            self.status_tr("saving_capture_status")
            self.log_tr("capture_start_log")
            image = self._capture_selected_window()
            captures_dir = APP_DIR / "captures"
            captures_dir.mkdir(exist_ok=True)
            filename = captures_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            image.save(filename)
            self.log_tr("capture_saved_log", path=filename)
            self.signals.status.emit(self.tr_text("screenshot_saved"))
        except Exception as exc:
            self.log_tr("capture_failed_log", error=exc)
            self.signals.status.emit(self.tr_text("screenshot_failed"))
        finally:
            self.signals.busy.emit(False)

    def start_analysis(self) -> None:
        if self.busy:
            QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("busy_msg"))
            return
        if not self._require_window():
            return
        if not self.config_data.api_key.strip() or not self.config_data.model.strip():
            QMessageBox.information(self, self.tr_text("info_title"), self.tr_text("missing_api_msg"))
            self.open_settings()
            return
        self.signals.busy.emit(True)
        self.status_tr("analysis_running_status")
        threading.Thread(target=self._analyze_worker, daemon=True).start()

    def _analyze_worker(self) -> None:
        try:
            self.log_tr("analysis_start_log")
            image = self._capture_selected_window()
            self.log_tr("analysis_capture_size_log", width=image.size[0], height=image.size[1])
            self.log_tr("analysis_call_model_log")
            client = AIClient(self.config_data)
            result = client.analyze_window_image(image)
            self.signals.result.emit(result)
            if self.config_data.auto_answer:
                answer_items = parse_ai_answers(result)
                if answer_items:
                    self.log_tr("analysis_auto_select_log", answers=format_answer_items(answer_items))
                    self._click_answer_options(image, answer_items, stop_on_missing=False)
                else:
                    preview_text = result.strip().replace("\n", " ")
                    self.log_tr("analysis_no_answer_log", preview=preview_text[:120])
            self.log_tr("analysis_complete_log")
            self.signals.status.emit(self.tr_text("analysis_done"))
        except Exception as exc:
            self.signals.result.emit("")
            self.log_tr("analysis_failed_log", error=exc)
            self.signals.status.emit(self.tr_text("analysis_failed"))
            self.signals.error.emit(str(exc))
        finally:
            self.signals.busy.emit(False)

    def closeEvent(self, event) -> None:
        self.is_auto_running = False
        if self.current_picker is not None:
            self.current_picker.close()
        if self.button_locator_dialog is not None:
            self.button_locator_dialog.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    font = QFont("SF Pro Display")
    font.setPointSize(10)
    app.setFont(font)
    window = QtMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
