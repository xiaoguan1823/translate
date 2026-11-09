#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
翻译工具 - 按快捷键手动触发翻译
支持多语言、深色模式、自定义快捷键、系统托盘
"""

import customtkinter as ctk
import threading
import time
import json
import os
import hashlib
import random
import sys
import ctypes
import requests
import pyperclip

# ── 翻译引擎 ──
from deep_translator import GoogleTranslator
try:
    from deep_translator import DeeplTranslator
except ImportError:
    DeeplTranslator = None
try:
    from deep_translator import BaiduTranslator
except ImportError:
    BaiduTranslator = None

# ── 系统托盘 ──
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), '翻译工具')
    os.makedirs(APP_DIR, exist_ok=True)
    # 迁移旧配置（exe同目录 → AppData）
    old_cfg = os.path.join(os.path.dirname(sys.executable), "translator_config.json")
    if os.path.isfile(old_cfg) and not os.path.isfile(os.path.join(APP_DIR, "translator_config.json")):
        try:
            import shutil
            shutil.copy2(old_cfg, os.path.join(APP_DIR, "translator_config.json"))
        except Exception:
            pass
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "translator_config.json")

LANGUAGES = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "pt": "Português",
    "ru": "Русский",
}

# 各平台的语言代码映射
PROVIDER_LANG_MAP = {
    "google": {"zh": "zh-CN", "en": "en", "ja": "ja", "ko": "ko",
               "fr": "fr", "de": "de", "es": "es", "pt": "pt", "ru": "ru"},
    "youdao": {"zh": "zh-CHS", "en": "en", "ja": "ja", "ko": "ko",
               "fr": "fr", "de": "de", "es": "es", "pt": "pt", "ru": "ru"},
    "baidu":  {"zh": "zh", "en": "en", "ja": "jp", "ko": "kor",
               "fr": "fra", "de": "de", "es": "spa", "pt": "pt", "ru": "ru"},
    "deepl":  {"zh": "ZH", "en": "EN", "ja": "JA", "ko": "KO",
               "fr": "FR", "de": "DE", "es": "ES", "pt": "PT", "ru": "RU"},
}

DEFAULT_CONFIG = {
    "provider": "google",
    "target_lang": "zh",
    "dark_mode": False,
    "hotkey": {"modifiers": ["ctrl"], "key": "t"},
    "smart_mode": True,
    "deepl": {"api_key": ""},
    "baidu": {"app_id": "", "app_key": ""},
    "youdao": {"app_id": "", "app_key": ""}
}

PROVIDER_INFO = {
    "google": ("Google 翻译", "无需配置"),
    "deepl": ("DeepL 翻译", "需 API Key"),
    "baidu": ("百度翻译", "需 App ID + Key"),
    "youdao": ("有道翻译", "需 App ID + Key"),
}


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2, sort_keys=False)


# ═══════════════════════════════════════════
# 语言检测 & 翻译
# ═══════════════════════════════════════════
def detect_lang(text):
    if not text:
        return "en"
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    hira = sum(1 for c in text if "぀" <= c <= "ゟ")
    kata = sum(1 for c in text if "゠" <= c <= "ヿ")
    hangul = sum(1 for c in text if "가" <= c <= "힯")
    total = max(len(text), 1)
    if (hira + kata) / total > 0.05:
        return "ja"
    if hangul / total > 0.05:
        return "ko"
    if cjk / total > 0.1:
        return "zh"
    return "en"


def get_proxy():
    for var in ["HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"]:
        val = os.environ.get(var, "")
        if val:
            return {"https": val, "http": val}
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        ) as key:
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            if enabled:
                server = winreg.QueryValueEx(key, "ProxyServer")[0]
                if server and "=" not in server:
                    proxy = f"http://{server}"
                    return {"https": proxy, "http": proxy}
    except Exception:
        pass
    return None


def do_translate(text, provider, target_lang, cfg):
    src_lang = detect_lang(text)
    if src_lang == target_lang:
        return text, src_lang, target_lang

    proxy = get_proxy()
    pmap = PROVIDER_LANG_MAP.get(provider, PROVIDER_LANG_MAP["google"])
    src_code = pmap.get(src_lang, pmap["en"])
    tgt_code = pmap.get(target_lang, pmap["zh"])

    if provider == "google":
        t = GoogleTranslator(source=src_code, target=tgt_code, proxies=proxy)
        result = t.translate(text)

    elif provider == "deepl":
        if not DeeplTranslator:
            raise Exception("DeepL 库不可用")
        k = cfg.get("deepl", {}).get("api_key", "")
        if not k:
            raise Exception("请先在设置中填写 DeepL API Key")
        t = DeeplTranslator(api_key=k, source=src_lang, target=tgt_code)
        result = t.translate(text)

    elif provider == "baidu":
        if not BaiduTranslator:
            raise Exception("百度翻译库不可用")
        bd = cfg.get("baidu", {})
        if not bd.get("app_id") or not bd.get("app_key"):
            raise Exception("请先在设置中填写百度翻译 App ID 和 App Key")
        t = BaiduTranslator(app_id=bd["app_id"], app_key=bd["app_key"],
                            source=src_lang, target=tgt_code)
        result = t.translate(text)

    elif provider == "youdao":
        yd = cfg.get("youdao", {})
        if not yd.get("app_id") or not yd.get("app_key"):
            raise Exception("请先在设置中填写有道翻译 App ID 和 App Key")

        def youdao_api(text):
            salt = str(random.randint(10000, 99999))
            sign = hashlib.md5(
                (yd["app_id"] + text + salt + yd["app_key"]).encode()
            ).hexdigest()
            resp = requests.post(
                "https://openapi.youdao.com/api",
                data={
                    "q": text, "from": src_code, "to": tgt_code,
                    "appKey": yd["app_id"], "salt": salt, "sign": sign,
                },
                timeout=15,
            )
            j = resp.json()
            if j.get("errorCode") != "0":
                raise Exception(f"有道API错误: {j.get('errorCode')}")
            return j["translation"][0]

        result = youdao_api(text)
    else:
        raise Exception(f"不支持的翻译平台: {provider}")

    return result, src_lang, target_lang


# ═══════════════════════════════════════════
# 热键虚拟键码
# ═══════════════════════════════════════════
VK_MAP = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4a, "k": 0x4b, "l": 0x4c,
    "m": 0x4d, "n": 0x4e, "o": 0x4f, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5a,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7a, "f12": 0x7b,
}

MOD_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12}


def format_hotkey(hk):
    parts = []
    for m in hk.get("modifiers", []):
        parts.append(m.capitalize())
    parts.append(hk.get("key", "").upper())
    return "+".join(parts)


# ═══════════════════════════════════════════
# 设置窗口
# ═══════════════════════════════════════════
class SettingsDialog:
    def __init__(self, parent, cfg, on_save):
        self.cfg = dict(cfg)
        self.on_save = on_save
        self._entries = {}
        self._capturing_hk = False

        self.win = ctk.CTkToplevel(parent)
        self.win.title("翻译设置")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.update_idletasks()
        st_w, st_h = 500, 520
        sx = (parent.winfo_screenwidth() - st_w) // 2
        sy = (parent.winfo_screenheight() - st_h) // 2
        self.win.geometry(f"{st_w}x{st_h}+{sx}+{sy}")
        self.win.bind("<KeyPress>", self._on_hk_key, add="+")

        self._build()
        self.win.wait_window()

    def _build(self):
        self.win.grid_columnconfigure(0, weight=1)

        row = 0

        # ── 翻译平台 ──
        ctk.CTkLabel(self.win, text="翻译平台",
                     font=("Microsoft YaHei UI", 13, "bold"),
                     anchor="w").grid(row=row, column=0, padx=20, pady=(16, 4), sticky="w")
        row += 1

        providers = list(PROVIDER_INFO.keys())
        p_labels = [f"{PROVIDER_INFO[k][0]}" for k in providers]
        self._label_to_key = {l: k for l, k in zip(p_labels, providers)}
        current = self.cfg.get("provider", "google")
        self.provider_combo = ctk.CTkComboBox(
            self.win, values=p_labels, state="readonly",
            width=300, command=self._on_provider_change
        )
        self.provider_combo.set(PROVIDER_INFO[current][0])
        self.provider_combo.grid(row=row, column=0, padx=20, pady=(0, 4), sticky="w")
        row += 1

        self.provider_hint = ctk.CTkLabel(
            self.win, text="", font=("Microsoft YaHei UI", 10),
            text_color="gray", anchor="w", wraplength=460
        )
        self.provider_hint.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="w")
        row += 1

        # Provider API key fields
        self.api_frame = ctk.CTkFrame(self.win, fg_color="transparent")
        self.api_frame.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.api_frame.grid_columnconfigure(1, weight=1)
        row += 1

        # ── 翻译方向 ──
        sep = ctk.CTkFrame(self.win, height=1)
        sep.grid(row=row, column=0, padx=20, pady=6, sticky="ew")
        row += 1

        ctk.CTkLabel(self.win, text="翻译方向",
                     font=("Microsoft YaHei UI", 13, "bold"),
                     anchor="w").grid(row=row, column=0, padx=20, pady=(4, 4), sticky="w")
        row += 1

        smart_val = self.cfg.get("smart_mode", True)
        self.smart_var = ctk.BooleanVar(value=smart_val)

        def on_smart_toggle():
            state = "disabled" if self.smart_var.get() else "normal"
            self.lang_combo.configure(state=state)

        smart_sw = ctk.CTkSwitch(
            self.win, text="智能互译（自动中↔英，忽略目标语言）",
            variable=self.smart_var, onvalue=True, offvalue=False,
            font=("Microsoft YaHei UI", 12),
            command=on_smart_toggle,
        )
        smart_sw.grid(row=row, column=0, padx=20, pady=(0, 4), sticky="w")
        row += 1

        lang_labels = [v for k, v in LANGUAGES.items()]
        self._label_to_lang = {v: k for k, v in LANGUAGES.items()}
        current_lang = self.cfg.get("target_lang", "zh")

        lang_f = ctk.CTkFrame(self.win, fg_color="transparent")
        lang_f.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="w")
        row += 1
        ctk.CTkLabel(lang_f, text="目标语言:",
                     font=("Microsoft YaHei UI", 12)).pack(side="left")
        self.lang_combo = ctk.CTkComboBox(
            lang_f, values=lang_labels, state="readonly", width=180
        )
        self.lang_combo.set(LANGUAGES.get(current_lang, "中文"))
        self.lang_combo.pack(side="left", padx=(6, 0))
        if smart_val:
            self.lang_combo.configure(state="disabled")

        # ── 快捷键 ──
        sep2 = ctk.CTkFrame(self.win, height=1)
        sep2.grid(row=row, column=0, padx=20, pady=6, sticky="ew")
        row += 1

        ctk.CTkLabel(self.win, text="快捷键",
                     font=("Microsoft YaHei UI", 13, "bold"),
                     anchor="w").grid(row=row, column=0, padx=20, pady=(4, 4), sticky="w")
        row += 1

        hkf = ctk.CTkFrame(self.win, fg_color="transparent")
        hkf.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="w")
        row += 1

        hk = self.cfg.get("hotkey", {"modifiers": ["ctrl", "shift"], "key": "t"})
        self._hotkey = dict(hk)

        ctk.CTkLabel(hkf, text="当前:", font=("Microsoft YaHei UI", 12)).pack(side="left")
        self.hk_btn = ctk.CTkButton(
            hkf, text=format_hotkey(self._hotkey),
            width=200, command=self._start_hk_capture,
            fg_color="#3a3a5c", hover_color="#4a4a7c"
        )
        self.hk_btn.pack(side="left", padx=8)
        ctk.CTkLabel(hkf, text="点击修改",
                     font=("Microsoft YaHei UI", 10), text_color="gray").pack(side="left")

        # ── 深色模式 ──
        sep3 = ctk.CTkFrame(self.win, height=1)
        sep3.grid(row=row, column=0, padx=20, pady=6, sticky="ew")
        row += 1

        self.dark_var = ctk.BooleanVar(value=self.cfg.get("dark_mode", False))
        dark_sw = ctk.CTkSwitch(
            self.win, text="深色模式",
            variable=self.dark_var, onvalue=True, offvalue=False,
            font=("Microsoft YaHei UI", 12),
            command=self._on_dark_toggle,
        )
        dark_sw.grid(row=row, column=0, padx=20, pady=(4, 10), sticky="w")
        row += 1

        # ── 按钮 ──
        bf = ctk.CTkFrame(self.win, fg_color="transparent")
        bf.grid(row=row, column=0, padx=20, pady=(6, 16), sticky="ew")
        bf.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(bf, text="保存", command=self._save).grid(row=0, column=0, padx=4)
        ctk.CTkButton(bf, text="取消", command=self.win.destroy,
                      fg_color="#444", hover_color="#555").grid(row=0, column=1, padx=4)

        self._show_api_fields()

    def _show_api_fields(self):
        for w in self.api_frame.winfo_children():
            w.destroy()
        self._entries.clear()

        key = self._label_to_key[self.provider_combo.get()]
        info = PROVIDER_INFO[key]
        self.provider_hint.configure(text=info[1])

        if key == "deepl":
            self._add_api_entry("api_key", "DeepL API Key：",
                                self.cfg.get("deepl", {}).get("api_key", ""), show="*")
        elif key == "baidu":
            self._add_api_entry("app_id", "App ID：",
                                self.cfg.get("baidu", {}).get("app_id", ""))
            self._add_api_entry("app_key", "App Key：",
                                self.cfg.get("baidu", {}).get("app_key", ""), show="*")
        elif key == "youdao":
            self._add_api_entry("app_id", "App ID：",
                                self.cfg.get("youdao", {}).get("app_id", ""))
            self._add_api_entry("app_key", "App Key：",
                                self.cfg.get("youdao", {}).get("app_key", ""), show="*")

    def _add_api_entry(self, key, label, value, show=""):
        r = len(self._entries)
        ctk.CTkLabel(self.api_frame, text=label,
                     font=("Microsoft YaHei UI", 12)).grid(row=r, column=0, sticky="w", pady=2)
        e = ctk.CTkEntry(self.api_frame, width=300, show=show)
        e.grid(row=r, column=1, padx=(8, 0), pady=2, sticky="w")
        if value:
            e.insert(0, value)
        self._entries[key] = e

    def _on_provider_change(self, choice):
        self._save_api_fields()
        self._show_api_fields()

    def _save_api_fields(self):
        key = self._label_to_key[self.provider_combo.get()]
        if key == "google":
            return
        d = self.cfg.setdefault(key, {})
        for k, e in self._entries.items():
            d[k] = e.get()

    # ── 快捷键捕获 ──
    def _start_hk_capture(self):
        self._capturing_hk = True
        self.hk_btn.configure(text="按下组合键...", state="disabled")
        self.win.focus_set()

    def _on_hk_key(self, event):
        if not self._capturing_hk:
            return
        if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"):
            return
        self._capturing_hk = False

        mods = []
        if event.state & 0x0004:
            mods.append("ctrl")
        if event.state & 0x0001:
            mods.append("shift")
        if event.state & 0x0008:
            mods.append("alt")

        key = event.keysym.lower()
        if not mods:
            self.hk_btn.configure(text=key.upper(), state="normal")
            self._hotkey = {"modifiers": [], "key": key}
            return

        self._hotkey = {"modifiers": mods, "key": key}
        self.hk_btn.configure(text=format_hotkey(self._hotkey), state="normal")

    def _on_dark_toggle(self):
        mode = "dark" if self.dark_var.get() else "light"
        ctk.set_appearance_mode(mode)

    def _save(self):
        self._save_api_fields()
        self.cfg["provider"] = self._label_to_key[self.provider_combo.get()]
        dm = self.dark_var.get()
        self.cfg["target_lang"] = self._label_to_lang[self.lang_combo.get()]
        self.cfg["smart_mode"] = self.smart_var.get()
        self.cfg["hotkey"] = dict(self._hotkey)
        self.cfg["dark_mode"] = dm
        ctk.set_appearance_mode("dark" if dm else "light")

        if self.on_save:
            self.on_save(dict(self.cfg))
        self.win.destroy()


# ═══════════════════════════════════════════
# 翻译弹窗
# ═══════════════════════════════════════════
class Popup:
    def __init__(self, root):
        self.root = root
        self._timer = None
        self._drag = {"x": 0, "y": 0}
        self._outside_count = 0
        self._build()

    def _build(self):
        self.win = ctk.CTkToplevel(self.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)

        # 外层容器（圆角）
        outer = ctk.CTkFrame(self.win, corner_radius=10, fg_color=("#c8c8c8", "#333333"))
        outer.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(outer, corner_radius=8, fg_color=("white", "#2b2b2b"))
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        # 标题栏
        tb = ctk.CTkFrame(inner, height=32, fg_color=("#4a90d9", "#2a6fb0"))
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self.title_lbl = ctk.CTkLabel(
            tb, text="  翻译", font=("Microsoft YaHei UI", 11),
            text_color="white"
        )
        self.title_lbl.pack(side="left", padx=8)

        self.prov_lbl = ctk.CTkLabel(
            tb, text="", font=("Microsoft YaHei UI", 9),
            text_color="#c0d9f0"
        )
        self.prov_lbl.pack(side="right", padx=4)

        close_btn = ctk.CTkLabel(
            tb, text="  ✕  ", font=("Arial", 14),
            text_color="white", cursor="hand2"
        )
        close_btn.pack(side="right", padx=4)
        close_btn.bind("<Button-1>", lambda e: self.hide())

        for w in (tb, self.title_lbl):
            w.bind("<Button-1>", self._drag_start, add="+")
            w.bind("<B1-Motion>", self._drag_move, add="+")

        # 内容
        body = ctk.CTkFrame(inner, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        self.src_lbl = ctk.CTkLabel(
            body, text="", font=("Microsoft YaHei UI", 10),
            text_color=("#888888", "#aaaaaa"), wraplength=360, justify="left", anchor="w"
        )
        self.src_lbl.pack(fill="x")

        sep = ctk.CTkFrame(body, height=1)
        sep.pack(fill="x", pady=6)

        self.tgt_lbl = ctk.CTkLabel(
            body, text="", font=("Microsoft YaHei UI", 13, "bold"),
            wraplength=360, justify="left", anchor="w", cursor="hand2"
        )
        self.tgt_lbl.pack(fill="x")
        self.tgt_lbl.bind("<Button-1>", self._copy)

        self.hint = ctk.CTkLabel(
            body, text="点击译文复制", font=("Microsoft YaHei UI", 9),
            text_color=("#aaaaaa", "#888888"), anchor="e"
        )
        self.hint.pack(fill="x", pady=(4, 0))

        self.win.bind("<Key-Escape>", lambda e: self.hide())

    def show(self, src, tgt, src_lang="?", tgt_lang="?", provider=""):
        lm = {"zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
              "fr": "Français", "de": "Deutsch", "es": "Español",
              "pt": "Português", "ru": "Русский"}
        self.title_lbl.configure(
            text=f"  {lm.get(src_lang, '?')} → {lm.get(tgt_lang, '?')}"
        )
        self.prov_lbl.configure(text=provider)

        d = src[:180]
        if len(src) > 180:
            d += "…"
        self.src_lbl.configure(text=d)
        self._result = tgt
        self.tgt_lbl.configure(text=tgt)

        self.win.update_idletasks()
        w = min(400, self.win.winfo_reqwidth())
        h = self.win.winfo_reqheight()
        if w < 100:
            w = 380
        if h < 50:
            h = 150
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        cx = max(0, (sw - w) // 2)
        cy = max(0, (sh - h) // 2)
        self.win.geometry(f"{w}x{h}+{cx}+{cy}")
        self.win.update()
        self.win.deiconify()
        self.win.lift()
        self.win.focus_set()
        self.win.focus_force()
        self.win.grab_set()
        self.win.after(100, self.win.focus_set)

        self._cancel_timer()
        self._outside_count = 0
        # 首次检查延迟 2 秒，给窗口管理器足够时间完成布局
        self._timer = self.win.after(2000, self._mouse_check_loop)

    def _mouse_check_loop(self):
        """每秒检查鼠标位置，连续 4 次不在弹窗内则关闭"""
        if not self.win.winfo_viewable():
            return
        self._cancel_timer()
        try:
            mx, my = self.win.winfo_pointerxy()
            wx, wy = self.win.winfo_rootx(), self.win.winfo_rooty()
            ww, wh = self.win.winfo_width(), self.win.winfo_height()
            inside = (wx <= mx <= wx + ww and wy <= my <= wy + wh)
        except Exception:
            inside = False

        if inside:
            self._outside_count = 0
            self._timer = self.win.after(1000, self._mouse_check_loop)
        else:
            self._outside_count += 1
            if self._outside_count >= 4:
                self.hide()
            else:
                self._timer = self.win.after(1000, self._mouse_check_loop)

    def hide(self):
        self._cancel_timer()
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.withdraw()

    def _sch(self, ms):
        self._cancel_timer()
        if self.win.winfo_viewable():
            self._timer = self.win.after(ms, self.hide)

    def _cancel_timer(self):
        if self._timer:
            self.win.after_cancel(self._timer)
            self._timer = None

    def _copy(self, event=None):
        try:
            pyperclip.copy(self._result)
            self.hint.configure(text="✓ 已复制", text_color="#4a90d9")
            self.win.after(1500, lambda: self.hint.configure(
                text="点击译文复制", text_color=("#aaaaaa", "#888888")))
        except Exception:
            pass

    def _drag_start(self, e):
        self._drag["x"], self._drag["y"] = e.x, e.y

    def _drag_move(self, e):
        self.win.geometry(f"+{self.win.winfo_x()+e.x-self._drag['x']}"
                          f"+{self.win.winfo_y()+e.y-self._drag['y']}")

    def destroy(self):
        self._cancel_timer()
        if self.win:
            self.win.destroy()


# ═══════════════════════════════════════════
# 主应用
# ═══════════════════════════════════════════
class App:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.withdraw()

        self.cfg = load_config()
        self.last = ""
        self.running = True
        self.popup = None
        self.provider = self.cfg.get("provider", "google")
        self.target_lang = self.cfg.get("target_lang", "zh")
        self.smart_mode = self.cfg.get("smart_mode", True)
        self.hotkey = self.cfg.get("hotkey", {"modifiers": ["ctrl"], "key": "t"})
        self._skip_until = 0

        # 应用深色模式
        ctk.set_appearance_mode("dark" if self.cfg.get("dark_mode") else "light")
        ctk.set_default_color_theme("blue")

        self._build_cw()
        self.popup = Popup(self.root)
        self._start_clipboard_watch()
        self._setup_hotkey()
        self._setup_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_cw(self):
        self.cw = ctk.CTkToplevel(self.root)
        self.cw.title("翻译工具")
        self.cw.resizable(False, False)
        self.cw.update_idletasks()
        cw_w, cw_h = 440, 260
        cx = (self.cw.winfo_screenwidth() - cw_w) // 2
        cy = (self.cw.winfo_screenheight() - cw_h) // 2
        self.cw.geometry(f"{cw_w}x{cw_h}+{cx}+{cy}")

        ctk.CTkLabel(self.cw, text="翻译工具",
                     font=("Microsoft YaHei UI", 18, "bold")).pack(pady=(20, 2))

        hk_str = format_hotkey(self.hotkey)
        ctk.CTkLabel(
            self.cw, text=f"复制文本后按 {hk_str} 翻译",
            font=("Microsoft YaHei UI", 11),
            text_color="gray"
        ).pack()

        # 快捷键提示框
        hint_f = ctk.CTkFrame(self.cw, fg_color=("#e8f0fe", "#2d2d3d"),
                              corner_radius=6)
        hint_f.pack(pady=(10, 0), padx=40, fill="x")
        ctk.CTkLabel(
            hint_f, text=f"  ⌨ 复制文本 → {hk_str} → 弹出译文",
            font=("Microsoft YaHei UI", 11),
            text_color=("#1967d2", "#8ab4f8")
        ).pack(pady=6)

        self.pi = ctk.CTkLabel(self.cw, text="",
                               font=("Microsoft YaHei UI", 11),
                               text_color="#4a90d9")
        self.pi.pack(pady=(6, 0))
        self._update_pi()

        self.sl = ctk.CTkLabel(self.cw, text="状态: 就绪 ✓",
                               font=("Microsoft YaHei UI", 11),
                               text_color="green")
        self.sl.pack(pady=(2, 0))

        bf = ctk.CTkFrame(self.cw, fg_color="transparent")
        bf.pack(pady=(12, 0))
        ctk.CTkButton(bf, text="翻译设置", command=self._settings,
                      width=100).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="隐藏到托盘",
                      command=lambda: self.cw.withdraw(),
                      fg_color="#555", hover_color="#666",
                      width=100).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="退出", command=self._quit,
                      fg_color="#c0392b", hover_color="#e74c3c",
                      width=100).pack(side="left", padx=5)

        self.cw.protocol("WM_DELETE_WINDOW", lambda: self.cw.withdraw())
        self.root.after(8000, lambda: self.cw.withdraw() if self.running else None)

    def _update_pi(self):
        name = PROVIDER_INFO.get(self.provider, [self.provider, ""])[0]
        if self.smart_mode:
            self.pi.configure(text=f"当前平台: {name}  |  智能互译 (中↔英)")
        else:
            tgt_name = LANGUAGES.get(self.target_lang, self.target_lang)
            self.pi.configure(text=f"当前平台: {name}  →  {tgt_name}")

    def _settings(self):
        def on_save(c):
            self.cfg = c
            old_hk = format_hotkey(self.hotkey)
            self.provider = c.get("provider", "google")
            self.target_lang = c.get("target_lang", "zh")
            self.smart_mode = c.get("smart_mode", True)
            self.hotkey = c.get("hotkey", {"modifiers": ["ctrl", "shift"], "key": "t"})
            save_config(c)

            # Hotkey change → restart poll
            if format_hotkey(self.hotkey) != old_hk:
                self._setup_hotkey(restart=True)

            self._update_pi()
            name = PROVIDER_INFO.get(self.provider, [self.provider, ""])[0]
            if self.smart_mode:
                self.popup.show("系统提示", f"已切换至 {name}\n智能互译: 中↔英",
                                "系统", "系统", provider="")
            else:
                tgt_name = LANGUAGES.get(self.target_lang, self.target_lang)
                self.popup.show("系统提示", f"已切换至 {name}\n目标语言: {tgt_name}",
                                "系统", "系统", provider="")
        SettingsDialog(self.cw, self.cfg, on_save)

    # ── 剪贴板追踪（仅缓存） ──
    def _start_clipboard_watch(self):
        def loop():
            while self.running:
                try:
                    t = pyperclip.paste().strip()
                    if t and len(t) < 2000:
                        self.last = t
                except Exception:
                    pass
                time.sleep(0.3)
        threading.Thread(target=loop, daemon=True).start()

    # ── 全局热键 ──
    def _setup_hotkey(self, restart=False):
        if restart and hasattr(self, "_hotkey_stop"):
            self._hotkey_stop.set()
            time.sleep(0.2)
        self._hotkey_was_down = False
        self._hotkey_stop = threading.Event()
        self._hotkey_stop.clear()
        threading.Thread(target=self._hotkey_poll, daemon=True).start()

    def _hotkey_poll(self):
        user32 = ctypes.windll.user32
        stop_event = self._hotkey_stop

        while self.running and not stop_event.is_set():
            try:
                # 每次循环重新读取快捷键，支持动态修改
                hk = self.hotkey
                mods = hk.get("modifiers", ["ctrl", "shift"])
                key = hk.get("key", "t")
                mod_vks = [MOD_VK.get(m, 0x11) for m in mods]
                key_vk = VK_MAP.get(key, 0x54)

                all_down = all(bool(user32.GetAsyncKeyState(vk) & 0x8000) for vk in mod_vks)
                key_down = bool(user32.GetAsyncKeyState(key_vk) & 0x8000)
                combo = all_down and key_down
                if combo and not self._hotkey_was_down:
                    self._hotkey_was_down = True
                elif not combo and self._hotkey_was_down:
                    self._hotkey_was_down = False
                    self.root.after(0, self.trigger_translate)
            except Exception:
                pass
            time.sleep(0.15)

    def trigger_translate(self):
        try:
            t = pyperclip.paste().strip()
            if t:
                self.last = t
                self.sl.configure(text="状态: 翻译中…", text_color="#4a90d9")
                if self.smart_mode:
                    src = detect_lang(t)
                    target = "en" if src == "zh" else "zh"
                else:
                    target = self.target_lang
                self._do_bg(t, target)
            else:
                self.sl.configure(text="状态: 剪贴板为空", text_color="orange")
        except Exception as e:
            self.sl.configure(text=f"剪贴板错误: {str(e)[:30]}", text_color="orange")

    # ── 后台翻译 ──
    def _do_bg(self, text, target_lang=None):
        if not text:
            return
        if target_lang is None:
            target_lang = self.target_lang

        def task():
            now = time.time()
            try:
                r, s, t = do_translate(text, self.provider, target_lang, self.cfg)
                if r and r.strip():
                    self._skip_until = 0
                    self.root.after(0, self.popup.show, text, r, s, t, self.provider)
                    self.root.after(0, self.sl.configure,
                                    text="状态: 就绪 ✓", text_color="green")
                else:
                    self._skip_until = now + 5
            except Exception as e:
                if now > self._skip_until:
                    self._skip_until = now + 5
                    self.root.after(0, self.sl.configure,
                                    text=f"翻译失败: {str(e)[:40]}", text_color="orange")

        threading.Thread(target=task, daemon=True).start()

    # ── 系统托盘 ──
    def _setup_tray(self):
        if not HAS_TRAY:
            return

        img = Image.new("RGB", (64, 64), "#4a90d9")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "译", font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (64 - tw) // 2 - bbox[0]
        y = (64 - th) // 2 - bbox[1]
        draw.text((x, y), "译", fill="white", font=font)

        hk_str = format_hotkey(self.hotkey)
        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", self._show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._quit),
        )
        self._tray = pystray.Icon("translator", img, f"翻译工具 ({hk_str})", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _show_window(self):
        self.root.after(0, self._show_window_ui)

    def _show_window_ui(self):
        self.cw.deiconify()
        self.cw.lift()

    def _on_close(self):
        self.cw.withdraw()
        if HAS_TRAY:
            try:
                self.popup.show("系统提示", "已最小化到系统托盘\n右键托盘图标可退出",
                                "系统", "系统", provider="")
            except Exception:
                pass

    # ── 退出 ──
    def _quit(self):
        self.running = False
        if hasattr(self, "_hotkey_stop"):
            self._hotkey_stop.set()
        if hasattr(self, "_tray") and self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.root.after(0, self._quit_ui)

    def _quit_ui(self):
        if self.popup:
            self.popup.destroy()
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
