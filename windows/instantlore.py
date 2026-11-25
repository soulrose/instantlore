"""InstantLore (Windows) — แปลซับเกมแบบ realtime ลอยทับหน้าจอ
ผู้พัฒนา: Soulrose

อ่านจอ (mss) → OCR (RapidOCR ออฟไลน์) → แปล (Google) → ซับไทยลอยทับเกม

ปุ่มลัด (Ctrl + Alt + ...):
  T เริ่ม/หยุดแปล    R ตั้งกล่องอ่านซับอังกฤษ    M ย้าย/ปรับขนาดซับไทย
  H ซ่อน/แสดงซับไทย  E แสดงภาษาอังกฤษด้วย       B เปิด/ปิดกล่องดำ   = / - ขนาดตัวอักษร
"""

import ctypes
import difflib
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from pathlib import Path

IS_WIN = sys.platform == "win32"
APP_NAME = "InstantLore"
APP_VERSION = "1.3"
DEVELOPER = "Soulrose"
REPO = "soulrose/instantlore"


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) + (0,) * (3 - len(re.findall(r"\d+", v)[:3]))


def latest_release():
    """เวอร์ชันล่าสุดบน GitHub: (เลขเวอร์ชัน, ลิงก์หน้าดาวน์โหลด)"""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["tag_name"].lstrip("v"), data["html_url"]

# ภาษาของเกม: (รหัส Google, ชื่ออังกฤษ, ชื่อไทย, ตัวอ่าน OCR เฉพาะภาษา หรือ None = ตัวหลายภาษาปกติ)
SOURCE_LANGS = [
    ("auto", "Auto detect", "ตรวจอัตโนมัติ", None),
    ("en", "English", "อังกฤษ", None),
    ("ja", "Japanese", "ญี่ปุ่น", None),
    ("zh-CN", "Chinese (Simplified)", "จีน (ตัวย่อ)", None),
    ("zh-TW", "Chinese (Traditional)", "จีน (ตัวเต็ม)", None),
    ("ko", "Korean", "เกาหลี", "korean"),
    ("fr", "French", "ฝรั่งเศส", None),
    ("de", "German", "เยอรมัน", None),
    ("es", "Spanish", "สเปน", None),
    ("it", "Italian", "อิตาลี", None),
    ("pt", "Portuguese", "โปรตุเกส", None),
    ("ru", "Russian", "รัสเซีย", "eslav"),
    ("th", "Thai", "ไทย", "th"),
]
SRC_MODEL = {c: m for c, _, _, m in SOURCE_LANGS}
# ภาษาที่จะแปลเป็น: (รหัส Google, ชื่ออังกฤษ, ชื่อไทย)
TARGET_LANGS = [
    ("th", "Thai", "ไทย"), ("en", "English", "อังกฤษ"), ("ja", "Japanese", "ญี่ปุ่น"),
    ("zh-CN", "Chinese (Simplified)", "จีน (ตัวย่อ)"), ("ko", "Korean", "เกาหลี"),
    ("vi", "Vietnamese", "เวียดนาม"), ("id", "Indonesian", "อินโดนีเซีย"), ("ms", "Malay", "มลายู"),
    ("lo", "Lao", "ลาว"), ("my", "Burmese", "พม่า"), ("km", "Khmer", "เขมร"),
    ("fr", "French", "ฝรั่งเศส"), ("es", "Spanish", "สเปน"),
]
UI_LANGS = [("en", "English"), ("th", "ไทย"), ("zh", "中文"), ("ja", "日本語")]
# ชื่อภาษาในรายการ สำหรับหน้าโปรแกรมภาษาจีน/ญี่ปุ่น
LANG_NAMES = {
    "zh": {"auto": "自动检测", "en": "英语", "ja": "日语", "zh-CN": "中文（简体）", "zh-TW": "中文（繁体）",
           "ko": "韩语", "fr": "法语", "de": "德语", "es": "西班牙语", "it": "意大利语", "pt": "葡萄牙语",
           "ru": "俄语", "th": "泰语", "vi": "越南语", "id": "印尼语", "ms": "马来语", "lo": "老挝语",
           "my": "缅甸语", "km": "高棉语"},
    "ja": {"auto": "自動検出", "en": "英語", "ja": "日本語", "zh-CN": "中国語（簡体字）", "zh-TW": "中国語（繁体字）",
           "ko": "韓国語", "fr": "フランス語", "de": "ドイツ語", "es": "スペイン語", "it": "イタリア語",
           "pt": "ポルトガル語", "ru": "ロシア語", "th": "タイ語", "vi": "ベトナム語", "id": "インドネシア語",
           "ms": "マレー語", "lo": "ラオ語", "my": "ビルマ語", "km": "クメール語"},
}


def system_ui_lang():
    """ภาษาของเครื่อง ถ้าไม่ใช่ภาษาที่มีให้ ใช้อังกฤษ"""
    code = ""
    try:
        if IS_WIN:
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            code = {0x1E: "th", 0x04: "zh", 0x11: "ja", 0x09: "en"}.get(primary, "")
        else:
            import locale
            code = (os.environ.get("LC_ALL") or os.environ.get("LANG") or locale.getlocale()[0] or "")[:2].lower()
    except Exception:
        pass
    return code if code in dict(UI_LANGS) else "en"

# ข้อความในโปรแกรม (ภาษาอังกฤษเป็นค่าเริ่มต้น)
STRINGS = {
    "en": {
        "start": "Start translating", "stop": "Stop translating",
        "sec_setup": "Setup",
        "capture": "Capture area", "capture_hint": "Drag it over the game's subtitles",
        "position": "Subtitle position", "position_hint": "Where the translation appears",
        "edit": "Edit", "done": "Done", "auto": "Auto",
        "st_auto": "Looking for subtitles… keep one on screen",
        "st_auto_found": "Found subtitles. Adjust the box if needed, then Done",
        "st_auto_none": "No subtitles found. Show a line on screen and try again",
        "show_subs": "Show subtitles",
        "sec_lang": "Language", "game_lang": "Game language", "translate_to": "Translate to",
        "sec_style": "Subtitle style", "text_size": "Text size",
        "show_orig": "Show original text", "show_orig_hint": "Original line above the translation",
        "bg_box": "Background box", "bg_box_hint": "Off: outlined text instead",
        "sec_scan": "Screen reading", "scan": "Read the screen", "fast": "Fast", "normal": "Normal",
        "light": "Light",
        "ui_lang": "Interface", "about": "About", "quit": "Quit",
        "update": "Check for updates", "up_checking": "Checking for updates…",
        "up_latest": "You have the latest version ({ver})", "up_title": "Update available",
        "up_body": "InstantLore {new} is available. You have {cur}.", "up_download": "Download", "up_later": "Later",
        "up_fail": "Couldn't check for updates: {e}",
        "ask": "Ask", "minimize": "Minimize",
        "close_title": "Close {app}?",
        "close_body": "Minimize keeps translating in the background.\nQuit stops the app completely.",
        "remember": "Remember my choice",
        "st_loading": "Loading text reader…", "st_ready": "Ready",
        "st_running": "Translating", "st_stopped": "Stopped",
        "st_reload": "Loading reader for {lang}…", "st_error": "Error: {e}",
        "st_ocr_fail": "Couldn't load the text reader: {e}",
        "st_no_keys": "Hotkeys unavailable, use this window",
        "box_region": "① Capture area: drag over the game's subtitles · Ctrl+Alt+R when done",
        "box_sub": "② Subtitle position: drag to move, corner to resize · Ctrl+Alt+M when done",
        "ph_tr": "Translated subtitle appears here", "ph_orig": "Original subtitle appears here",
        "about_title": "About {app}",
        "about_body": "{app} {ver}\n\nDeveloped by {dev}\n\n"
                      "Text reading: RapidOCR, runs on this PC\nTranslation: Google Translate (internet)",
    },
    "th": {
        "start": "เริ่มแปล", "stop": "หยุดแปล",
        "sec_setup": "ตั้งค่าพื้นที่",
        "capture": "กล่องอ่านซับ", "capture_hint": "ลากไปครอบซับในเกม",
        "position": "ตำแหน่งซับแปล", "position_hint": "ตำแหน่งที่คำแปลจะขึ้น",
        "edit": "แก้ไข", "done": "เสร็จ", "auto": "อัตโนมัติ",
        "st_auto": "กำลังหาซับ… ให้มีซับขึ้นอยู่บนจอ",
        "st_auto_found": "เจอซับแล้ว ปรับกล่องได้ถ้าต้องการ แล้วกดเสร็จ",
        "st_auto_none": "ไม่เจอซับ ให้มีซับขึ้นบนจอแล้วลองอีกครั้ง",
        "show_subs": "แสดงซับแปล",
        "sec_lang": "ภาษา", "game_lang": "ภาษาของเกม", "translate_to": "แปลเป็น",
        "sec_style": "รูปแบบซับ", "text_size": "ขนาดตัวอักษร",
        "show_orig": "แสดงข้อความต้นฉบับ", "show_orig_hint": "ต้นฉบับขึ้นเหนือคำแปล",
        "bg_box": "กล่องพื้นหลัง", "bg_box_hint": "ปิดแล้วตัวหนังสือจะมีขอบดำแทน",
        "sec_scan": "การอ่านหน้าจอ", "scan": "ความถี่", "fast": "เร็ว", "normal": "ปกติ",
        "light": "ประหยัด",
        "ui_lang": "ภาษาโปรแกรม", "about": "เกี่ยวกับ", "quit": "ปิดโปรแกรม",
        "update": "ตรวจหาเวอร์ชันใหม่", "up_checking": "กำลังตรวจหาเวอร์ชันใหม่…",
        "up_latest": "ใช้เวอร์ชันล่าสุดอยู่แล้ว ({ver})", "up_title": "มีเวอร์ชันใหม่",
        "up_body": "InstantLore {new} ออกแล้ว ตอนนี้ใช้ {cur} อยู่", "up_download": "ดาวน์โหลด", "up_later": "ไว้ทีหลัง",
        "up_fail": "ตรวจหาเวอร์ชันใหม่ไม่ได้: {e}",
        "ask": "ถาม", "minimize": "ย่อ",
        "close_title": "ปิด {app}?",
        "close_body": "ย่อ: โปรแกรมยังแปลต่ออยู่เบื้องหลัง\nปิดโปรแกรม: หยุดการทำงานทั้งหมด",
        "remember": "จำการเลือกนี้",
        "st_loading": "กำลังโหลดตัวอ่านข้อความ…", "st_ready": "พร้อม",
        "st_running": "กำลังแปล", "st_stopped": "หยุดอยู่",
        "st_reload": "กำลังโหลดตัวอ่านภาษา{lang}…", "st_error": "ผิดพลาด: {e}",
        "st_ocr_fail": "โหลดตัวอ่านข้อความไม่ได้: {e}",
        "st_no_keys": "ปุ่มลัดใช้ไม่ได้ ใช้ปุ่มในหน้าต่างนี้แทน",
        "box_region": "① กล่องอ่านซับ: ลากครอบซับในเกม · กด Ctrl+Alt+R เมื่อเสร็จ",
        "box_sub": "② ตำแหน่งซับแปล: ลากเพื่อย้าย ลากมุมเพื่อปรับขนาด · กด Ctrl+Alt+M เมื่อเสร็จ",
        "ph_tr": "ซับแปลจะแสดงตรงนี้", "ph_orig": "ข้อความต้นฉบับจะแสดงตรงนี้",
        "about_title": "เกี่ยวกับ {app}",
        "about_body": "{app} เวอร์ชัน {ver}\n\nผู้พัฒนา: {dev}\n\n"
                      "อ่านตัวหนังสือ: RapidOCR ทำงานในเครื่อง\nแปล: Google Translate (ต้องต่ออินเทอร์เน็ต)",
    },
    "zh": {
        "start": "开始翻译", "stop": "停止翻译",
        "sec_setup": "区域设置",
        "capture": "字幕读取区域", "capture_hint": "拖动框住游戏字幕",
        "position": "译文位置", "position_hint": "译文显示的位置",
        "edit": "编辑", "done": "完成", "auto": "自动",
        "st_auto": "正在查找字幕…请保持字幕显示在屏幕上",
        "st_auto_found": "已找到字幕。如有需要可调整框，然后点完成",
        "st_auto_none": "未找到字幕。请让字幕显示在屏幕上后重试",
        "show_subs": "显示译文",
        "sec_lang": "语言", "game_lang": "游戏语言", "translate_to": "翻译为",
        "sec_style": "字幕样式", "text_size": "字号",
        "show_orig": "显示原文", "show_orig_hint": "原文显示在译文上方",
        "bg_box": "背景框", "bg_box_hint": "关闭后文字改为描边",
        "sec_scan": "屏幕读取", "scan": "读取频率", "fast": "快", "normal": "标准", "light": "省电",
        "ui_lang": "界面语言", "about": "关于", "quit": "退出",
        "update": "检查更新", "up_checking": "正在检查更新…",
        "up_latest": "已是最新版本（{ver}）", "up_title": "有新版本",
        "up_body": "InstantLore {new} 已发布，当前版本为 {cur}。", "up_download": "下载", "up_later": "以后再说",
        "up_fail": "无法检查更新：{e}",
        "ask": "询问", "minimize": "最小化",
        "close_title": "关闭 {app}？",
        "close_body": "最小化：在后台继续翻译。\n退出：完全关闭程序。",
        "remember": "记住我的选择",
        "st_loading": "正在加载文字识别…", "st_ready": "就绪",
        "st_running": "翻译中", "st_stopped": "已停止",
        "st_reload": "正在加载{lang}识别…", "st_error": "错误：{e}",
        "st_ocr_fail": "无法加载文字识别：{e}",
        "st_no_keys": "快捷键不可用，请使用此窗口",
        "box_region": "① 字幕读取区域：拖动框住游戏字幕 · 完成后按 Ctrl+Alt+R",
        "box_sub": "② 译文位置：拖动移动，拖动角落调整大小 · 完成后按 Ctrl+Alt+M",
        "ph_tr": "译文将显示在这里", "ph_orig": "原文将显示在这里",
        "about_title": "关于 {app}",
        "about_body": "{app} {ver}\n\n开发者：{dev}\n\n"
                      "文字识别：RapidOCR，在本机运行\n翻译：Google 翻译（需联网）",
    },
    "ja": {
        "start": "翻訳を開始", "stop": "翻訳を停止",
        "sec_setup": "エリア設定",
        "capture": "字幕の読み取りエリア", "capture_hint": "ゲームの字幕に重ねてドラッグ",
        "position": "翻訳の表示位置", "position_hint": "翻訳が表示される場所",
        "edit": "編集", "done": "完了", "auto": "自動",
        "st_auto": "字幕を探しています…字幕を画面に表示したままにしてください",
        "st_auto_found": "字幕が見つかりました。必要なら枠を調整して完了を押してください",
        "st_auto_none": "字幕が見つかりません。字幕を表示してからもう一度お試しください",
        "show_subs": "翻訳を表示",
        "sec_lang": "言語", "game_lang": "ゲームの言語", "translate_to": "翻訳先",
        "sec_style": "字幕のスタイル", "text_size": "文字サイズ",
        "show_orig": "原文を表示", "show_orig_hint": "翻訳の上に原文を表示",
        "bg_box": "背景ボックス", "bg_box_hint": "オフ：縁取り文字で表示",
        "sec_scan": "画面の読み取り", "scan": "読み取り頻度", "fast": "高速", "normal": "標準", "light": "省電力",
        "ui_lang": "表示言語", "about": "情報", "quit": "終了",
        "update": "アップデートを確認", "up_checking": "アップデートを確認中…",
        "up_latest": "最新バージョンです（{ver}）", "up_title": "新しいバージョンがあります",
        "up_body": "InstantLore {new} が公開されています。現在のバージョンは {cur} です。", "up_download": "ダウンロード", "up_later": "後で",
        "up_fail": "アップデートを確認できません：{e}",
        "ask": "確認", "minimize": "最小化",
        "close_title": "{app} を閉じますか？",
        "close_body": "最小化：バックグラウンドで翻訳を続けます。\n終了：アプリを完全に終了します。",
        "remember": "この選択を記憶する",
        "st_loading": "文字認識を読み込み中…", "st_ready": "準備完了",
        "st_running": "翻訳中", "st_stopped": "停止中",
        "st_reload": "{lang}の認識を読み込み中…", "st_error": "エラー：{e}",
        "st_ocr_fail": "文字認識を読み込めません：{e}",
        "st_no_keys": "ショートカットが使えません。このウィンドウを使ってください",
        "box_region": "① 読み取りエリア：ゲームの字幕に重ねてドラッグ · 完了したら Ctrl+Alt+R",
        "box_sub": "② 翻訳の表示位置：ドラッグで移動、角でサイズ変更 · 完了したら Ctrl+Alt+M",
        "ph_tr": "ここに翻訳が表示されます", "ph_orig": "ここに原文が表示されます",
        "about_title": "{app} について",
        "about_body": "{app} {ver}\n\n開発者：{dev}\n\n"
                      "文字認識：RapidOCR（このPCで動作）\n翻訳：Google 翻訳（インターネット接続が必要）",
    }
}


def lang_name(table, code, ui):
    if ui in LANG_NAMES and code in LANG_NAMES[ui]:
        return LANG_NAMES[ui][code]
    for row in table:
        if row[0] == code:
            return row[2] if ui == "th" else row[1]
    return code


CJK = {"ja", "zh-CN", "zh-TW"}

if IS_WIN:
    # ให้เกมได้ CPU ก่อนเสมอ
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
    except Exception:
        pass
    # ให้พิกัดของ tkinter ตรงกับพิกเซลจริงของจอ (จอที่ตั้ง scale 125%/150%)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

CONFIG = Path.home() / ".instantlore.json"
# ไฟล์ตัวอ่าน OCR เก็บไว้ถาวร (exe แบบไฟล์เดียวแตกไฟล์ไปโฟลเดอร์ชั่วคราวทุกครั้ง จะได้ไม่ต้องโหลดใหม่ทุกรอบ)
MODEL_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".cache")) / "InstantLore" / "models"
OLD_CONFIG = Path.home() / ".gamesubth.json"  # ชื่อเดิมของโปรแกรม
DEFAULTS = {
    "region": None,     # [x, y, w, h] กล่องอ่านซับอังกฤษ
    "sub": None,        # [x, y, w, h] กล่องซับไทย
    "font_size": 26,
    "show_english": True,
    "bg_box": True,     # True = กล่องดำหลังซับ, False = ไม่มีกล่อง (ตัวหนังสือมีขอบดำ)
    "interval": 0.5,
    "src_lang": "en",   # ภาษาของเกม
    "dst_lang": "th",   # ภาษาที่จะแปลเป็น
    "ui_lang": "",      # ภาษาของโปรแกรม: en / th / zh / ja, ว่าง = ตามภาษาของเครื่อง
    "close_action": "ask",  # กดปุ่ม X: ask = ถามทุกครั้ง, minimize = ย่อ, quit = ปิดโปรแกรม
}
KEY = "#010203"  # สีนี้จะโปร่งใส


def load_config():
    cfg = dict(DEFAULTS)
    try:
        src = CONFIG if CONFIG.exists() else OLD_CONFIG  # ย้ายค่าที่ตั้งไว้จากชื่อเดิมมาด้วย
        cfg.update(json.loads(src.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- Win32 tricks

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_NOACTIVATE = 0x8000000
WDA_EXCLUDEFROMCAPTURE = 0x11


def hwnd_of(win):
    win.update_idletasks()
    return ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()


def set_click_through(win, on):
    """on=True: คลิกทะลุหน้าต่างลงไปที่เกม"""
    if not IS_WIN:
        return
    u = ctypes.windll.user32
    h = hwnd_of(win)
    st = u.GetWindowLongW(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    st = st | WS_EX_TRANSPARENT if on else st & ~WS_EX_TRANSPARENT
    u.SetWindowLongW(h, GWL_EXSTYLE, st)


def exclude_from_capture(win):
    """ซ่อนหน้าต่างเราจากการจับภาพจอ → ซับไทยทับซับอังกฤษได้โดย OCR ยังอ่านซับอังกฤษข้างใต้ได้ (Win10 2004+)"""
    if IS_WIN:
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd_of(win), WDA_EXCLUDEFROMCAPTURE)


def make_overlay(root):
    w = tk.Toplevel(root)
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.config(bg=KEY)
    if IS_WIN:
        w.attributes("-transparentcolor", KEY)
    return w


# ---------------------------------------------------------------- OCR / แปล

class OCR:
    """ตั้งค่าให้เบาที่สุด (วัดแล้ว: CPU ต่อครั้งจาก 3.3 วิ เหลือ ~0.07 วิ, RAM จาก 1.8 GB เหลือ ~0.2 GB)"""

    # ภาษาที่ตัวอ่านรุ่นจิ๋วอ่านพลาด ใช้รุ่นใหญ่ขึ้นหนึ่งขั้น
    NEEDS_SMALL_REC = {"ja", "zh-TW", "auto"}

    def __init__(self, src_lang="en"):
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.join = "" if src_lang in CJK else " "
        params = {
            "Global.use_cls": False,                   # ซับเกมไม่กลับหัว ไม่ต้องตรวจทิศทาง
            "Global.log_level": "error",
            "Global.model_root_dir": str(MODEL_DIR),
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,  # เหลือ CPU ให้เกม
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "Det.model_type": ModelType.TINY,
            "Det.limit_type": "max",                   # ค่าเดิมขยายภาพแถบซับ ~2.5 เท่า → ย่ออย่างเดียว
            "Det.limit_side_len": 1280,
        }
        model = SRC_MODEL.get(src_lang)
        if model:
            # เกาหลี/รัสเซีย/ไทย ใช้ตัวอ่านเฉพาะภาษา (โหลดจากเน็ตครั้งแรกครั้งเดียว)
            params.update({"Rec.lang_type": LangRec(model), "Rec.ocr_version": OCRVersion.PPOCRV5,
                           "Rec.model_type": ModelType.MOBILE})
        else:
            params["Rec.model_type"] = ModelType.SMALL if src_lang in self.NEEDS_SMALL_REC else ModelType.TINY
        self.engine = RapidOCR(params=params)
        self.lock = threading.Lock()  # ค้นหาซับอัตโนมัติกับการแปลใช้ตัวอ่านเดียวกัน
        self.last_thumb = None
        self.last_text = ""

    def changed(self, bgr):
        """ภาพในกล่องเปลี่ยนจากรอบก่อนไหม (เทียบภาพย่อขาวดำ ใช้เวลาไม่ถึง 1 มิลลิวินาที)"""
        import numpy as np
        thumb = bgr[::8, ::8, 1].astype(np.int16)
        same = (self.last_thumb is not None and thumb.shape == self.last_thumb.shape
                and np.abs(thumb - self.last_thumb).mean() < 1.5)
        self.last_thumb = thumb
        return not same

    def read(self, bgr):
        if not self.changed(bgr):
            return self.last_text  # ภาพเหมือนเดิม ไม่ต้องอ่านซ้ำ
        self.last_text = self._read(bgr)
        return self.last_text

    def lines(self, bgr, min_score=0.6):
        """ข้อความทุกบรรทัดในภาพ: [(x0, y0, x1, y1, text)]"""
        with self.lock:
            out = self.engine(bgr)
        if out.txts is None:
            return []
        res = []
        for box, txt, score in zip(out.boxes, out.txts, out.scores):
            if score >= min_score:
                xs, ys = [p[0] for p in box], [p[1] for p in box]
                res.append((min(xs), min(ys), max(xs), max(ys), txt))
        return res

    def _read(self, bgr):
        with self.lock:
            out = self.engine(bgr)
        if out.txts is None or len(out.txts) == 0:
            return ""
        items = []
        for box, txt, score in zip(out.boxes, out.txts, out.scores):
            if score < 0.6:
                continue
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append(((sum(ys) / 4), min(xs), max(ys) - min(ys), txt))
        # เรียงบนลงล่าง แล้วซ้ายไปขวา
        items.sort(key=lambda t: (round(t[0] / max(8, t[2] * 0.6)), t[1]))
        text = self.join.join(t[3] for t in items)
        return re.sub(r"\s+", " ", text).strip()


class Translator:
    def __init__(self):
        self.cache = {}
        self.sl, self.tl = "en", "th"

    def translate(self, text, sl=None, tl=None):
        sl, tl = sl or self.sl, tl or self.tl
        key = (sl, tl, text)
        if key in self.cache:
            return self.cache[key]
        try:
            out = self._dict_ext(text, sl, tl)
        except Exception:
            out = self._gtx(text, sl, tl)  # ปลายทางสำรอง เผื่อตัวแรกโดนจำกัด (429)
        if len(self.cache) > 500:
            self.cache.clear()
        self.cache[key] = out
        return out

    @staticmethod
    def _get(url, params):
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read().decode("utf-8"))

    def _gtx(self, text, sl, tl):
        data = self._get("https://translate.googleapis.com/translate_a/single",
                         {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": text})
        return "".join(part[0] for part in data[0] if part and part[0])

    def _dict_ext(self, text, sl, tl):
        data = self._get("https://clients5.google.com/translate_a/t",
                         {"client": "dict-chrome-ex", "sl": sl, "tl": tl, "q": text})
        first = data[0]
        return first if isinstance(first, str) else first[0]


def find_subtitle_region(frames, W, H, exclude=()):
    """หาตำแหน่งซับจากภาพจอหลายเฟรม

    frames: [[(x0, y0, x1, y1, text), ...] ต่อเฟรม] เป็นพิกัดบนจอ
    ซับมักอยู่ครึ่งล่าง ค่อนกลางจอ มีหลายคำ และข้อความเปลี่ยนไปเรื่อยๆ (ต่างจาก HUD ที่นิ่ง)
    คืน [x, y, w, h] ของกล่องอ่านซับ หรือ None ถ้าหาไม่เจอ
    """
    def wordy(t):
        t = t.strip()
        return len(t.split()) >= 2 or (len(t) >= 4 and not t.isascii())

    def blocked(b):
        return any(b[0] < ex + ew and b[2] > ex and b[1] < ey + eh and b[3] > ey for ex, ey, ew, eh in exclude)

    cands = []  # (frame index, box)
    for i, boxes in enumerate(frames):
        for b in boxes:
            cx, cy, bh = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[3] - b[1]
            if cy > H * 0.45 and W * 0.2 < cx < W * 0.8 and 0 < bh < H * 0.12 and wordy(b[4]) and not blocked(b):
                cands.append((i, b))
    if not cands:
        return None

    # บรรทัดที่ข้อความเปลี่ยนระหว่างเฟรม = น่าจะเป็นซับ
    def same_band(a, b):
        return min(a[3], b[3]) - max(a[1], b[1]) > 0.5 * min(a[3] - a[1], b[3] - b[1])
    varied = [(i, b) for i, b in cands
              if any(j != i and same_band(b, c) and norm(c[4]) != norm(b[4]) for j, c in cands)]
    if varied:
        chosen = [b for _, b in varied]
    else:
        # ไม่มีบรรทัดไหนเปลี่ยน: เชื่อเฉพาะข้อความชิดล่างจอ (ปุ่มกด/คำแนะนำกลางจอมักนิ่ง ไม่ใช่ซับ)
        chosen = [b for _, b in cands if (b[1] + b[3]) / 2 > H * 0.7]
        if not chosen:
            return None

    # ตัดบรรทัดที่อยู่ห่างกลุ่มหลักทิ้ง
    hs = sorted(b[3] - b[1] for b in chosen)
    lh = hs[len(hs) // 2]
    cys = sorted((b[1] + b[3]) / 2 for b in chosen)
    mid = cys[len(cys) // 2]
    chosen = [b for b in chosen if abs((b[1] + b[3]) / 2 - mid) <= 3 * lh]

    x0, y0 = min(b[0] for b in chosen), min(b[1] for b in chosen)
    x1, y1 = max(b[2] for b in chosen), max(b[3] for b in chosen)
    # เผื่อซับยาวขึ้น / ขึ้น 2 บรรทัด
    w = max(x1 - x0 + 2 * lh, W * 0.5)
    h = max(y1 - y0 + 1.6 * lh, 2.6 * lh)
    cx = (x0 + x1) / 2
    x = min(max(0, cx - w / 2), W - w)
    y = min(max(0, y0 - lh), H - h)
    return [int(x), int(y), int(w), int(h)]


def norm(s):
    # เก็บเฉพาะตัวอักษร/ตัวเลขทุกภาษา (รวมจีน ญี่ปุ่น เกาหลี รัสเซีย)
    return re.sub(r"[\W_]+", "", s.lower())


def similar(a, b):
    if a == b:
        return True
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() > 0.9


# ---------------------------------------------------------------- กล่องลาก/ปรับขนาดได้

class Box:
    """หน้าต่างลอยที่ลากย้ายได้ และลากมุมขวาล่างเพื่อปรับขนาด (ตอนแก้ไข)"""

    HANDLE = 22

    def __init__(self, root, rect, color, title, on_change):
        self.win = make_overlay(root)
        self.color, self.title, self.on_change = color, title, on_change
        self.editing = False
        x, y, w, h = rect
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.canvas = tk.Canvas(self.win, bg=KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._up)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self._start = None

    def rect(self):
        w = self.win
        return [w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()]

    def draw_edit(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        # พื้นทึบ (สีโปร่งใสจะคลิกทะลุ ลากไม่ได้) แล้วทำทั้งหน้าต่างให้โปร่งแสงแทน
        c.create_rectangle(0, 0, w, h, fill="#303030", outline="")
        c.create_rectangle(2, 2, w - 2, h - 2, outline=self.color, width=3, dash=(10, 5))
        c.create_rectangle(w - self.HANDLE, h - self.HANDLE, w, h, fill=self.color, outline="")
        t = c.create_text(10, 8, anchor="nw", text="  " + self.title + "  ", fill="#141518",
                          font=(UI_FAMILY, 10, "bold"))
        c.tag_lower(c.create_rectangle(*c.bbox(t), fill=self.color, outline=""), t)

    def redraw(self):
        self.canvas.delete("all")
        if self.editing:
            self.draw_edit()

    alpha_edit, alpha_normal = 0.5, 1.0

    def set_editing(self, on):
        self.editing = on
        set_click_through(self.win, not on)
        self.win.attributes("-alpha", self.alpha_edit if on else self.alpha_normal)
        self.redraw()

    def _down(self, e):
        if not self.editing:
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self._resize = e.x > w - self.HANDLE and e.y > h - self.HANDLE
        self._start = (e.x_root, e.y_root, *self.rect())

    def _drag(self, e):
        if not self.editing or not self._start:
            return
        sx, sy, x, y, w, h = self._start
        dx, dy = e.x_root - sx, e.y_root - sy
        if self._resize:
            self.win.geometry(f"{max(120, w + dx)}x{max(40, h + dy)}+{x}+{y}")
        else:
            self.win.geometry(f"{w}x{h}+{x + dx}+{y + dy}")

    def _up(self, e):
        if self.editing:
            self.on_change()


class SubtitleBox(Box):
    def __init__(self, root, rect, cfg, title, on_change):
        super().__init__(root, rect, "#4cc38a", title, on_change)
        self.cfg = cfg
        self.en = ""
        self.th = ""
        self.placeholder = ("Translated subtitle appears here", "Original subtitle appears here")
        exclude_from_capture(self.win)

    def show(self, en, th):
        self.en, self.th = en, th
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        if self.editing:
            self.draw_edit()
        th, en = self.th, self.en
        if not th:
            if not self.editing:
                return
            th, en = self.placeholder
        w, h = c.winfo_width(), c.winfo_height()
        fs = int(self.cfg["font_size"])
        wrap = max(100, w - 40)
        items = []
        # วาดจากล่างขึ้นบน: ไทย (ใหญ่) แล้วอังกฤษ (เล็ก) ข้างบน
        y = h - 12
        for text, size, color, weight in (
            [(th, fs, "white", "bold")]
            + ([(en, max(11, int(fs * 0.55)), "#d8d8d8", "normal")] if self.cfg["show_english"] and en else [])
        ):
            font = ("Leelawadee UI", size, weight) if IS_WIN else ("Helvetica", size, weight)
            if self.cfg["bg_box"]:
                offsets = [(2, 2)]  # เงาเบาๆ
            else:
                k = 2 if size >= 20 else 1  # ขอบดำรอบตัวอักษร ให้อ่านออกบนฉากสว่าง
                offsets = [(dx, dy) for dx in (-k, 0, k) for dy in (-k, 0, k) if dx or dy]
            for dx, dy in offsets:
                items.append(c.create_text(w // 2 + dx, y + dy, text=text, width=wrap, anchor="s",
                                           justify="center", fill="black", font=font))
            t = c.create_text(w // 2, y, text=text, width=wrap, anchor="s", justify="center",
                              fill=color, font=font)
            items.append(t)
            y = c.bbox(t)[1] - 4
        if not self.cfg["bg_box"]:
            return
        x0 = min(c.bbox(i)[0] for i in items) - 18
        x1 = max(c.bbox(i)[2] for i in items) + 18
        y0 = min(c.bbox(i)[1] for i in items) - 8
        bg = c.create_rectangle(max(0, x0), max(0, y0), min(w, x1), h - 2, fill="#101010", outline="")
        c.tag_lower(bg, items[0])


# ---------------------------------------------------------------- หน้าตาโปรแกรม

UI_FAMILY = "Segoe UI" if IS_WIN else "Helvetica Neue"
C = {
    "bg": "#141518", "card": "#1c1e23", "line": "#2a2d34", "hover": "#252830",
    "text": "#ececee", "muted": "#8d919b", "faint": "#5f636d",
    "accent": "#f0b43c", "accent_hi": "#f6c55f", "on_accent": "#1b1505",
    "good": "#4cc38a", "bad": "#e5534b",
}


def F(size=10, weight="normal"):
    return (UI_FAMILY, size, weight)


def _bind_all(widget, seq, fn):
    widget.bind(seq, fn)
    for ch in widget.winfo_children():
        _bind_all(ch, seq, fn)


class Button(tk.Frame):
    """ปุ่มแบน: kind = primary (สีเน้น) / secondary (ขอบบาง) / ghost (ตัวหนังสือ)"""

    def __init__(self, parent, text, command, kind="secondary", hint=None, pad=(14, 7)):
        self.kind, self.command = kind, command
        bg, fg, hint_fg = self._colors(False)
        super().__init__(parent, bg=bg, highlightthickness=1 if kind == "secondary" else 0,
                         highlightbackground=C["line"], cursor="hand2")
        self.label = tk.Label(self, text=text, bg=bg, fg=fg,
                              font=F(11 if kind == "primary" else 10, "bold" if kind == "primary" else "normal"))
        self.label.pack(side="left", padx=pad[0], pady=pad[1])
        self.hint = None
        if hint:
            self.hint = tk.Label(self, text=hint, bg=bg, fg=hint_fg, font=F(9))
            self.hint.pack(side="right", padx=pad[0])
        _bind_all(self, "<Enter>", lambda e: self._paint(True))
        _bind_all(self, "<Leave>", lambda e: self._paint(False))
        _bind_all(self, "<Button-1>", lambda e: self.command())

    def _colors(self, hover):
        if self.kind == "primary":
            return (C["accent_hi"] if hover else C["accent"]), C["on_accent"], "#6b5216"
        if self.kind == "ghost":
            return C["bg"], (C["text"] if hover else C["muted"]), C["faint"]
        return (C["hover"] if hover else C["card"]), C["text"], C["faint"]

    def _paint(self, hover):
        bg, fg, hint_fg = self._colors(hover)
        self.config(bg=bg)
        self.label.config(bg=bg, fg=fg)
        if self.hint:
            self.hint.config(bg=bg, fg=hint_fg)

    def set(self, text=None, kind=None):
        if kind:
            self.kind = kind
            self.config(highlightthickness=1 if kind == "secondary" else 0)
            self.label.config(font=F(11 if kind == "primary" else 10, "bold" if kind == "primary" else "normal"))
        if text is not None:
            self.label.config(text=text)
        self._paint(False)


class Toggle(tk.Canvas):
    """สวิตช์เปิด/ปิด"""

    W, H = 38, 22

    def __init__(self, parent, value, command):
        # เผื่อขอบ 2px กันวงกลมโดนตัดขอบ
        super().__init__(parent, width=self.W + 4, height=self.H + 4, bg=C["card"], highlightthickness=0,
                         bd=0, cursor="hand2")
        self.value, self.command = value, command
        self.bind("<Button-1>", lambda e: self._flip())
        self.draw()

    def _flip(self):
        self.value = not self.value
        self.draw()
        self.command(self.value)

    def set(self, value):
        self.value = value
        self.draw()

    def draw(self):
        self.delete("all")
        o, w, h = 2, self.W, self.H
        r = h // 2
        track = C["accent"] if self.value else C["line"]
        self.create_oval(o, o, o + h, o + h, fill=track, outline=track)
        self.create_oval(o + w - h, o, o + w, o + h, fill=track, outline=track)
        self.create_rectangle(o + r, o, o + w - r, o + h, fill=track, outline=track)
        x = o + (w - h + 3 if self.value else 3)
        knob = C["on_accent"] if self.value else C["muted"]
        self.create_oval(x, o + 3, x + h - 6, o + h - 3, fill=knob, outline=knob)


class Stepper(tk.Frame):
    """[−] ค่า [+]"""

    def __init__(self, parent, value, command, lo=12, hi=72, step=2):
        super().__init__(parent, bg=C["card"])
        self.value, self.command, self.lo, self.hi, self.step = value, command, lo, hi, step
        Button(self, "−", lambda: self.change(-self.step), pad=(9, 2)).pack(side="left")
        self.label = tk.Label(self, text=str(value), width=3, bg=C["card"], fg=C["text"], font=F(10, "bold"))
        self.label.pack(side="left", padx=4)
        Button(self, "+", lambda: self.change(self.step), pad=(8, 2)).pack(side="left")

    def change(self, d):
        self.set(self.value + d)
        self.command(self.value)

    def set(self, v):
        self.value = max(self.lo, min(self.hi, int(v)))
        self.label.config(text=str(self.value))


class Segmented(tk.Frame):
    """ตัวเลือกแบบแถบ เลือกได้อย่างเดียว"""

    def __init__(self, parent, options, value, command):
        super().__init__(parent, bg=C["line"], padx=1, pady=1)
        self.value, self.command, self.items = value, command, {}
        for v, text in options:
            lb = tk.Label(self, text=text, font=F(9), padx=10, pady=3, cursor="hand2")
            lb.pack(side="left", padx=(0, 1) if v != options[-1][0] else 0)
            lb.bind("<Button-1>", lambda e, v=v: self._pick(v))
            self.items[v] = lb
        self.paint()

    def _pick(self, v):
        self.value = v
        self.paint()
        self.command(v)

    def paint(self):
        for v, lb in self.items.items():
            on = v == self.value
            lb.config(bg=C["hover"] if on else C["card"], fg=C["text"] if on else C["muted"])


class Dropdown(Button):
    """ปุ่มที่กดแล้วขึ้นรายการให้เลือก"""

    def __init__(self, parent, options, value, command):
        self.options, self.value, self.on_pick = options, value, command
        super().__init__(parent, self._text(), self._open, pad=(10, 4))

    def _text(self):
        return dict(self.options).get(self.value, self.value) + "   ▾"

    def _open(self):
        m = tk.Menu(self, tearoff=0, bg=C["card"], fg=C["text"], activebackground=C["hover"],
                    activeforeground=C["text"], bd=0, font=F(10))
        for code, text in self.options:
            m.add_command(label=("✓  " if code == self.value else "     ") + text,
                          command=lambda c=code: self._pick(c))
        m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())

    def _pick(self, code):
        self.value = code
        self.set(self._text())
        self.on_pick(code)


class Card(tk.Frame):
    """กล่องรวมการตั้งค่า แต่ละแถวคั่นด้วยเส้นบาง"""

    def __init__(self, parent):
        super().__init__(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        self.rows = 0

    def row(self, label, hint=None, key=None):
        if self.rows:
            tk.Frame(self, bg=C["line"], height=1).pack(fill="x", padx=14)
        self.rows += 1
        r = tk.Frame(self, bg=C["card"])
        r.pack(fill="x", padx=14, pady=7)
        left = tk.Frame(r, bg=C["card"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=label, bg=C["card"], fg=C["text"], font=F(10), anchor="w").pack(anchor="w")
        if hint:
            tk.Label(left, text=hint, bg=C["card"], fg=C["muted"], font=F(9), anchor="w").pack(anchor="w")
        right = tk.Frame(r, bg=C["card"])
        right.pack(side="right")
        if key:
            tk.Label(right, text=key, bg=C["card"], fg=C["faint"], font=F(9)).pack(side="left", padx=(0, 10))
        return right


# ---------------------------------------------------------------- แอปหลัก

class App:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg=C["bg"])
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.ui_q = queue.Queue()
        self.running = False
        self.ocr = None
        self.tr = Translator()
        self.status = ("st_loading", {}, "faint")
        self.subs_visible = True

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        region = self.cfg["region"] or [int(sw * .2), int(sh * .8), int(sw * .6), int(sh * .14)]
        sub = self.cfg["sub"] or [int(sw * .15), int(sh * .58), int(sw * .7), int(sh * .2)]
        first_run = not self.cfg["region"]

        self.region = Box(self.root, region, C["accent"], self.t("box_region"), self.save_boxes)
        self.sub = SubtitleBox(self.root, sub, self.cfg, self.t("box_sub"), self.save_boxes)
        self.sub.alpha_edit, self.sub.alpha_normal = 0.75, 0.92
        self.cfg["region"], self.cfg["sub"] = region, sub
        self.region.set_editing(False)
        self.region.win.withdraw()
        self.sub.set_editing(False)

        self.build_panel()
        self.setup_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(50, self.pump)
        threading.Thread(target=self.load_ocr, daemon=True).start()
        if first_run:
            self.toggle_region()
            self.toggle_sub()

    def ui(self):
        return self.cfg.get("ui_lang") or system_ui_lang()

    def t(self, key, **kw):
        ui = self.ui()
        text = STRINGS.get(ui, STRINGS["en"]).get(key) or STRINGS["en"][key]
        return text.format(**kw) if kw else text

    # ---------- หน้าต่างควบคุม
    def build_panel(self):
        r = self.root
        for w in r.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        ui = self.ui()
        body = tk.Frame(r, bg=C["bg"], padx=18, pady=16)
        body.pack(fill="both")

        head = tk.Frame(body, bg=C["bg"])
        head.pack(fill="x")
        title = tk.Frame(head, bg=C["bg"])
        title.pack(side="left")
        tk.Label(title, text=APP_NAME, bg=C["bg"], fg=C["text"], font=F(15, "bold")).pack(anchor="w")
        st = tk.Frame(head, bg=C["bg"])
        st.pack(side="right", anchor="n", pady=4)
        self.dot = tk.Canvas(st, width=12, height=12, bg=C["bg"], highlightthickness=0, bd=0)
        self.dot.pack(side="left", padx=(0, 6))
        self.status_label = tk.Label(st, bg=C["bg"], fg=C["muted"], font=F(9), wraplength=200, justify="right")
        self.status_label.pack(side="left")

        self.run_btn = Button(body, self.t("stop" if self.running else "start"), self.toggle_run,
                              kind="secondary" if self.running else "primary", hint="Ctrl+Alt+T", pad=(16, 10))
        self.run_btn.pack(fill="x", pady=(14, 2))

        # สองคอลัมน์ กว้างเท่ากันเสมอ ไม่ว่าจะเป็นภาษาไหน
        cols = tk.Frame(body, bg=C["bg"])
        cols.pack(fill="x")
        cols.grid_columnconfigure(0, weight=1, uniform="col", minsize=330)
        cols.grid_columnconfigure(1, weight=1, uniform="col", minsize=330)
        left, right = tk.Frame(cols, bg=C["bg"]), tk.Frame(cols, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        def section(key, parent):
            tk.Label(parent, text=self.t(key), bg=C["bg"], fg=C["muted"], font=F(9, "bold")).pack(
                anchor="w", pady=(12, 6))
            card = Card(parent)
            card.pack(fill="x")
            return card

        card = section("sec_setup", left)
        row = card.row(self.t("capture"), self.t("capture_hint"), "Ctrl+Alt+R")
        Button(row, self.t("auto"), self.auto_detect, pad=(12, 4)).pack(side="left", padx=(0, 6))
        self.region_btn = Button(row, self.t("done" if self.region.editing else "edit"), self.toggle_region, pad=(12, 4))
        self.region_btn.pack(side="left")
        row = card.row(self.t("position"), self.t("position_hint"), "Ctrl+Alt+M")
        self.sub_btn = Button(row, self.t("done" if self.sub.editing else "edit"), self.toggle_sub, pad=(12, 4))
        self.sub_btn.pack(side="left")
        row = card.row(self.t("show_subs"), key="Ctrl+Alt+H")
        self.w_show = Toggle(row, self.subs_visible, lambda v: self.toggle_hide())
        self.w_show.pack(side="left")

        card = section("sec_lang", left)
        row = card.row(self.t("game_lang"))
        Dropdown(row, [(c, lang_name(SOURCE_LANGS, c, ui)) for c, *_ in SOURCE_LANGS],
                 self.cfg["src_lang"], lambda c: self.lang_changed(src=c)).pack(side="left")
        row = card.row(self.t("translate_to"))
        Dropdown(row, [(c, lang_name(TARGET_LANGS, c, ui)) for c, *_ in TARGET_LANGS],
                 self.cfg["dst_lang"], lambda c: self.lang_changed(dst=c)).pack(side="left")

        card = section("sec_style", right)
        row = card.row(self.t("text_size"), key="Ctrl+Alt+ = / −")
        self.w_size = Stepper(row, self.cfg["font_size"], self.set_font_size)
        self.w_size.pack(side="left")
        row = card.row(self.t("show_orig"), self.t("show_orig_hint"), "Ctrl+Alt+E")
        self.w_eng = Toggle(row, self.cfg["show_english"], self.set_english)
        self.w_eng.pack(side="left")
        row = card.row(self.t("bg_box"), self.t("bg_box_hint"), "Ctrl+Alt+B")
        self.w_box = Toggle(row, self.cfg["bg_box"], self.set_box)
        self.w_box.pack(side="left")

        card = section("sec_scan", right)
        row = card.row(self.t("scan"))
        Segmented(row, [(0.3, self.t("fast")), (0.5, self.t("normal")), (1.0, self.t("light"))],
                  self.cfg["interval"], self.set_interval).pack(side="left")

        foot = tk.Frame(body, bg=C["bg"])
        foot.pack(fill="x", pady=(16, 0))
        tk.Label(foot, text=self.t("ui_lang"), bg=C["bg"], fg=C["muted"], font=F(9)).pack(side="left")
        Segmented(foot, UI_LANGS, ui, self.set_ui_lang).pack(side="left", padx=8)
        Button(foot, self.t("quit"), self.quit, kind="ghost", pad=(4, 2)).pack(side="right")
        Button(foot, self.t("about"), self.about, kind="ghost", pad=(4, 2)).pack(side="right", padx=(0, 12))
        Button(foot, self.t("update"), self.check_update, kind="ghost", pad=(4, 2)).pack(side="right", padx=(0, 12))

        self.paint_status()
        self.region.title, self.sub.title = self.t("box_region"), self.t("box_sub")
        self.sub.placeholder = (self.t("ph_tr"), self.t("ph_orig"))
        self.region.redraw()
        self.sub.redraw()

    def set_status(self, key, tone="muted", **kw):
        self.status = (key, kw, tone)
        self.paint_status()

    def paint_status(self):
        key, kw, tone = self.status
        self.status_label.config(text=self.t(key, **kw), fg=C["text"] if tone == "good" else C["muted"])
        self.dot.delete("all")
        col = {"good": C["good"], "bad": C["bad"], "ready": C["accent"]}.get(tone, C["faint"])
        self.dot.create_oval(2, 2, 10, 10, fill=col, outline=col)

    def check_update(self):
        self.set_status("up_checking")

        def run():
            try:
                new, url = latest_release()
                self.ui_q.put(("call", lambda: self._update_result(new, url)))
            except Exception as e:
                self.ui_q.put(("status", ("up_fail", "bad", {"e": e})))
        threading.Thread(target=run, daemon=True).start()

    def _update_result(self, new, url):
        if version_tuple(new) <= version_tuple(APP_VERSION):
            self.set_status("up_latest", "good", ver=APP_VERSION)
            return
        self.paint_status_idle()
        import webbrowser
        self.dialog(self.t("up_title"), self.t("up_body", new=new, cur=APP_VERSION),
                    [(self.t("up_later"), None, "secondary"),
                     (self.t("up_download"), lambda: webbrowser.open(url), "primary")])

    def paint_status_idle(self):
        self.set_status("st_running" if self.running else "st_ready", "good" if self.running else "ready")

    def dialog(self, title, body, buttons):
        """กล่องข้อความตามธีมของโปรแกรม: buttons = [(ข้อความ, คำสั่ง, primary/secondary)] เรียงซ้ายไปขวา"""
        r = self.root
        r.attributes("-topmost", False)
        d = tk.Toplevel(r, bg=C["bg"], padx=22, pady=18)
        d.bind("<Destroy>", lambda e: e.widget is d and r.winfo_exists() and r.attributes("-topmost", True))
        d.title(APP_NAME)
        d.resizable(False, False)
        d.transient(r)
        d.attributes("-topmost", True)
        tk.Label(d, text=title, bg=C["bg"], fg=C["text"], font=F(13, "bold")).pack(anchor="w")
        tk.Label(d, text=body, bg=C["bg"], fg=C["muted"], font=F(10), justify="left",
                 wraplength=380).pack(anchor="w", pady=(6, 0))
        bar = tk.Frame(d, bg=C["bg"])
        bar.pack(fill="x", pady=(18, 0))

        def press(fn):
            d.destroy()
            if fn:
                fn()
        for text, fn, kind in reversed(buttons):
            Button(bar, text, lambda fn=fn: press(fn), kind=kind, pad=(18, 6)).pack(side="right", padx=(10, 0))
        d.bind("<Escape>", lambda e: d.destroy())
        d.update_idletasks()
        x = r.winfo_rootx() + (r.winfo_width() - d.winfo_width()) // 2
        y = r.winfo_rooty() + (r.winfo_height() - d.winfo_height()) // 3
        d.geometry(f"+{max(0, x)}+{max(0, y)}")
        d.lift()
        d.grab_set()
        self.last_dialog = d
        return d

    def about(self):
        from tkinter import messagebox
        messagebox.showinfo(self.t("about_title", app=APP_NAME),
                            self.t("about_body", app=APP_NAME, ver=APP_VERSION, dev=DEVELOPER), parent=self.root)

    # ---------- ปุ่มลัด
    def setup_hotkeys(self):
        try:
            import keyboard
        except Exception:
            self.set_status("st_no_keys", "bad")
            return
        keys = {
            "ctrl+alt+t": self.toggle_run, "ctrl+alt+r": self.toggle_region, "ctrl+alt+a": self.auto_detect,
            "ctrl+alt+m": self.toggle_sub, "ctrl+alt+h": self.toggle_hide,
            "ctrl+alt+e": lambda: self.set_english(not self.cfg["show_english"]),
            "ctrl+alt+b": lambda: self.set_box(not self.cfg["bg_box"]),
            "ctrl+alt+=": lambda: self.set_font_size(self.cfg["font_size"] + 2),
            "ctrl+alt+-": lambda: self.set_font_size(self.cfg["font_size"] - 2),
        }
        for k, fn in keys.items():
            keyboard.add_hotkey(k, lambda fn=fn: self.ui_q.put(("call", fn)), suppress=False)

    # ---------- คำสั่ง
    def save_boxes(self):
        self.cfg["region"] = self.region.rect()
        self.cfg["sub"] = self.sub.rect()
        save_config(self.cfg)

    def auto_detect(self):
        """จับภาพทั้งจอ ~5 วิ แล้วหาว่าซับอยู่ตรงไหน"""
        if self.ocr is None or getattr(self, "detecting", False):
            return
        self.detecting = True
        if self.running:
            self.toggle_run()
        if self.region.editing:
            self.toggle_region()
        self.set_status("st_auto", "ready")
        r = self.root
        # ไม่นับข้อความในหน้าต่างโปรแกรมเอง และในกล่องซับแปล
        exclude = [(r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()), tuple(self.sub.rect())]
        threading.Thread(target=self._detect_worker, args=(exclude,), daemon=True).start()

    def _detect_worker(self, exclude):
        import mss
        import numpy as np
        region = None
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]
                W, H, top = mon["width"], mon["height"], int(mon["height"] * 0.4)
                f = max(1, -(-W // 1600))  # ย่อภาพให้กว้างไม่เกิน ~1600 px
                frames = []
                for _ in range(10):
                    shot = np.asarray(sct.grab({"left": mon["left"], "top": mon["top"] + top,
                                                "width": W, "height": H - top}))[::f, ::f, :3]
                    boxes = self.ocr.lines(np.ascontiguousarray(shot))
                    frames.append([(x0 * f, y0 * f + top, x1 * f, y1 * f + top, t) for x0, y0, x1, y1, t in boxes])
                    time.sleep(0.45)
                ex = [(x - mon["left"], y - mon["top"], w, h) for x, y, w, h in exclude]
                found = find_subtitle_region(frames, W, H, ex)
                if found:
                    region = [found[0] + mon["left"], found[1] + mon["top"], found[2], found[3]]
        except Exception as e:
            self.ui_q.put(("status", ("st_error", "bad", {"e": e})))
        self.ui_q.put(("call", lambda: self._detect_done(region)))

    def _detect_done(self, region):
        self.detecting = False
        if not region:
            self.set_status("st_auto_none", "bad")
            return
        x, y, w, h = region
        self.region.win.geometry(f"{w}x{h}+{x}+{y}")
        self.cfg["region"] = region
        save_config(self.cfg)
        if not self.region.editing:
            self.toggle_region()  # โชว์กล่องให้ดู ปรับต่อได้ กดเสร็จเมื่อพอใจ
        self.set_status("st_auto_found", "good")

    def toggle_region(self):
        on = not self.region.editing
        if on:
            self.region.win.deiconify()
            self.region.win.attributes("-topmost", True)
        self.region.set_editing(on)
        if not on:
            self.save_boxes()
            self.region.win.withdraw()
        if hasattr(self, "region_btn"):
            self.region_btn.set(self.t("done" if on else "edit"))

    def toggle_sub(self):
        self.sub.set_editing(not self.sub.editing)
        if not self.sub.editing:
            self.save_boxes()
        if hasattr(self, "sub_btn"):
            self.sub_btn.set(self.t("done" if self.sub.editing else "edit"))

    def toggle_hide(self):
        self.subs_visible = not self.subs_visible
        if self.subs_visible:
            self.sub.win.deiconify()
            self.sub.win.attributes("-topmost", True)
            set_click_through(self.sub.win, not self.sub.editing)
            exclude_from_capture(self.sub.win)
        else:
            self.sub.win.withdraw()
        self.w_show.set(self.subs_visible)

    def set_english(self, v):
        self.cfg["show_english"] = bool(v)
        self.w_eng.set(self.cfg["show_english"])
        save_config(self.cfg)
        self.sub.redraw()

    def set_box(self, v):
        self.cfg["bg_box"] = bool(v)
        self.w_box.set(self.cfg["bg_box"])
        save_config(self.cfg)
        self.sub.redraw()

    def set_interval(self, v):
        self.cfg["interval"] = v
        save_config(self.cfg)

    def set_font_size(self, v):
        self.cfg["font_size"] = max(12, min(72, int(v)))
        self.w_size.set(self.cfg["font_size"])
        save_config(self.cfg)
        self.sub.redraw()

    def set_ui_lang(self, code):
        self.cfg["ui_lang"] = code
        save_config(self.cfg)
        self.build_panel()

    def lang_changed(self, src=None, dst=None):
        src = src or self.cfg["src_lang"]
        dst = dst or self.cfg["dst_lang"]
        old = self.cfg["src_lang"]
        need_reload = SRC_MODEL.get(src) != SRC_MODEL.get(old) or (src in CJK) != (old in CJK)
        self.cfg["src_lang"], self.cfg["dst_lang"] = src, dst
        self.tr.sl, self.tr.tl = src, dst
        save_config(self.cfg)
        if need_reload:
            self.ocr_ready = False
            self.set_status("st_reload", lang=lang_name(SOURCE_LANGS, src, self.ui()))
            threading.Thread(target=self.load_ocr, daemon=True).start()

    def toggle_run(self):
        if self.ocr is None:
            return
        self.running = not self.running
        if self.running:
            if self.region.editing:
                self.toggle_region()
            if self.sub.editing:
                self.toggle_sub()
            self.run_btn.set(self.t("stop"), "secondary")
            self.set_status("st_running", "good")
            threading.Thread(target=self.worker, daemon=True).start()
        else:
            self.run_btn.set(self.t("start"), "primary")
            self.set_status("st_stopped")
            self.sub.show("", "")

    def set_close_action(self, v):
        self.cfg["close_action"] = v
        save_config(self.cfg)

    def on_close(self):
        """ปุ่ม X: ทำตามที่จำไว้ หรือถามครั้งแรก"""
        action = self.cfg.get("close_action", "ask")
        if action == "minimize":
            self.root.iconify()
        elif action == "quit":
            self.quit()
        else:
            self.ask_close()

    def ask_close(self):
        r = self.root
        r.attributes("-topmost", False)  # ให้กล่องถามอยู่เหนือหน้าต่างหลักได้แน่นอน
        d = tk.Toplevel(r, bg=C["bg"], padx=22, pady=18)
        d.bind("<Destroy>", lambda e: e.widget is d and r.winfo_exists() and r.attributes("-topmost", True))
        d.title(APP_NAME)
        d.resizable(False, False)
        d.transient(r)
        d.attributes("-topmost", True)
        tk.Label(d, text=self.t("close_title", app=APP_NAME), bg=C["bg"], fg=C["text"],
                 font=F(13, "bold")).pack(anchor="w")
        tk.Label(d, text=self.t("close_body"), bg=C["bg"], fg=C["muted"], font=F(10),
                 justify="left").pack(anchor="w", pady=(6, 14))
        remember = {"on": False}
        rm = tk.Frame(d, bg=C["bg"])
        rm.pack(anchor="w", fill="x")
        box = tk.Canvas(rm, width=18, height=18, bg=C["bg"], highlightthickness=0, bd=0, cursor="hand2")
        box.pack(side="left")
        lab = tk.Label(rm, text=self.t("remember"), bg=C["bg"], fg=C["text"], font=F(10), cursor="hand2")
        lab.pack(side="left", padx=(8, 0))

        def draw():
            box.delete("all")
            if remember["on"]:
                box.create_rectangle(1, 1, 17, 17, fill=C["accent"], outline=C["accent"])
                box.create_line(5, 9, 8, 12, 13, 5, fill=C["on_accent"], width=2)
            else:
                box.create_rectangle(1, 1, 17, 17, fill=C["card"], outline=C["muted"])

        def flip(_=None):
            remember["on"] = not remember["on"]
            draw()
        box.bind("<Button-1>", flip)
        lab.bind("<Button-1>", flip)
        draw()

        def choose(action):
            if remember["on"]:
                self.set_close_action(action)
            d.destroy()
            if action == "quit":
                self.quit()
            else:
                r.iconify()

        bar = tk.Frame(d, bg=C["bg"])
        bar.pack(fill="x", pady=(18, 0))
        Button(bar, self.t("minimize"), lambda: choose("minimize"), kind="primary", pad=(18, 7)).pack(side="right")
        Button(bar, self.t("quit"), lambda: choose("quit"), pad=(18, 6)).pack(side="right", padx=(0, 10))
        d.bind("<Escape>", lambda e: d.destroy())
        d.update_idletasks()
        x = r.winfo_rootx() + (r.winfo_width() - d.winfo_width()) // 2
        y = r.winfo_rooty() + (r.winfo_height() - d.winfo_height()) // 3
        d.geometry(f"+{max(0, x)}+{max(0, y)}")
        d.lift()
        d.grab_set()
        d.focus_set()
        self.close_dialog = d

    def quit(self):
        self.running = False
        self.save_boxes()
        self.root.destroy()

    # ---------- เธรดทำงาน
    def load_ocr(self):
        try:
            self.tr.sl, self.tr.tl = self.cfg["src_lang"], self.cfg["dst_lang"]
            self.ocr = OCR(self.cfg["src_lang"])
            self.ui_q.put(("ready", None))
        except Exception as e:
            self.ui_q.put(("status", ("st_ocr_fail", "bad", {"e": e})))

    def worker(self):
        import mss
        import numpy as np
        candidate = shown = ""
        empty_since = None
        with mss.mss() as sct:
            while self.running:
                t0 = time.time()
                try:
                    x, y, w, h = self.cfg["region"]  # อ่านจาก cfg (tk ห้ามเรียกจากเธรดอื่น)
                    shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
                    bgr = np.asarray(shot)[:, :, :3]
                    text = self.ocr.read(bgr)
                    key = norm(text)
                    if len(key) < (1 if self.cfg["src_lang"] in CJK else 3):
                        empty_since = empty_since or time.time()
                        if shown and time.time() - empty_since > 1.2:
                            shown = ""
                            self.ui_q.put(("sub", ("", "")))
                        candidate = ""
                    else:
                        empty_since = None
                        if not similar(key, shown):
                            if not similar(key, candidate):
                                candidate = key  # รอให้ข้อความนิ่งอีก 1 รอบก่อนแปล
                            else:
                                shown = key
                                th = self.tr.translate(text)
                                if self.running:
                                    self.ui_q.put(("sub", (text, th)))
                                    self.ui_q.put(("status", ("st_running", "good", {})))
                except Exception as e:
                    shown = ""
                    self.ui_q.put(("status", ("st_error", "bad", {"e": e})))
                time.sleep(max(0.05, self.cfg["interval"] - (time.time() - t0)))

    def pump(self):
        try:
            while True:
                kind, val = self.ui_q.get_nowait()
                if kind == "call":
                    val()
                elif kind == "sub":
                    if self.running:
                        self.sub.show(*val)
                elif kind == "status":
                    key, tone, kw = val
                    self.set_status(key, tone, **kw)
                elif kind == "ready":
                    self.set_status("st_running" if self.running else "st_ready",
                                    "good" if self.running else "ready")
        except queue.Empty:
            pass
        self.root.after(50, self.pump)

    def run(self):
        self.root.mainloop()


def selftest(out_path):
    """ใช้ตอน build: เช็กว่าตัวอ่าน OCR โหลดและอ่านภาพได้จริงใน exe (ไม่เปิดหน้าต่าง)"""
    import numpy as np
    try:
        ocr = OCR("en")
        img = np.full((120, 800, 3), 60, np.uint8)
        ocr.read(img)
        result = "ok"
    except Exception as e:
        result = f"fail: {e!r}"
    Path(out_path).write_text(result, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
    else:
        App().run()
