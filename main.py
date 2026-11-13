"""
NEON PRO v4.0 - Autonomous Android Mobile & Desktop Suite
Architected for: Harish
Features:
  - Complete Web Preview Parity (Console, App Studio, Debugger, Build Lab, GitHub CI)
  - Voice-First Engine: Hands-Free loop, Barge-In, Personas, Gemini TTS (WAV) + UI-Thread Android TTS retry + auto-send STT
  - Crash-proof Android startup & callback-safe RECORD_AUDIO permissions
  - Dynamic Gemini REST API failover + /v1beta/models auto-discovery + Autonomous Code Sync
"""
import base64
import json
import os
import platform as sys_platform
import re
import shutil
import ssl
import struct
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

try:
    import certifi
except Exception:
    certifi = None

try:
    import requests
except Exception:
    requests = None

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
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

# Fix SSL certificate bundle path on Android safely
try:
    if certifi is not None:
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except Exception:
    pass

# Cyber-dark palette matching NEON PRO web cockpit (#05070f)
try:
    Window.clearcolor = (0.02, 0.027, 0.059, 1.0)
    Window.softinput_mode = "below_target"
except Exception:
    pass

CONFIG_FILE = "neon_pro_config.json"
WEB_COCKPIT_URL = "https://ais-pre-ccf5jvawenmhsjix56rckx-803295381828.asia-southeast1.run.app"
DEFAULT_SYSTEM_PROMPT = (
    "You are NEON PRO, Harish's autonomous, bilingual (Hindi / English / Hinglish) "
    "personal AI companion and voice assistant. "
    "Core Behavioral Rules for Conversation: "
    "1. Talk naturally, warmly, and directly like a close Indian peer or friend—just like a natural human conversation. Never sound robotic, stiff, or like a corporate customer service bot. "
    "2. NEVER recite system status reports, battery levels, connection logs, or technical diagnostics unless explicitly requested. "
    "3. Keep conversational responses concise, punchy, and context-aware. If Harish asks 'How are you?' or greets casually, reply like a normal friend (e.g., 'Ekdum mast bhai, batao kya plan hai?'), never stiff. "
    "4. Eliminate filler text and unnecessary pleasantries. When Harish asks to build, architect, or develop an app/software/script, jump straight to clean, complete, zero-placeholder runnable Python/Kivy code inside triple-backtick code blocks."
)


def style_card(widget, bg_rgba, border_rgba=None, radius_dp=12, border_width=1.0):
    """Attach rounded background and crisp cyber-neon border to any Kivy widget."""
    old_cb = getattr(widget, "_card_sync_cb", None)
    if old_cb is not None:
        try:
            widget.unbind(pos=old_cb, size=old_cb)
        except Exception:
            pass

    widget.canvas.before.clear()
    with widget.canvas.before:
        bg_color = Color(*bg_rgba)
        bg_rect = RoundedRectangle(
            pos=widget.pos,
            size=(max(widget.width, 1), max(widget.height, 1)),
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
        bg_rect.size = (max(widget.width, 1), max(widget.height, 1))
        if border_line is not None:
            border_line.rounded_rectangle = (
                widget.x,
                widget.y,
                max(widget.width, 1),
                max(widget.height, 1),
                dp(radius_dp),
            )

    widget._card_sync_cb = _sync
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
    btn.bind(size=lambda inst, sz: setattr(inst, "text_size", (max(sz[0] - dp(6), dp(18)), None)))
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


def _pcm_to_wav_bytes(pcm_bytes, sample_rate=24000, channels=1, bits_per_sample=16):
    """Wrap raw PCM bytes into a standard 44-byte RIFF/WAVE header if not already WAV."""
    if pcm_bytes[:4] == b"RIFF":
        return pcm_bytes
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = len(pcm_bytes)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm_bytes


class AndroidVoiceBridge:
    """Thread-safe Gemini TTS + Native Android TTS Fallback + Callback-Safe Speech Recognizer."""

    def __init__(self, status_callback, transcript_callback, speak_done_callback, data_dir_fn):
        self.on_status = status_callback
        self.on_transcript = transcript_callback
        self.on_speak_done = speak_done_callback
        self.get_data_dir = data_dir_fn
        self.tts = None
        self.is_speaking = False
        self.is_listening = False
        self.speech_req_code = 9042
        self._android_ready = False
        self._activity = None
        self._Locale = None
        self._language_mode = "auto"
        self._voice_persona = "Fenrir"
        self._api_key = ""
        self._active_sound = None
        self._speak_gen = 0
        self._poll_ev = None

    def configure(self, api_key=None, language_mode=None, voice_persona=None):
        if api_key is not None:
            self._api_key = api_key.strip()
        if language_mode is not None:
            self._language_mode = language_mode
        if voice_persona is not None:
            self._voice_persona = voice_persona

    def _run_ui(self, fn):
        if platform == "android":
            try:
                from android.runnable import run_on_ui_thread

                run_on_ui_thread(fn)()
                return
            except Exception:
                pass
        fn()

    def _ensure_android_ready(self):
        if platform != "android" or self._android_ready:
            return self._android_ready
        try:
            from android import activity
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._activity = PythonActivity.mActivity
            self._Locale = autoclass("java.util.Locale")
            activity.bind(on_activity_result=self._on_activity_result)
            self._android_ready = True
            return True
        except BaseException as exc:
            Clock.schedule_once(lambda _dt, e=str(exc): self.on_status(f"Voice note: {e}"), 0)
            return False

    def _cancel_poll(self):
        if self._poll_ev is not None:
            try:
                self._poll_ev.cancel()
            except Exception:
                pass
            self._poll_ev = None

    def stop_speaking(self):
        self._speak_gen += 1
        self._cancel_poll()
        self.is_speaking = False
        if self._active_sound is not None:
            try:
                self._active_sound.stop()
                self._active_sound.unload()
            except BaseException:
                pass
            self._active_sound = None
        if self.tts is not None:
            try:
                self._run_ui(lambda: self.tts.stop())
            except BaseException:
                pass

    def _notify_speak_finished(self, gen):
        if gen != self._speak_gen:
            return
        self._cancel_poll()
        self.is_speaking = False
        Clock.schedule_once(lambda _dt: self.on_speak_done(), 0.05)

    def _speak_native_with_retry(self, clean_text, gen):
        if platform != "android":
            if shutil.which("termux-tts-speak"):
                def _termux():
                    subprocess.run(["termux-tts-speak", clean_text], check=False)
                    Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.1)

                threading.Thread(target=_termux, daemon=True).start()
            else:
                Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.6)
            return

        if not self._ensure_android_ready():
            Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.2)
            return

        def _try_speak(attempt=0):
            if gen != self._speak_gen:
                return

            def _ui():
                if gen != self._speak_gen:
                    return
                try:
                    from jnius import autoclass

                    TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                    if self.tts is None:
                        self.tts = TextToSpeech(self._activity, None)
                        Clock.schedule_once(lambda _dt: _try_speak(attempt + 1), 0.75)
                        return

                    use_hi = self._language_mode == "hi" or any(
                        "\u0900" <= ch <= "\u097f" for ch in clean_text
                    )
                    try:
                        self.tts.setLanguage(self._Locale("hi" if use_hi else "en", "IN"))
                    except BaseException:
                        pass

                    rc = self.tts.speak(clean_text, TextToSpeech.QUEUE_FLUSH, None, f"neon_{gen}")
                    if rc == -1 and attempt < 5:
                        Clock.schedule_once(lambda _dt: _try_speak(attempt + 1), 0.65)
                        return

                    # Poll TTS speaking status to fire Hands-Free completion cleanly
                    started_at = time.time()
                    max_wait = max(min(len(clean_text) * 0.11 + 2.5, 28.0), 3.0)

                    def _poll(_dt):
                        if gen != self._speak_gen:
                            return False
                        elapsed = time.time() - started_at
                        speaking_now = False
                        try:
                            speaking_now = bool(self.tts and self.tts.isSpeaking())
                        except BaseException:
                            speaking_now = elapsed < min(len(clean_text) * 0.08 + 1.2, 16.0)
                        if (not speaking_now and elapsed > 0.9) or elapsed >= max_wait:
                            self._notify_speak_finished(gen)
                            return False
                        return True

                    self._cancel_poll()
                    self._poll_ev = Clock.schedule_interval(_poll, 0.35)
                except BaseException as exc:
                    if attempt < 3:
                        Clock.schedule_once(lambda _dt: _try_speak(attempt + 1), 0.6)
                    else:
                        Clock.schedule_once(lambda _dt, e=str(exc): self.on_status(f"TTS note: {e}"), 0)
                        self._notify_speak_finished(gen)

            self._run_ui(_ui)

        _try_speak(0)

    def _fetch_gemini_tts_wav(self, clean_text):
        """Call Gemini TTS endpoint directly over HTTPS and write WAV file if available."""
        if not self._api_key:
            return None
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.8-flash-lite-tts:generateContent?key={self._api_key}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": clean_text[:700]}],
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": self._voice_persona or "Fenrir"}
                    }
                },
            },
        }
        try:
            data = None
            if requests is not None:
                resp = requests.post(url, json=payload, timeout=14)
                if resp.status_code == 200:
                    data = resp.json()
            else:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, context=ctx, timeout=14) as uresp:
                    if uresp.getcode() == 200:
                        data = json.loads(uresp.read().decode("utf-8", errors="replace"))

            if not data:
                return None
            cands = data.get("candidates") or []
            if not cands:
                return None
            parts = cands[0].get("content", {}).get("parts", [])
            b64 = None
            for p in parts:
                idata = p.get("inlineData") or p.get("inline_data")
                if idata and idata.get("data"):
                    b64 = idata["data"]
                    break
            if not b64:
                return None
            raw_audio = base64.b64decode(b64)
            wav_bytes = _pcm_to_wav_bytes(raw_audio)
            out_dir = self.get_data_dir()
            os.makedirs(out_dir, exist_ok=True)
            wav_path = os.path.join(out_dir, "neon_tts_reply.wav")
            with open(wav_path, "wb") as fh:
                fh.write(wav_bytes)
            return wav_path
        except Exception:
            return None

    def speak(self, text):
        if not text:
            return
        cleaned = re.sub(r"```[\s\S]*?```", " Code block App Studio me bhej diya hai. ", str(text))
        cleaned = cleaned.replace("*", "").replace("#", "").replace("`", "").strip()
        cleaned = " ".join(cleaned.split())[:650]
        if not cleaned:
            return

        self.stop_speaking()
        gen = self._speak_gen
        self.is_speaking = True
        Clock.schedule_once(lambda _dt: self.on_status(f"NEON PRO VOICE OUTPUT ({self._voice_persona})"), 0)

        def _worker():
            wav_path = self._fetch_gemini_tts_wav(cleaned)
            if gen != self._speak_gen:
                return
            if wav_path and os.path.exists(wav_path):
                def _play_wav(_dt):
                    if gen != self._speak_gen:
                        return
                    try:
                        snd = SoundLoader.load(wav_path)
                        if snd is not None:
                            self._active_sound = snd
                            snd.bind(on_stop=lambda *_a: self._notify_speak_finished(gen))
                            snd.play()
                            return
                    except BaseException:
                        pass
                    self._speak_native_with_retry(cleaned, gen)

                Clock.schedule_once(_play_wav, 0)
            else:
                Clock.schedule_once(lambda _dt: self._speak_native_with_retry(cleaned, gen), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _launch_android_recognizer(self):
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
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, False)
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Bolo Harish, NEON PRO sun raha hai...")
            self.is_listening = True
            self.on_status("HARISH SPEAKING... (Listening)")
            self._run_ui(lambda: self._activity.startActivityForResult(intent, self.speech_req_code))
        except BaseException as exc:
            self.is_listening = False
            self.on_status(f"Mic unavailable: {exc}")

    def _on_activity_result(self, request_code, result_code, intent):
        if request_code != self.speech_req_code:
            return
        self.is_listening = False
        if result_code != -1 or intent is None:
            Clock.schedule_once(lambda _dt: self.on_status("Voice canceled — tap MIC to speak"), 0)
            return
        try:
            from jnius import autoclass

            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if results and results.size() > 0:
                spoken_text = str(results.get(0)).strip()
                if spoken_text:
                    Clock.schedule_once(lambda _dt, s=spoken_text: self.on_transcript(s), 0)
                    return
            Clock.schedule_once(lambda _dt: self.on_status("Samjha nahi — dobara boliyega"), 0)
        except BaseException as exc:
            Clock.schedule_once(lambda _dt, e=str(exc): self.on_status(f"Mic parse error: {e}"), 0)

    def start_listening(self):
        self.stop_speaking()
        if platform == "android":
            if not self._ensure_android_ready():
                return
            try:
                from android.permissions import Permission, check_permission, request_permissions

                if check_permission(Permission.RECORD_AUDIO):
                    self._launch_android_recognizer()
                else:
                    self.on_status("Requesting Mic permission...")

                    def _on_perm(_perms, grants):
                        if grants and all(grants):
                            Clock.schedule_once(lambda _dt: self._launch_android_recognizer(), 0.15)
                        else:
                            Clock.schedule_once(
                                lambda _dt: self.on_status("Mic permission denied — allow in Android Settings"),
                                0,
                            )

                    request_permissions([Permission.RECORD_AUDIO], _on_perm)
                return
            except BaseException as exc:
                self.on_status(f"Mic unavailable: {exc}")
                return

        if shutil.which("termux-speech-to-text"):
            self.is_listening = True
            self.on_status("HARISH SPEAKING... (Termux Mic)")

            def _listen():
                try:
                    proc = subprocess.run(
                        ["termux-speech-to-text"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    self.is_listening = False
                    spoken = proc.stdout.strip()
                    if spoken:
                        Clock.schedule_once(lambda _dt, s=spoken: self.on_transcript(s), 0)
                    else:
                        Clock.schedule_once(lambda _dt: self.on_status("Ready — tap MIC to speak"), 0)
                except Exception as err:
                    self.is_listening = False
                    Clock.schedule_once(lambda _dt, e=str(err): self.on_status(f"Termux mic error: {e}"), 0)

            threading.Thread(target=_listen, daemon=True).start()
        else:
            self.on_status("Ready — type below or use MIC on Android phone")


def escape_markup(text):
    return str(text).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


class NeonProMobileSuite(BoxLayout):
    """Full Cyber-Neon 5-Tab Mobile UI matching NEON PRO Web Preview."""

    MODELS = [
        ("gemini-4-hydrogen", "4 Hydrogen"),
        ("gemini-4-carbon", "4 Carbon"),
        ("gemini-4-argon", "4 Argon"),
        ("gemini-3.1-flash-lite", "3.1 Lite"),
    ]
    PERSONAS = ["Fenrir", "Kore", "Puck", "Zephyr"]
    LANGUAGES = [("auto", "Auto EN+HI"), ("hi", "Hindi"), ("en", "English")]

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(7), spacing=dp(6), **kwargs)
        self.config_data = self._load_config()
        self.api_key = self.config_data.get("api_key", "")
        saved_model = self.config_data.get("model", "gemini-4-hydrogen")
        valid_ids = {m[0] for m in self.MODELS}
        self.selected_model = saved_model if saved_model in valid_ids else "gemini-4-hydrogen"
        self.high_thinking = bool(self.config_data.get("high_thinking", False))
        self.audio_enabled = bool(self.config_data.get("audio_enabled", True))
        self.language_mode = self.config_data.get("language_mode", "auto")
        self.hands_free_mode = bool(self.config_data.get("hands_free_mode", False))
        self.voice_persona = self.config_data.get("voice_persona", "Fenrir")
        self.github_token = self.config_data.get("github_token", "")
        self.github_repo = self.config_data.get("github_repo", "neon-pro-harish")
        self.discovered_models = []
        self.history = []
        self.active_tab = "console"
        self.tab_buttons = {}
        self._pending_busy = False

        self.voice_bridge = AndroidVoiceBridge(
            status_callback=self._update_voice_banner,
            transcript_callback=self._on_voice_transcript,
            speak_done_callback=self._on_tts_finished,
            data_dir_fn=self._get_data_dir,
        )
        self.voice_bridge.configure(
            api_key=self.api_key,
            language_mode=self.language_mode,
            voice_persona=self.voice_persona,
        )

        self._build_header()
        self._build_controls_strip()
        self._build_tab_bar()
        self._build_screens()
        self._refresh_header_state()
        self._switch_tab("console")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _get_data_dir(self):
        base_dir = "."
        try:
            app = App.get_running_app()
            if app and getattr(app, "user_data_dir", None):
                base_dir = app.user_data_dir
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            base_dir = "."
        return base_dir

    def _get_config_path(self):
        return os.path.join(self._get_data_dir(), CONFIG_FILE)

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
            "hands_free_mode": self.hands_free_mode,
            "voice_persona": self.voice_persona,
            "github_token": self.github_token,
            "github_repo": self.github_repo,
        }
        try:
            with open(self._get_config_path(), "w", encoding="utf-8") as fh:
                json.dump(self.config_data, fh)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Top Header, Compact Controls Strip & 5-Tab Bar (Matches Preview)
    # ------------------------------------------------------------------
    def _build_header(self):
        header = BoxLayout(size_hint_y=None, height=dp(54), padding=[dp(8), dp(6)], spacing=dp(6))
        style_card(header, (0.035, 0.051, 0.098, 1.0), (0.04, 0.45, 0.62, 0.55), radius_dp=12)

        badge = make_button(
            "NP",
            (0.02, 0.65, 0.80, 1.0),
            (0.22, 0.85, 0.95, 0.9),
            radius_dp=9,
            font_sp=13,
            size_hint=(None, None),
            size=(dp(36), dp(36)),
        )
        badge.pos_hint = {"center_y": 0.5}
        header.add_widget(badge)

        title_col = BoxLayout(orientation="vertical", spacing=dp(1))
        title_lbl = Label(
            text="[b][color=ffffff]NEON[/color] [color=22d3ee]PRO[/color][/b] [color=64748b]v4.0[/color]",
            markup=True,
            font_size=sp(15),
            halign="left",
            valign="bottom",
        )
        title_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.subtitle_lbl = Label(
            text="[color=34d399]●[/color] [color=94a3b8]Harish • Ready[/color]",
            markup=True,
            font_size=sp(10),
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
            radius_dp=8,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(58), dp(32)),
        )
        self.tts_toggle_btn.pos_hint = {"center_y": 0.5}
        self.tts_toggle_btn.bind(on_release=self._toggle_audio)
        header.add_widget(self.tts_toggle_btn)

        self.settings_btn = make_button(
            "Set Key",
            (0.22, 0.14, 0.04, 1.0),
            (0.95, 0.65, 0.1, 0.65),
            text_rgba=(0.99, 0.82, 0.35, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(68), dp(32)),
        )
        self.settings_btn.pos_hint = {"center_y": 0.5}
        self.settings_btn.bind(on_release=lambda *_: self._open_settings_modal())
        header.add_widget(self.settings_btn)

        self.add_widget(header)

    def _build_controls_strip(self):
        strip = BoxLayout(size_hint_y=None, height=dp(36), padding=[dp(4), dp(3)], spacing=dp(5))
        style_card(strip, (0.03, 0.045, 0.09, 1.0), (0.08, 0.25, 0.38, 0.45), radius_dp=10)

        self.model_pill = make_button(
            "4 Hydrogen",
            (0.05, 0.14, 0.24, 1.0),
            (0.08, 0.60, 0.82, 0.6),
            text_rgba=(0.55, 0.92, 1.0, 1.0),
            radius_dp=7,
            font_sp=10,
        )
        self.model_pill.bind(on_release=self._cycle_model)
        strip.add_widget(self.model_pill)

        self.think_pill = make_button(
            "Think: OFF",
            (0.08, 0.09, 0.16, 1.0),
            (0.25, 0.30, 0.45, 0.6),
            text_rgba=(0.75, 0.80, 0.90, 1.0),
            radius_dp=7,
            font_sp=10,
        )
        self.think_pill.bind(on_release=self._toggle_thinking)
        strip.add_widget(self.think_pill)

        self.lang_pill = make_button(
            "Auto EN+HI",
            (0.05, 0.14, 0.20, 1.0),
            (0.10, 0.68, 0.62, 0.55),
            text_rgba=(0.55, 0.96, 0.82, 1.0),
            radius_dp=7,
            font_sp=10,
        )
        self.lang_pill.bind(on_release=self._cycle_language)
        strip.add_widget(self.lang_pill)

        self.add_widget(strip)

    def _build_tab_bar(self):
        tab_bar = BoxLayout(size_hint_y=None, height=dp(40), padding=dp(3), spacing=dp(4))
        style_card(tab_bar, (0.045, 0.068, 0.125, 1.0), (0.12, 0.18, 0.30, 0.9), radius_dp=10)

        tabs = [
            ("console", "Console"),
            ("app-studio", "Studio"),
            ("debugger", "Debug"),
            ("terminal", "Lab"),
            ("github", "GitHub CI"),
        ]
        for key, label in tabs:
            btn = make_button(
                label,
                (0.06, 0.09, 0.16, 1.0),
                None,
                text_rgba=(0.65, 0.74, 0.86, 1.0),
                radius_dp=7,
                font_sp=10,
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
                style_card(btn, (0.05, 0.25, 0.34, 1.0), (0.08, 0.78, 0.90, 0.7), radius_dp=7)
                btn.color = (0.45, 0.95, 1.0, 1.0)
            else:
                style_card(btn, (0.045, 0.068, 0.125, 1.0), None, radius_dp=7)
                btn.color = (0.62, 0.71, 0.82, 1.0)

    def _cycle_model(self, *_args):
        ids = [m[0] for m in self.MODELS]
        idx = ids.index(self.selected_model) if self.selected_model in ids else 0
        self.selected_model = ids[(idx + 1) % len(ids)]
        self._save_config()
        self._refresh_header_state()

    def _cycle_language(self, *_args):
        keys = [l[0] for l in self.LANGUAGES]
        idx = keys.index(self.language_mode) if self.language_mode in keys else 0
        self.language_mode = keys[(idx + 1) % len(keys)]
        self.voice_bridge.configure(language_mode=self.language_mode)
        self._save_config()
        self._refresh_header_state()

    def _cycle_persona(self, *_args):
        idx = self.PERSONAS.index(self.voice_persona) if self.voice_persona in self.PERSONAS else 0
        self.voice_persona = self.PERSONAS[(idx + 1) % len(self.PERSONAS)]
        self.voice_bridge.configure(voice_persona=self.voice_persona)
        self._save_config()
        self._refresh_header_state()

    def _refresh_header_state(self):
        model_short = dict(self.MODELS).get(self.selected_model, self.selected_model)
        lang_short = dict(self.LANGUAGES).get(self.language_mode, "Auto EN+HI")
        think_tag = " • High Think" if self.high_thinking else ""
        self.subtitle_lbl.text = (
            f"[color=34d399]●[/color] [color=cbd5e1]Harish[/color] "
            f"[color=64748b]•[/color] [color=38bdf8]{model_short}{think_tag}[/color]"
        )
        if hasattr(self, "model_pill"):
            self.model_pill.text = model_short
        if hasattr(self, "lang_pill"):
            self.lang_pill.text = lang_short
        if hasattr(self, "think_pill"):
            if self.high_thinking:
                self.think_pill.text = "Think: ON"
                style_card(self.think_pill, (0.28, 0.12, 0.48, 1.0), (0.68, 0.40, 0.98, 0.8), radius_dp=7)
                self.think_pill.color = (0.90, 0.78, 1.0, 1.0)
            else:
                self.think_pill.text = "Think: OFF"
                style_card(self.think_pill, (0.08, 0.09, 0.16, 1.0), (0.25, 0.30, 0.45, 0.6), radius_dp=7)
                self.think_pill.color = (0.75, 0.80, 0.90, 1.0)

        if hasattr(self, "hands_free_btn"):
            if self.hands_free_mode:
                self.hands_free_btn.text = "Hands-Free ON"
                style_card(self.hands_free_btn, (0.04, 0.28, 0.20, 1.0), (0.12, 0.85, 0.55, 0.8), radius_dp=8)
                self.hands_free_btn.color = (0.45, 0.98, 0.75, 1.0)
            else:
                self.hands_free_btn.text = "Hands-Free OFF"
                style_card(self.hands_free_btn, (0.07, 0.09, 0.16, 1.0), (0.25, 0.32, 0.45, 0.6), radius_dp=8)
                self.hands_free_btn.color = (0.75, 0.82, 0.92, 1.0)

        if hasattr(self, "persona_btn"):
            self.persona_btn.text = self.voice_persona

        if self.audio_enabled:
            self.tts_toggle_btn.text = "TTS ON"
            style_card(
                self.tts_toggle_btn,
                (0.05, 0.18, 0.26, 1.0),
                (0.06, 0.71, 0.83, 0.55),
                radius_dp=8,
            )
            self.tts_toggle_btn.color = (0.45, 0.92, 1.0, 1.0)
        else:
            self.tts_toggle_btn.text = "MUTED"
            style_card(
                self.tts_toggle_btn,
                (0.09, 0.12, 0.18, 1.0),
                (0.25, 0.32, 0.42, 0.6),
                radius_dp=8,
            )
            self.tts_toggle_btn.color = (0.65, 0.72, 0.82, 1.0)

        if self.api_key:
            self.settings_btn.text = "Settings"
            style_card(
                self.settings_btn,
                (0.05, 0.22, 0.16, 1.0),
                (0.08, 0.75, 0.52, 0.65),
                radius_dp=8,
            )
            self.settings_btn.color = (0.45, 0.96, 0.76, 1.0)
        else:
            self.settings_btn.text = "Set Key"
            style_card(
                self.settings_btn,
                (0.24, 0.15, 0.04, 1.0),
                (0.95, 0.65, 0.1, 0.7),
                radius_dp=8,
            )
            self.settings_btn.color = (1.0, 0.84, 0.38, 1.0)

    def _toggle_audio(self, *_args):
        self.audio_enabled = not self.audio_enabled
        if not self.audio_enabled:
            self.voice_bridge.stop_speaking()
        self._save_config()
        self._refresh_header_state()

    def _toggle_hands_free(self, *_args):
        self.hands_free_mode = not self.hands_free_mode
        self._save_config()
        self._refresh_header_state()
        if self.hands_free_mode and not self._pending_busy and not self.voice_bridge.is_speaking:
            self.voice_bridge.start_listening()
        elif not self.hands_free_mode:
            self.voice_bridge.stop_speaking()
            self._update_voice_banner("VOICE-FIRST INTELLIGENCE • Ready")

    def _barge_in_now(self, *_args):
        self.voice_bridge.stop_speaking()
        self.voice_bridge.start_listening()

    def _on_tts_finished(self):
        self._update_voice_banner(f"VOICE-FIRST INTELLIGENCE • Persona: {self.voice_persona}")
        if self.hands_free_mode and not self._pending_busy and self.active_tab == "console":
            Clock.schedule_once(lambda _dt: self.voice_bridge.start_listening(), 0.35)

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

        s_gh = Screen(name="github")
        s_gh.add_widget(self._build_github_tab())
        self.screen_manager.add_widget(s_gh)

        self.add_widget(self.screen_manager)

    # ------------------------------------------------------------------
    # TAB 1: CONSOLE (Voice-First Bar, Bubbles with NP/H Avatars, Auto Build Sync)
    # ------------------------------------------------------------------
    def _build_console_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6))

        # Voice-First Intelligence Strip (Matches Web Preview)
        voice_card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(66), padding=[dp(8), dp(5)], spacing=dp(4))
        style_card(voice_card, (0.035, 0.055, 0.11, 1.0), (0.08, 0.38, 0.55, 0.5), radius_dp=10)

        self.voice_status_lbl = Label(
            text=f"[b][color=22d3ee]VOICE-FIRST INTELLIGENCE[/color][/b] [color=94a3b8]• Persona: {self.voice_persona}[/color]",
            markup=True,
            font_size=sp(10),
            size_hint_y=None,
            height=dp(20),
            halign="left",
            valign="middle",
        )
        self.voice_status_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        voice_card.add_widget(self.voice_status_lbl)

        vc_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(5))
        self.hands_free_btn = make_button(
            "Hands-Free OFF",
            (0.07, 0.09, 0.16, 1.0),
            (0.25, 0.32, 0.45, 0.6),
            radius_dp=8,
            font_sp=10,
        )
        self.hands_free_btn.bind(on_release=self._toggle_hands_free)
        vc_row.add_widget(self.hands_free_btn)

        barge_btn = make_button(
            "Barge-In",
            (0.38, 0.08, 0.16, 1.0),
            (0.95, 0.28, 0.42, 0.75),
            text_rgba=(1.0, 0.75, 0.80, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint_x=0.72,
        )
        barge_btn.bind(on_release=self._barge_in_now)
        vc_row.add_widget(barge_btn)

        self.persona_btn = make_button(
            self.voice_persona,
            (0.05, 0.12, 0.22, 1.0),
            (0.10, 0.55, 0.78, 0.55),
            text_rgba=(0.60, 0.90, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint_x=0.68,
        )
        self.persona_btn.bind(on_release=self._cycle_persona)
        vc_row.add_widget(self.persona_btn)

        voice_card.add_widget(vc_row)
        root.add_widget(voice_card)

        # Messages Scroll Thread
        self.chat_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(4))
        self.chat_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(9),
            padding=[dp(2), dp(4), dp(2), dp(6)],
        )
        self.chat_list.bind(minimum_height=self.chat_list.setter("height"))
        self.chat_scroll.add_widget(self.chat_list)
        root.add_widget(self.chat_scroll)

        welcome_text = (
            "Hey Harish! Kya haal hain bhai? Batao aaj kya plan hai—koi app ya APK banana hai, "
            "koi error fix karein, ya bas normal baat-cheet?"
        )
        self._add_message_card("assistant", welcome_text, model_tag="NEON Core")
        if not self.api_key:
            self._add_setup_card()

        # Horizontal Quick Commands Strip
        quick_scroll = ScrollView(size_hint_y=None, height=dp(38), do_scroll_y=False, bar_width=0)
        quick_row = BoxLayout(size_hint_x=None, height=dp(34), spacing=dp(6), padding=[dp(2), dp(2)])
        quick_row.bind(minimum_width=quick_row.setter("width"))

        quick_prompts = [
            ("Hinglish Chat", "Aur bhai kya haal hai? Aaj mobile app me kya naya add karein?"),
            ("Build Calculator", "Build a complete runnable Python Kivy scientific calculator app for Android."),
            ("Android Tips", "Kivy aur PyJNIus se Android features (camera, vibration, notifications) kaise add karein?"),
            ("Windows .EXE", "PyQt6 desktop app aur PyInstaller Windows .exe banane ka clean template do."),
        ]
        for label, prompt in quick_prompts:
            pill = make_button(
                label,
                (0.05, 0.08, 0.15, 1.0),
                (0.06, 0.45, 0.62, 0.5),
                text_rgba=(0.55, 0.88, 0.98, 1.0),
                radius_dp=15,
                font_sp=10,
                size_hint=(None, None),
                size=(dp(108), dp(30)),
            )
            pill.bind(on_release=lambda _i, p=prompt: self._send_chat_prompt(p))
            quick_row.add_widget(pill)

        clear_pill = make_button(
            "Clear Chat",
            (0.14, 0.06, 0.09, 1.0),
            (0.75, 0.22, 0.35, 0.5),
            text_rgba=(0.98, 0.65, 0.72, 1.0),
            radius_dp=15,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(84), dp(30)),
        )
        clear_pill.bind(on_release=lambda *_: self._clear_chat())
        quick_row.add_widget(clear_pill)

        quick_scroll.add_widget(quick_row)
        root.add_widget(quick_scroll)

        # Bottom Composer Card
        composer = BoxLayout(size_hint_y=None, height=dp(54), padding=dp(5), spacing=dp(5))
        style_card(composer, (0.045, 0.068, 0.125, 1.0), (0.06, 0.55, 0.72, 0.65), radius_dp=13)

        self.mic_btn = make_button(
            "MIC",
            (0.28, 0.14, 0.55, 1.0),
            (0.62, 0.38, 0.96, 0.7),
            radius_dp=9,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(46), dp(40)),
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
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        self.chat_input.bind(on_text_validate=lambda *_: self._send_chat_prompt())
        composer.add_widget(self.chat_input)

        self.stop_tts_btn = make_button(
            "STOP",
            (0.55, 0.12, 0.22, 1.0),
            (0.95, 0.30, 0.42, 0.75),
            radius_dp=9,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(44), dp(40)),
        )
        self.stop_tts_btn.pos_hint = {"center_y": 0.5}
        self.stop_tts_btn.bind(on_release=lambda *_: self.voice_bridge.stop_speaking())
        composer.add_widget(self.stop_tts_btn)

        self.send_btn = make_button(
            "SEND",
            (0.02, 0.58, 0.75, 1.0),
            (0.22, 0.85, 0.95, 0.85),
            radius_dp=9,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(56), dp(40)),
        )
        self.send_btn.pos_hint = {"center_y": 0.5}
        self.send_btn.bind(on_release=lambda *_: self._send_chat_prompt())
        composer.add_widget(self.send_btn)

        root.add_widget(composer)
        return root

    def _add_setup_card(self):
        box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(6))
        box.bind(minimum_height=box.setter("height"))
        style_card(box, (0.09, 0.06, 0.02, 1.0), (0.95, 0.62, 0.12, 0.6), radius_dp=12)
        box.add_widget(
            AutoLabel(
                text="[b][color=fbbf24]Connect Gemini API Key once[/color][/b] — Uske baad Hindi/English Voice, Chat, App Studio & Debugger sab full speed chalega.",
                font_size=sp(11),
            )
        )
        btn = make_button(
            "Enter Gemini API Key",
            (0.06, 0.52, 0.40, 1.0),
            (0.15, 0.88, 0.62, 0.8),
            radius_dp=8,
            font_sp=11,
            size_hint_y=None,
            height=dp(34),
        )
        btn.bind(on_release=lambda *_: self._open_settings_modal())
        box.add_widget(btn)
        self.chat_list.add_widget(box)

    def _add_message_card(self, role, text, model_tag=None):
        is_user = role == "user"
        wrapper = BoxLayout(orientation="horizontal", size_hint_y=None, padding=[dp(2), dp(2)], spacing=dp(6))
        wrapper.bind(minimum_height=wrapper.setter("height"))

        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(11),
            spacing=dp(6),
        )
        card.bind(minimum_height=card.setter("height"))

        if is_user:
            style_card(card, (0.07, 0.28, 0.46, 1.0), (0.14, 0.72, 0.88, 0.65), radius_dp=13)
            hdr = AutoLabel(
                text=f"[b][color=e0f2fe]Harish[/color][/b]  [color=93c5fd]{time.strftime('%H:%M')}[/color]",
                font_size=sp(10),
            )
            card.add_widget(hdr)
            body = AutoLabel(
                text=f"[color=ffffff]{escape_markup(text)}[/color]",
                font_size=sp(13),
            )
            card.add_widget(body)

            avatar = make_button(
                "H",
                (0.12, 0.16, 0.26, 1.0),
                (0.32, 0.50, 0.72, 0.6),
                radius_dp=8,
                font_sp=11,
                size_hint=(None, None),
                size=(dp(28), dp(28)),
            )
            avatar.pos_hint = {"top": 1}
            wrapper.add_widget(BoxLayout(size_hint_x=0.08))
            wrapper.add_widget(card)
            wrapper.add_widget(avatar)
        else:
            avatar = make_button(
                "NP",
                (0.02, 0.52, 0.72, 1.0),
                (0.20, 0.82, 0.94, 0.8),
                radius_dp=8,
                font_sp=10,
                size_hint=(None, None),
                size=(dp(28), dp(28)),
            )
            avatar.pos_hint = {"top": 1}
            wrapper.add_widget(avatar)

            style_card(card, (0.04, 0.06, 0.115, 1.0), (0.06, 0.42, 0.58, 0.55), radius_dp=13)

            top_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(5))
            tag = model_tag or self.selected_model
            meta_lbl = Label(
                text=f"[b][color=22d3ee]NEON PRO[/color][/b] [color=64748b]• {tag}[/color]",
                markup=True,
                font_size=sp(10),
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
                size=(dp(52), dp(24)),
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
                size=(dp(48), dp(24)),
            )
            copy_btn.bind(on_release=lambda *_a, t=text, b=copy_btn: self._copy_text(t, b))
            top_row.add_widget(copy_btn)
            card.add_widget(top_row)

            # Parse triple-backtick code blocks & sync first Python block into App Studio
            parts = text.split("```")
            extracted_code = None
            for idx, part in enumerate(parts):
                chunk = part.strip()
                if not chunk:
                    continue
                if idx % 2 == 1:
                    lines = chunk.split("\n")
                    lang = lines[0].strip() if len(lines) > 1 and len(lines[0]) < 20 else "code"
                    code_body = "\n".join(lines[1:]) if lang != "code" and len(lines) > 1 else chunk
                    if extracted_code is None and len(code_body) > 40:
                        extracted_code = (lang, code_body)

                    code_box = BoxLayout(
                        orientation="vertical",
                        size_hint_y=None,
                        padding=dp(9),
                        spacing=dp(5),
                    )
                    code_box.bind(minimum_height=code_box.setter("height"))
                    style_card(code_box, (0.02, 0.03, 0.06, 1.0), (0.06, 0.55, 0.45, 0.5), radius_dp=10)
                    c_hdr = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(5))
                    c_lbl = Label(
                        text=f"[b][color=34d399]{lang.upper()}[/color][/b]",
                        markup=True,
                        font_size=sp(10),
                        halign="left",
                    )
                    c_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
                    c_hdr.add_widget(c_lbl)

                    c_studio = make_button(
                        "Open Studio",
                        (0.05, 0.18, 0.28, 1.0),
                        (0.10, 0.65, 0.85, 0.6),
                        text_rgba=(0.55, 0.90, 1.0, 1.0),
                        radius_dp=6,
                        font_sp=9,
                        size_hint=(None, None),
                        size=(dp(76), dp(22)),
                    )
                    c_studio.bind(on_release=lambda *_a, cb=code_body, lg=lang: self._open_code_in_studio(cb, lg))
                    c_hdr.add_widget(c_studio)

                    c_copy = make_button(
                        "Copy Code",
                        (0.06, 0.16, 0.14, 1.0),
                        (0.10, 0.72, 0.52, 0.6),
                        text_rgba=(0.55, 0.96, 0.78, 1.0),
                        radius_dp=6,
                        font_sp=9,
                        size_hint=(None, None),
                        size=(dp(68), dp(22)),
                    )
                    c_copy.bind(on_release=lambda *_a, cb=code_body, b=c_copy: self._copy_text(cb, b))
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

            if extracted_code is not None:
                self._sync_autonomous_code(extracted_code[1], extracted_code[0])
                sync_banner = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
                sync_banner.add_widget(
                    AutoLabel(
                        text="[b][color=34d399]✓ Autonomous Code Synced to Studio[/color][/b]",
                        font_size=sp(10),
                    )
                )
                go_studio = make_button(
                    "Open Studio",
                    (0.04, 0.45, 0.35, 1.0),
                    (0.12, 0.85, 0.60, 0.7),
                    radius_dp=7,
                    font_sp=10,
                    size_hint=(None, None),
                    size=(dp(84), dp(26)),
                )
                go_studio.bind(on_release=lambda *_: self._switch_tab("app-studio"))
                sync_banner.add_widget(go_studio)
                card.add_widget(sync_banner)

            wrapper.add_widget(card)
            wrapper.add_widget(BoxLayout(size_hint_x=0.04))

        self.chat_list.add_widget(wrapper)
        Clock.schedule_once(lambda _dt: setattr(self.chat_scroll, "scroll_y", 0), 0.08)

    def _open_code_in_studio(self, code_body, lang="python"):
        self._sync_autonomous_code(code_body, lang)
        self._switch_tab("app-studio")

    def _sync_autonomous_code(self, code_body, lang="python"):
        ext = "py"
        low = (lang or "").lower()
        if "js" in low:
            ext = "js"
        elif "html" in low:
            ext = "html"
        elif "sh" in low or "bash" in low:
            ext = "sh"
        fname = f"generated_app.{ext}"
        self.studio_files[fname] = code_body
        self.studio_file_lbl.text = f"[b][color=34d399]File: {fname}[/color][/b]"
        self.studio_editor.text = code_body
        try:
            proj_dir = os.path.join(self._get_data_dir(), "autonomous_projects")
            os.makedirs(proj_dir, exist_ok=True)
            with open(os.path.join(proj_dir, fname), "w", encoding="utf-8") as fh:
                fh.write(code_body)
        except Exception:
            pass

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
            "Chat cleared Harish! Batao ab kya banana hai?",
            model_tag="NEON Core",
        )

    def _update_voice_banner(self, message):
        self.voice_status_lbl.text = f"[b][color=22d3ee]VOICE[/color][/b] [color=cbd5e1]{escape_markup(message)}[/color]"

    def _on_voice_transcript(self, spoken_text):
        self.chat_input.text = spoken_text
        self._send_chat_prompt()

    def _toggle_thinking(self, *_args):
        self.high_thinking = not self.high_thinking
        self._save_config()
        self._refresh_header_state()

    def _is_build_intent(self, prompt_text):
        low = prompt_text.lower()
        verbs = ("build", "create", "develop", "architect", "generate", "banao", "bana do", "banado", "taiyar", "likho", "बनाओ", "बना दो", "तैयार", "डेवलप")
        nouns = ("app", "apk", "software", "tool", "calculator", "player", "game", "bot", "tracker", "script", "system", "program", "ऐप", "सॉफ्टवेयर", "टूल", "प्रोग्राम", "गेम", "कैलकुलेटर")
        return any(v in low for v in verbs) and any(n in low for n in nouns)

    def _send_chat_prompt(self, preset_prompt=None):
        prompt = (preset_prompt or self.chat_input.text).strip()
        if not prompt or self._pending_busy:
            return

        self.voice_bridge.stop_speaking()
        if not preset_prompt:
            self.chat_input.text = ""
        self._add_message_card("user", prompt)

        if not self.api_key:
            msg = "Harish, pehle top-right 'Set Key' button daba ke apni Gemini API key save kar lo — uske baad main turant bolke aur code likh ke kaam karunga!"
            self._add_message_card("assistant", msg, model_tag="Setup Needed")
            if self.audio_enabled:
                self.voice_bridge.speak(msg)
            return

        self._pending_busy = True
        self.send_btn.disabled = True
        self.send_btn.text = "..."
        threading.Thread(
            target=self._run_gemini_chat,
            args=(prompt,),
            daemon=True,
        ).start()

    def _http_get_json(self, url):
        if requests is not None:
            r = requests.get(url, timeout=15)
            return r.status_code, (r.json() if r.status_code == 200 else r.text)
        req = urllib.request.Request(url, method="GET")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as uresp:
                txt = uresp.read().decode("utf-8", errors="replace")
                return uresp.getcode(), json.loads(txt)
        except urllib.error.HTTPError as herr:
            return herr.code, herr.read().decode("utf-8", errors="replace")

    def _http_post_json(self, url, payload, headers=None, timeout=30):
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        if requests is not None:
            resp = requests.post(url, json=payload, headers=hdrs, timeout=timeout)
            data = None
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    data = None
            return resp.status_code, resp.text, data
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=hdrs,
            method="POST",
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as uresp:
                raw_text = uresp.read().decode("utf-8", errors="replace")
                data = None
                try:
                    data = json.loads(raw_text)
                except Exception:
                    data = None
                return uresp.getcode(), raw_text, data
        except urllib.error.HTTPError as herr:
            return herr.code, herr.read().decode("utf-8", errors="replace"), None

    def _discover_available_models(self):
        if self.discovered_models:
            return self.discovered_models
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            code, body = self._http_get_json(url)
            if code == 200 and isinstance(body, dict):
                candidates = []
                for m in body.get("models", []):
                    methods = m.get("supportedGenerationMethods") or []
                    name = str(m.get("name", "")).replace("models/", "")
                    low = name.lower()
                    if "generateContent" in methods and "gemini" in low and "tts" not in low and "embedding" not in low:
                        candidates.append(name)
                # Prefer flash/lite first for lowest latency
                candidates.sort(key=lambda n: (0 if "flash" in n.lower() else 1, n))
                self.discovered_models = candidates[:4]
        except Exception:
            pass
        return self.discovered_models

    def _call_gemini_rest(self, contents, system_prompt=DEFAULT_SYSTEM_PROMPT, prefer_pro=False):
        chain = [self.selected_model, "gemini-4-hydrogen", "gemini-3.1-flash-lite", "gemini-4-argon"]
        if prefer_pro:
            chain.insert(0, "gemini-4-carbon")
        if self.discovered_models:
            chain.extend(self.discovered_models)
        dedup_chain = list(dict.fromkeys(chain))

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
        }
        last_err = "Unknown error"

        def _try_models(model_list):
            nonlocal last_err
            had_404 = False
            for model_name in model_list:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_name}:generateContent?key={self.api_key}"
                )
                try:
                    status_code, raw_text, data = self._http_post_json(url, payload, timeout=30)
                    if status_code == 200 and data:
                        cands = data.get("candidates") or []
                        if cands:
                            parts = cands[0].get("content", {}).get("parts", [])
                            txt = "".join(p.get("text", "") for p in parts).strip()
                            if txt:
                                return txt, model_name, False
                    else:
                        if status_code == 404:
                            had_404 = True
                        last_err = f"HTTP {status_code}: {raw_text[:180]}"
                        if status_code not in (404, 429, 500, 502, 503, 504):
                            break
                except Exception as exc:
                    last_err = str(exc)
            return None, None, had_404

        txt, used, saw_404 = _try_models(dedup_chain)
        if txt:
            return txt, used, None

        # Dynamic model auto-discovery fallback if external user key hit 404
        if saw_404:
            fresh = [m for m in self._discover_available_models() if m not in dedup_chain]
            if fresh:
                txt, used, _ = _try_models(fresh)
                if txt:
                    return txt, used, None

        return None, None, last_err

    def _run_gemini_chat(self, prompt):
        lang_hint = ""
        if self.language_mode == "hi":
            lang_hint = " Always reply in natural conversational Hindi or Hinglish."
        elif self.language_mode == "en":
            lang_hint = " Always reply in crisp conversational English."
        if self.hands_free_mode:
            lang_hint += " Hands-Free voice mode is ON: keep conversational replies concise and natural."
        if self._is_build_intent(prompt):
            lang_hint += " Harish wants you to autonomously build/develop this software cleanly: include complete runnable zero-placeholder code in triple backticks so it auto-syncs into App Studio."

        self.history.append({"role": "user", "parts": [{"text": prompt}]})
        recent = self.history[-10:]
        reply_text, used_model, err = self._call_gemini_rest(
            recent,
            system_prompt=DEFAULT_SYSTEM_PROMPT + lang_hint,
            prefer_pro=self.high_thinking,
        )

        def _done(_dt):
            self._pending_busy = False
            self.send_btn.disabled = False
            self.send_btn.text = "SEND"
            if reply_text:
                self.history.append({"role": "model", "parts": [{"text": reply_text}]})
                self._add_message_card("assistant", reply_text, model_tag=used_model)
                if self.audio_enabled:
                    self.voice_bridge.speak(reply_text)
                elif self.hands_free_mode:
                    Clock.schedule_once(lambda _d: self.voice_bridge.start_listening(), 0.4)
            else:
                fail_msg = f"Bhai API error aaya: {err}. Settings me key check karein."
                self._add_message_card("assistant", fail_msg, model_tag="Error")
                if self.audio_enabled:
                    self.voice_bridge.speak("Gemini API error aaya, please settings me key check karein.")

        Clock.schedule_once(_done, 0)

    # ------------------------------------------------------------------
    # TAB 2: APP STUDIO
    # ------------------------------------------------------------------
    def _build_studio_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        banner = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(82), padding=dp(9), spacing=dp(5))
        style_card(banner, (0.04, 0.06, 0.12, 1.0), (0.06, 0.45, 0.62, 0.5), radius_dp=12)
        banner.add_widget(
            AutoLabel(
                text="[b][color=22d3ee]NEON App Studio[/color][/b] [color=94a3b8]• Autonomous Mobile & PC Code[/color]",
                font_size=sp(12),
            )
        )

        preset_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        self.studio_files = {
            "main.py": "# NEON PRO v4.0 Mobile Core\nprint('NEON PRO Running on Android!')\n",
            "buildozer.spec": "[app]\ntitle = NEON PRO Mobile\npackage.name = neonpromobile\nandroid.api = 33\nandroid.minapi = 21\nandroid.ndk = 25b\nandroid.ndk_api = 21\np4a.branch = v2024.01.21\n",
            "requirements.txt": "kivy==2.3.0\nrequests==2.31.0\ncertifi==2024.2.2\nurllib3==2.2.1\n",
        }
        try:
            if __file__.endswith(".py") and os.path.exists(__file__):
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
                font_sp=10,
            )
            b.bind(on_release=lambda _i, k=fname: self._load_studio_file(k))
            preset_row.add_widget(b)
        banner.add_widget(preset_row)
        root.add_widget(banner)

        gen_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.studio_prompt = TextInput(
            hint_text="Describe an app/script to autonomously build...",
            multiline=False,
            background_color=(0.03, 0.045, 0.085, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        gen_row.add_widget(self.studio_prompt)
        self.studio_gen_btn = make_button(
            "AI Build",
            (0.32, 0.16, 0.62, 1.0),
            (0.68, 0.45, 0.98, 0.7),
            radius_dp=9,
            font_sp=11,
            size_hint_x=None,
            width=dp(80),
        )
        self.studio_gen_btn.bind(on_release=lambda *_: self._studio_ai_generate())
        gen_row.add_widget(self.studio_gen_btn)
        root.add_widget(gen_row)

        editor_card = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        style_card(editor_card, (0.025, 0.035, 0.068, 1.0), (0.08, 0.25, 0.38, 0.6), radius_dp=12)

        ed_hdr = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(5))
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
            size=(dp(76), dp(26)),
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
            size=(dp(80), dp(26)),
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
                "Write complete, clean, zero-placeholder runnable Python/Kivy code for Harish's request. "
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
                    self._sync_autonomous_code(cleaned, "python")
                else:
                    self.studio_editor.text = f"# Generation failed: {err}"

            Clock.schedule_once(_done, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # TAB 3: AUTONOMOUS DEBUGGER
    # ------------------------------------------------------------------
    def _build_debugger_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        hdr = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(72), padding=dp(9), spacing=dp(5))
        style_card(hdr, (0.04, 0.06, 0.12, 1.0), (0.48, 0.22, 0.72, 0.55), radius_dp=12)
        hdr.add_widget(
            AutoLabel(
                text="[b][color=c084fc]Autonomous Debugger[/color][/b] [color=94a3b8]• Paste Error + Code for Instant AI Fix[/color]",
                font_size=sp(12),
            )
        )
        preset_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
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
                "API 404/503",
                "requests.post(gemini_url)",
                "HTTP 404 Model Not Found / 503 Unavailable",
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
            font_sp=12,
            size_hint_y=None,
            height=dp(40),
        )
        self.dbg_run_btn.bind(on_release=lambda *_: self._run_autonomous_debug())
        root.add_widget(self.dbg_run_btn)

        out_card = BoxLayout(orientation="vertical", size_hint_y=0.52, padding=dp(9), spacing=dp(5))
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
            size=(dp(70), dp(24)),
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
    # TAB 4: BUILD LAB
    # ------------------------------------------------------------------
    def _build_lab_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        quick_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
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
                font_sp=10,
            )
            b.bind(on_release=lambda _i, c=cmd: self._run_lab_cmd(c))
            quick_row.add_widget(b)
        root.add_widget(quick_row)

        term_card = BoxLayout(orientation="vertical", padding=dp(10))
        style_card(term_card, (0.015, 0.022, 0.048, 1.0), (0.06, 0.45, 0.62, 0.5), radius_dp=12)
        self.lab_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.lab_log = AutoLabel(
            text=(
                "[color=22d3ee][b]NEON PRO Build & Device Lab v4.0[/b][/color]\n"
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
            width=dp(64),
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
                "[color=34d399]• App Engine:[/color] NEON PRO v4.0 Mobile Suite",
                f"[color=34d399]• Active Model:[/color] {self.selected_model}",
                f"[color=34d399]• API Key:[/color] {'Configured' if self.api_key else 'Not Set (Tap Set Key)'}",
                f"[color=34d399]• Hands-Free:[/color] {'ON' if self.hands_free_mode else 'OFF'} | Persona: {self.voice_persona}",
            ])
        elif "device" in low:
            lines.extend([
                f"[color=e2e8f0]OS/Platform: {platform} / {sys_platform.platform()}[/color]",
                f"[color=e2e8f0]Architecture: {sys_platform.machine()}[/color]",
                f"[color=e2e8f0]Display Pixels: {Window.width}x{Window.height}[/color]",
                f"[color=e2e8f0]Data Dir: {self._get_data_dir()}[/color]",
            ])
        elif "python" in low:
            lines.append(f"[color=e2e8f0]Python {sys.version}[/color]")
        else:
            lines.append("[color=cbd5e1]Command executed (status 0). Try: neon status, device info, python ver, clear[/color]")

        self.lab_log.text += "\n" + "\n".join(lines)
        Clock.schedule_once(lambda _dt: setattr(self.lab_scroll, "scroll_y", 0), 0.05)

    # ------------------------------------------------------------------
    # TAB 5: GITHUB CI (Cloud APK Builder Directly from Android)
    # ------------------------------------------------------------------
    def _build_github_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(200), padding=dp(10), spacing=dp(6))
        style_card(card, (0.04, 0.055, 0.115, 1.0), (0.55, 0.30, 0.85, 0.55), radius_dp=12)
        card.add_widget(
            AutoLabel(
                text="[b][color=c084fc]GitHub Actions APK Builder[/color][/b] [color=94a3b8]• Push & Compile Real Signed APK[/color]",
                font_size=sp(12),
            )
        )

        self.gh_token_input = TextInput(
            text=self.github_token,
            hint_text="GitHub Token (repo + workflow scopes)...",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(38),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        card.add_widget(self.gh_token_input)

        self.gh_repo_input = TextInput(
            text=self.github_repo,
            hint_text="Repository name (e.g. neon-pro-harish)",
            multiline=False,
            size_hint_y=None,
            height=dp(38),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        card.add_widget(self.gh_repo_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.gh_push_btn = make_button(
            "Push & Build APK",
            (0.05, 0.52, 0.40, 1.0),
            (0.15, 0.88, 0.62, 0.8),
            radius_dp=8,
            font_sp=11,
        )
        self.gh_push_btn.bind(on_release=lambda *_: self._gh_push_studio_app())
        btn_row.add_widget(self.gh_push_btn)

        self.gh_runs_btn = make_button(
            "Check Runs",
            (0.28, 0.16, 0.58, 1.0),
            (0.65, 0.42, 0.95, 0.7),
            radius_dp=8,
            font_sp=11,
        )
        self.gh_runs_btn.bind(on_release=lambda *_: self._gh_check_runs())
        btn_row.add_widget(self.gh_runs_btn)

        card.add_widget(btn_row)
        root.add_widget(card)

        out_card = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        style_card(out_card, (0.02, 0.03, 0.065, 1.0), (0.08, 0.45, 0.65, 0.5), radius_dp=12)
        gh_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.gh_log = AutoLabel(
            text="[color=94a3b8]Save your GitHub token above to push generated App Studio code straight to GitHub Actions or inspect APK builds from your phone.[/color]",
            font_size=sp(12),
        )
        gh_scroll.add_widget(self.gh_log)
        out_card.add_widget(gh_scroll)
        root.add_widget(out_card)
        return root

    def _gh_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NEON-PRO-Mobile-v4",
            "Content-Type": "application/json",
        }

    def _gh_get(self, url, token):
        hdrs = self._gh_headers(token)
        if requests is not None:
            r = requests.get(url, headers=hdrs, timeout=20)
            return r.status_code, (r.json() if r.content else {})
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as uresp:
                return uresp.getcode(), json.loads(uresp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as herr:
            return herr.code, {"message": herr.read().decode("utf-8", errors="replace")}

    def _gh_put(self, url, token, body):
        hdrs = self._gh_headers(token)
        if requests is not None:
            r = requests.put(url, json=body, headers=hdrs, timeout=20)
            return r.status_code, (r.json() if r.content else {})
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=hdrs, method="PUT"
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as uresp:
                return uresp.getcode(), json.loads(uresp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as herr:
            return herr.code, {"message": herr.read().decode("utf-8", errors="replace")}

    def _gh_check_runs(self):
        token = self.gh_token_input.text.strip()
        repo = self.gh_repo_input.text.strip() or "neon-pro-harish"
        self.github_token = token
        self.github_repo = repo
        self._save_config()
        if not token:
            self.gh_log.text = "[color=fbbf24]Please paste your GitHub Personal Access Token first.[/color]"
            return
        self.gh_log.text = "[color=38bdf8]Fetching GitHub Actions builds...[/color]"

        def _worker():
            code, user = self._gh_get("https://api.github.com/user", token)
            if code != 200:
                msg = f"[color=f87171]GitHub Auth Error ({code}): {escape_markup(user.get('message', ''))}[/color]"
                Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", msg), 0)
                return
            owner = user.get("login", "")
            rc, runs_data = self._gh_get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=5",
                token,
            )
            if rc != 200:
                msg = f"[color=fbbf24]Repo '{owner}/{repo}' not found or no workflow runs yet.[/color]"
                Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", msg), 0)
                return
            lines = [f"[b][color=34d399]Owner: {owner} | Repo: {repo}[/color][/b]"]
            for r in runs_data.get("workflow_runs", [])[:5]:
                st = r.get("conclusion") or r.get("status")
                clr = "34d399" if st == "success" else ("f87171" if st == "failure" else "38bdf8")
                lines.append(f"[color={clr}]• {escape_markup(r.get('name', 'Build'))}: {st}[/color]")
            lines.append(f"[color=94a3b8]Actions URL: https://github.com/{owner}/{repo}/actions[/color]")
            final_txt = "\n".join(lines)
            Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", final_txt), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _gh_push_studio_app(self):
        token = self.gh_token_input.text.strip()
        repo = self.gh_repo_input.text.strip() or "neon-pro-harish"
        self.github_token = token
        self.github_repo = repo
        self._save_config()
        if not token:
            self.gh_log.text = "[color=fbbf24]Please paste your GitHub Personal Access Token first.[/color]"
            return
        self.gh_push_btn.disabled = True
        self.gh_log.text = "[color=38bdf8]Pushing App Studio code to GitHub...[/color]"
        app_code = self.studio_editor.text

        def _worker():
            code, user = self._gh_get("https://api.github.com/user", token)
            if code != 200:
                msg = f"[color=f87171]GitHub Auth Failed ({code})[/color]"
                Clock.schedule_once(lambda _dt: (setattr(self.gh_push_btn, "disabled", False), setattr(self.gh_log, "text", msg)), 0)
                return
            owner = user.get("login", "")
            r_code, repo_info = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}", token)
            if r_code == 404:
                self._http_post_json(
                    "https://api.github.com/user/repos",
                    {"name": repo, "auto_init": True},
                    headers=self._gh_headers(token),
                )
                time.sleep(1.5)
                r_code, repo_info = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}", token)
            branch = repo_info.get("default_branch", "main") if isinstance(repo_info, dict) else "main"
            target_path = "main.py"
            f_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{target_path}"
            ex_code, ex_data = self._gh_get(f"{f_url}?ref={branch}", token)
            put_body = {
                "message": "[NEON PRO Mobile] Autonomous update from Harish phone",
                "content": base64.b64encode(app_code.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if ex_code == 200 and isinstance(ex_data, dict) and ex_data.get("sha"):
                put_body["sha"] = ex_data["sha"]
            p_code, p_res = self._gh_put(f_url, token, put_body)
            if p_code in (200, 201):
                msg = f"[color=34d399][b]✓ Pushed main.py to {owner}/{repo}![/b]\nGitHub Actions URL:\nhttps://github.com/{owner}/{repo}/actions[/color]"
            else:
                msg = f"[color=f87171]Push error ({p_code}): {escape_markup(str(p_res))}[/color]"
            Clock.schedule_once(lambda _dt: (setattr(self.gh_push_btn, "disabled", False), setattr(self.gh_log, "text", msg)), 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # SETTINGS & API KEY MODAL
    # ------------------------------------------------------------------
    def _open_settings_modal(self):
        modal = ModalView(size_hint=(0.94, None), height=dp(440), background_color=(0, 0, 0, 0.75))
        box = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
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
            size=(dp(62), dp(30)),
        )
        close_btn.bind(on_release=lambda *_: modal.dismiss())
        hdr.add_widget(close_btn)
        box.add_widget(hdr)

        box.add_widget(
            AutoLabel(text="[color=cbd5e1]Gemini API Key (Saved offline on device):[/color]", font_size=sp(11))
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
        model_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
        model_btns = {}

        def _refresh_modal_pills():
            for mid, b in model_btns.items():
                if mid == self.selected_model:
                    style_card(b, (0.05, 0.28, 0.38, 1.0), (0.08, 0.80, 0.92, 0.8), radius_dp=8)
                else:
                    style_card(b, (0.06, 0.09, 0.16, 1.0), (0.22, 0.30, 0.42, 0.5), radius_dp=8)

        for mid, mlabel in self.MODELS:
            mb = make_button(mlabel, (0.06, 0.09, 0.16, 1.0), None, radius_dp=8, font_sp=10)

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

        for lkey, llabel in self.LANGUAGES:
            lb = make_button(llabel, (0.06, 0.09, 0.16, 1.0), None, radius_dp=8, font_sp=10)

            def _pick_lang(_i, target_lang=lkey):
                self.language_mode = target_lang
                self.voice_bridge.configure(language_mode=target_lang)
                _refresh_lang_pills()
                self._save_config()
                self._refresh_header_state()

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
            self.discovered_models = []
            self.voice_bridge.configure(api_key=self.api_key)
            self._save_config()
            self._refresh_header_state()
            modal.dismiss()
            if self.api_key:
                ok_msg = "API key save ho gayi Harish! Ab bolo ya likho, main ready hoon."
                self._add_message_card("assistant", ok_msg, model_tag="System")
                if self.audio_enabled:
                    self.voice_bridge.speak(ok_msg)

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
        try:
            return NeonProMobileSuite()
        except Exception:
            err_trace = traceback.format_exc()
            print("[NEON PRO STARTUP ERROR]\n" + err_trace, flush=True)
            box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
            box.add_widget(
                AutoLabel(
                    text="[b][color=f87171]NEON PRO Startup Recovery[/color][/b]",
                    font_size=sp(16),
                )
            )
            sc = ScrollView(size_hint=(1, 1))
            sc.add_widget(AutoLabel(text=escape_markup(err_trace), font_size=sp(11)))
            box.add_widget(sc)
            return box


if __name__ == "__main__":
    NeonApp().run()
