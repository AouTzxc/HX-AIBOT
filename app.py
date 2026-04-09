import base64
import ctypes
import io
import json
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict
import re

import requests
import tkinter as tk
from PIL import Image, ImageGrab, ImageTk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# 新增鼠标操作相关库
import pyautogui
# 禁用pyautogui的失败安全（防止鼠标移到角落终止程序）
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.2  # 点击间隔

try:
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    cv2 = None
    np = None
    RapidOCR = None

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"
APP_ICON_FILE = APP_DIR / "HXlogo.ico"
_OCR_ENGINE = None
_OCR_ENGINE_ERROR: Optional[str] = None

# 旧版提示词（必须保留，代码会调用，不能删！）
LEGACY_ANALYSIS_PROMPT = """请读取这张应用窗口截图，并按下面结构输出：
1. 可见文字：尽量逐字转写窗口内能看清的文字。
2. 内容概述：总结这个窗口当前在展示什么。
3. 关键元素：列出可见按钮、选项、输入框、状态信息。
4. 需要人工处理：列出需要用户自己决定的内容。

注意：
- 只基于截图内容回答。
- 不要声称已经点击、提交或执行了任何操作。
- 不要代替用户做决定。"""

# 新版：只识别题目 + 给出答案 + 详细解析（增强答案提取）
DEFAULT_ANALYSIS_PROMPT = """请读取这张应用窗口截图，只提取题目相关内容，并严格按下面结构输出：
1. 题目：
- 只保留当前题目的题干。
- 如果题干看不全，明确说明“题干显示不完整”。

2. 选项：
- 逐行列出当前题目的可见选项，例如 A、B、C、D。
- 如果有缺失选项，明确标注“未完整显示”。

3. 答案：
- 直接给出本题的正确答案（选项+内容）。
- 单选题格式示例：A、答案内容。
- 多选题必须列出全部正确选项，格式示例：A、答案内容；C、答案内容；D、答案内容。

4. 解析：
- 详细说明答案依据，清晰易懂。

注意：
- 忽略页面上的倒计时、提交按钮、题号跳转、上下题按钮等无关信息。
- 只基于截图内容回答。
- 必须直接给出正确答案。
- 如果是多选题，绝不能只返回其中一个选项。
- 答案部分只能包含选项字母+内容，不能有多余文字。"""

DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
SYSTEM_PROMPT = (
    "你是一个专业解题助手。你的任务是从截图里提取题目，给出正确答案和详细解析，"
    "直接输出答案，不回避、不模糊。"
    "答案部分必须严格按照 选项字母+内容 的格式输出，例如 A、答案内容。"
    "如果题目是多选题，必须一次性列出全部正确选项，不能只给一个。"
)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class AppConfig:
    api_url: str = DEFAULT_ENDPOINT
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    analysis_prompt: str = DEFAULT_ANALYSIS_PROMPT
    auto_submit: bool = False  # 新增自动提交开关
    auto_answer: bool = True   # 新增自动答题开关
    ui_language: str = "zh"
    theme_mode: str = "light"
    option_a_offset: Optional[Tuple[int, int]] = None
    option_b_offset: Optional[Tuple[int, int]] = None
    option_c_offset: Optional[Tuple[int, int]] = None
    option_d_offset: Optional[Tuple[int, int]] = None
    next_button_offset: Optional[Tuple[int, int]] = None
    submit_button_offset: Optional[Tuple[int, int]] = None


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    rect: Tuple[int, int, int, int]


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def load_config() -> AppConfig:
    if not SETTINGS_FILE.exists():
        config = AppConfig()
        save_config(config)
        return config

    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return AppConfig()

    config = AppConfig()
    for field_name in asdict(config).keys():
        if field_name in payload:
            setattr(config, field_name, payload[field_name])
    config.option_a_offset = normalize_point(config.option_a_offset)
    config.option_b_offset = normalize_point(config.option_b_offset)
    config.option_c_offset = normalize_point(config.option_c_offset)
    config.option_d_offset = normalize_point(config.option_d_offset)
    config.next_button_offset = normalize_point(config.next_button_offset)
    config.submit_button_offset = normalize_point(config.submit_button_offset)
    config.ui_language = normalize_ui_language(getattr(config, "ui_language", "zh"))
    config.theme_mode = normalize_theme_mode(getattr(config, "theme_mode", "light"))
    if not config.analysis_prompt.strip() or config.analysis_prompt.strip() == LEGACY_ANALYSIS_PROMPT.strip():
        config.analysis_prompt = DEFAULT_ANALYSIS_PROMPT
    if "多选题" not in config.analysis_prompt and "答案部分只能包含选项字母+内容" in config.analysis_prompt:
        config.analysis_prompt = DEFAULT_ANALYSIS_PROMPT
    return config


def save_config(config: AppConfig) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_point(value) -> Optional[Tuple[int, int]]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def normalize_ui_language(value) -> str:
    if isinstance(value, str) and value.lower().startswith("en"):
        return "en"
    return "zh"


def normalize_theme_mode(value) -> str:
    if isinstance(value, str) and value.lower() == "dark":
        return "dark"
    return "light"


def format_offset_text(offset: Optional[Tuple[int, int]]) -> str:
    if offset is None:
        return "未设置"
    return f"窗口内偏移: ({offset[0]}, {offset[1]})"


def get_option_offset(config: AppConfig, option_char: str) -> Optional[Tuple[int, int]]:
    option_key = option_char.upper()
    field_name = f"option_{option_key.lower()}_offset"
    return normalize_point(getattr(config, field_name, None))


def format_answer_items(answer_items: List[Tuple[str, str]]) -> str:
    if not answer_items:
        return ""
    parts: List[str] = []
    for option_char, option_content in answer_items:
        parts.append(option_char if not option_content else f"{option_char} - {option_content}")
    return " | ".join(parts)


def get_root_window_from_point(screen_x: int, screen_y: int) -> Optional[int]:
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.restype = ctypes.c_void_p
    user32.GetAncestor.restype = ctypes.c_void_p

    point = POINT(screen_x, screen_y)
    hwnd = user32.WindowFromPoint(point)
    if not hwnd:
        return None

    ga_root = 2
    root_hwnd = user32.GetAncestor(hwnd, ga_root)
    return int(root_hwnd or hwnd)


def get_window_title(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("无法读取目标窗口位置。")
    return rect.left, rect.top, rect.right, rect.bottom


def is_window_visible(hwnd: int) -> bool:
    return bool(ctypes.windll.user32.IsWindowVisible(hwnd))


def focus_window(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    try:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def capture_window(hwnd: int) -> Image.Image:
    focus_window(hwnd)
    time.sleep(0.15)

    left, top, right, bottom = get_window_rect(hwnd)
    width = max(0, right - left)
    height = max(0, bottom - top)
    if width < 50 or height < 50:
        raise RuntimeError("目标窗口尺寸过小，无法截图。")

    image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
    return image


def prepare_image_for_upload(image: Image.Image, max_side: int = 1600) -> str:
    working = image.convert("RGB")
    if max(working.size) > max_side:
        working.thumbnail((max_side, max_side))

    buffer = io.BytesIO()
    working.save(buffer, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def extract_message_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return "接口返回中没有 choices 字段。"

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part).strip()

    return str(content).strip()


# 新增：解析AI返回的答案
def _clean_option_content(text: str) -> str:
    return re.sub(r"^[\s\.,:;\)\]\-\u3001\uff0c\uff1a\uff1b\uff09]+", "", text or "").strip()


def parse_ai_answer(ai_response: str) -> Tuple[str, str]:
    """
    解析 AI 返回的答案，兼容以下常见格式：
    - 3. 答案：C、内容
    - 3. 答案：\nC. 内容
    - 答案是 C
    """
    response = ai_response.strip()
    if not response:
        return "", ""

    answer_keywords = (
        "\u7b54\u6848",
        "\u6b63\u786e\u7b54\u6848",
        "\u53c2\u8003\u7b54\u6848",
        "\u5e94\u9009",
        "\u9009\u62e9",
    )
    analysis_keywords = (
        "\u89e3\u6790",
        "\u7b54\u6848\u89e3\u6790",
        "\u89e3\u91ca",
    )
    inline_answer_pattern = re.compile(
        r"([A-D])(?:\s*[\.、,:\)\]\-，：）]\s*(.*))?$",
        re.IGNORECASE,
    )
    plain_option_pattern = re.compile(
        r"^\s*([A-D])(?:\s*[\.、,:\)\]\-，：）]\s*(.*))?\s*$",
        re.IGNORECASE,
    )

    def extract_from_line(line: str) -> Tuple[str, str]:
        inline_match = inline_answer_pattern.search(line)
        if not inline_match:
            return "", ""
        return inline_match.group(1).upper(), _clean_option_content(inline_match.group(2) or "")

    lines = [line.strip() for line in response.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not any(keyword in line for keyword in answer_keywords):
            continue

        option_char, option_content = extract_from_line(line)
        if option_char:
            return option_char, option_content

        for next_line in lines[index + 1:index + 4]:
            if any(keyword in next_line for keyword in analysis_keywords):
                break
            match = plain_option_pattern.match(next_line)
            if match:
                return match.group(1).upper(), _clean_option_content(match.group(2) or "")

    for line in lines[:6]:
        option_char, option_content = extract_from_line(line)
        if option_char:
            return option_char, option_content

    return "", ""


def _unique_option_sequence(option_chars: List[str]) -> List[str]:
    unique_chars: List[str] = []
    for option_char in option_chars:
        normalized = option_char.upper()
        if normalized in {"A", "B", "C", "D"} and normalized not in unique_chars:
            unique_chars.append(normalized)
    return unique_chars


def parse_ai_answers(ai_response: str) -> List[Tuple[str, str]]:
    """
    解析 AI 返回的答案，兼容单选与多选：
    - 3. 答案：C、内容
    - 3. 答案：A、内容；C、内容
    - 3. 答案：AC
    - 3. 答案：A/C/D
    """
    response = ai_response.strip()
    if not response:
        return []

    answer_keywords = ("答案", "正确答案", "参考答案", "应选", "选择")
    analysis_keywords = ("解析", "答案解析", "解释")
    explicit_item_pattern = re.compile(
        r"([A-D])\s*[\.、,:：\)\]）/\-]\s*(.*?)(?=(?:[；;]\s*)?[A-D]\s*[\.、,:：\)\]）/\-]|$)",
        re.IGNORECASE,
    )
    compact_group_pattern = re.compile(r"(?<![A-Z])([A-D]{1,4})(?![A-Z])", re.IGNORECASE)

    def collect_from_answer_block(answer_block: str) -> List[Tuple[str, str]]:
        results: List[Tuple[str, str]] = []

        for match in explicit_item_pattern.finditer(answer_block):
            option_char = match.group(1).upper()
            option_content = _clean_option_content(match.group(2) or "")
            if option_char not in [item[0] for item in results]:
                results.append((option_char, option_content))

        compact_block = re.sub(r"[\s/、,，;；|+和及与]", "", answer_block.upper())
        pure_option_block = re.sub(r"(答案|正确答案|参考答案|应选|选择|[:：])", "", compact_block)
        if pure_option_block and set(pure_option_block).issubset({"A", "B", "C", "D"}):
            return [(letter, "") for letter in _unique_option_sequence(list(pure_option_block))]

        if results:
            suspicious_suffix = "".join(option_content for _, option_content in results if option_content)
            suspicious_suffix = re.sub(r"[\s/、,，;；|+和及与]", "", suspicious_suffix.upper())
            if suspicious_suffix and set(suspicious_suffix).issubset({"A", "B", "C", "D"}):
                merged_letters = _unique_option_sequence(
                    re.findall(r"[A-D]", "".join(option_char + option_content for option_char, option_content in results).upper())
                )
                if len(merged_letters) > len(results):
                    return [(letter, "") for letter in merged_letters]
            return results

        for match in compact_group_pattern.finditer(compact_block):
            letters = _unique_option_sequence(list(match.group(1)))
            if letters:
                return [(letter, "") for letter in letters]

        inline_letters = _unique_option_sequence(re.findall(r"[A-D]", answer_block.upper()))
        if inline_letters:
            return [(letter, "") for letter in inline_letters]

        return []

    lines = [line.strip() for line in response.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not any(keyword in line for keyword in answer_keywords):
            continue

        answer_lines = [line]
        for next_line in lines[index + 1:index + 5]:
            if any(keyword in next_line for keyword in analysis_keywords):
                break
            answer_lines.append(next_line)

        parsed_items = collect_from_answer_block("\n".join(answer_lines))
        if parsed_items:
            return parsed_items

    first_answer = parse_ai_answer(ai_response)
    if first_answer[0]:
        return [first_answer]

    return []


# 新增：在截图中定位选项位置
def find_option_position(
    window_rect: Tuple[int, int, int, int],
    image: Image.Image,
    target_option: str,
    saved_offset: Optional[Tuple[int, int]] = None,
) -> Optional[Tuple[int, int]]:
    """
    在窗口范围内查找目标选项的坐标
    window_rect: 窗口坐标 (left, top, right, bottom)
    image: 截图
    target_option: 目标选项内容
    返回：选项中心坐标 (x, y)
    """
    left, top, _, _ = window_rect

    detected_in_image = _ocr_detect_option_position(image, target_option)
    if detected_in_image is not None:
        return left + detected_in_image[0], top + detected_in_image[1]

    custom_position = _resolve_saved_button_position(window_rect, saved_offset)
    if custom_position is not None:
        return custom_position

    return None


# 新增：定位下一题按钮
def _resolve_saved_button_position(
    window_rect: Tuple[int, int, int, int],
    saved_offset: Optional[Tuple[int, int]],
) -> Optional[Tuple[int, int]]:
    if saved_offset is None:
        return None

    left, top, right, bottom = window_rect
    x = left + saved_offset[0]
    y = top + saved_offset[1]
    x = max(left, min(x, max(left, right - 1)))
    y = max(top, min(y, max(top, bottom - 1)))
    return x, y


def point_in_rect(screen_x: int, screen_y: int, rect: Tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = rect
    return left <= screen_x < right and top <= screen_y < bottom


def get_ocr_engine():
    global _OCR_ENGINE, _OCR_ENGINE_ERROR
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    if _OCR_ENGINE_ERROR is not None:
        return None
    if RapidOCR is None or cv2 is None or np is None:
        _OCR_ENGINE_ERROR = "OCR 依赖未安装"
        return None
    try:
        _OCR_ENGINE = RapidOCR()
    except Exception as exc:
        _OCR_ENGINE_ERROR = str(exc)
        return None
    return _OCR_ENGINE


def get_ocr_status() -> str:
    if get_ocr_engine() is not None:
        return "ready"
    return _OCR_ENGINE_ERROR or "OCR 不可用"


def _box_bounds(box) -> Tuple[int, int, int, int]:
    xs = [int(point[0]) for point in box]
    ys = [int(point[1]) for point in box]
    return min(xs), min(ys), max(xs), max(ys)


def _normalize_ocr_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).upper()


def _make_ocr_variants(image: Image.Image) -> List[Tuple[str, "np.ndarray"]]:
    if cv2 is None or np is None:
        return []

    rgb = image.convert("RGB")
    base = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    variants: List[Tuple[str, "np.ndarray"]] = [("base", base)]

    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    upscaled = cv2.resize(gray, None, fx=1.4, fy=1.4, interpolation=cv2.INTER_CUBIC)
    variants.append(("gray_upscaled", upscaled))

    _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("binary_otsu", binary))

    adaptive = cv2.adaptiveThreshold(
        upscaled,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    variants.append(("binary_adaptive", adaptive))
    return variants


def _ocr_detect_option_position(image: Image.Image, target_option: str) -> Optional[Tuple[int, int]]:
    engine = get_ocr_engine()
    if engine is None:
        return None

    option_key = target_option.upper()
    candidates: List[Tuple[float, Tuple[int, int]]] = []

    for variant_name, variant_image in _make_ocr_variants(image):
        try:
            result, _elapsed = engine(variant_image)
        except Exception:
            continue
        if not result:
            continue

        image_height, image_width = variant_image.shape[:2]
        scale_x = image.width / image_width
        scale_y = image.height / image_height

        for line in result:
            if not isinstance(line, (list, tuple)) or len(line) < 3:
                continue
            box, text, score = line[0], str(line[1]), float(line[2] or 0)
            normalized_text = _normalize_ocr_text(text)
            if not normalized_text:
                continue

            matches_prefix = normalized_text.startswith(option_key)
            matches_exact = normalized_text == option_key
            if not matches_prefix and not matches_exact:
                continue

            box_left, box_top, box_right, box_bottom = _box_bounds(box)
            box_left = int(box_left * scale_x)
            box_top = int(box_top * scale_y)
            box_right = int(box_right * scale_x)
            box_bottom = int(box_bottom * scale_y)

            if box_top < int(image.height * 0.12) or box_top > int(image.height * 0.92):
                continue
            if box_left > int(image.width * 0.72):
                continue

            click_x = max(8, min(image.width - 8, (box_left + box_right) // 2))
            click_y = max(8, min(image.height - 8, (box_top + box_bottom) // 2))

            priority = score
            if matches_prefix:
                priority += 0.6
            if matches_exact:
                priority += 0.2
            if variant_name == "base":
                priority += 0.1

            candidates.append((priority, (click_x, click_y)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def find_next_question_btn(
    window_rect: Tuple[int, int, int, int],
    saved_offset: Optional[Tuple[int, int]] = None,
) -> Tuple[int, int]:
    """
    定位下一题按钮坐标（简化实现，需根据实际界面调整）
    """
    custom_position = _resolve_saved_button_position(window_rect, saved_offset)
    if custom_position is not None:
        return custom_position

    left, top, right, bottom = window_rect
    # 假设下一题按钮在窗口右下角
    return (right - 100, bottom - 50)


# 新增：定位提交按钮
def find_submit_btn(
    window_rect: Tuple[int, int, int, int],
    saved_offset: Optional[Tuple[int, int]] = None,
) -> Tuple[int, int]:
    """
    定位提交按钮坐标（简化实现，需根据实际界面调整）
    """
    custom_position = _resolve_saved_button_position(window_rect, saved_offset)
    if custom_position is not None:
        return custom_position

    left, top, right, bottom = window_rect
    # 假设提交按钮在窗口底部中间
    return (left + (right - left) // 2, bottom - 80)


# 新增：模拟点击
def click_at(x: int, y: int, settle_delay: float = 0.3) -> None:
    """模拟鼠标点击指定坐标"""
    pyautogui.moveTo(x, y, duration=0.08)
    pyautogui.click(x, y)
    time.sleep(settle_delay)


class AIClient:
    def __init__(self, config: AppConfig):
        self.config = config

    def analyze_window_image(self, image: Image.Image) -> str:
        if not self.config.api_key.strip():
            raise RuntimeError("请先在设置中填写 API Key。")
        if not self.config.model.strip():
            raise RuntimeError("请先在设置中填写模型 ID。")

        api_url = self.config.api_url.strip().rstrip("/")
        if not api_url.endswith("/chat/completions"):
            api_url = f"{api_url}/chat/completions"

        payload = {
            "model": self.config.model.strip(),
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.config.analysis_prompt.strip()},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": prepare_image_for_upload(image),
                            },
                        },
                    ],
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key.strip()}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        if not response.ok:
            body = response.text[:500].strip()
            raise RuntimeError(f"接口调用失败：HTTP {response.status_code}\n{body}")

        data = response.json()
        return extract_message_content(data)


class WindowPicker(tk.Toplevel):
    def __init__(self, master: tk.Tk, on_pick: Callable[[int, int], None], label: str = ""):
        super().__init__(master)
        self.on_pick = on_pick
        self.configure(bg="#101114")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.72)
        self.geometry("58x58+200+200")

        canvas = tk.Canvas(
            self,
            width=58,
            height=58,
            bg="#101114",
            highlightthickness=0,
            cursor="crosshair",
        )
        canvas.pack(fill="both", expand=True)
        canvas.create_oval(7, 7, 51, 51, outline="#ffd84d", width=2)
        canvas.create_line(29, 8, 29, 50, fill="#ffd84d", width=2)
        canvas.create_line(8, 29, 50, 29, fill="#ffd84d", width=2)
        canvas.create_oval(24, 24, 34, 34, outline="#fff1a8", width=1)
        if label:
            canvas.create_text(29, 51, text=label, fill="#fff6c4", font=("Segoe UI", 7, "bold"))

        self._drag_offset_x = 0
        self._drag_offset_y = 0

        canvas.bind("<ButtonPress-1>", self._start_drag)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._finish_drag)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Button-3>", lambda _event: self.destroy())

    def _start_drag(self, event) -> None:
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

    def _on_drag(self, event) -> None:
        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self.geometry(f"+{x}+{y}")

    def _finish_drag(self, event) -> None:
        screen_x = event.x_root
        screen_y = event.y_root
        self.destroy()
        self.on_pick(screen_x, screen_y)


class ButtonLocatorDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, app: "MainApp"):
        super().__init__(master)
        self.app = app
        self.title("按钮定位")
        if APP_ICON_FILE.exists():
            try:
                self.iconbitmap(str(APP_ICON_FILE))
            except Exception:
                pass
        self.resizable(False, False)
        self.transient(master)

        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="用十字准星记录目标窗口里的按钮位置，保存的是相对窗口左上角的偏移。",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        self.window_var = tk.StringVar()
        self.option_a_var = tk.StringVar()
        self.option_b_var = tk.StringVar()
        self.option_c_var = tk.StringVar()
        self.option_d_var = tk.StringVar()
        self.next_var = tk.StringVar()
        self.submit_var = tk.StringVar()

        ttk.Label(container, textvariable=self.window_var).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(10, 12)
        )

        ttk.Label(container, text="选项 A").grid(row=2, column=0, sticky="w")
        ttk.Label(container, textvariable=self.option_a_var).grid(row=2, column=1, sticky="w", padx=(10, 10))
        ttk.Button(container, text="设置 A", command=lambda: self.app.pick_option_position("A")).grid(
            row=2, column=2, sticky="e"
        )

        ttk.Label(container, text="选项 B").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Label(container, textvariable=self.option_b_var).grid(
            row=3, column=1, sticky="w", padx=(10, 10), pady=(10, 0)
        )
        ttk.Button(container, text="设置 B", command=lambda: self.app.pick_option_position("B")).grid(
            row=3, column=2, sticky="e", pady=(10, 0)
        )

        ttk.Label(container, text="选项 C").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Label(container, textvariable=self.option_c_var).grid(
            row=4, column=1, sticky="w", padx=(10, 10), pady=(10, 0)
        )
        ttk.Button(container, text="设置 C", command=lambda: self.app.pick_option_position("C")).grid(
            row=4, column=2, sticky="e", pady=(10, 0)
        )

        ttk.Label(container, text="选项 D").grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Label(container, textvariable=self.option_d_var).grid(
            row=5, column=1, sticky="w", padx=(10, 10), pady=(10, 0)
        )
        ttk.Button(container, text="设置 D", command=lambda: self.app.pick_option_position("D")).grid(
            row=5, column=2, sticky="e", pady=(10, 0)
        )

        ttk.Separator(container, orient="horizontal").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(12, 8)
        )

        ttk.Label(container, text="下一题按钮").grid(row=7, column=0, sticky="w")
        ttk.Label(container, textvariable=self.next_var).grid(row=7, column=1, sticky="w", padx=(10, 10))
        ttk.Button(container, text="设置下一题", command=self.app.pick_next_button_position).grid(
            row=7, column=2, sticky="e"
        )

        ttk.Label(container, text="提交按钮").grid(row=8, column=0, sticky="w", pady=(10, 0))
        ttk.Label(container, textvariable=self.submit_var).grid(
            row=8, column=1, sticky="w", padx=(10, 10), pady=(10, 0)
        )
        ttk.Button(container, text="设置提交", command=self.app.pick_submit_button_position).grid(
            row=8, column=2, sticky="e", pady=(10, 0)
        )

        action_row = ttk.Frame(container)
        action_row.grid(row=9, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(action_row, text="清空 A-D", command=self.app.clear_all_option_positions).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(action_row, text="清空下一题", command=self.app.clear_next_button_position).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(action_row, text="清空提交", command=self.app.clear_submit_button_position).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(action_row, text="关闭", command=self._close).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.refresh()

    def refresh(self) -> None:
        window_text = "当前目标窗口：未选择"
        if self.app.selected_window is not None:
            window_text = f"当前目标窗口：{self.app.selected_window.title}"
        self.window_var.set(window_text)
        self.option_a_var.set(format_offset_text(self.app.config_data.option_a_offset))
        self.option_b_var.set(format_offset_text(self.app.config_data.option_b_offset))
        self.option_c_var.set(format_offset_text(self.app.config_data.option_c_offset))
        self.option_d_var.set(format_offset_text(self.app.config_data.option_d_offset))
        self.next_var.set(format_offset_text(self.app.config_data.next_button_offset))
        self.submit_var.set(format_offset_text(self.app.config_data.submit_button_offset))

    def _close(self) -> None:
        self.app.button_locator_dialog = None
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, config: AppConfig, on_save):
        super().__init__(master)
        self.title("设置")
        if APP_ICON_FILE.exists():
            try:
                self.iconbitmap(str(APP_ICON_FILE))
            except Exception:
                pass
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.on_save = on_save
        self.source_config = config

        self.api_url_var = tk.StringVar(value=config.api_url)
        self.api_key_var = tk.StringVar(value=config.api_key)
        self.model_var = tk.StringVar(value=config.model)
        self.timeout_var = tk.StringVar(value=str(config.timeout_seconds))
        self.auto_submit_var = tk.BooleanVar(value=config.auto_submit)
        self.auto_answer_var = tk.BooleanVar(value=config.auto_answer)
        self.option_a_offset = normalize_point(config.option_a_offset)
        self.option_b_offset = normalize_point(config.option_b_offset)
        self.option_c_offset = normalize_point(config.option_c_offset)
        self.option_d_offset = normalize_point(config.option_d_offset)
        self.next_button_offset = normalize_point(config.next_button_offset)
        self.submit_button_offset = normalize_point(config.submit_button_offset)

        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="API 地址（兼容 chat/completions）").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(container, textvariable=self.api_url_var, width=64).grid(
            row=1, column=0, sticky="ew", pady=(4, 10)
        )

        ttk.Label(container, text="API Key").grid(row=2, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.api_key_var, width=64, show="*").grid(
            row=3, column=0, sticky="ew", pady=(4, 10)
        )

        ttk.Label(container, text="模型 ID / Endpoint ID").grid(row=4, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.model_var, width=64).grid(
            row=5, column=0, sticky="ew", pady=(4, 10)
        )

        ttk.Label(container, text="超时秒数").grid(row=6, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.timeout_var, width=12).grid(
            row=7, column=0, sticky="w", pady=(4, 10)
        )

        # 新增自动答题开关
        ttk.Checkbutton(
            container, 
            text="启用自动答题（选择答案+自动切题）", 
            variable=self.auto_answer_var
        ).grid(row=8, column=0, sticky="w", pady=(4, 10))

        # 新增自动提交开关
        ttk.Checkbutton(
            container, 
            text="启用自动提交（所有题目完成后）", 
            variable=self.auto_submit_var
        ).grid(row=9, column=0, sticky="w", pady=(4, 10))

        ttk.Label(container, text="分析提示词").grid(row=10, column=0, sticky="w")
        self.prompt_text = ScrolledText(container, width=70, height=12, wrap="word")
        self.prompt_text.grid(row=11, column=0, sticky="nsew", pady=(4, 10))
        self.prompt_text.insert("1.0", config.analysis_prompt)

        button_row = ttk.Frame(container)
        button_row.grid(row=12, column=0, sticky="e")
        ttk.Button(button_row, text="恢复学习模板", command=self._reset_prompt).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="保存", command=self._save).pack(side="left")

        container.columnconfigure(0, weight=1)
        container.rowconfigure(11, weight=1)

    def _reset_prompt(self) -> None:
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", DEFAULT_ANALYSIS_PROMPT)

    def _save(self) -> None:
        try:
            timeout_value = int(self.timeout_var.get().strip())
            if timeout_value <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("设置错误", "超时秒数需要是正整数。", parent=self)
            return

        config = AppConfig(
            api_url=self.api_url_var.get().strip() or DEFAULT_ENDPOINT,
            api_key=self.api_key_var.get().strip(),
            model=self.model_var.get().strip(),
            timeout_seconds=timeout_value,
            analysis_prompt=self.prompt_text.get("1.0", "end").strip() or DEFAULT_ANALYSIS_PROMPT,
            auto_submit=self.auto_submit_var.get(),
            auto_answer=self.auto_answer_var.get(),
            ui_language=self.source_config.ui_language,
            theme_mode=self.source_config.theme_mode,
            option_a_offset=self.option_a_offset,
            option_b_offset=self.option_b_offset,
            option_c_offset=self.option_c_offset,
            option_d_offset=self.option_d_offset,
            next_button_offset=self.next_button_offset,
            submit_button_offset=self.submit_button_offset,
        )
        self.on_save(config)
        self.destroy()


class MainApp:
    def __init__(self) -> None:
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("HX-AIBOT")
        if APP_ICON_FILE.exists():
            try:
                self.root.iconbitmap(str(APP_ICON_FILE))
            except Exception:
                pass
        self.root.geometry("1120x760")
        self.root.minsize(960, 640)

        self.config_data = load_config()
        self.selected_window: Optional[WindowInfo] = None
        self.log_queue: "queue.Queue[tuple]" = queue.Queue()
        self.preview_image_ref = None
        self.current_picker: Optional[WindowPicker] = None
        self.button_locator_dialog: Optional[ButtonLocatorDialog] = None
        self.busy = False
        self.is_auto_running = False  # 自动答题运行状态

        self.window_title_var = tk.StringVar(value="未选择目标窗口")
        self.window_rect_var = tk.StringVar(value="窗口范围：-")
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self.root.after(120, self._drain_ui_queue)
        self.root.after(450, self.open_window_picker)

        self.log("程序已启动。")
        self._log_auto_mode()
        self.log(f"OCR 状态：{get_ocr_status()}")

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="HX-AIBOT", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )

        button_row = ttk.Frame(header)
        button_row.grid(row=0, column=1, sticky="e")
        ttk.Button(button_row, text="选择窗口", command=self.open_window_picker).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="单次答题", command=self.start_analysis).pack(
            side="left", padx=(0, 8)
        )
        # 新增自动答题按钮
        self.auto_run_btn = ttk.Button(
            button_row, 
            text="开始自动答题", 
            command=self.toggle_auto_answer
        )
        self.auto_run_btn.pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="按钮定位", command=self.open_button_locator).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="保存截图", command=self.save_screenshot).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="设置", command=self.open_settings).pack(side="left")

        summary = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        summary.grid(row=1, column=0, sticky="nsew")
        summary.columnconfigure(0, weight=3)
        summary.columnconfigure(1, weight=2)
        summary.rowconfigure(0, weight=1)

        left = ttk.Frame(summary)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        selected_card = ttk.LabelFrame(left, text="当前目标窗口", padding=10)
        selected_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        selected_card.columnconfigure(0, weight=1)
        ttk.Label(selected_card, textvariable=self.window_title_var, font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(selected_card, textvariable=self.window_rect_var).grid(row=1, column=0, sticky="w", pady=(6, 0))

        preview_card = ttk.LabelFrame(left, text="最近截图预览", padding=10)
        preview_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.preview_label = ttk.Label(preview_card, text="还没有截图", anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        result_card = ttk.LabelFrame(left, text="题目提取与解题思路", padding=10)
        result_card.grid(row=2, column=0, sticky="nsew")
        result_card.rowconfigure(0, weight=1)
        result_card.columnconfigure(0, weight=1)
        self.result_text = ScrolledText(result_card, wrap="word", font=("Consolas", 10))
        self.result_text.grid(row=0, column=0, sticky="nsew")

        right = ttk.LabelFrame(summary, text="运行日志", padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.log_text = ScrolledText(right, wrap="word", font=("Consolas", 10), state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(
            footer,
            text="拖动十字准星到目标窗口后松开鼠标即可选择，也可以用“按钮定位”单独标定 A-D 选项、下一题和提交按钮。",
        ).grid(row=0, column=1, sticky="e")

    # 新增：切换自动答题状态
    def toggle_auto_answer(self) -> None:
        if self.is_auto_running:
            self.stop_auto_answer()
        else:
            self.start_auto_answer()

    # 新增：启动自动答题
    def start_auto_answer(self) -> None:
        if self.busy:
            messagebox.showinfo("提示", "当前正在处理，请稍候。", parent=self.root)
            return
        if not self._require_window():
            return
        if not self.config_data.api_key.strip() or not self.config_data.model.strip():
            messagebox.showinfo("提示", "请先在设置里填写 API Key 和模型 ID。", parent=self.root)
            self.open_settings()
            return
        
        self.is_auto_running = True
        self.auto_run_btn.config(text="停止自动答题")
        self.set_status("自动答题已启动")
        self.log("开始自动答题循环...")
        
        # 启动自动答题线程
        thread = threading.Thread(target=self._auto_answer_worker, daemon=True)
        thread.start()

    # 新增：停止自动答题
    def stop_auto_answer(self) -> None:
        self.is_auto_running = False
        self.auto_run_btn.config(text="开始自动答题")
        self.set_status("自动答题已停止")
        self.log("自动答题已手动停止")

    # 新增：自动答题核心逻辑
    def _auto_answer_worker(self) -> None:
        try:
            question_count = 0
            while self.is_auto_running and self.config_data.auto_answer:
                # 1. 截图并分析
                self.set_status(f"正在处理第 {question_count + 1} 题...")
                self.log(f"===== 处理第 {question_count + 1} 题 =====")
                
                # 截图
                image = self._capture_selected_window()
                self.log(f"截图完成，尺寸：{image.size[0]} x {image.size[1]}")
                
                # 调用AI分析
                client = AIClient(self.config_data)
                ai_response = client.analyze_window_image(image)
                self.set_result(ai_response)
                self.log("AI分析完成")
                
                # 2. 解析答案并点击
                answer_items = parse_ai_answers(ai_response)
                if not answer_items:
                    preview_text = ai_response.strip().replace("\n", " ")
                    self.log(f"未能解析到有效答案，原始返回片段：{preview_text[:120]}")
                    # 尝试点击下一题
                    self._click_next_question()
                    continue

                self.log(f"解析到答案：{format_answer_items(answer_items)}")

                if not self._click_answer_options(image, answer_items, stop_on_missing=True):
                    break

                question_count += 1
                
                # 3. 检查是否是最后一题（简化判断：可根据实际界面调整）
                is_last_question = self._check_if_last_question(ai_response)
                if is_last_question:
                    self.log("检测到最后一题，自动答题完成")
                    # 如果开启自动提交
                    if self.config_data.auto_submit:
                        self.log("执行自动提交...")
                        submit_pos = find_submit_btn(
                            self.selected_window.rect,
                            self.config_data.submit_button_offset,
                        )
                        click_at(*submit_pos)
                        submit_source = (
                            "自定义定位" if self.config_data.submit_button_offset is not None else "默认定位"
                        )
                        self.log(f"已点击提交按钮（{submit_source}），坐标：{submit_pos}")
                    break
                
                # 4. 点击下一题
                self._click_next_question()
                
                # 等待页面加载
                time.sleep(1.5)
            
            # 循环结束
            self.is_auto_running = False
            self.auto_run_btn.config(text="开始自动答题")
            if question_count > 0:
                self.set_status(f"自动答题完成，共处理 {question_count} 题")
                self.log(f"自动答题循环结束，共处理 {question_count} 题")
            else:
                self.set_status("自动答题未处理任何题目")
                
        except Exception as exc:
            self.is_auto_running = False
            self.auto_run_btn.config(text="开始自动答题")
            self.log(f"自动答题异常：{exc}")
            self.set_status("自动答题异常终止")
            self.show_error(f"自动答题失败：{str(exc)}")

    # 新增：点击下一题按钮
    def _click_next_question(self) -> None:
        next_pos = find_next_question_btn(
            self.selected_window.rect,
            self.config_data.next_button_offset,
        )
        next_source = "自定义定位" if self.config_data.next_button_offset is not None else "默认定位"
        self.log(f"点击下一题按钮（{next_source}），坐标：{next_pos}")
        click_at(*next_pos)

    # 新增：判断是否是最后一题（简化实现，需根据实际场景调整）
    def _check_if_last_question(self, ai_response: str) -> bool:
        """
        简化判断逻辑：
        - 可根据AI返回的题干/选项中是否包含"最后一题"等关键词
        - 或根据窗口内的页码（如 10/10）判断
        - 这里临时返回False，模拟还有下一题
        """
        # 实际场景请替换为真实判断逻辑
        return False

    def _click_answer_options(
        self,
        image: Image.Image,
        answer_items: List[Tuple[str, str]],
        stop_on_missing: bool,
    ) -> bool:
        for option_char, _option_content in answer_items:
            option_offset = get_option_offset(self.config_data, option_char)
            option_pos = find_option_position(
                self.selected_window.rect,
                image,
                option_char,
                option_offset,
            )
            if not option_pos:
                if stop_on_missing:
                    self.log(
                        f"未能定位到选项 {option_char}，自动答题已暂停，请先在“按钮定位”里标定 A-D 选项位置。"
                    )
                    self.is_auto_running = False
                    self.set_status(f"未定位到 {option_char} 选项，请先标定选项坐标")
                else:
                    self.log(f"未能定位到选项 {option_char}，请先在“按钮定位”里标定 A-D 选项位置。")
                return False

            option_source = "自定义定位" if option_offset is not None else "默认定位"
            self.log(f"点击选项 {option_char}（{option_source}），坐标：{option_pos}")
            is_multi_select = len(answer_items) > 1
            click_at(*option_pos, settle_delay=0.18 if is_multi_select else 0.28)
            time.sleep(0.18 if is_multi_select else 0.38)

        return True

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(("log", f"[{timestamp}] {message}\n"))

    def set_status(self, message: str) -> None:
        self.log_queue.put(("status", message))

    def set_result(self, content: str) -> None:
        self.log_queue.put(("result", content))

    def set_preview(self, image: Image.Image) -> None:
        self.log_queue.put(("preview", image))

    def show_error(self, message: str) -> None:
        self.log_queue.put(("error", message))

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.log_queue.put(("busy", busy))

    def _drain_ui_queue(self) -> None:
        while not self.log_queue.empty():
            kind, payload = self.log_queue.get()
            if kind == "log":
                self.log_text.configure(state="normal")
                self.log_text.insert("end", payload)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
            elif kind == "status":
                self.status_var.set(payload)
            elif kind == "result":
                self.result_text.delete("1.0", "end")
                self.result_text.insert("1.0", payload)
            elif kind == "preview":
                preview = payload.copy()
                preview.thumbnail((520, 260))
                tk_image = ImageTk.PhotoImage(preview)
                self.preview_image_ref = tk_image
                self.preview_label.configure(image=tk_image, text="")
            elif kind == "error":
                messagebox.showerror("执行失败", payload, parent=self.root)
            elif kind == "busy":
                self.busy = payload
        self.root.after(120, self._drain_ui_queue)

    def open_settings(self) -> None:
        SettingsDialog(self.root, self.config_data, self._save_settings)

    def _save_settings(self, config: AppConfig) -> None:
        config.option_a_offset = normalize_point(config.option_a_offset)
        config.option_b_offset = normalize_point(config.option_b_offset)
        config.option_c_offset = normalize_point(config.option_c_offset)
        config.option_d_offset = normalize_point(config.option_d_offset)
        config.next_button_offset = normalize_point(config.next_button_offset)
        config.submit_button_offset = normalize_point(config.submit_button_offset)
        self.config_data = config
        save_config(config)
        self.log("设置已保存。")
        self._log_auto_mode()
        self._refresh_button_locator_dialog()
        self.set_status("设置已更新")

    def open_window_picker(self) -> None:
        self._open_crosshair_picker(
            self._on_window_picked,
            "请拖动十字准星到目标窗口后松开鼠标",
            "十字准星已打开，请拖到目标窗口上后松开鼠标。",
            "窗口",
        )

    def _on_window_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        hwnd = get_root_window_from_point(screen_x, screen_y)
        if not hwnd:
            self.log("没有识别到目标窗口。")
            self.set_status("窗口选择失败")
            return

        app_hwnds = {int(self.root.winfo_id())}
        if hwnd in app_hwnds:
            self.log("选中了当前程序本身，请重新选择其他窗口。")
            self.set_status("请选择其他窗口")
            return

        if not is_window_visible(hwnd):
            self.log("目标窗口当前不可见，请确认它没有被最小化。")
            self.set_status("目标窗口不可见")
            return

        title = get_window_title(hwnd) or "(无标题窗口)"
        rect = get_window_rect(hwnd)
        self.selected_window = WindowInfo(hwnd=hwnd, title=title, rect=rect)
        self.window_title_var.set(f"{title}  (HWND: {hwnd})")
        self.window_rect_var.set(f"窗口范围：{rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}")
        self.log(f"已选择窗口：{title}，句柄 {hwnd}。")
        self._refresh_button_locator_dialog()
        self.set_status("目标窗口已选择")

    def _require_window(self) -> bool:
        if self.selected_window is not None:
            return True
        messagebox.showinfo("提示", "请先选择一个目标窗口。", parent=self.root)
        self.open_window_picker()
        return False

    def _capture_selected_window(self) -> Image.Image:
        if not self.selected_window:
            raise RuntimeError("还没有选择目标窗口。")
        image = capture_window(self.selected_window.hwnd)
        self._refresh_selected_window_rect()
        self.set_preview(image)
        return image

    def _open_crosshair_picker(
        self,
        on_pick: Callable[[int, int], None],
        status_message: str,
        log_message: str,
        label: str,
    ) -> None:
        if self.current_picker and self.current_picker.winfo_exists():
            self.current_picker.destroy()
        self.current_picker = WindowPicker(self.root, on_pick, label=label)
        self.set_status(status_message)
        self.log(log_message)

    def _refresh_selected_window_rect(self) -> Tuple[int, int, int, int]:
        if not self.selected_window:
            raise RuntimeError("还没有选择目标窗口。")
        self.selected_window.rect = get_window_rect(self.selected_window.hwnd)
        rect = self.selected_window.rect
        self.window_rect_var.set(f"窗口范围：{rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}")
        return rect

    def _log_auto_mode(self) -> None:
        auto_answer_status = "开启" if self.config_data.auto_answer else "关闭"
        auto_submit_status = "开启" if self.config_data.auto_submit else "关闭"
        self.log(f"自动答题：{auto_answer_status} | 自动提交：{auto_submit_status}")

    def _refresh_button_locator_dialog(self) -> None:
        if self.button_locator_dialog and self.button_locator_dialog.winfo_exists():
            self.button_locator_dialog.refresh()

    def open_button_locator(self) -> None:
        if not self._require_window():
            return
        if self.button_locator_dialog and self.button_locator_dialog.winfo_exists():
            self.button_locator_dialog.lift()
            self.button_locator_dialog.focus_force()
            self.button_locator_dialog.refresh()
            return
        self.button_locator_dialog = ButtonLocatorDialog(self.root, self)
        self.button_locator_dialog.focus_force()
        self.set_status("按钮定位面板已打开")

    def pick_next_button_position(self) -> None:
        if not self._require_window():
            return
        self._open_crosshair_picker(
            self._on_next_button_picked,
            "请拖动十字准星到“下一题”按钮后松开鼠标",
            "开始定位“下一题”按钮，请把十字准星拖到按钮中心后松开鼠标。",
            "下一题",
        )

    def pick_submit_button_position(self) -> None:
        if not self._require_window():
            return
        self._open_crosshair_picker(
            self._on_submit_button_picked,
            "请拖动十字准星到“提交”按钮后松开鼠标",
            "开始定位“提交”按钮，请把十字准星拖到按钮中心后松开鼠标。",
            "提交",
        )

    def pick_option_position(self, option_char: str) -> None:
        if not self._require_window():
            return
        option_key = option_char.upper()
        self._open_crosshair_picker(
            lambda x, y: self._on_option_picked(option_key, x, y),
            f"请拖动十字准星到“{option_key} 选项”后松开鼠标",
            f"开始定位“{option_key} 选项”，请把十字准星拖到对应选项的可点击区域中心后松开鼠标。",
            f"选项{option_key}",
        )

    def _on_next_button_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        self._save_button_offset("next_button_offset", "下一题", screen_x, screen_y)

    def _on_submit_button_picked(self, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        self._save_button_offset("submit_button_offset", "提交", screen_x, screen_y)

    def _on_option_picked(self, option_char: str, screen_x: int, screen_y: int) -> None:
        self.current_picker = None
        self._save_button_offset(
            f"option_{option_char.lower()}_offset",
            f"{option_char} 选项",
            screen_x,
            screen_y,
        )

    def _save_button_offset(
        self,
        attr_name: str,
        button_name: str,
        screen_x: int,
        screen_y: int,
    ) -> None:
        if not self._require_window():
            return
        rect = self._refresh_selected_window_rect()
        if not point_in_rect(screen_x, screen_y, rect):
            self.log(f"{button_name}按钮定位失败：({screen_x}, {screen_y}) 不在目标窗口内。")
            self.set_status(f"{button_name}按钮定位失败")
            self.show_error("请把十字准星拖到目标窗口内部的按钮上再松开鼠标。")
            self._refresh_button_locator_dialog()
            return

        offset = (screen_x - rect[0], screen_y - rect[1])
        setattr(self.config_data, attr_name, offset)
        save_config(self.config_data)
        self.log(
            f"{button_name}按钮定位已保存，屏幕坐标：({screen_x}, {screen_y})，窗口内偏移：{offset}"
        )
        self.set_status(f"{button_name}按钮定位已保存")
        self._refresh_button_locator_dialog()

    def clear_next_button_position(self) -> None:
        self.config_data.next_button_offset = None
        save_config(self.config_data)
        self.log("已清空“下一题”按钮的自定义定位。")
        self.set_status("已清空下一题按钮定位")
        self._refresh_button_locator_dialog()

    def clear_submit_button_position(self) -> None:
        self.config_data.submit_button_offset = None
        save_config(self.config_data)
        self.log("已清空“提交”按钮的自定义定位。")
        self.set_status("已清空提交按钮定位")
        self._refresh_button_locator_dialog()

    def clear_all_option_positions(self) -> None:
        self.config_data.option_a_offset = None
        self.config_data.option_b_offset = None
        self.config_data.option_c_offset = None
        self.config_data.option_d_offset = None
        save_config(self.config_data)
        self.log("已清空 A-D 选项的自定义定位。")
        self.set_status("已清空 A-D 选项定位")
        self._refresh_button_locator_dialog()

    def save_screenshot(self) -> None:
        if self.busy:
            messagebox.showinfo("提示", "当前正在处理，请稍候。", parent=self.root)
            return
        if not self._require_window():
            return

        self.set_busy(True)
        thread = threading.Thread(target=self._save_capture_worker, daemon=True)
        thread.start()

    def _save_capture_worker(self) -> None:
        try:
            self.set_status("正在截图...")
            self.log("开始截图目标窗口。")
            image = self._capture_selected_window()
            captures_dir = APP_DIR / "captures"
            captures_dir.mkdir(exist_ok=True)
            filename = captures_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            image.save(filename)
            self.log(f"截图已保存到：{filename}")
            self.set_status("截图已保存")
        except Exception as exc:
            self.log(f"截图失败：{exc}")
            self.set_status("截图失败")
        finally:
            self.set_busy(False)

    def start_analysis(self) -> None:
        """单次答题分析（保留原功能）"""
        if self.busy:
            messagebox.showinfo("提示", "当前正在处理，请稍候。", parent=self.root)
            return
        if not self._require_window():
            return
        if not self.config_data.api_key.strip() or not self.config_data.model.strip():
            messagebox.showinfo("提示", "请先在设置里填写 API Key 和模型 ID。", parent=self.root)
            self.open_settings()
            return

        self.set_busy(True)
        self.set_status("正在截图并调用模型...")
        thread = threading.Thread(target=self._analyze_worker, daemon=True)
        thread.start()

    def _analyze_worker(self) -> None:
        """单次答题处理（保留原功能）"""
        try:
            self.log("开始截图目标窗口。")
            image = self._capture_selected_window()
            self.log(f"截图完成，尺寸：{image.size[0]} x {image.size[1]}。")
            self.log("开始调用豆包兼容 API 分析截图。")
            client = AIClient(self.config_data)
            result = client.analyze_window_image(image)
            self.set_result(result)
            
            # 如果开启自动答题，自动选择答案
            if self.config_data.auto_answer:
                answer_items = parse_ai_answers(result)
                if answer_items:
                    self.log(f"自动选择答案：{format_answer_items(answer_items)}")
                    self._click_answer_options(image, answer_items, stop_on_missing=False)
                else:
                    preview_text = result.strip().replace("\n", " ")
                    self.log(f"单次答题未解析到答案，原始返回片段：{preview_text[:120]}")
            
            self.log("模型分析完成。")
            self.set_status("分析完成")
        except Exception as exc:
            self.set_result("")
            self.log(f"分析失败：{exc}")
            self.set_status("分析失败")
            self.show_error(str(exc))
        finally:
            self.set_busy(False)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    # 安装依赖提示（首次运行）
    try:
        import pyautogui
    except ImportError:
        print("请先安装依赖：pip install pyautogui")
        exit(1)
    MainApp().run()
