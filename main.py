"""
NEON PRO - Autonomous Android Mobile & Desktop Application
Architected for: Harish
Features:
  - Sleek cyber-dark Kivy UI (Android + Windows + Linux + Termux compatible)
  - Direct Gemini REST API integration with automatic model failover
  - Native Android Voice Input & Indian-accent TTS via PyJNIus
  - Instant Barge-In (tap Stop/Mic to silence TTS immediately)
  - Termux:API voice fallback when running inside Termux
"""
import json
import os
import shutil
import subprocess
import threading
import certifi
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

# Fix SSL certificate bundle path on Android
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# Sleek cyber-dark mobile palette
Window.clearcolor = (0.02, 0.03, 0.06, 1.0)

CONFIG_FILE = "neon_pro_config.json"
DEFAULT_SYSTEM_PROMPT = (
    "You are NEON PRO, an elite bilingual (Hindi/English/Hinglish) AI assistant "
    "and software developer built for Harish. Respond concisely, naturally, and accurately."
)


class AndroidVoiceBridge:
    """Handles native Android TTS + Voice Recognition via PyJNIus or Termux:API."""

    def __init__(self, log_callback, transcript_callback):
        self.log = log_callback
        self.on_transcript = transcript_callback
        self.tts = None
        self.is_speaking = False
        self.speech_req_code = 9042
        self._android_ready = False

        if platform == "android":
            Clock.schedule_once(lambda dt: self._init_android_bridge(), 0.5)

    def _init_android_bridge(self):
        try:
            from android.permissions import Permission, request_permissions
            from android import activity
            from jnius import autoclass

            request_permissions([
                Permission.INTERNET,
                Permission.RECORD_AUDIO,
            ])

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
            self.log("[color=10b981]>> Native Android PyJNIus Voice & TTS ready.[/color]")
        except Exception as exc:
            self.log(f"[color=f59e0b]>> Android native bridge note: {exc}[/color]")

    def _on_activity_result(self, request_code, result_code, intent):
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
            Clock.schedule_once(
                lambda dt: self.log(f"[color=ef4444]>> Voice parse error: {exc}[/color]"),
                0,
            )

    def stop_speaking(self):
        """Instant Barge-In: halt TTS immediately."""
        self.is_speaking = False
        if self.tts is not None:
            try:
                self.tts.stop()
            except Exception:
                pass

    def speak(self, text):
        if not text:
            return
        clean = text.replace("*", "").replace("#", "").replace("`", "")[:450]
        self.stop_speaking()
        self.is_speaking = True

        if platform == "android" and self.tts is not None:
            try:
                from jnius import autoclass

                TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                # Switch to Hindi locale automatically if Devanagari characters present
                if any("\u0900" <= ch <= "\u097f" for ch in clean):
                    self.tts.setLanguage(self._Locale("hi", "IN"))
                else:
                    self.tts.setLanguage(self._Locale("en", "IN"))
                self.tts.speak(clean, TextToSpeech.QUEUE_FLUSH, None, "neon_tts")
                return
            except Exception:
                pass

        # Termux:API fallback
        if shutil.which("termux-tts-speak"):
            threading.Thread(
                target=lambda: subprocess.run(
                    ["termux-tts-speak", clean],
                    check=False,
                ),
                daemon=True,
            ).start()

    def start_listening(self):
        # Barge-In: stop TTS immediately when Harish speaks
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
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                intent.putExtra(
                    RecognizerIntent.EXTRA_PROMPT, "Speak to NEON PRO, Harish..."
                )
                self._activity.startActivityForResult(intent, self.speech_req_code)
                return
            except Exception as exc:
                self.log(f"[color=f59e0b]>> Mic launch failed: {exc}[/color]")

        # Termux:API fallback
        if shutil.which("termux-speech-to-text"):
            self.log("[color=06b6d4]>> Listening via Termux:API...[/color]")

            def _listen_termux():
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
                    Clock.schedule_once(
                        lambda dt: self.log(f"[color=ef4444]>> Termux mic error: {err}[/color]"),
                        0,
                    )

            threading.Thread(target=_listen_termux, daemon=True).start()
        else:
            self.log(
                "[color=f59e0b]>> Mic input requires Android APK (PyJNIus) or Termux:API. Type below![/color]"
            )


class NeonMobileUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=16, spacing=10, **kwargs)
        self.api_key = self._load_api_key()
        self.history = []

        # Header
        self.header = Label(
            text="[b]NEON PRO[/b] [color=06b6d4]MOBILE[/color]",
            markup=True,
            font_size="22sp",
            size_hint_y=None,
            height=44,
            color=(0.95, 0.98, 1.0, 1.0),
        )
        self.add_widget(self.header)

        self.sub_label = Label(
            text="Autonomous Gemini AI & Voice Cockpit for Harish",
            font_size="12sp",
            size_hint_y=None,
            height=22,
            color=(0.5, 0.65, 0.8, 1.0),
        )
        self.add_widget(self.sub_label)

        # Gemini API Key bar (saved locally on device)
        key_row = BoxLayout(size_hint_y=None, height=40, spacing=8)
        self.key_input = TextInput(
            text=self.api_key,
            hint_text="Paste GEMINI_API_KEY (saved locally on phone)...",
            password=True,
            multiline=False,
            background_color=(0.06, 0.09, 0.16, 1.0),
            foreground_color=(0.9, 0.95, 1.0, 1.0),
            cursor_color=(0.02, 0.71, 0.83, 1.0),
            padding=[10, 10, 10, 10],
            font_size="12sp",
        )
        key_row.add_widget(self.key_input)

        save_key_btn = Button(
            text="SAVE KEY",
            size_hint_x=None,
            width=95,
            background_normal="",
            background_color=(0.08, 0.25, 0.35, 1.0),
            color=(0.2, 0.9, 1.0, 1.0),
            bold=True,
            font_size="12sp",
        )
        save_key_btn.bind(on_release=self.save_api_key)
        key_row.add_widget(save_key_btn)
        self.add_widget(key_row)

        # Output Scroll Terminal
        self.scroll = ScrollView(size_hint=(1, 1))
        self.log_label = Label(
            text=(
                "[color=10b981]>> NEON PRO Core Online. Welcome, Harish.[/color]\n"
                "[color=94a3b8]>> Add your Gemini API key above or speak/type a command below.[/color]\n"
            ),
            markup=True,
            font_size="13sp",
            size_hint_y=None,
            halign="left",
            valign="top",
            color=(0.9, 0.95, 1.0, 1.0),
        )
        self.log_label.bind(texture_size=self._update_log_height)
        self.scroll.add_widget(self.log_label)
        self.add_widget(self.scroll)

        # Prompt Input
        self.input_field = TextInput(
            hint_text="Type message or command in Hindi / English...",
            multiline=False,
            size_hint_y=None,
            height=46,
            background_color=(0.06, 0.09, 0.16, 1.0),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0.02, 0.71, 0.83, 1.0),
            padding=[12, 12, 12, 12],
        )
        self.input_field.bind(on_text_validate=lambda _: self.send_prompt())
        self.add_widget(self.input_field)

        # Action Buttons
        btn_row = BoxLayout(size_hint_y=None, height=46, spacing=8)

        self.send_btn = Button(
            text="SEND",
            background_normal="",
            background_color=(0.02, 0.71, 0.83, 1.0),
            color=(1, 1, 1, 1),
            bold=True,
        )
        self.send_btn.bind(on_release=lambda _: self.send_prompt())
        btn_row.add_widget(self.send_btn)

        self.mic_btn = Button(
            text="VOICE",
            background_normal="",
            background_color=(0.45, 0.25, 0.85, 1.0),
            color=(1, 1, 1, 1),
            bold=True,
        )
        self.mic_btn.bind(on_release=lambda _: self.voice_bridge.start_listening())
        btn_row.add_widget(self.mic_btn)

        self.stop_btn = Button(
            text="STOP TTS",
            background_normal="",
            background_color=(0.75, 0.18, 0.28, 1.0),
            color=(1, 1, 1, 1),
            bold=True,
        )
        self.stop_btn.bind(on_release=lambda _: self.voice_bridge.stop_speaking())
        btn_row.add_widget(self.stop_btn)

        self.add_widget(btn_row)

        self.voice_bridge = AndroidVoiceBridge(
            log_callback=self.append_log,
            transcript_callback=self.on_voice_transcript,
        )

    def _get_config_path(self):
        app = App.get_running_app()
        base_dir = app.user_data_dir if app else "."
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, CONFIG_FILE)

    def _load_api_key(self):
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_key:
            return env_key
        try:
            path = self._get_config_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh).get("api_key", "")
        except Exception:
            pass
        return ""

    def save_api_key(self, _instance):
        self.api_key = self.key_input.text.strip()
        try:
            with open(self._get_config_path(), "w", encoding="utf-8") as fh:
                json.dump({"api_key": self.api_key}, fh)
            self.append_log("[color=10b981]>> API Key saved securely on device.[/color]")
        except Exception as exc:
            self.append_log(f"[color=ef4444]>> Could not save key: {exc}[/color]")

    def _update_log_height(self, instance, size):
        instance.height = max(size[1], self.scroll.height)
        instance.text_size = (instance.width - 12, None)

    def append_log(self, line):
        self.log_label.text += f"\n{line}"
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def on_voice_transcript(self, spoken_text):
        self.input_field.text = spoken_text
        self.send_prompt()

    def send_prompt(self):
        prompt = self.input_field.text.strip()
        if not prompt:
            return

        # Barge-In: silence any active speech immediately when sending a new prompt
        self.voice_bridge.stop_speaking()
        self.input_field.text = ""
        self.append_log(f"[color=38bdf8][b]Harish:[/b][/color] {prompt}")

        active_key = self.key_input.text.strip() or self.api_key
        if not active_key:
            self.append_log(
                "[color=f59e0b]>> Please paste your GEMINI_API_KEY in the top bar first.[/color]"
            )
            return

        self.send_btn.disabled = True
        threading.Thread(
            target=self._query_gemini,
            args=(prompt, active_key),
            daemon=True,
        ).start()

    def _query_gemini(self, prompt, api_key):
        models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        self.history.append({"role": "user", "parts": [{"text": prompt}]})
        recent_history = self.history[-10:]

        payload = {
            "system_instruction": {"parts": [{"text": DEFAULT_SYSTEM_PROMPT}]},
            "contents": recent_history,
        }

        reply_text = None
        last_err = ""

        for model_name in models_to_try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={api_key}"
            )
            try:
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        reply_text = "".join(p.get("text", "") for p in parts).strip()
                        if reply_text:
                            break
                else:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:180]}"
                    if resp.status_code not in (429, 500, 502, 503, 504):
                        break
            except Exception as exc:
                last_err = str(exc)

        def _finish(_dt):
            self.send_btn.disabled = False
            if reply_text:
                self.history.append({"role": "model", "parts": [{"text": reply_text}]})
                safe_text = reply_text.replace("[", "(").replace("]", ")")
                self.append_log(f"[color=10b981][b]NEON PRO:[/b][/color] {safe_text}")
                self.voice_bridge.speak(reply_text)
            else:
                self.append_log(
                    f"[color=ef4444]>> Gemini API Error: {last_err or 'No response'}[/color]"
                )

        Clock.schedule_once(_finish, 0)


class NeonApp(App):
    def build(self):
        self.title = "NEON PRO Mobile"
        return NeonMobileUI()


if __name__ == "__main__":
    NeonApp().run()
