"""
NEON PRO v3.2 - Autonomous Android Mobile & Desktop Suite
Architected for: Harish
Features:
  - Full Cyber-Neon Multi-Tab UI matching NEON PRO Preview (Console, App Studio, Debugger, Build Lab)
  - Proper dp()/sp() responsive scaling for high-DPI Android phones (zero squished/blank views)
  - Styled Rounded Cards, Message Bubbles, Code Blocks, Quick Prompts, and Settings Modal
  - Direct Gemini REST API with automatic model failover + High Thinking mode
  - Native Android Voice Input & Indian-accent TTS via PyJNIus + Instant Barge-In + Termux fallback
"""
import json
import os
import platform as sys_platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import certifi
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

# Fix SSL certificate bundle path on Android
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# Cyber-dark palette matching NEON PRO web cockpit (#05070f)
Window.clearcolor = (0.02, 0.027, 0.059, 1.0)
Window.softinput_mode = "below_target"

CONFIG_FILE = "neon_pro_config.json"
WEB_COCKPIT_URL = "https://ais-pre-ccf5jvawenmhsjix56rckx-803295381828.asia-southeast1.run.app"
DEFAULT_SYSTEM_PROMPT = (
    "You are NEON PRO, Harish's autonomous, bilingual (Hindi / English / Hinglish) "
    "personal AI companion and voice assistant. "
    "Core Behavioral Rules: "
    "1. Talk naturally, warmly, and directly like a close Indian peer or friend—never robotic, stiff, or corporate. "
    "2. NEVER recite system status reports, battery levels, connection logs, or technical diagnostics unless explicitly requested. "
    "3. Keep conversational responses concise, punchy, and context-aware (e.g., if Harish greets casually or asks how you are, reply like a friend like 'Ekdum mast bhai, batao kya plan hai?'). "
    "4. Eliminate filler text and repetitive status announcements; give direct answers and clean production code when asked to build or debug."
)


def style_card(widget, bg_rgba, border_rgba=None, radius_dp=12, border_width=1.0):
    """Attach rounded background and crisp cyber-neon border to any Kivy widget."""
    widget.canvas.before.clear()
    with widget.canvas.before:
        bg_color = Color(*bg_rgba)
        bg_rect = RoundedRectangle(
            pos=widget.pos,
            size=widget.size,
            radius=[dp(radius_dp)],
        )
        border_color = None
        border_line = None
        if border_rgba is not None:
            border_color = Color(*border_rgba)
            border_line = Line(
                rounded_rectangle=(
                    widget.x,
                    widget.y,
                    max(widget.width, 1),
                    max(widget.height, 1),
                    dp(radius_dp),
                ),
                width=dp(border_width),
            )

    def _sync(*_args):
        bg_rect.pos = widget.pos
        bg_rect.size = widget.size
        if border_line is not None:
            border_line.rounded_rectangle = (
                widget.x,
                widget.y,
                max(widget.width, 1),
                max(widget.height, 1),
                dp(radius_dp),
            )

    widget.bind(pos=_sync, size=_sync)
    return bg_color, border_color


def make_button(
    text,
    bg_rgba,
    border_rgba=None,
    text_rgba=(1, 1, 1, 1),
    radius_dp=10,
    font_sp=12,
    bold=True,
    **kwargs,
):
    btn = Button(
        text=text,
        background_normal="",
        background_down="",
        background_color=(0, 0, 0, 0),
        color=text_rgba,
        font_size=sp(font_sp),
        bold=bold,
        markup=True,
        halign="center",
        valign="middle",
        **kwargs,
    )
    btn.bind(size=lambda inst, sz: setattr(inst, "text_size", (sz[0] - dp(8), None)))
    style_card(btn, bg_rgba, border_rgba, radius_dp=radius_dp, border_width=1.0)
    return btn


class AutoLabel(Label):
    """Word-wrapped Label that automatically sizes height to its rendered texture."""

    def __init__(self, **kwargs):
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "top")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("markup", True)
        super().__init__(**kwargs)
        self.bind(width=self._update_text_size, texture_size=self._update_height)

    def _update_text_size(self, *_args):
        self.text_size = (max(self.width, dp(40)), None)

    def _update_height(self, *_args):
        self.height = max(self.texture_size[1] + dp(4), dp(20))


class AndroidVoiceBridge:
    """Handles native Android TTS + Voice Recognition via PyJNIus or Termux:API."""

    def __init__(self, status_callback, transcript_callback):
        self.on_status = status_callback
        self.on_transcript = transcript_callback
        self.tts = None
        self.is_speaking = False
        self.speech_req_code = 9042
        self._android_ready = False
        self._language_mode = "auto"

        if platform == "android":
            Clock.schedule_once(lambda dt: self._init_android_bridge(), 0.6)

    def set_language_mode(self, mode):
        self._language_mode = mode

    def _init_android_bridge(self):
        try:
            from android import activity
            from android.permissions import Permission, request_permissions
            from jnius import autoclass

            request_permissions([Permission.INTERNET, Permission.RECORD_AUDIO])

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
            Locale = autoclass("java.util.Locale")

            self._activity = PythonActivity.mActivity
            self._Locale = Locale
            self.tts = TextToSpeech(self._activity, None)
            try:
                self.tts.setLanguage(Locale("en", "IN"))
            except Exception:
                pass

            activity.bind(on_activity_result=self._on_activity_result)
            self._android_ready = True
            self.on_status("Native Android Voice & TTS Ready")
        except Exception as exc:
            self.on_status(f"Voice note: {exc}")

    def _on_activity_result(self, request_code, _result_code, intent):
        if request_code != self.speech_req_code or intent is None:
            return
        try:
            from jnius import autoclass

            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if results and results.size() > 0:
                spoken_text = str(results.get(0))
                Clock.schedule_once(lambda dt: self.on_transcript(spoken_text), 0)
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.on_status(f"Mic parse error: {exc}"), 0)

    def stop_speaking(self):
        self.is_speaking = False
        if self.tts is not None:
            try:
                self.tts.stop()
            except Exception:
                pass

    def speak(self, text):
        if not text:
            return
        clean = text.replace("*", "").replace("#", "").replace("`", "")[:450].strip()
        if not clean:
            return
        self.stop_speaking()
        self.is_speaking = True

        if platform == "android" and self.tts is not None:
            try:
                from jnius import autoclass

                TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                use_hi = self._language_mode == "hi" or any(
                    "\u0900" <= ch <= "\u097f" for ch in clean
                )
                self.tts.setLanguage(self._Locale("hi" if use_hi else "en", "IN"))
                self.tts.speak(clean, TextToSpeech.QUEUE_FLUSH, None, "neon_tts")
                return
            except Exception:
                pass

        if shutil.which("termux-tts-speak"):
            threading.Thread(
                target=lambda: subprocess.run(["termux-tts-speak", clean], check=False),
                daemon=True,
            ).start()

    def start_listening(self):
        self.stop_speaking()
        if platform == "android" and self._android_ready:
            try:
                from jnius import autoclass

                Intent = autoclass("android.content.Intent")
                RecognizerIntent = autoclass("android.speech.RecognizerIntent")
                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                )
                lang_tag = "hi-IN" if self._language_mode == "hi" else "en-IN"
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang_tag)
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to NEON PRO, Harish...")
                self._activity.startActivityForResult(intent, self.speech_req_code)
                return
            except Exception as exc:
                self.on_status(f"Mic unavailable: {exc}")
                return

        if shutil.which("termux-speech-to-text"):
            self.on_status("Listening via Termux:API...")

            def _listen():
                try:
                    proc = subprocess.run(
                        ["termux-speech-to-text"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    spoken = proc.stdout.strip()
                    if spoken:
                        Clock.schedule_once(lambda dt: self.on_transcript(spoken), 0)
                except Exception as err:
                    Clock.schedule_once(lambda dt: self.on_status(f"Termux mic error: {err}"), 0)

            threading.Thread(target=_listen, daemon=True).start()
        else:
            self.on_status("Type message below (Voice active on Android/Termux)")


def escape_markup(text):
    return str(text).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


class NeonProMobileSuite(BoxLayout):
    """Full Cyber-Neon Multi-Tab Mobile UI matching NEON PRO Web Preview."""

    MODELS = [
        ("gemini-4-hydrogen", "4 Hydrogen"),
        ("gemini-3.1-flash-lite", "3.1 Lite"),
        ("gemini-4-argon", "4 Argon"),
    ]

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(8), **kwargs)
        self.config_data = self._load_config()
        self.api_key = self.config_data.get("api_key", "")
        saved_model = self.config_data.get("model", "gemini-4-hydrogen")
        valid_ids = {m[0] for m in self.MODELS}
        self.selected_model = saved_model if saved_model in valid_ids else "gemini-4-hydrogen"
        self.high_thinking = bool(self.config_data.get("high_thinking", False))
        self.audio_enabled = bool(self.config_data.get("audio_enabled", True))
        self.language_mode = self.config_data.get("language_mode", "auto")
        self.history = []
        self.active_tab = "console"
        self.tab_buttons = {}

        self.voice_bridge = AndroidVoiceBridge(
            status_callback=self._update_voice_banner,
            transcript_callback=self._on_voice_transcript,
        )
        self.voice_bridge.set_language_mode(self.language_mode)

        self._build_header()
        self._build_tab_bar()
        self._build_screens()
        self._refresh_header_state()
        self._switch_tab("console")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _get_config_path(self):
        app = App.get_running_app()
        base_dir = app.user_data_dir if app else "."
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, CONFIG_FILE)

    def _load_config(self):
        data = {}
        try:
            path = self._get_config_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
        except Exception:
            data = {}
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_key and not data.get("api_key"):
            data["api_key"] = env_key
        return data

    def _save_config(self):
        self.config_data = {
            "api_key": self.api_key,
            "model": self.selected_model,
            "high_thinking": self.high_thinking,
            "audio_enabled": self.audio_enabled,
            "language_mode": self.language_mode,
        }
        try:
            with open(self._get_config_path(), "w", encoding="utf-8") as fh:
                json.dump(self.config_data, fh)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Top Header & Navigation Tabs
    # ------------------------------------------------------------------
    def _build_header(self):
        header = BoxLayout(size_hint_y=None, height=dp(58), padding=[dp(10), dp(8)], spacing=dp(8))
        style_card(header, (0.035, 0.051, 0.098, 1.0), (0.04, 0.45, 0.62, 0.55), radius_dp=14)

        badge = make_button(
            "NP",
            (0.02, 0.65, 0.80, 1.0),
            (0.22, 0.85, 0.95, 0.9),
            radius_dp=10,
            font_sp=14,
            size_hint=(None, None),
            size=(dp(40), dp(40)),
        )
        badge.pos_hint = {"center_y": 0.5}
        header.add_widget(badge)

        title_col = BoxLayout(orientation="vertical", spacing=dp(2))
        title_lbl = Label(
            text="[b][color=ffffff]NEON[/color] [color=22d3ee]PRO[/color][/b]",
            markup=True,
            font_size=sp(17),
            halign="left",
            valign="bottom",
        )
        title_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.subtitle_lbl = Label(
            text="[color=34d399]●[/color] [color=94a3b8]Harish • Ready[/color]",
            markup=True,
            font_size=sp(11),
            halign="left",
            valign="top",
        )
        self.subtitle_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        title_col.add_widget(title_lbl)
        title_col.add_widget(self.subtitle_lbl)
        header.add_widget(title_col)

        self.tts_toggle_btn = make_button(
            "TTS ON",
            (0.05, 0.17, 0.25, 1.0),
            (0.06, 0.71, 0.83, 0.5),
            text_rgba=(0.45, 0.92, 1.0, 1.0),
            radius_dp=9,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(62), dp(34)),
        )
        self.tts_toggle_btn.pos_hint = {"center_y": 0.5}
        self.tts_toggle_btn.bind(on_release=self._toggle_audio)
        header.add_widget(self.tts_toggle_btn)

        self.settings_btn = make_button(
            "API Key",
            (0.22, 0.14, 0.04, 1.0),
            (0.95, 0.65, 0.1, 0.65),
            text_rgba=(0.99, 0.82, 0.35, 1.0),
            radius_dp=9,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(76), dp(34)),
        )
        self.settings_btn.pos_hint = {"center_y": 0.5}
        self.settings_btn.bind(on_release=lambda *_: self._open_settings_modal())
        header.add_widget(self.settings_btn)

        self.add_widget(header)

    def _build_tab_bar(self):
        tab_bar = BoxLayout(size_hint_y=None, height=dp(44), padding=dp(4), spacing=dp(5))
        style_card(tab_bar, (0.045, 0.068, 0.125, 1.0), (0.12, 0.18, 0.30, 0.9), radius_dp=12)

        tabs = [
            ("console", "Console"),
            ("app-studio", "App Studio"),
            ("debugger", "Debugger"),
            ("terminal", "Build Lab"),
        ]
        for key, label in tabs:
            btn = make_button(
                label,
                (0.06, 0.09, 0.16, 1.0),
                None,
                text_rgba=(0.65, 0.74, 0.86, 1.0),
                radius_dp=8,
                font_sp=11,
            )
            btn.bind(on_release=lambda _inst, k=key: self._switch_tab(k))
            self.tab_buttons[key] = btn
            tab_bar.add_widget(btn)

        self.add_widget(tab_bar)

    def _switch_tab(self, tab_key):
        self.active_tab = tab_key
        self.screen_manager.current = tab_key
        for key, btn in self.tab_buttons.items():
            if key == tab_key:
                style_card(btn, (0.05, 0.25, 0.34, 1.0), (0.08, 0.78, 0.90, 0.7), radius_dp=8)
                btn.color = (0.45, 0.95, 1.0, 1.0)
            else:
                style_card(btn, (0.045, 0.068, 0.125, 1.0), None, radius_dp=8)
                btn.color = (0.62, 0.71, 0.82, 1.0)

    def _refresh_header_state(self):
        model_short = dict(self.MODELS).get(self.selected_model, self.selected_model)
        think_tag = " • High Think" if self.high_thinking else ""
        self.subtitle_lbl.text = (
            f"[color=34d399]●[/color] [color=cbd5e1]Harish[/color] "
            f"[color=64748b]•[/color] [color=38bdf8]{model_short}{think_tag}[/color]"
        )
        if self.audio_enabled:
            self.tts_toggle_btn.text = "TTS ON"
            style_card(
                self.tts_toggle_btn,
                (0.05, 0.18, 0.26, 1.0),
                (0.06, 0.71, 0.83, 0.55),
                radius_dp=9,
            )
            self.tts_toggle_btn.color = (0.45, 0.92, 1.0, 1.0)
        else:
            self.tts_toggle_btn.text = "MUTED"
            style_card(
                self.tts_toggle_btn,
                (0.09, 0.12, 0.18, 1.0),
                (0.25, 0.32, 0.42, 0.6),
                radius_dp=9,
            )
            self.tts_toggle_btn.color = (0.65, 0.72, 0.82, 1.0)

        if self.api_key:
            self.settings_btn.text = "Settings"
            style_card(
                self.settings_btn,
                (0.05, 0.22, 0.16, 1.0),
                (0.08, 0.75, 0.52, 0.65),
                radius_dp=9,
            )
            self.settings_btn.color = (0.45, 0.96, 0.76, 1.0)
        else:
            self.settings_btn.text = "Set Key"
            style_card(
                self.settings_btn,
                (0.24, 0.15, 0.04, 1.0),
                (0.95, 0.65, 0.1, 0.7),
                radius_dp=9,
            )
            self.settings_btn.color = (1.0, 0.84, 0.38, 1.0)

        if hasattr(self, "key_prompt_card"):
            if self.api_key:
                self.key_prompt_card.height = 0
                self.key_prompt_card.opacity = 0
                self.key_prompt_card.disabled = True
            else:
                self.key_prompt_card.height = dp(92)
                self.key_prompt_card.opacity = 1
                self.key_prompt_card.disabled = False

    def _toggle_audio(self, *_args):
        self.audio_enabled = not self.audio_enabled
        if not self.audio_enabled:
            self.voice_bridge.stop_speaking()
        self._save_config()
        self._refresh_header_state()

    def _build_screens(self):
        self.screen_manager = ScreenManager(transition=NoTransition())

        s_console = Screen(name="console")
        s_console.add_widget(self._build_console_tab())
        self.screen_manager.add_widget(s_console)

        s_studio = Screen(name="app-studio")
        s_studio.add_widget(self._build_studio_tab())
        self.screen_manager.add_widget(s_studio)

        s_debug = Screen(name="debugger")
        s_debug.add_widget(self._build_debugger_tab())
        self.screen_manager.add_widget(s_debug)

        s_term = Screen(name="terminal")
        s_term.add_widget(self._build_lab_tab())
        self.screen_manager.add_widget(s_term)

        self.add_widget(self.screen_manager)

    # ------------------------------------------------------------------
    # TAB 1: CONSOLE (Chat, Voice Visualizer, Bubbles, Quick Prompts)
    # ------------------------------------------------------------------
    def _build_console_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        # Voice & Neural Status Strip
        voice_bar = BoxLayout(size_hint_y=None, height=dp(44), padding=[dp(10), dp(6)], spacing=dp(6))
        style_card(voice_bar, (0.04, 0.06, 0.12, 1.0), (0.08, 0.35, 0.48, 0.45), radius_dp=10)

        self.voice_status_lbl = Label(
            text="[b][color=22d3ee]VOICE-FIRST ENGINE[/color][/b]  [color=94a3b8]• Bilingual EN / HI[/color]",
            markup=True,
            font_size=sp(11),
            halign="left",
            valign="middle",
        )
        self.voice_status_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        voice_bar.add_widget(self.voice_status_lbl)

        self.think_pill = make_button(
            "Think: OFF",
            (0.08, 0.09, 0.16, 1.0),
            (0.25, 0.30, 0.45, 0.6),
            text_rgba=(0.75, 0.80, 0.90, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(84), dp(30)),
        )
        self.think_pill.pos_hint = {"center_y": 0.5}
        self.think_pill.bind(on_release=self._toggle_thinking)
        voice_bar.add_widget(self.think_pill)
        root.add_widget(voice_bar)

        # Collapsible Key Prompt Card (only visible until key is saved)
        self.key_prompt_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(92),
            padding=dp(10),
            spacing=dp(6),
        )
        style_card(self.key_prompt_card, (0.09, 0.06, 0.02, 1.0), (0.90, 0.58, 0.10, 0.55), radius_dp=12)
        key_hint = AutoLabel(
            text="[b][color=fbbf24]Connect Gemini API Key[/color][/b] [color=cbd5e1](Saved offline on your phone)[/color]",
            font_size=sp(11),
        )
        self.key_prompt_card.add_widget(key_hint)

        key_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.inline_key_input = TextInput(
            hint_text="Paste AIza... Gemini API key here",
            password=True,
            multiline=False,
            background_color=(0.03, 0.04, 0.08, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            cursor_color=(0.08, 0.78, 0.90, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        key_row.add_widget(self.inline_key_input)
        save_inline_btn = make_button(
            "Save",
            (0.06, 0.55, 0.42, 1.0),
            (0.15, 0.85, 0.62, 0.8),
            radius_dp=8,
            font_sp=12,
            size_hint_x=None,
            width=dp(72),
        )
        save_inline_btn.bind(on_release=self._save_inline_key)
        key_row.add_widget(save_inline_btn)
        self.key_prompt_card.add_widget(key_row)
        root.add_widget(self.key_prompt_card)

        # Messages Scroll Thread
        self.chat_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(4))
        self.chat_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=[dp(2), dp(4), dp(2), dp(6)],
        )
        self.chat_list.bind(minimum_height=self.chat_list.setter("height"))
        self.chat_scroll.add_widget(self.chat_list)
        root.add_widget(self.chat_scroll)

        # Seed initial NEON PRO welcome card (matches Web Console)
        welcome_text = (
            "Hey Harish! Kya haal hain bhai? Batao aaj kya scene hai—koi naya app banana hai, "
            "koi bug fix karein, ya bas normal baat-cheet?"
        )
        self._add_message_card("assistant", welcome_text, model_tag="NEON Core")

        # Horizontal Quick Commands Strip
        quick_scroll = ScrollView(size_hint_y=None, height=dp(40), do_scroll_y=False, bar_width=0)
        quick_row = BoxLayout(size_hint_x=None, height=dp(36), spacing=dp(6), padding=[dp(2), dp(2)])
        quick_row.bind(minimum_width=quick_row.setter("width"))

        quick_prompts = [
            ("Hinglish Chat", "Aur bhai kya haal hai? Aaj mobile app me kya naya add karein?"),
            ("Android Tips", "Kivy aur PyJNIus se Android features (camera, vibration, notifications) kaise add karein?"),
            ("Windows .EXE", "PyQt6 desktop app aur PyInstaller Windows .exe banane ka clean template do."),
            ("AI Architect", "Build a complete Python automation script with clean modular architecture."),
        ]
        for label, prompt in quick_prompts:
            pill = make_button(
                label,
                (0.05, 0.08, 0.15, 1.0),
                (0.06, 0.45, 0.62, 0.5),
                text_rgba=(0.55, 0.88, 0.98, 1.0),
                radius_dp=16,
                font_sp=11,
                size_hint=(None, None),
                size=(dp(108), dp(32)),
            )
            pill.bind(on_release=lambda _i, p=prompt: self._send_chat_prompt(p))
            quick_row.add_widget(pill)

        clear_pill = make_button(
            "Clear Chat",
            (0.14, 0.06, 0.09, 1.0),
            (0.75, 0.22, 0.35, 0.5),
            text_rgba=(0.98, 0.65, 0.72, 1.0),
            radius_dp=16,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(88), dp(32)),
        )
        clear_pill.bind(on_release=lambda *_: self._clear_chat())
        quick_row.add_widget(clear_pill)

        quick_scroll.add_widget(quick_row)
        root.add_widget(quick_scroll)

        # Bottom Composer Card
        composer = BoxLayout(size_hint_y=None, height=dp(56), padding=dp(6), spacing=dp(6))
        style_card(composer, (0.045, 0.068, 0.125, 1.0), (0.06, 0.55, 0.72, 0.65), radius_dp=14)

        self.mic_btn = make_button(
            "MIC",
            (0.28, 0.14, 0.55, 1.0),
            (0.62, 0.38, 0.96, 0.7),
            radius_dp=10,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(48), dp(42)),
        )
        self.mic_btn.pos_hint = {"center_y": 0.5}
        self.mic_btn.bind(on_release=lambda *_: self.voice_bridge.start_listening())
        composer.add_widget(self.mic_btn)

        self.chat_input = TextInput(
            hint_text="Ask NEON PRO in Hindi / English...",
            multiline=False,
            background_color=(0.025, 0.038, 0.075, 1.0),
            foreground_color=(0.96, 0.98, 1.0, 1.0),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            cursor_color=(0.08, 0.80, 0.92, 1.0),
            font_size=sp(13),
            padding=[dp(10), dp(11), dp(10), dp(11)],
        )
        self.chat_input.bind(on_text_validate=lambda *_: self._send_chat_prompt())
        composer.add_widget(self.chat_input)

        self.stop_tts_btn = make_button(
            "STOP",
            (0.55, 0.12, 0.22, 1.0),
            (0.95, 0.30, 0.42, 0.75),
            radius_dp=10,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(48), dp(42)),
        )
        self.stop_tts_btn.pos_hint = {"center_y": 0.5}
        self.stop_tts_btn.bind(on_release=lambda *_: self.voice_bridge.stop_speaking())
        composer.add_widget(self.stop_tts_btn)

        self.send_btn = make_button(
            "SEND",
            (0.02, 0.58, 0.75, 1.0),
            (0.22, 0.85, 0.95, 0.85),
            radius_dp=10,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(60), dp(42)),
        )
        self.send_btn.pos_hint = {"center_y": 0.5}
        self.send_btn.bind(on_release=lambda *_: self._send_chat_prompt())
        composer.add_widget(self.send_btn)

        root.add_widget(composer)
        return root

    def _add_message_card(self, role, text, model_tag=None):
        is_user = role == "user"
        wrapper = BoxLayout(orientation="horizontal", size_hint_y=None, padding=[dp(4), dp(2)])
        wrapper.bind(minimum_height=wrapper.setter("height"))

        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(6),
        )
        card.bind(minimum_height=card.setter("height"))

        if is_user:
            style_card(card, (0.07, 0.28, 0.46, 1.0), (0.14, 0.72, 0.88, 0.65), radius_dp=14)
            hdr = AutoLabel(
                text=f"[b][color=e0f2fe]Harish[/color][/b]  [color=93c5fd]{time.strftime('%H:%M')}[/color]",
                font_size=sp(11),
            )
            card.add_widget(hdr)
            body = AutoLabel(
                text=f"[color=ffffff]{escape_markup(text)}[/color]",
                font_size=sp(13),
            )
            card.add_widget(body)
            spacer = BoxLayout(size_hint_x=0.14)
            wrapper.add_widget(spacer)
            wrapper.add_widget(card)
        else:
            style_card(card, (0.04, 0.06, 0.115, 1.0), (0.06, 0.42, 0.58, 0.55), radius_dp=14)

            top_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
            tag = model_tag or self.selected_model
            meta_lbl = Label(
                text=f"[b][color=22d3ee]NEON PRO[/color][/b] [color=64748b]• {tag}[/color]",
                markup=True,
                font_size=sp(11),
                halign="left",
                valign="middle",
            )
            meta_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
            top_row.add_widget(meta_lbl)

            speak_btn = make_button(
                "Speak",
                (0.05, 0.14, 0.22, 1.0),
                (0.08, 0.65, 0.80, 0.5),
                text_rgba=(0.45, 0.92, 1.0, 1.0),
                radius_dp=7,
                font_sp=10,
                size_hint=(None, None),
                size=(dp(56), dp(26)),
            )
            speak_btn.bind(on_release=lambda *_a, t=text: self.voice_bridge.speak(t))
            top_row.add_widget(speak_btn)

            copy_btn = make_button(
                "Copy",
                (0.08, 0.11, 0.18, 1.0),
                (0.25, 0.34, 0.48, 0.6),
                text_rgba=(0.82, 0.88, 0.96, 1.0),
                radius_dp=7,
                font_sp=10,
                size_hint=(None, None),
                size=(dp(52), dp(26)),
            )
            copy_btn.bind(on_release=lambda *_a, t=text, b=copy_btn: self._copy_text(t, b))
            top_row.add_widget(copy_btn)
            card.add_widget(top_row)

            # Parse triple-backtick code blocks into styled dark code cards
            parts = text.split("```")
            for idx, part in enumerate(parts):
                chunk = part.strip()
                if not chunk:
                    continue
                if idx % 2 == 1:
                    lines = chunk.split("\n")
                    lang = lines[0].strip() if len(lines) > 1 and len(lines[0]) < 20 else "code"
                    code_body = "\n".join(lines[1:]) if lang != "code" and len(lines) > 1 else chunk
                    code_box = BoxLayout(
                        orientation="vertical",
                        size_hint_y=None,
                        padding=dp(10),
                        spacing=dp(6),
                    )
                    code_box.bind(minimum_height=code_box.setter("height"))
                    style_card(code_box, (0.02, 0.03, 0.06, 1.0), (0.06, 0.55, 0.45, 0.5), radius_dp=10)
                    c_hdr = BoxLayout(size_hint_y=None, height=dp(24))
                    c_lbl = Label(
                        text=f"[b][color=34d399]{lang.upper()}[/color][/b]",
                        markup=True,
                        font_size=sp(10),
                        halign="left",
                    )
                    c_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
                    c_copy = make_button(
                        "Copy Code",
                        (0.06, 0.16, 0.14, 1.0),
                        (0.10, 0.72, 0.52, 0.6),
                        text_rgba=(0.55, 0.96, 0.78, 1.0),
                        radius_dp=6,
                        font_sp=10,
                        size_hint=(None, None),
                        size=(dp(76), dp(22)),
                    )
                    c_copy.bind(on_release=lambda *_a, cb=code_body, b=c_copy: self._copy_text(cb, b))
                    c_hdr.add_widget(c_lbl)
                    c_hdr.add_widget(c_copy)
                    code_box.add_widget(c_hdr)
                    code_txt = AutoLabel(
                        text=f"[color=6ee7b7]{escape_markup(code_body)}[/color]",
                        font_size=sp(11),
                    )
                    code_box.add_widget(code_txt)
                    card.add_widget(code_box)
                else:
                    body = AutoLabel(
                        text=f"[color=e2e8f0]{escape_markup(chunk)}[/color]",
                        font_size=sp(13),
                    )
                    card.add_widget(body)

            wrapper.add_widget(card)
            wrapper.add_widget(BoxLayout(size_hint_x=0.06))

        self.chat_list.add_widget(wrapper)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.08)

    def _copy_text(self, text, btn=None):
        try:
            Clipboard.copy(text)
            if btn is not None:
                old = btn.text
                btn.text = "Copied!"
                Clock.schedule_once(lambda _dt: setattr(btn, "text", old), 1.5)
        except Exception:
            pass

    def _clear_chat(self):
        self.history = []
        self.chat_list.clear_widgets()
        self._add_message_card(
            "assistant",
            "Chat cleared, Harish. Ready for your next command!",
            model_tag="NEON Core",
        )

    def _update_voice_banner(self, message):
        self.voice_status_lbl.text = f"[b][color=22d3ee]VOICE[/color][/b] [color=cbd5e1]{escape_markup(message)}[/color]"

    def _on_voice_transcript(self, spoken_text):
        self.chat_input.text = spoken_text
        self._send_chat_prompt()

    def _toggle_thinking(self, *_args):
        self.high_thinking = not self.high_thinking
        if self.high_thinking:
            self.think_pill.text = "Think: ON"
            style_card(self.think_pill, (0.28, 0.12, 0.48, 1.0), (0.68, 0.40, 0.98, 0.8), radius_dp=8)
            self.think_pill.color = (0.90, 0.78, 1.0, 1.0)
        else:
            self.think_pill.text = "Think: OFF"
            style_card(self.think_pill, (0.08, 0.09, 0.16, 1.0), (0.25, 0.30, 0.45, 0.6), radius_dp=8)
            self.think_pill.color = (0.75, 0.80, 0.90, 1.0)
        self._save_config()
        self._refresh_header_state()

    def _save_inline_key(self, *_args):
        val = self.inline_key_input.text.strip()
        if not val:
            return
        self.api_key = val
        self._save_config()
        self._refresh_header_state()
        self._add_message_card(
            "assistant",
            "Gemini API key saved securely on your Android device! Ask me anything in Hindi or English.",
            model_tag="System",
        )

    def _send_chat_prompt(self, preset_prompt=None):
        prompt = (preset_prompt or self.chat_input.text).strip()
        if not prompt:
            return

        self.voice_bridge.stop_speaking()
        if not preset_prompt:
            self.chat_input.text = ""
        self._add_message_card("user", prompt)

        if not self.api_key:
            self._add_message_card(
                "assistant",
                "Harish, please tap 'Set Key' at the top right (or use the orange box above) to save your Gemini API key once. After that, all AI Chat, App Studio & Debugger features work instantly!",
                model_tag="Setup Needed",
            )
            return

        self.send_btn.disabled = True
        self.send_btn.text = "..."
        threading.Thread(
            target=self._run_gemini_chat,
            args=(prompt,),
            daemon=True,
        ).start()

    def _call_gemini_rest(self, contents, system_prompt=DEFAULT_SYSTEM_PROMPT, prefer_pro=False):
        chain = [self.selected_model, "gemini-4-hydrogen", "gemini-3.1-flash-lite"]
        if prefer_pro and "gemini-4-argon" not in chain:
            chain.insert(0, "gemini-4-argon")
        dedup_chain = list(dict.fromkeys(chain))

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
        }
        last_err = "Unknown error"
        for model_name in dedup_chain:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={self.api_key}"
            )
            try:
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    cands = data.get("candidates") or []
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        txt = "".join(p.get("text", "") for p in parts).strip()
                        if txt:
                            return txt, model_name, None
                else:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
                    if resp.status_code not in (404, 429, 500, 502, 503, 504):
                        break
            except Exception as exc:
                last_err = str(exc)
        return None, None, last_err

    def _run_gemini_chat(self, prompt):
        lang_hint = ""
        if self.language_mode == "hi":
            lang_hint = " Always reply in natural Hindi/Hinglish."
        elif self.language_mode == "en":
            lang_hint = " Always reply in crisp English."

        self.history.append({"role": "user", "parts": [{"text": prompt}]})
        recent = self.history[-10:]
        reply_text, used_model, err = self._call_gemini_rest(
            recent,
            system_prompt=DEFAULT_SYSTEM_PROMPT + lang_hint,
            prefer_pro=self.high_thinking,
        )

        def _done(_dt):
            self.send_btn.disabled = False
            self.send_btn.text = "SEND"
            if reply_text:
                self.history.append({"role": "model", "parts": [{"text": reply_text}]})
                self._add_message_card("assistant", reply_text, model_tag=used_model)
                if self.audio_enabled:
                    self.voice_bridge.speak(reply_text)
            else:
                self._add_message_card(
                    "assistant",
                    f"Gemini API Error: {err}",
                    model_tag="Error",
                )

        Clock.schedule_once(_done, 0)

    # ------------------------------------------------------------------
    # TAB 2: APP STUDIO (Templates, Live Code Viewer/Editor, AI Synthesis)
    # ------------------------------------------------------------------
    def _build_studio_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        banner = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(86), padding=dp(10), spacing=dp(6))
        style_card(banner, (0.04, 0.06, 0.12, 1.0), (0.06, 0.45, 0.62, 0.5), radius_dp=12)
        banner.add_widget(
            AutoLabel(
                text="[b][color=22d3ee]NEON App Studio[/color][/b] [color=94a3b8]• Inspect & Generate Mobile/PC Code[/color]",
                font_size=sp(12),
            )
        )

        preset_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        self.studio_files = {
            "main.py": "# NEON PRO Mobile Core\nprint('NEON PRO Running on Android!')\n",
            "buildozer.spec": "[app]\ntitle = NEON PRO Mobile\npackage.name = neonpromobile\nandroid.api = 33\nandroid.minapi = 21\nandroid.ndk = 25b\nandroid.ndk_api = 21\np4a.branch = v2024.01.21\n",
            "requirements.txt": "kivy>=2.3.0\nrequests>=2.31.0\ncertifi>=2024.2.2\n",
        }
        try:
            with open(__file__, "r", encoding="utf-8") as self_fh:
                self.studio_files["main.py"] = self_fh.read()
        except Exception:
            pass

        for fname in ("main.py", "buildozer.spec", "requirements.txt"):
            b = make_button(
                fname,
                (0.06, 0.12, 0.22, 1.0),
                (0.10, 0.65, 0.85, 0.5),
                text_rgba=(0.65, 0.92, 1.0, 1.0),
                radius_dp=8,
                font_sp=11,
            )
            b.bind(on_release=lambda _i, k=fname: self._load_studio_file(k))
            preset_row.add_widget(b)
        banner.add_widget(preset_row)
        root.add_widget(banner)

        # AI Code Generator Prompt Row
        gen_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.studio_prompt = TextInput(
            hint_text="Describe an app/script to generate with AI...",
            multiline=False,
            background_color=(0.03, 0.045, 0.085, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        gen_row.add_widget(self.studio_prompt)
        self.studio_gen_btn = make_button(
            "AI Build",
            (0.32, 0.16, 0.62, 1.0),
            (0.68, 0.45, 0.98, 0.7),
            radius_dp=9,
            font_sp=11,
            size_hint_x=None,
            width=dp(84),
        )
        self.studio_gen_btn.bind(on_release=lambda *_: self._studio_ai_generate())
        gen_row.add_widget(self.studio_gen_btn)
        root.add_widget(gen_row)

        # Code Editor Container
        editor_card = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        style_card(editor_card, (0.025, 0.035, 0.068, 1.0), (0.08, 0.25, 0.38, 0.6), radius_dp=12)

        ed_hdr = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
        self.studio_file_lbl = Label(
            text="[b][color=34d399]File: main.py[/color][/b]",
            markup=True,
            font_size=sp(11),
            halign="left",
            valign="middle",
        )
        self.studio_file_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        ed_hdr.add_widget(self.studio_file_lbl)

        copy_ed_btn = make_button(
            "Copy Code",
            (0.06, 0.18, 0.16, 1.0),
            (0.10, 0.72, 0.52, 0.6),
            text_rgba=(0.55, 0.96, 0.78, 1.0),
            radius_dp=7,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(80), dp(26)),
        )
        copy_ed_btn.bind(on_release=lambda *_: self._copy_text(self.studio_editor.text, copy_ed_btn))
        ed_hdr.add_widget(copy_ed_btn)

        debug_ed_btn = make_button(
            "Send Debug",
            (0.22, 0.10, 0.35, 1.0),
            (0.65, 0.35, 0.90, 0.6),
            text_rgba=(0.88, 0.72, 1.0, 1.0),
            radius_dp=7,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(84), dp(26)),
        )
        debug_ed_btn.bind(on_release=lambda *_: self._send_code_to_debugger())
        ed_hdr.add_widget(debug_ed_btn)
        editor_card.add_widget(ed_hdr)

        self.studio_editor = TextInput(
            text=self.studio_files["main.py"],
            multiline=True,
            background_color=(0.015, 0.022, 0.045, 1.0),
            foreground_color=(0.55, 0.94, 0.78, 1.0),
            cursor_color=(0.08, 0.80, 0.92, 1.0),
            font_size=sp(11),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )
        editor_card.add_widget(self.studio_editor)
        root.add_widget(editor_card)
        return root

    def _load_studio_file(self, fname):
        self.studio_file_lbl.text = f"[b][color=34d399]File: {fname}[/color][/b]"
        self.studio_editor.text = self.studio_files.get(fname, "")

    def _send_code_to_debugger(self):
        self.dbg_code.text = self.studio_editor.text[:6000]
        self._switch_tab("debugger")

    def _studio_ai_generate(self):
        goal = self.studio_prompt.text.strip()
        if not goal:
            return
        if not self.api_key:
            self._open_settings_modal()
            return
        self.studio_gen_btn.disabled = True
        self.studio_gen_btn.text = "Building..."

        def _worker():
            sys_p = (
                "Write complete, clean, zero-placeholder Python code for Harish's request. "
                "Return ONLY the complete source code without markdown fences if possible."
            )
            txt, _m, err = self._call_gemini_rest(
                [{"role": "user", "parts": [{"text": goal}]}],
                system_prompt=sys_p,
                prefer_pro=self.high_thinking,
            )

            def _done(_dt):
                self.studio_gen_btn.disabled = False
                self.studio_gen_btn.text = "AI Build"
                if txt:
                    cleaned = txt.replace("```python", "").replace("```", "").strip()
                    self.studio_file_lbl.text = "[b][color=34d399]File: generated_app.py[/color][/b]"
                    self.studio_editor.text = cleaned
                else:
                    self.studio_editor.text = f"# Generation failed: {err}"

            Clock.schedule_once(_done, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # TAB 3: AUTONOMOUS DEBUGGER
    # ------------------------------------------------------------------
    def _build_debugger_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        hdr = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74), padding=dp(10), spacing=dp(6))
        style_card(hdr, (0.04, 0.06, 0.12, 1.0), (0.48, 0.22, 0.72, 0.55), radius_dp=12)
        hdr.add_widget(
            AutoLabel(
                text="[b][color=c084fc]Autonomous Debugger[/color][/b] [color=94a3b8]• Paste Error + Code for Instant AI Fix[/color]",
                font_size=sp(12),
            )
        )
        preset_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
        dbg_presets = [
            (
                "Buildozer Fix",
                "p4a.branch = master\nrequirements = python3,kivy==2.3.0",
                "cgl_gl.c: error: too few arguments to function call, expected 6, have 5",
            ),
            (
                "Termux Fix",
                "pip install kivy psutil",
                "fatal error: 'Python.h' file not found",
            ),
            (
                "API 503/429",
                "requests.post(gemini_url)",
                "HTTP 503 Service Unavailable / Quota Exceeded",
            ),
        ]
        for label, scode, serr in dbg_presets:
            b = make_button(
                label,
                (0.11, 0.08, 0.20, 1.0),
                (0.58, 0.35, 0.85, 0.55),
                text_rgba=(0.86, 0.72, 1.0, 1.0),
                radius_dp=7,
                font_sp=10,
            )
            b.bind(on_release=lambda _i, c=scode, e=serr: self._load_debug_preset(c, e))
            preset_row.add_widget(b)
        hdr.add_widget(preset_row)
        root.add_widget(hdr)

        self.dbg_code = TextInput(
            hint_text="Paste source code or config (optional)...",
            multiline=True,
            size_hint_y=0.25,
            background_color=(0.025, 0.038, 0.075, 1.0),
            foreground_color=(0.90, 0.95, 1.0, 1.0),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(11),
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        root.add_widget(self.dbg_code)

        self.dbg_err = TextInput(
            hint_text="Paste error traceback or crash message here...",
            multiline=True,
            size_hint_y=0.23,
            background_color=(0.06, 0.025, 0.035, 1.0),
            foreground_color=(0.98, 0.70, 0.74, 1.0),
            hint_text_color=(0.65, 0.42, 0.48, 1.0),
            font_size=sp(11),
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        root.add_widget(self.dbg_err)

        self.dbg_run_btn = make_button(
            "Execute Autonomous Fix",
            (0.30, 0.16, 0.65, 1.0),
            (0.08, 0.75, 0.90, 0.7),
            radius_dp=10,
            font_sp=13,
            size_hint_y=None,
            height=dp(42),
        )
        self.dbg_run_btn.bind(on_release=lambda *_: self._run_autonomous_debug())
        root.add_widget(self.dbg_run_btn)

        out_card = BoxLayout(orientation="vertical", size_hint_y=0.52, padding=dp(10), spacing=dp(6))
        style_card(out_card, (0.03, 0.045, 0.088, 1.0), (0.08, 0.62, 0.48, 0.5), radius_dp=12)
        out_hdr = BoxLayout(size_hint_y=None, height=dp(26))
        out_hdr.add_widget(
            AutoLabel(text="[b][color=34d399]Diagnosis & Fix Output[/color][/b]", font_size=sp(11))
        )
        copy_dbg = make_button(
            "Copy Fix",
            (0.06, 0.18, 0.15, 1.0),
            (0.10, 0.72, 0.52, 0.6),
            text_rgba=(0.55, 0.96, 0.78, 1.0),
            radius_dp=6,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(72), dp(24)),
        )
        copy_dbg.bind(on_release=lambda *_: self._copy_text(self.dbg_output.text, copy_dbg))
        out_hdr.add_widget(copy_dbg)
        out_card.add_widget(out_hdr)

        dbg_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.dbg_output = AutoLabel(
            text="[color=94a3b8]Select a preset above or paste an error log and tap 'Execute Autonomous Fix'.[/color]",
            font_size=sp(12),
        )
        dbg_scroll.add_widget(self.dbg_output)
        out_card.add_widget(dbg_scroll)
        root.add_widget(out_card)
        return root

    def _load_debug_preset(self, code_str, err_str):
        self.dbg_code.text = code_str
        self.dbg_err.text = err_str

    def _run_autonomous_debug(self):
        code_v = self.dbg_code.text.strip()
        err_v = self.dbg_err.text.strip()
        if not code_v and not err_v:
            return
        if not self.api_key:
            self._open_settings_modal()
            return

        self.dbg_run_btn.disabled = True
        self.dbg_run_btn.text = "Analyzing with NEON PRO..."

        def _worker():
            prompt = (
                "Diagnose this issue for Harish with: 1) Root Cause, 2) Exact Working Fix.\n\n"
                f"CODE:\n{code_v}\n\nERROR:\n{err_v}"
            )
            txt, _m, err = self._call_gemini_rest(
                [{"role": "user", "parts": [{"text": prompt}]}],
                prefer_pro=True,
            )

            def _done(_dt):
                self.dbg_run_btn.disabled = False
                self.dbg_run_btn.text = "Execute Autonomous Fix"
                if txt:
                    self.dbg_output.text = f"[color=e2e8f0]{escape_markup(txt)}[/color]"
                else:
                    self.dbg_output.text = f"[color=fda4af]Debugger Error: {escape_markup(err)}[/color]"

            Clock.schedule_once(_done, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # TAB 4: BUILD LAB (Device Telemetry + Quick Command Terminal)
    # ------------------------------------------------------------------
    def _build_lab_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        quick_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        for label, cmd in (
            ("neon status", "neon status"),
            ("device info", "device info"),
            ("python ver", "python ver"),
            ("clear", "clear"),
        ):
            b = make_button(
                label,
                (0.05, 0.11, 0.18, 1.0),
                (0.06, 0.65, 0.50, 0.55),
                text_rgba=(0.45, 0.95, 0.76, 1.0),
                radius_dp=8,
                font_sp=11,
            )
            b.bind(on_release=lambda _i, c=cmd: self._run_lab_cmd(c))
            quick_row.add_widget(b)
        root.add_widget(quick_row)

        term_card = BoxLayout(orientation="vertical", padding=dp(10))
        style_card(term_card, (0.015, 0.022, 0.048, 1.0), (0.06, 0.45, 0.62, 0.5), radius_dp=12)
        self.lab_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.lab_log = AutoLabel(
            text=(
                "[color=22d3ee][b]NEON PRO Build & Device Lab v3.0[/b][/color]\n"
                "[color=34d399]Operator: Harish | Platform: "
                f"{platform.upper()} ({sys_platform.machine()})[/color]\n"
                f"[color=94a3b8]Python: {sys.version.split()[0]} | Screen: {Window.width}x{Window.height}[/color]\n"
                "[color=6ee7b7]Ready. Tap a quick command above or type below.[/color]"
            ),
            font_size=sp(12),
        )
        self.lab_scroll.add_widget(self.lab_log)
        term_card.add_widget(self.lab_scroll)
        root.add_widget(term_card)

        cmd_bar = BoxLayout(size_hint_y=None, height=dp(46), padding=dp(5), spacing=dp(6))
        style_card(cmd_bar, (0.04, 0.06, 0.11, 1.0), (0.06, 0.50, 0.68, 0.55), radius_dp=12)
        self.lab_input = TextInput(
            hint_text="Type command (neon status, device info, clear)...",
            multiline=False,
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(0.45, 0.96, 0.72, 1.0),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        self.lab_input.bind(on_text_validate=lambda *_: self._run_lab_cmd())
        cmd_bar.add_widget(self.lab_input)
        run_btn = make_button(
            "Run",
            (0.04, 0.48, 0.36, 1.0),
            (0.10, 0.80, 0.58, 0.7),
            radius_dp=8,
            font_sp=11,
            size_hint_x=None,
            width=dp(68),
        )
        run_btn.bind(on_release=lambda *_: self._run_lab_cmd())
        cmd_bar.add_widget(run_btn)
        root.add_widget(cmd_bar)
        return root

    def _run_lab_cmd(self, preset=None):
        cmd = (preset or self.lab_input.text).strip()
        if not cmd:
            return
        if not preset:
            self.lab_input.text = ""
        if cmd == "clear":
            self.lab_log.text = "[color=34d399]Terminal cleared. Ready.[/color]"
            return

        lines = [f"[color=38bdf8]harish@neon-pro:~$ {escape_markup(cmd)}[/color]"]
        low = cmd.lower()
        if "status" in low:
            lines.extend([
                f"[color=34d399]• App Engine:[/color] NEON PRO v3.0 Mobile Suite",
                f"[color=34d399]• Active Model:[/color] {self.selected_model}",
                f"[color=34d399]• API Key:[/color] {'Configured' if self.api_key else 'Not Set (Tap Set Key)'}",
                f"[color=34d399]• Native Voice:[/color] {'Ready' if self.voice_bridge._android_ready else 'Text/Termux Fallback'}",
            ])
        elif "device" in low:
            lines.extend([
                f"[color=e2e8f0]OS/Platform: {platform} / {sys_platform.platform()}[/color]",
                f"[color=e2e8f0]Architecture: {sys_platform.machine()}[/color]",
                f"[color=e2e8f0]Display Pixels: {Window.width}x{Window.height}[/color]",
                f"[color=e2e8f0]Data Dir: {App.get_running_app().user_data_dir}[/color]",
            ])
        elif "python" in low:
            lines.append(f"[color=e2e8f0]Python {sys.version}[/color]")
        else:
            lines.append("[color=cbd5e1]Command executed (status 0). Try: neon status, device info, python ver, clear[/color]")

        self.lab_log.text += "\n" + "\n".join(lines)
        Clock.schedule_once(lambda dt: setattr(self.lab_scroll, "scroll_y", 0), 0.05)

    # ------------------------------------------------------------------
    # SETTINGS & API KEY MODAL
    # ------------------------------------------------------------------
    def _open_settings_modal(self):
        modal = ModalView(size_hint=(0.94, None), height=dp(450), background_color=(0, 0, 0, 0.72))
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        style_card(box, (0.04, 0.06, 0.12, 1.0), (0.08, 0.72, 0.88, 0.75), radius_dp=16, border_width=1.3)

        hdr = BoxLayout(size_hint_y=None, height=dp(32))
        hdr.add_widget(
            AutoLabel(text="[b][color=22d3ee]NEON PRO Settings & API[/color][/b]", font_size=sp(15))
        )
        close_btn = make_button(
            "Close",
            (0.18, 0.08, 0.12, 1.0),
            (0.85, 0.28, 0.38, 0.65),
            radius_dp=8,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(64), dp(30)),
        )
        close_btn.bind(on_release=lambda *_: modal.dismiss())
        hdr.add_widget(close_btn)
        box.add_widget(hdr)

        box.add_widget(
            AutoLabel(text="[color=cbd5e1]Gemini API Key (Saved on device):[/color]", font_size=sp(11))
        )
        key_inp = TextInput(
            text=self.api_key,
            hint_text="Paste GEMINI_API_KEY (AIza...)",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(42),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            font_size=sp(12),
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        box.add_widget(key_inp)

        box.add_widget(AutoLabel(text="[color=cbd5e1]Select Gemini Model:[/color]", font_size=sp(11)))
        model_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        model_btns = {}

        def _refresh_modal_pills():
            for mid, b in model_btns.items():
                if mid == self.selected_model:
                    style_card(b, (0.05, 0.28, 0.38, 1.0), (0.08, 0.80, 0.92, 0.8), radius_dp=8)
                else:
                    style_card(b, (0.06, 0.09, 0.16, 1.0), (0.22, 0.30, 0.42, 0.5), radius_dp=8)

        for mid, mlabel in self.MODELS:
            mb = make_button(mlabel, (0.06, 0.09, 0.16, 1.0), None, radius_dp=8, font_sp=11)

            def _pick_model(_i, target_id=mid):
                self.selected_model = target_id
                _refresh_modal_pills()
                self._save_config()
                self._refresh_header_state()

            mb.bind(on_release=_pick_model)
            model_btns[mid] = mb
            model_row.add_widget(mb)
        _refresh_modal_pills()
        box.add_widget(model_row)

        box.add_widget(AutoLabel(text="[color=cbd5e1]Language Mode:[/color]", font_size=sp(11)))
        lang_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        lang_btns = {}

        def _refresh_lang_pills():
            for lkey, b in lang_btns.items():
                if lkey == self.language_mode:
                    style_card(b, (0.05, 0.28, 0.38, 1.0), (0.08, 0.80, 0.92, 0.8), radius_dp=8)
                else:
                    style_card(b, (0.06, 0.09, 0.16, 1.0), (0.22, 0.30, 0.42, 0.5), radius_dp=8)

        for lkey, llabel in (("auto", "Auto (EN+HI)"), ("hi", "Hindi"), ("en", "English")):
            lb = make_button(llabel, (0.06, 0.09, 0.16, 1.0), None, radius_dp=8, font_sp=11)

            def _pick_lang(_i, target_lang=lkey):
                self.language_mode = target_lang
                self.voice_bridge.set_language_mode(target_lang)
                _refresh_lang_pills()
                self._save_config()

            lb.bind(on_release=_pick_lang)
            lang_btns[lkey] = lb
            lang_row.add_widget(lb)
        _refresh_lang_pills()
        box.add_widget(lang_row)

        save_btn = make_button(
            "Save Settings",
            (0.04, 0.55, 0.42, 1.0),
            (0.15, 0.90, 0.65, 0.8),
            radius_dp=10,
            font_sp=13,
            size_hint_y=None,
            height=dp(42),
        )

        def _save_and_close(*_a):
            self.api_key = key_inp.text.strip()
            self._save_config()
            self._refresh_header_state()
            modal.dismiss()

        save_btn.bind(on_release=_save_and_close)
        box.add_widget(save_btn)

        web_btn = make_button(
            "Open Cloud Web Cockpit in Browser",
            (0.10, 0.15, 0.28, 1.0),
            (0.28, 0.48, 0.88, 0.6),
            text_rgba=(0.68, 0.85, 1.0, 1.0),
            radius_dp=10,
            font_sp=11,
            size_hint_y=None,
            height=dp(36),
        )
        web_btn.bind(on_release=lambda *_: webbrowser.open(WEB_COCKPIT_URL))
        box.add_widget(web_btn)

        modal.add_widget(box)
        modal.open()


class NeonApp(App):
    def build(self):
        self.title = "NEON PRO Mobile"
        return NeonProMobileSuite()


if __name__ == "__main__":
    NeonApp().run()
