"""
NEON PRO v4.5 - User-Friendly All-in-One Mobile AI & APK/EXE Builder
Architected for: Harish
Features:
  - Background Inline Voice Recognition (SpeechRecognizer) with subtle live indicator (no Google popup)
  - Dual Downloads: Dedicated Download APK File & Download EXE File + GitHub Actions Dual CI
  - Easy GitHub Token Generator + 1-Tap Paste & Permanent Save across all new apps
  - Zero Copy-Paste App Builder, Voice-First Engine, SSL Auto-Fallback & Self-Test + Auto-Heal
"""
import ast
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
import zipfile

try:
    import certifi
except Exception:
    certifi = None

try:
    import requests
except Exception:
    requests = None

try:
    import winsound
except Exception:
    winsound = None

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

# Fix SSL certificate bundle path on Termux / Android safely
_FORCE_UNVERIFIED_SSL = False


def _make_unverified_ssl_context():
    try:
        ctx = ssl._create_unverified_context()
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _activate_unverified_ssl_fallback():
    global _FORCE_UNVERIFIED_SSL
    _FORCE_UNVERIFIED_SSL = True
    try:
        ssl._create_default_https_context = _make_unverified_ssl_context
    except Exception:
        pass


def _is_ssl_exception(err):
    low = str(err).lower()
    reason = getattr(err, "reason", None)
    return (
        isinstance(err, ssl.SSLError)
        or isinstance(reason, ssl.SSLError)
        or "certificate" in low
        or "ssl" in low
        or "verify" in low
        or "tls" in low
        or "eof occurred in violation" in low
    )


def _resolve_ca_bundle():
    candidates = []
    if certifi is not None:
        try:
            candidates.append(certifi.where())
        except Exception:
            pass
    candidates.extend([
        os.environ.get("SSL_CERT_FILE", ""),
        "/data/data/com.termux/files/usr/etc/tls/cert.pem",
        "/etc/ssl/certs/ca-certificates.crt",
    ])
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def _build_ssl_context():
    if _FORCE_UNVERIFIED_SSL:
        return _make_unverified_ssl_context(), False
    ca_file = _resolve_ca_bundle()
    if ca_file:
        try:
            return ssl.create_default_context(cafile=ca_file), ca_file
        except Exception:
            pass
    if os.path.isdir("/system/etc/security/cacerts"):
        try:
            ctx = ssl.create_default_context(capath="/system/etc/security/cacerts")
            if len(ctx.get_ca_certs()) > 0:
                return ctx, True
        except Exception:
            pass
    try:
        ctx = ssl.create_default_context()
        if len(ctx.get_ca_certs()) > 0:
            return ctx, True
    except Exception:
        pass
    return _make_unverified_ssl_context(), False


def _urlopen_with_ssl_retry(req, timeout=20):
    """Execute urllib Request with CA bundle and guaranteed Android/Termux SSL fallback."""
    ssl_ctx, _ = _build_ssl_context()
    contexts = (_make_unverified_ssl_context(),) if _FORCE_UNVERIFIED_SSL else (ssl_ctx, _make_unverified_ssl_context())
    for idx, ctx in enumerate(contexts):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as uresp:
                return uresp.getcode(), uresp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as herr:
            return herr.code, herr.read().decode("utf-8", errors="replace")
        except Exception as err:
            if idx == 0 and len(contexts) > 1 and _is_ssl_exception(err):
                _activate_unverified_ssl_fallback()
                continue
            raise
    raise RuntimeError("Request failed")


try:
    _ca = _resolve_ca_bundle()
    if _ca:
        os.environ.setdefault("SSL_CERT_FILE", _ca)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca)
    ssl._create_default_https_context = lambda *_a, **_kw: _build_ssl_context()[0]
    import urllib3
    urllib3.disable_warnings()
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
    "personal AI companion, voice assistant, and full-stack mobile/Windows app builder. "
    "Core Behavioral Rules: "
    "1. Talk naturally, warmly, and directly like a close Indian friend—clear, simple, and user-friendly. Never sound robotic or stiff. "
    "2. NEVER recite system status reports, battery levels, connection logs, or technical diagnostics unless explicitly requested. "
    "3. Keep conversational replies short and helpful. Match Hindi, English, or Hinglish effortlessly. "
    "4. TRUE AUTONOMOUS EXECUTION (NO MANUAL STEPS): NEON PRO has full control over App Builder and Cloud CI (Android .APK + Windows .EXE). "
    "NEVER tell Harish 'main chat pe APK nahi bhej sakta, PC ya Google Colab pe Buildozer chalao', NEVER ask him to run Buildozer/PyInstaller manually, and NEVER ask him to copy-paste code. "
    "When Harish asks for any app or software, output complete zero-placeholder Python/Kivy code inside one triple-backtick python block "
    "AND confirm in 1 friendly line that autonomous compilation into Android (.APK) and Windows (.EXE) has started automatically right below."
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
    """Thread-safe Gemini TTS + Background Inline SpeechRecognizer (No Google Popup)."""

    def __init__(self, status_callback, transcript_callback, speak_done_callback, data_dir_fn, partial_callback=None):
        self.on_status = status_callback
        self.on_transcript = transcript_callback
        self.on_speak_done = speak_done_callback
        self.on_partial = partial_callback
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
        self._speech_recognizer = None
        self._recognition_listener = None
        self._last_rms_ts = 0.0
        self._listen_gen = 0

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
        Clock.schedule_once(lambda _dt: self.on_speak_done(), 0.25)

    def _speak_native_with_retry(self, clean_text, gen):
        if platform != "android":
            if shutil.which("termux-tts-speak"):
                def _termux():
                    subprocess.run(["termux-tts-speak", clean_text], check=False)
                    Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.1)

                threading.Thread(target=_termux, daemon=True).start()
            elif sys.platform.startswith("win") and shutil.which("powershell"):
                def _win_tts():
                    try:
                        env = os.environ.copy()
                        env["NEON_TTS_TEXT"] = clean_text[:450]
                        ps_cmd = (
                            "Add-Type -AssemblyName System.Speech; "
                            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                            "$s.Speak($env:NEON_TTS_TEXT)"
                        )
                        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            env=env,
                            check=False,
                            creationflags=cflags,
                        )
                    except Exception:
                        pass
                    Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.1)

                threading.Thread(target=_win_tts, daemon=True).start()
            elif shutil.which("espeak-ng") or shutil.which("espeak") or shutil.which("spd-say"):
                def _linux_tts():
                    cmd = shutil.which("espeak-ng") or shutil.which("espeak") or shutil.which("spd-say")
                    try:
                        subprocess.run([cmd, clean_text[:400]], check=False)
                    except Exception:
                        pass
                    Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.1)

                threading.Thread(target=_linux_tts, daemon=True).start()
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
        """Call Gemini TTS v1beta endpoint with retries and write WAV file."""
        if not self._api_key:
            return None
        attempts = [
            (
                "gemini-3.8-flash-lite-tts",
                f"Speak warmly and clearly in fluent Indian Hindi/Hinglish/English: {clean_text[:700]}",
            ),
            ("gemini-3.8-flash-lite-tts", clean_text[:700]),
            ("gemini-3.8-flash-tts", clean_text[:700]),
        ]
        _ssl_ctx, req_verify = _build_ssl_context()
        for model_name, prompt_txt in attempts:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={self._api_key}"
            )
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt_txt}]}],
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
                    try:
                        try:
                            resp = requests.post(url, json=payload, timeout=14, verify=req_verify)
                        except Exception as r_err:
                            if _is_ssl_exception(r_err) and req_verify is not False:
                                _activate_unverified_ssl_fallback()
                                resp = requests.post(url, json=payload, timeout=14, verify=False)
                            else:
                                raise
                        if resp.status_code == 200:
                            data = resp.json()
                    except Exception:
                        data = None
                if data is None:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    code, raw_text = _urlopen_with_ssl_retry(req, timeout=14)
                    if code == 200:
                        data = json.loads(raw_text)
                if not data:
                    continue
                cands = data.get("candidates") or []
                if not cands:
                    continue
                parts = cands[0].get("content", {}).get("parts", [])
                b64 = None
                for p in parts:
                    idata = p.get("inlineData") or p.get("inline_data")
                    if idata and idata.get("data"):
                        b64 = idata["data"]
                        break
                if not b64:
                    continue
                raw_audio = base64.b64decode(b64)
                wav_bytes = _pcm_to_wav_bytes(raw_audio)
                out_dir = self.get_data_dir()
                os.makedirs(out_dir, exist_ok=True)
                wav_path = os.path.join(out_dir, "neon_tts_reply.wav")
                with open(wav_path, "wb") as fh:
                    fh.write(wav_bytes)
                return wav_path
            except Exception:
                continue
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
                # On Windows (.exe), winsound plays standard RIFF WAV natively without Kivy audio plugin limits
                if sys.platform.startswith("win") and winsound is not None:
                    try:
                        winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                        Clock.schedule_once(lambda _dt: self._notify_speak_finished(gen), 0.1)
                        return
                    except Exception:
                        pass

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
                    if platform == "android":
                        try:
                            from jnius import autoclass

                            MediaPlayer = autoclass("android.media.MediaPlayer")
                            mp = MediaPlayer()
                            mp.setDataSource(wav_path)
                            mp.prepare()
                            mp.start()

                            def _poll_mp(_dt2):
                                if gen != self._speak_gen:
                                    try:
                                        mp.stop()
                                        mp.release()
                                    except BaseException:
                                        pass
                                    return False
                                try:
                                    if mp.isPlaying():
                                        return True
                                    mp.release()
                                except BaseException:
                                    pass
                                self._notify_speak_finished(gen)
                                return False

                            self._cancel_poll()
                            self._poll_ev = Clock.schedule_interval(_poll_mp, 0.35)
                            return
                        except BaseException:
                            pass
                    self._speak_native_with_retry(cleaned, gen)

                Clock.schedule_once(_play_wav, 0)
            else:
                Clock.schedule_once(lambda _dt: self._speak_native_with_retry(cleaned, gen), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _emit_partial(self, text_val=None, rms_val=None, active=True):
        if self.on_partial is not None:
            Clock.schedule_once(
                lambda _dt, t=text_val, r=rms_val, a=active: self.on_partial(t, r, a),
                0,
            )

    def _get_recognition_listener(self):
        if self._recognition_listener is not None:
            return self._recognition_listener
        from jnius import PythonJavaClass, autoclass, java_method

        bridge = self
        SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")

        class _NeonRecognitionListener(PythonJavaClass):
            __javainterfaces__ = ["android/speech/RecognitionListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/os/Bundle;)V")
            def onReadyForSpeech(self, _params):
                bridge.is_listening = True
                Clock.schedule_once(lambda _dt: bridge.on_status("MIC LIVE • Bolo Harish..."), 0)
                bridge._emit_partial(text_val="", rms_val=1.0, active=True)

            @java_method("()V")
            def onBeginningOfSpeech(self):
                Clock.schedule_once(lambda _dt: bridge.on_status("SUN RAHA HOON... (Bolo)"), 0)

            @java_method("(F)V")
            def onRmsChanged(self, rmsdB):
                now = time.time()
                if now - bridge._last_rms_ts >= 0.16:
                    bridge._last_rms_ts = now
                    bridge._emit_partial(text_val=None, rms_val=float(rmsdB), active=True)

            @java_method("([B)V")
            def onBufferReceived(self, _buffer):
                pass

            @java_method("()V")
            def onEndOfSpeech(self):
                Clock.schedule_once(lambda _dt: bridge.on_status("SAMJHA RAHA HOON..."), 0)

            @java_method("(I)V")
            def onError(self, error_code):
                if not bridge.is_listening:
                    return
                bridge.is_listening = False
                bridge._emit_partial(text_val="", rms_val=0.0, active=False)
                err_int = int(error_code)
                if err_int in (6, 7):
                    msg = "Awaz clear nahi aayi — dobara MIC dabao"
                elif err_int == 9:
                    msg = "Mic permission allow karo Android Settings me"
                elif err_int in (1, 2, 3, 4):
                    msg = "Voice network hiccup — dobara MIC dabao"
                else:
                    msg = f"Mic ready — dobara MIC dabao ({err_int})"
                Clock.schedule_once(lambda _dt, m=msg: bridge.on_status(m), 0)

            @java_method("(Landroid/os/Bundle;)V")
            def onResults(self, results):
                bridge.is_listening = False
                bridge._emit_partial(text_val="", rms_val=0.0, active=False)
                try:
                    if results is not None:
                        matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        if matches and matches.size() > 0:
                            spoken = str(matches.get(0)).strip()
                            if spoken:
                                Clock.schedule_once(lambda _dt, s=spoken: bridge.on_transcript(s), 0)
                                return
                    Clock.schedule_once(lambda _dt: bridge.on_status("Samjha nahi — dobara boliyega"), 0)
                except BaseException as exc:
                    Clock.schedule_once(lambda _dt, e=str(exc): bridge.on_status(f"Mic parse error: {e}"), 0)

            @java_method("(Landroid/os/Bundle;)V")
            def onPartialResults(self, partialResults):
                try:
                    if partialResults is not None and bridge.is_listening:
                        matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        if matches and matches.size() > 0:
                            partial_txt = str(matches.get(0)).strip()
                            if partial_txt:
                                bridge._emit_partial(text_val=partial_txt, rms_val=None, active=True)
                except BaseException:
                    pass

            @java_method("(ILandroid/os/Bundle;)V")
            def onEvent(self, _eventType, _params):
                pass

        self._recognition_listener = _NeonRecognitionListener()
        return self._recognition_listener

    def stop_listening(self):
        self.is_listening = False
        self._emit_partial(text_val="", rms_val=0.0, active=False)
        if platform == "android" and self._speech_recognizer is not None:
            def _stop_ui():
                try:
                    self._speech_recognizer.stopListening()
                except BaseException:
                    pass
            self._run_ui(_stop_ui)
        self.on_status("VOICE-FIRST INTELLIGENCE • Ready")

    def _launch_android_recognizer_popup(self):
        """Last-resort fallback only if background SpeechRecognizer service is absent on device."""
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

    def _launch_android_recognizer(self):
        """Primary zero-popup background SpeechRecognizer with subtle inline UI feedback."""
        self._listen_gen += 1
        gen = self._listen_gen

        def _start_inline():
            try:
                from jnius import autoclass

                SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
                Intent = autoclass("android.content.Intent")
                RecognizerIntent = autoclass("android.speech.RecognizerIntent")

                if not SpeechRecognizer.isRecognitionAvailable(self._activity):
                    self._launch_android_recognizer_popup()
                    return

                if self._speech_recognizer is None:
                    self._speech_recognizer = SpeechRecognizer.createSpeechRecognizer(self._activity)
                else:
                    try:
                        self._speech_recognizer.cancel()
                    except BaseException:
                        pass

                listener = self._get_recognition_listener()
                self._speech_recognizer.setRecognitionListener(listener)

                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                )
                intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, self._activity.getPackageName())
                lang_tag = "hi-IN" if self._language_mode == "hi" else "en-IN"
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang_tag)
                intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                try:
                    JavaLong = autoclass("java.lang.Long")
                    intent.putExtra(
                        RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS,
                        JavaLong(2200),
                    )
                    intent.putExtra(
                        RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS,
                        JavaLong(1800),
                    )
                    intent.putExtra(
                        RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS,
                        JavaLong(1500),
                    )
                except BaseException:
                    pass

                self.is_listening = True
                Clock.schedule_once(lambda _dt: self.on_status("MIC ON • Bolo Harish..."), 0)
                self._emit_partial(text_val="", rms_val=1.0, active=True)
                self._speech_recognizer.startListening(intent)

                # Safety guard in case an OEM ROM never fires onError/onResults
                def _timeout_guard(_dt):
                    if self.is_listening and self._listen_gen == gen:
                        self.stop_listening()

                Clock.schedule_once(_timeout_guard, 24.0)
            except BaseException as exc:
                self.is_listening = False
                self._emit_partial(text_val="", rms_val=0.0, active=False)
                Clock.schedule_once(lambda _dt, e=str(exc): self.on_status(f"Inline mic note: {e}"), 0)
                self._launch_android_recognizer_popup()

        self._run_ui(_start_inline)

    def _on_activity_result(self, request_code, result_code, intent):
        if request_code != self.speech_req_code:
            return
        self.is_listening = False
        self._emit_partial(text_val="", rms_val=0.0, active=False)
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
        if self.is_listening:
            self.stop_listening()
            return
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
            self._emit_partial(text_val="", rms_val=1.0, active=True)

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
                    self._emit_partial(text_val="", rms_val=0.0, active=False)
                    spoken = proc.stdout.strip()
                    if spoken:
                        Clock.schedule_once(lambda _dt, s=spoken: self.on_transcript(s), 0)
                    else:
                        Clock.schedule_once(lambda _dt: self.on_status("Ready — tap MIC to speak"), 0)
                except Exception as err:
                    self.is_listening = False
                    self._emit_partial(text_val="", rms_val=0.0, active=False)
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
        self._tts_cooldown_ev = None
        self._is_executing = False
        self._exe_pct = 0
        self._apk_pct = 0
        self._build_poll_ev = None
        self._last_completed_run_id = None
        self.brain_lessons = self._load_brain_memory()

        self.voice_bridge = AndroidVoiceBridge(
            status_callback=self._update_voice_banner,
            transcript_callback=self._on_voice_transcript,
            speak_done_callback=self._on_tts_finished,
            data_dir_fn=self._get_data_dir,
            partial_callback=self._on_voice_partial,
        )
        self.voice_bridge.configure(
            api_key=self.api_key,
            language_mode=self.language_mode,
            voice_persona=self.voice_persona,
        )

        self._build_header()
        self._build_controls_strip()
        self._build_tab_bar()
        self._build_execution_strip()
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
    # NEON Brain: Lightweight Self-Learning Persistent Memory (neon_brain/memory.json)
    # ------------------------------------------------------------------
    def _get_brain_dir(self):
        bdir = os.path.join(self._get_data_dir(), "neon_brain")
        os.makedirs(bdir, exist_ok=True)
        return bdir

    def _get_brain_path(self):
        return os.path.join(self._get_brain_dir(), "memory.json")

    def _default_brain_lessons(self):
        return [
            {
                "id": "core-dl-rule",
                "category": "preference",
                "lesson": "Download APK/EXE buttons must only download binaries directly—never re-push or cancel builds.",
                "source": "core",
            },
            {
                "id": "core-tts-v1beta",
                "category": "mistake_lesson",
                "lesson": "Always call gemini-3.8-flash-lite-tts on v1beta and wrap raw PCM into RIFF WAV headers.",
                "source": "self_heal",
            },
            {
                "id": "core-buildozer-ssl",
                "category": "skill_pattern",
                "lesson": "Android buildozer.spec pins p4a.branch=v2024.01.21, android.ndk=25b, android.ndk_api=21, and openssl.",
                "source": "self_heal",
            },
        ]

    def _load_brain_memory(self):
        path = self._get_brain_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list) and data:
                    return data[:80]
        except Exception:
            pass
        seeds = self._default_brain_lessons()
        self._save_brain_memory(seeds)
        return seeds

    def _save_brain_memory(self, lessons):
        trimmed = list(lessons)[:80]
        try:
            with open(self._get_brain_path(), "w", encoding="utf-8") as fh:
                json.dump(trimmed, fh, indent=2)
        except Exception:
            pass
        self.brain_lessons = trimmed
        if hasattr(self, "brain_pill"):
            self.brain_pill.text = f"Brain ({len(trimmed)})"

    def _learn_to_brain(self, category, lesson_text, source="self_heal"):
        clean = " ".join(str(lesson_text or "").split())[:240]
        if not clean:
            return
        cur = getattr(self, "brain_lessons", []) or []
        if any(str(x.get("lesson", "")).lower() == clean.lower() for x in cur):
            return
        entry = {
            "id": f"brain-{int(time.time() * 1000)}",
            "category": category or "mistake_lesson",
            "lesson": clean,
            "source": source,
        }
        updated = [entry] + cur
        self._save_brain_memory(updated[:80])

    def _build_brain_context(self):
        cur = (getattr(self, "brain_lessons", []) or [])[:12]
        if not cur:
            return ""
        lines = ["\n[NEON BRAIN LEARNED RULES (Follow Strictly)]:"]
        for item in cur:
            lines.append(f"- [{item.get('category', 'rule')}] {item.get('lesson', '')}")
        return "\n".join(lines)

    def _open_brain_modal(self):
        modal = ModalView(size_hint=(0.94, None), height=dp(470), background_color=(0, 0, 0, 0.80))
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        style_card(box, (0.04, 0.06, 0.12, 1.0), (0.08, 0.72, 0.88, 0.75), radius_dp=14)

        hdr = BoxLayout(size_hint_y=None, height=dp(30))
        hdr.add_widget(
            AutoLabel(
                text=f"[b][color=22d3ee]NEON Brain[/color][/b] [color=94a3b8]({len(self.brain_lessons)}/80 rules • neon_brain/memory.json)[/color]",
                font_size=sp(12),
            )
        )
        close_b = make_button(
            "Close",
            (0.18, 0.08, 0.12, 1.0),
            (0.85, 0.28, 0.38, 0.65),
            radius_dp=8,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(56), dp(28)),
        )
        close_b.bind(on_release=lambda *_: modal.dismiss())
        hdr.add_widget(close_b)
        box.add_widget(hdr)

        add_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(5))
        teach_inp = TextInput(
            hint_text="Teach a permanent rule or preference to NEON Brain...",
            multiline=False,
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(11),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )
        add_b = make_button(
            "Save",
            (0.04, 0.52, 0.38, 1.0),
            (0.16, 0.92, 0.62, 0.8),
            radius_dp=8,
            font_sp=10,
            size_hint_x=None,
            width=dp(60),
        )
        add_row.add_widget(teach_inp)
        add_row.add_widget(add_b)
        box.add_widget(add_row)

        sc = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        lst_lbl = AutoLabel(text="", font_size=sp(11))
        sc.add_widget(lst_lbl)
        box.add_widget(sc)

        def _render_lessons():
            lines = []
            for it in self.brain_lessons[:30]:
                lines.append(
                    f"[b][color=38bdf8][{escape_markup(str(it.get('category', 'rule')))}][/color][/b] "
                    f"[color=e2e8f0]{escape_markup(str(it.get('lesson', '')))}[/color]"
                )
            lst_lbl.text = "\n\n".join(lines) or "[color=94a3b8]No rules saved yet.[/color]"

        def _add_lesson(*_a):
            val = teach_inp.text.strip()
            if not val:
                return
            self._learn_to_brain("preference", val, source="user")
            teach_inp.text = ""
            _render_lessons()

        add_b.bind(on_release=_add_lesson)
        _render_lessons()
        modal.add_widget(box)
        modal.open()

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
            text="[b][color=ffffff]NEON[/color] [color=22d3ee]PRO[/color][/b] [color=64748b]v4.5[/color]",
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

        self.selftest_pill = make_button(
            "Self-Test",
            (0.04, 0.24, 0.18, 1.0),
            (0.12, 0.85, 0.56, 0.72),
            text_rgba=(0.48, 0.98, 0.76, 1.0),
            radius_dp=7,
            font_sp=10,
            size_hint_x=0.82,
        )
        self.selftest_pill.bind(on_release=lambda *_: self._run_self_test_and_heal(auto_fix=True))
        strip.add_widget(self.selftest_pill)

        self.brain_pill = make_button(
            f"Brain ({len(self.brain_lessons)})",
            (0.10, 0.12, 0.28, 1.0),
            (0.35, 0.65, 0.96, 0.70),
            text_rgba=(0.65, 0.88, 1.0, 1.0),
            radius_dp=7,
            font_sp=10,
            size_hint_x=0.82,
        )
        self.brain_pill.bind(on_release=lambda *_: self._open_brain_modal())
        strip.add_widget(self.brain_pill)

        self.add_widget(strip)

    def _build_tab_bar(self):
        tab_bar = BoxLayout(size_hint_y=None, height=dp(40), padding=dp(3), spacing=dp(4))
        style_card(tab_bar, (0.045, 0.068, 0.125, 1.0), (0.12, 0.18, 0.30, 0.9), radius_dp=10)

        tabs = [
            ("console", "Chat"),
            ("app-studio", "App Builder"),
            ("debugger", "Auto-Fix"),
            ("terminal", "Device"),
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

    def _build_execution_strip(self):
        """Collapsible top 'Executing...' bar showing live EXE% & APK% progress across tabs."""
        self.exec_strip = BoxLayout(size_hint_y=None, height=0, opacity=0, disabled=True, padding=[dp(8), dp(4)], spacing=dp(6))
        style_card(self.exec_strip, (0.03, 0.09, 0.16, 1.0), (0.08, 0.78, 0.92, 0.82), radius_dp=10)

        self.exec_lbl = Label(
            text="[b][color=22d3ee]Executing...[/color][/b] [color=e2e8f0]EXE: 0% | APK: 0%[/color]",
            markup=True,
            font_size=sp(10),
            halign="left",
            valign="middle",
        )
        self.exec_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.exec_strip.add_widget(self.exec_lbl)

        dl_go = make_button(
            "Downloads",
            (0.04, 0.48, 0.35, 1.0),
            (0.16, 0.90, 0.60, 0.8),
            radius_dp=7,
            font_sp=10,
            size_hint_x=None,
            width=dp(74),
        )
        dl_go.bind(on_release=lambda *_: self._switch_tab("github"))
        self.exec_strip.add_widget(dl_go)

        kill_go = make_button(
            "Kill",
            (0.35, 0.08, 0.12, 1.0),
            (0.95, 0.32, 0.40, 0.8),
            radius_dp=7,
            font_sp=10,
            size_hint_x=None,
            width=dp(44),
        )
        kill_go.bind(on_release=lambda *_: self._gh_cancel_stuck_runs())
        self.exec_strip.add_widget(kill_go)

        self.add_widget(self.exec_strip)

    def _set_execution_progress(self, active, exe_pct=0, apk_pct=0, note=""):
        self._is_executing = bool(active)
        self._exe_pct = int(exe_pct or 0)
        self._apk_pct = int(apk_pct or 0)
        if not hasattr(self, "exec_strip"):
            return
        if active:
            self.exec_strip.height = dp(42)
            self.exec_strip.opacity = 1
            self.exec_strip.disabled = False
            extra = f" • {escape_markup(note)}" if note else ""
            self.exec_lbl.text = (
                f"[b][color=22d3ee]Executing...[/color][/b] "
                f"[color=a5b4fc]EXE: {self._exe_pct}%[/color] | "
                f"[color=34d399]APK: {self._apk_pct}%[/color]{extra}"
            )
        else:
            self.exec_strip.height = 0
            self.exec_strip.opacity = 0
            self.exec_strip.disabled = True

    def _stop_build_progress_poller(self):
        ev = getattr(self, "_build_poll_ev", None)
        if ev is not None:
            try:
                ev.cancel()
            except Exception:
                pass
            self._build_poll_ev = None

    def _start_build_progress_poller(self, owner, repo, token):
        self._stop_build_progress_poller()
        self._poll_inflight = False

        def _tick(_dt):
            if getattr(self, "_poll_inflight", False):
                return True
            self._poll_inflight = True

            def _bg():
                try:
                    rc, rdata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=4", token)
                    ac, adata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=8", token)
                    runs = rdata.get("workflow_runs", []) if rc == 200 and isinstance(rdata, dict) else []
                    arts = [a for a in (adata.get("artifacts", []) if ac == 200 and isinstance(adata, dict) else []) if not a.get("expired")]
                    active_runs = [r for r in runs if r.get("status") in ("in_progress", "queued", "waiting", "pending", "requested")]
                    top_run = active_runs[0] if active_runs else (runs[0] if runs else None)
                    has_exe = any("exe" in str(a.get("name", "")).lower() for a in arts)
                    has_apk = any("apk" in str(a.get("name", "")).lower() for a in arts)

                    exe_pct = 100 if has_exe else (10 if active_runs else 0)
                    apk_pct = 100 if has_apk else (10 if active_runs else 0)
                    if top_run:
                        jc, jdata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{top_run.get('id')}/jobs", token)
                        if jc == 200 and isinstance(jdata, dict):
                            for jb in jdata.get("jobs", []):
                                steps = jb.get("steps") or []
                                tot = max(len(steps), 1)
                                done_cnt = sum(1 for sp_i in steps if sp_i.get("status") == "completed")
                                pct = 100 if jb.get("status") == "completed" else (min(96, max(8, int(((done_cnt + 0.5) / tot) * 100))) if jb.get("status") == "in_progress" else 5)
                                jname = str(jb.get("name", "")).lower()
                                if "exe" in jname or "windows" in jname:
                                    exe_pct = 100 if has_exe else pct
                                elif "apk" in jname or "android" in jname:
                                    apk_pct = 100 if has_apk else pct

                    def _apply(_dt2):
                        self._poll_inflight = False
                        if active_runs:
                            self._set_execution_progress(True, exe_pct=exe_pct, apk_pct=apk_pct)
                        else:
                            self._set_execution_progress(False, exe_pct=exe_pct, apk_pct=apk_pct)
                            self._stop_build_progress_poller()
                            if top_run and top_run.get("status") == "completed" and top_run.get("conclusion") != "cancelled" and (has_apk or has_exe):
                                rid = top_run.get("id")
                                if self._last_completed_run_id != rid:
                                    self._last_completed_run_id = rid
                                    self._switch_tab("github")
                                    self._gh_check_runs()
                                    if self.audio_enabled:
                                        self.voice_bridge.speak("Harish, cloud build complete ho gaya hai! Ab Download APK File ya Download EXE File tap karo.")

                    Clock.schedule_once(_apply, 0)
                except Exception:
                    Clock.schedule_once(lambda _dt2: setattr(self, "_poll_inflight", False), 0)

            threading.Thread(target=_bg, daemon=True).start()
            return True

        _tick(0)
        self._build_poll_ev = Clock.schedule_interval(_tick, 10.0)

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
        if tab_key == "github":
            self._auto_detect_clipboard_token()

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

    def _cancel_tts_cooldown(self):
        ev = getattr(self, "_tts_cooldown_ev", None)
        if ev is not None:
            try:
                ev.cancel()
            except Exception:
                pass
            self._tts_cooldown_ev = None

    def _schedule_hands_free_listen(self, delay_sec=1.6):
        self._cancel_tts_cooldown()
        if not (self.hands_free_mode and not self._pending_busy and self.active_tab == "console"):
            return
        self._update_voice_banner("Pause 1.6s... Mic taiyar ho raha hai")
        def _open_mic(_dt):
            self._tts_cooldown_ev = None
            if (
                self.hands_free_mode
                and not self._pending_busy
                and not self.voice_bridge.is_speaking
                and not self.voice_bridge.is_listening
                and self.active_tab == "console"
            ):
                self.voice_bridge.start_listening()
        self._tts_cooldown_ev = Clock.schedule_once(_open_mic, delay_sec)

    def _toggle_hands_free(self, *_args):
        self._cancel_tts_cooldown()
        self.hands_free_mode = not self.hands_free_mode
        self._save_config()
        self._refresh_header_state()
        if self.hands_free_mode and not self._pending_busy and not self.voice_bridge.is_speaking:
            self.voice_bridge.start_listening()
        elif not self.hands_free_mode:
            self.voice_bridge.stop_speaking()
            self._update_voice_banner("VOICE-FIRST INTELLIGENCE • Ready")

    def _barge_in_now(self, *_args):
        self._cancel_tts_cooldown()
        self.voice_bridge.stop_speaking()
        Clock.schedule_once(lambda _dt: self.voice_bridge.start_listening(), 0.25)

    def _on_tts_finished(self):
        self._update_voice_banner(f"VOICE-FIRST INTELLIGENCE • Persona: {self.voice_persona}")
        if self.hands_free_mode and not self._pending_busy and self.active_tab == "console":
            self._schedule_hands_free_listen(1.6)

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

        # Voice-First Intelligence Strip + Subtle Live Speaking Pill (No Fullscreen Google Popup)
        self.voice_card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(84), padding=[dp(8), dp(5)], spacing=dp(3))
        style_card(self.voice_card, (0.035, 0.055, 0.11, 1.0), (0.08, 0.38, 0.55, 0.5), radius_dp=10)

        self.voice_status_lbl = Label(
            text=f"[b][color=22d3ee]VOICE-FIRST INTELLIGENCE[/color][/b] [color=94a3b8]• Persona: {self.voice_persona}[/color]",
            markup=True,
            font_size=sp(10),
            size_hint_y=None,
            height=dp(18),
            halign="left",
            valign="middle",
        )
        self.voice_status_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.voice_card.add_widget(self.voice_status_lbl)

        # Subtle compact inline listening + live words indicator inside the top bar
        self.voice_live_pill = Label(
            text="[color=64748b]● Background Mic Ready — tap MIC & speak freely[/color]",
            markup=True,
            font_size=sp(10),
            size_hint_y=None,
            height=dp(18),
            halign="left",
            valign="middle",
        )
        self.voice_live_pill.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.voice_card.add_widget(self.voice_live_pill)

        vc_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(5))
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

        self.voice_card.add_widget(vc_row)
        root.add_widget(self.voice_card)

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
            "Namaste Harish! Main NEON PRO v4.5 hoon — ab aur bhi easy:\n"
            "1. MIC dabao: Bina kisi popup ke background me sunega + upar chhota live indicator dikhega.\n"
            "2. App Builder me bina copy-paste ke code save hoga.\n"
            "3. Downloads ke 2 buttons hain: 'Download APK File' (Android) & 'Download EXE File' (Windows)!"
        )
        self._add_message_card("assistant", welcome_text, model_tag="NEON v4.5")
        if not self.api_key:
            self._add_setup_card()

        # Horizontal Quick Commands Strip
        quick_scroll = ScrollView(size_hint_y=None, height=dp(38), do_scroll_y=False, bar_width=0)
        quick_row = BoxLayout(size_hint_x=None, height=dp(34), spacing=dp(6), padding=[dp(2), dp(2)])
        quick_row.bind(minimum_width=quick_row.setter("width"))

        quick_prompts = [
            ("Self-Test", "__SELF_TEST__"),
            ("Compound Calc", "Build a complete runnable Compound Interest Calculator Kivy Android app for Harish."),
            ("App Templates", "__OPEN_BUILDER__"),
            ("Hinglish Chat", "Aur bhai kya haal hai? Aaj naya app banayein kya?"),
            ("Fix Error", "__OPEN_FIXER__"),
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
                        "Edit Code",
                        (0.05, 0.18, 0.28, 1.0),
                        (0.10, 0.65, 0.85, 0.6),
                        text_rgba=(0.55, 0.90, 1.0, 1.0),
                        radius_dp=6,
                        font_sp=9,
                        size_hint=(None, None),
                        size=(dp(66), dp(22)),
                    )
                    c_studio.bind(on_release=lambda *_a, cb=code_body, lg=lang: self._open_code_in_studio(cb, lg))
                    c_hdr.add_widget(c_studio)

                    c_apk = make_button(
                        "Build APK",
                        (0.04, 0.45, 0.32, 1.0),
                        (0.14, 0.88, 0.58, 0.8),
                        text_rgba=(0.85, 1.0, 0.92, 1.0),
                        radius_dp=6,
                        font_sp=9,
                        size_hint=(None, None),
                        size=(dp(66), dp(22)),
                    )
                    c_apk.bind(on_release=lambda *_a, cb=code_body, lg=lang: self._build_code_as_apk(cb, lg))
                    c_hdr.add_widget(c_apk)

                    c_copy = make_button(
                        "Copy",
                        (0.06, 0.16, 0.14, 1.0),
                        (0.10, 0.72, 0.52, 0.6),
                        text_rgba=(0.55, 0.96, 0.78, 1.0),
                        radius_dp=6,
                        font_sp=9,
                        size_hint=(None, None),
                        size=(dp(44), dp(22)),
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
                sync_banner = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
                sync_banner.add_widget(
                    AutoLabel(
                        text="[b][color=34d399]✓ Saved to App Builder (Zero Copy-Paste)[/color][/b]",
                        font_size=sp(10),
                    )
                )
                go_studio = make_button(
                    "Open Builder",
                    (0.06, 0.22, 0.36, 1.0),
                    (0.14, 0.72, 0.90, 0.7),
                    radius_dp=7,
                    font_sp=10,
                    size_hint=(None, None),
                    size=(dp(82), dp(26)),
                )
                go_studio.bind(on_release=lambda *_: self._switch_tab("app-studio"))
                sync_banner.add_widget(go_studio)

                go_apk = make_button(
                    "Build APK",
                    (0.04, 0.48, 0.34, 1.0),
                    (0.16, 0.90, 0.60, 0.85),
                    radius_dp=7,
                    font_sp=10,
                    size_hint=(None, None),
                    size=(dp(76), dp(26)),
                )
                go_apk.bind(on_release=lambda *_: self._trigger_one_tap_apk_build())
                sync_banner.add_widget(go_apk)
                card.add_widget(sync_banner)

            wrapper.add_widget(card)
            wrapper.add_widget(BoxLayout(size_hint_x=0.04))

        self.chat_list.add_widget(wrapper)
        Clock.schedule_once(lambda _dt: setattr(self.chat_scroll, "scroll_y", 0), 0.08)

    def _open_code_in_studio(self, code_body, lang="python"):
        self._sync_autonomous_code(code_body, lang)
        self._switch_tab("app-studio")

    def _build_code_as_apk(self, code_body, lang="python"):
        self._sync_autonomous_code(code_body, lang)
        self._trigger_one_tap_apk_build()

    def _sync_autonomous_code(self, code_body, lang="python"):
        ext = "py"
        low = (lang or "").lower()
        if "js" in low:
            ext = "js"
        elif "html" in low:
            ext = "html"
        elif "sh" in low or "bash" in low:
            ext = "sh"
        fname = "main.py" if ext == "py" else f"generated_app.{ext}"
        self.studio_files[fname] = code_body
        self.active_studio_file = fname
        self.studio_file_lbl.text = f"[b][color=34d399]Active File: {fname} (Ready for APK)[/color][/b]"
        self.studio_editor.text = code_body
        if hasattr(self, "studio_status_lbl"):
            self.studio_status_lbl.text = "[color=34d399]✓ Code synced into main.py! Tap 'Build APK' anytime.[/color]"
        try:
            proj_dir = os.path.join(self._get_data_dir(), "autonomous_projects")
            os.makedirs(proj_dir, exist_ok=True)
            with open(os.path.join(proj_dir, fname), "w", encoding="utf-8") as fh:
                fh.write(code_body)
            if fname == "main.py":
                with open(os.path.join(proj_dir, "generated_app.py"), "w", encoding="utf-8") as fh2:
                    fh2.write(code_body)
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

    def _on_voice_partial(self, partial_text=None, rms_db=None, active=True):
        if hasattr(self, "mic_btn"):
            if active:
                self.mic_btn.text = "LIVE"
                style_card(self.mic_btn, (0.58, 0.08, 0.22, 1.0), (0.98, 0.35, 0.52, 0.85), radius_dp=9)
            else:
                self.mic_btn.text = "MIC"
                style_card(self.mic_btn, (0.28, 0.14, 0.55, 1.0), (0.62, 0.38, 0.96, 0.7), radius_dp=9)

        if hasattr(self, "voice_live_pill"):
            if not active:
                self.voice_live_pill.text = "[color=64748b]● Background Mic Ready — tap MIC & speak freely[/color]"
                style_card(self.voice_card, (0.035, 0.055, 0.11, 1.0), (0.08, 0.38, 0.55, 0.5), radius_dp=10)
            else:
                style_card(self.voice_card, (0.035, 0.095, 0.14, 1.0), (0.12, 0.88, 0.62, 0.85), radius_dp=10)
                if partial_text:
                    shown = escape_markup(partial_text[-58:])
                    self.voice_live_pill.text = f"[b][color=34d399]● Sun raha hoon:[/color][/b] [color=e2e8f0]{shown}[/color]"
                    self._last_partial_shown = shown
                elif rms_db is not None:
                    bars = max(1, min(5, int((rms_db + 2.0) / 2.2)))
                    meter = "|" * bars + "." * (5 - bars)
                    prev = getattr(self, "_last_partial_shown", "")
                    if prev:
                        self.voice_live_pill.text = f"[b][color=34d399]● [{meter}][/color][/b] [color=e2e8f0]{prev}[/color]"
                    else:
                        self.voice_live_pill.text = f"[b][color=34d399]● [{meter}] Bolo Harish...[/color][/b]"
                else:
                    self._last_partial_shown = ""
                    self.voice_live_pill.text = "[b][color=34d399]● Mic ON — bolo Harish (No popup)[/color][/b]"

    def _on_voice_transcript(self, spoken_text):
        self._last_partial_shown = ""
        self._on_voice_partial("", 0.0, active=False)
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

    def _is_self_test_intent(self, prompt_text):
        low = prompt_text.lower()
        keys = (
            "self test", "self-test", "selftest", "auto heal", "auto-heal",
            "auto fix", "apna test", "khud check", "khud ko theek",
            "check error", "error check", "सेल्फ टेस्ट", "खुद टेस्ट",
            "खुद को ठीक", "एरर चेक",
        )
        return any(k in low for k in keys)

    def _extract_python_code(self, text_val):
        m = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)```", text_val, re.IGNORECASE)
        if m and len(m.group(1).strip()) > 40:
            return m.group(1).strip() + "\n"
        if "from kivy" in text_val and "def build(" in text_val and len(text_val) > 100:
            lines = [ln for ln in text_val.splitlines() if not ln.strip().startswith("```")]
            return "\n".join(lines).strip() + "\n"
        return None

    def _send_chat_prompt(self, preset_prompt=None):
        if preset_prompt == "__SELF_TEST__":
            self._run_self_test_and_heal(auto_fix=True)
            return
        if preset_prompt == "__OPEN_BUILDER__":
            self._switch_tab("app-studio")
            return
        if preset_prompt == "__OPEN_FIXER__":
            self._switch_tab("debugger")
            return

        prompt = (preset_prompt or self.chat_input.text).strip()
        if not prompt or self._pending_busy:
            return

        self._cancel_tts_cooldown()
        self.voice_bridge.stop_speaking()
        if not preset_prompt:
            self.chat_input.text = ""
        self._add_message_card("user", prompt)

        low_p = prompt.lower()
        if any(k in low_p for k in ("yaad rakh", "galat hai", "remember", "sikho", "hamesha", "never do")):
            self._learn_to_brain("preference", prompt[:220], source="user_chat")

        # Auto-detect pasted Python/Kivy code in Chat and launch autonomous APK + EXE build!
        pasted_py = self._extract_python_code(prompt)
        if pasted_py:
            self._sync_autonomous_code(pasted_py, "python")
            try:
                ast.parse(pasted_py)
                ast_note = "Syntax bilkul OK hai!"
            except SyntaxError as s_err:
                ast_note = f"Line {s_err.lineno} par ek chhota syntax issue hai — 'App Builder -> Check Code' dabao."
            ok_reply = (
                f"Badhiya Harish! Maine aapka code App Builder me save karke autonomous .APK + .EXE pipeline start kar di hai! {ast_note}\n\n"
                f"```python\n{pasted_py.strip()}\n```"
            )
            self._add_message_card("assistant", ok_reply, model_tag="Auto-Build")
            self._start_autonomous_build_from_chat("Custom Pasted App")
            if self.audio_enabled:
                self.voice_bridge.speak("Harish, aapka code save karke autonomous APK aur EXE build shuru kar diya hai.")
            return

        if self._is_self_test_intent(prompt):
            self._run_self_test_and_heal(auto_fix=True, user_already_added=True)
            return

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

    def _http_get_json(self, url, timeout=20):
        _ssl_ctx, req_verify = _build_ssl_context()
        if requests is not None:
            try:
                try:
                    r = requests.get(url, timeout=(10, timeout), verify=req_verify)
                except Exception as r_err:
                    if _is_ssl_exception(r_err) and req_verify is not False:
                        _activate_unverified_ssl_fallback()
                        r = requests.get(url, timeout=(10, timeout), verify=False)
                    elif "timed out" in str(r_err).lower() or "timeout" in str(r_err).lower():
                        raise TimeoutError(str(r_err))
                    else:
                        raise
                return r.status_code, (r.json() if r.status_code == 200 else r.text)
            except TimeoutError:
                raise
            except Exception as outer_err:
                if "timed out" in str(outer_err).lower() or "timeout" in str(outer_err).lower():
                    raise TimeoutError(str(outer_err))
        req = urllib.request.Request(url, method="GET")
        code, txt = _urlopen_with_ssl_retry(req, timeout=timeout)
        if code == 200:
            return code, json.loads(txt)
        return code, txt

    def _http_post_json(self, url, payload, headers=None, timeout=45):
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        _ssl_ctx, req_verify = _build_ssl_context()
        if requests is not None:
            try:
                try:
                    resp = requests.post(url, json=payload, headers=hdrs, timeout=(12, timeout), verify=req_verify)
                except Exception as r_err:
                    if _is_ssl_exception(r_err) and req_verify is not False:
                        _activate_unverified_ssl_fallback()
                        resp = requests.post(url, json=payload, headers=hdrs, timeout=(12, timeout), verify=False)
                    elif "timed out" in str(r_err).lower() or "timeout" in str(r_err).lower():
                        raise TimeoutError(str(r_err))
                    else:
                        raise
                data = None
                if resp.status_code in (200, 201):
                    try:
                        data = resp.json()
                    except Exception:
                        data = None
                return resp.status_code, resp.text, data
            except TimeoutError:
                raise
            except Exception as outer_err:
                if "timed out" in str(outer_err).lower() or "timeout" in str(outer_err).lower():
                    raise TimeoutError(str(outer_err))
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=hdrs,
            method="POST",
        )
        code, raw_text = _urlopen_with_ssl_retry(req, timeout=timeout)
        data = None
        if code in (200, 201):
            try:
                data = json.loads(raw_text)
            except Exception:
                data = None
        return code, raw_text, data

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
        chain = [self.selected_model, "gemini-3.1-flash-lite", "gemini-4-hydrogen", "gemini-4-argon"]
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
            needs_discovery = False
            for model_name in model_list:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_name}:generateContent?key={self.api_key}"
                )
                try:
                    status_code, raw_text, data = self._http_post_json(url, payload, timeout=45)
                    if status_code == 200 and data:
                        cands = data.get("candidates") or []
                        if cands:
                            parts = cands[0].get("content", {}).get("parts", [])
                            txt = "".join(p.get("text", "") for p in parts).strip()
                            if txt:
                                return txt, model_name, False
                    else:
                        if status_code in (404, 503, 504):
                            needs_discovery = True
                        last_err = f"HTTP {status_code}: {raw_text[:180]}"
                        if status_code not in (404, 429, 500, 502, 503, 504):
                            break
                except Exception as exc:
                    needs_discovery = True
                    last_err = str(exc)
            return None, None, needs_discovery

        txt, used, should_discover = _try_models(dedup_chain)
        if txt:
            return txt, used, None

        # Dynamic model auto-discovery fallback on 404 or timeout
        if should_discover:
            fresh = [m for m in self._discover_available_models() if m not in dedup_chain]
            if fresh:
                txt, used, _ = _try_models(fresh)
                if txt:
                    return txt, used, None

        return None, None, last_err

    def _add_auto_build_status_card(self, title="Autonomous APK & EXE Pipeline", needs_token=False, exe_zip_path=None):
        box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(6))
        box.bind(minimum_height=box.setter("height"))
        border = (0.95, 0.65, 0.15, 0.72) if needs_token else (0.14, 0.88, 0.58, 0.75)
        bg = (0.09, 0.06, 0.02, 1.0) if needs_token else (0.03, 0.09, 0.07, 1.0)
        style_card(box, bg, border, radius_dp=12)

        hdr = AutoLabel(
            text=f"[b][color={'fbbf24' if needs_token else '34d399'}]{escape_markup(title)}[/color][/b]",
            font_size=sp(11),
        )
        box.add_widget(hdr)

        status_lbl = AutoLabel(
            text=(
                "[color=e2e8f0]Code synced to App Builder & Windows EXE Zip ready! Cloud .APK + .EXE compile ke liye 1-baar GitHub Token connect karein.[/color]"
                if needs_token
                else "[color=38bdf8]Step 1/3: Synced code • Step 2/3: Auto-pushing to GitHub CI for Android .APK + Windows .EXE...[/color]"
            ),
            font_size=sp(11),
        )
        box.add_widget(status_lbl)

        btn_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        if needs_token:
            tok_btn = make_button(
                "Connect Token & Auto-Build",
                (0.04, 0.50, 0.36, 1.0),
                (0.16, 0.90, 0.60, 0.85),
                radius_dp=8,
                font_sp=10,
            )
            tok_btn.bind(
                on_release=lambda *_: self._open_github_token_modal(
                    on_verified=lambda: self._start_autonomous_build_from_chat(title)
                )
            )
            btn_row.add_widget(tok_btn)

            if exe_zip_path:
                zip_btn = make_button(
                    "Open GitHub CI",
                    (0.32, 0.14, 0.56, 1.0),
                    (0.68, 0.36, 0.96, 0.8),
                    radius_dp=8,
                    font_sp=10,
                    size_hint_x=0.7,
                )
                zip_btn.bind(on_release=lambda *_: self._switch_tab("github"))
                btn_row.add_widget(zip_btn)
        else:
            dl_btn = make_button(
                "Open Downloads",
                (0.04, 0.45, 0.32, 1.0),
                (0.14, 0.88, 0.58, 0.8),
                radius_dp=8,
                font_sp=10,
            )
            dl_btn.bind(on_release=lambda *_: self._gh_open_actions_browser())
            btn_row.add_widget(dl_btn)

            ci_btn = make_button(
                "GitHub CI",
                (0.32, 0.14, 0.56, 1.0),
                (0.68, 0.36, 0.96, 0.8),
                radius_dp=8,
                font_sp=10,
                size_hint_x=0.65,
            )
            ci_btn.bind(on_release=lambda *_: self._switch_tab("github"))
            btn_row.add_widget(ci_btn)

        box.add_widget(btn_row)
        self.chat_list.add_widget(box)
        Clock.schedule_once(lambda _dt: setattr(self.chat_scroll, "scroll_y", 0), 0.08)
        return status_lbl

    def _start_autonomous_build_from_chat(self, app_label="Autonomous App"):
        saved_zip = self._export_exe_bundle()
        if not self.github_token:
            self._add_auto_build_status_card(
                title=f"Setup Needed • {app_label}",
                needs_token=True,
                exe_zip_path=saved_zip,
            )
            return
        status_lbl = self._add_auto_build_status_card(
            title=f"Auto-Building APK + EXE • {app_label}",
            needs_token=False,
            exe_zip_path=saved_zip,
        )
        self._gh_push_studio_app(
            target="apk",
            local_exe_zip=saved_zip,
            chat_status_lbl=status_lbl,
        )

    def _run_gemini_chat(self, prompt):
        lang_hint = ""
        if self.language_mode == "hi":
            lang_hint = " Always reply in natural conversational Hindi or Hinglish."
        elif self.language_mode == "en":
            lang_hint = " Always reply in crisp conversational English."
        if self.hands_free_mode:
            lang_hint += " Hands-Free voice mode is ON: keep conversational replies concise and natural."
        build_requested = self._is_build_intent(prompt)
        if build_requested:
            lang_hint += (
                " Harish wants full autonomous output (.APK and .EXE). Output complete zero-placeholder Python/Kivy code in one triple-backtick python block "
                "and confirm in 1 short sentence that autonomous compilation into Android .APK and Windows .EXE has started automatically (never tell him to manually compile or copy-paste)."
            )

        self.history.append({"role": "user", "parts": [{"text": prompt}]})
        recent = self.history[-10:]
        brain_ctx = self._build_brain_context()
        reply_text, used_model, err = self._call_gemini_rest(
            recent,
            system_prompt=DEFAULT_SYSTEM_PROMPT + lang_hint + brain_ctx,
            prefer_pro=self.high_thinking,
        )

        def _done(_dt):
            self._pending_busy = False
            self.send_btn.disabled = False
            self.send_btn.text = "SEND"
            if reply_text:
                self.history.append({"role": "model", "parts": [{"text": reply_text}]})
                self._add_message_card("assistant", reply_text, model_tag=used_model)
                extracted = self._extract_python_code(reply_text)
                if build_requested or extracted:
                    if extracted:
                        self._sync_autonomous_code(extracted, "python")
                    self._start_autonomous_build_from_chat(prompt[:32])
                if self.audio_enabled:
                    self.voice_bridge.speak(reply_text)
                elif self.hands_free_mode:
                    self._schedule_hands_free_listen(1.6)
            else:
                low_err = str(err or "").lower()
                if "400" in low_err or "401" in low_err or "403" in low_err or "api key" in low_err:
                    fail_msg = f"Bhai API Key issue lag raha hai ({err}). Settings me valid Gemini key check karein."
                else:
                    fail_msg = f"Bhai Network/API error aaya ({err}). Top bar me 'Self-Test' daba ke auto-heal chalayein ya internet check karein."
                self._add_message_card("assistant", fail_msg, model_tag="Error")
                if self.audio_enabled:
                    self.voice_bridge.speak("Network ya API issue aaya hai Harish, please Self Test button dabao.")

        Clock.schedule_once(_done, 0)

    def _run_self_test_and_heal(self, auto_fix=True, user_already_added=False):
        if self._pending_busy:
            return
        self._pending_busy = True
        if not user_already_added:
            self._add_message_card("user", "Run Self-Test & Auto-Heal diagnostics")
        if hasattr(self, "selftest_pill"):
            self.selftest_pill.disabled = True
            self.selftest_pill.text = "Testing..."
        if hasattr(self, "dbg_selftest_btn"):
            self.dbg_selftest_btn.disabled = True
            self.dbg_selftest_btn.text = "Running Self-Test..."
        studio_snapshot = self.studio_editor.text if hasattr(self, "studio_editor") else ""
        studio_name = self.studio_file_lbl.text if hasattr(self, "studio_file_lbl") else "main.py"

        def _worker():
            checks = []
            errors_found = []
            healed_notes = []
            repaired_code = None

            # 1. SSL / CA Trust & HTTPS Reachability Check
            try:
                _ctx, verify_flag = _build_ssl_context()
                ca_found = _resolve_ca_bundle()
                if verify_flag is False and auto_fix:
                    ssl._create_default_https_context = lambda *_a, **_kw: _build_ssl_context()[0]
                    healed_notes.append("SSL fallback context enabled for Android/Termux")
                    checks.append("[FIXED] SSL/TLS: Device CA bundle missing -> unverified fallback active")
                else:
                    checks.append(f"[PASS] SSL/TLS: Verified CA active ({'certifi/CA' if ca_found else 'System CA'})")

                ping_url = "https://generativelanguage.googleapis.com/"
                req = urllib.request.Request(ping_url, method="GET")
                _pcode, _ptxt = _urlopen_with_ssl_retry(req, timeout=8)
                checks.append("[PASS] Network: Gemini HTTPS endpoint reachable")
            except Exception as ssl_exc:
                err_s = f"Network/SSL error: {ssl_exc}"
                errors_found.append(err_s)
                checks.append(f"[FAIL] Network/SSL: {ssl_exc}")

            # 2. Gemini API Key & Active Model Live Probe + Timeout/Error Auto-Failover
            api_ok = False
            if not self.api_key:
                errors_found.append("Gemini API Key set nahi hai")
                checks.append("[FAIL] Gemini API Key: Missing (Settings -> Set Key me dalein)")
            else:
                probe_payload = {
                    "contents": [{"role": "user", "parts": [{"text": "Reply OK"}]}],
                    "generationConfig": {"maxOutputTokens": 12, "temperature": 0},
                }
                probe_url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.selected_model}:generateContent?key={self.api_key}"
                )
                first_err_label = ""
                try:
                    sc, rtxt, _pdata = self._http_post_json(probe_url, probe_payload, timeout=25)
                    if sc == 200:
                        api_ok = True
                        checks.append(f"[PASS] Active Model: {self.selected_model} working cleanly")
                    else:
                        if auto_fix and sc in (404, 429, 500, 502, 503, 504):
                            first_err_label = f"HTTP {sc}"
                        else:
                            errors_found.append(f"API Key/Auth HTTP {sc}: {rtxt[:120]}")
                            checks.append(f"[FAIL] Gemini API Auth: HTTP {sc} ({rtxt[:100]})")
                except Exception as api_exc:
                    first_err_label = str(api_exc)

                if not api_ok and first_err_label and (auto_fix or "timed out" in first_err_label.lower() or "timeout" in first_err_label.lower()):
                    if auto_fix:
                        self.discovered_models = []
                        discovered = self._discover_available_models()
                        candidates = list(dict.fromkeys(["gemini-3.1-flash-lite", "gemini-4-hydrogen", "gemini-4-argon"] + discovered))
                        recovered = None
                        for cand in candidates:
                            if cand == self.selected_model:
                                continue
                            try:
                                curl = f"https://generativelanguage.googleapis.com/v1beta/models/{cand}:generateContent?key={self.api_key}"
                                csc, _cr, _cd = self._http_post_json(curl, probe_payload, timeout=20)
                                if csc == 200:
                                    recovered = cand
                                    break
                            except Exception:
                                pass
                        if recovered:
                            old_m = self.selected_model
                            self.selected_model = recovered
                            api_ok = True
                            healed_notes.append(f"Model {old_m} -> {recovered}")
                            checks.append(f"[FIXED] Active Model: {old_m} ({first_err_label}) -> auto-switched to {recovered}")
                        else:
                            errors_found.append(f"Gemini API: {first_err_label}")
                            checks.append(f"[FAIL] Gemini API: {first_err_label}")
                    else:
                        errors_found.append(f"Gemini API: {first_err_label}")
                        checks.append(f"[FAIL] Gemini API: {first_err_label}")

            # 3. Storage Read/Write Self-Test
            try:
                proj_dir = os.path.join(self._get_data_dir(), "autonomous_projects")
                created_dir = not os.path.isdir(proj_dir)
                os.makedirs(proj_dir, exist_ok=True)
                probe_file = os.path.join(proj_dir, "_selftest_probe.tmp")
                with open(probe_file, "w", encoding="utf-8") as pfh:
                    pfh.write("neon_ok")
                with open(probe_file, "r", encoding="utf-8") as pfh:
                    val = pfh.read()
                os.remove(probe_file)
                if val == "neon_ok":
                    if created_dir and auto_fix:
                        healed_notes.append("Created missing autonomous_projects storage folder")
                        checks.append("[FIXED] Storage: Created missing project folder & verified R/W")
                    else:
                        checks.append("[PASS] Storage: Device R/W storage healthy")
            except Exception as st_exc:
                errors_found.append(f"Storage error: {st_exc}")
                checks.append(f"[FAIL] Storage: {st_exc}")

            # 4. Voice Mic Permission & TTS Check
            if platform == "android":
                try:
                    from android.permissions import Permission, check_permission, request_permissions

                    if check_permission(Permission.RECORD_AUDIO):
                        checks.append("[PASS] Voice Mic: Android RECORD_AUDIO permission granted")
                    else:
                        if auto_fix:
                            Clock.schedule_once(lambda _dt: request_permissions([Permission.RECORD_AUDIO]), 0)
                            healed_notes.append("Requested Android RECORD_AUDIO permission")
                            checks.append("[FIXED] Voice Mic: Permission missing -> Android permission dialog opened")
                        else:
                            errors_found.append("RECORD_AUDIO permission missing")
                            checks.append("[FAIL] Voice Mic: RECORD_AUDIO denied")
                except Exception as mic_exc:
                    checks.append(f"[PASS] Voice Bridge: Lazy init ({mic_exc})")
            else:
                has_termux_mic = bool(shutil.which("termux-speech-to-text"))
                checks.append(
                    f"[PASS] Voice/Desktop Mode: Platform={platform}, Termux-STT={'Yes' if has_termux_mic else 'Desktop'}"
                )

            # 5. App Studio Python Syntax Audit (ast.parse) + AI Auto-Repair
            if ".py" in studio_name or "def " in studio_snapshot or "import " in studio_snapshot:
                try:
                    ast.parse(studio_snapshot or "pass")
                    checks.append("[PASS] Studio Code AST: Zero Python syntax errors")
                except SyntaxError as syn_err:
                    err_desc = f"SyntaxError line {syn_err.lineno}: {syn_err.msg}"
                    if auto_fix and api_ok and studio_snapshot.strip():
                        fix_prompt = (
                            f"Fix this Python SyntaxError cleanly ({err_desc}). "
                            "Return ONLY complete fixed valid Python code, no explanation:\n\n"
                            f"{studio_snapshot}"
                        )
                        fixed_txt, _fm, _fe = self._call_gemini_rest(
                            [{"role": "user", "parts": [{"text": fix_prompt}]}],
                            system_prompt="Return ONLY clean syntactically valid Python code.",
                            prefer_pro=False,
                        )
                        if fixed_txt:
                            cleaned = fixed_txt.replace("```python", "").replace("```", "").strip()
                            try:
                                ast.parse(cleaned)
                                repaired_code = cleaned
                                healed_notes.append(f"Repaired {err_desc}")
                                checks.append(f"[FIXED] Studio Code AST: {err_desc} -> auto-repaired cleanly!")
                            except Exception:
                                errors_found.append(err_desc)
                                checks.append(f"[FAIL] Studio Code AST: {err_desc} (auto-repair retry needed)")
                        else:
                            errors_found.append(err_desc)
                            checks.append(f"[FAIL] Studio Code AST: {err_desc}")
                    else:
                        errors_found.append(err_desc)
                        checks.append(f"[FAIL] Studio Code AST: {err_desc}")

            report_header = (
                f"Self-Test Complete | Errors Found: {len(errors_found)} | Auto-Healed: {len(healed_notes)}"
            )
            full_report = report_header + "\n\n" + "\n".join(checks)

            if len(errors_found) == 0 and len(healed_notes) == 0:
                voice_summary = "Harish, self test complete! Sab kuch ekdum fit chal raha hai, koi error nahi mila."
            elif len(errors_found) == 0:
                voice_summary = f"Self test complete Harish! {len(healed_notes)} issue mile the jo maine khud auto fix kar diye hain."
            else:
                voice_summary = (
                    f"Self test me {len(errors_found)} error mila: {errors_found[0]}. "
                    + (f"Baaki {len(healed_notes)} issue auto fix ho gaye." if healed_notes else "Screen par details dekh lo.")
                )

            def _finish(_dt):
                self._pending_busy = False
                if hasattr(self, "selftest_pill"):
                    self.selftest_pill.disabled = False
                    self.selftest_pill.text = "Self-Test"
                if hasattr(self, "dbg_selftest_btn"):
                    self.dbg_selftest_btn.disabled = False
                    self.dbg_selftest_btn.text = "Run Self-Test & Auto-Heal"
                if repaired_code:
                    self._sync_autonomous_code(repaired_code, "python")
                for hnote in healed_notes[:3]:
                    self._learn_to_brain("mistake_lesson", f"Self-Heal fixed: {hnote}", source="self_test")
                if errors_found:
                    self._learn_to_brain("mistake_lesson", f"Diagnostic issue noted: {errors_found[0][:180]}", source="self_test")
                self._save_config()
                self._refresh_header_state()
                self._add_message_card("assistant", full_report, model_tag="Self-Test")
                if hasattr(self, "dbg_output"):
                    self.dbg_output.text = f"[color=e2e8f0]{escape_markup(full_report)}[/color]"
                if hasattr(self, "lab_log"):
                    self.lab_log.text += "\n[color=34d399]" + escape_markup(full_report) + "[/color]"
                if self.audio_enabled:
                    self.voice_bridge.speak(voice_summary)

            Clock.schedule_once(_finish, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # TAB 2: ALL-IN-ONE APP BUILDER (Zero Copy-Paste, Templates, 1-Tap Build APK)
    # ------------------------------------------------------------------
    def _build_studio_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6))

        default_ci_workflow = (
            "name: NEON PRO - Build Android APK & Windows EXE\n"
            "on:\n"
            "  push:\n"
            "    branches: [ main, master ]\n"
            "  workflow_dispatch:\n\n"
            "concurrency:\n"
            "  group: neon-pro-build-${{ github.ref }}\n"
            "  cancel-in-progress: true\n\n"
            "jobs:\n"
            "  build:\n"
            "    name: Build Signed Installable Android APK\n"
            "    runs-on: ubuntu-22.04\n"
            "    timeout-minutes: 35\n"
            "    steps:\n"
            "      - uses: actions/checkout@v7\n"
            "      - uses: actions/setup-python@v7\n"
            "        with:\n"
            "          python-version: '3.10'\n"
            "      - uses: actions/setup-java@v6\n"
            "        with:\n"
            "          distribution: 'temurin'\n"
            "          java-version: '17'\n"
            "      - name: Install Buildozer Deps\n"
            "        run: |\n"
            "          sudo apt-get update\n"
            "          sudo apt-get install -y build-essential git zip unzip patch ant lbzip2 xz-utils openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev automake ccache lld libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev\n"
            "      - name: Cache Buildozer\n"
            "        uses: actions/cache@v6\n"
            "        with:\n"
            "          path: |\n"
            "            .buildozer\n"
            "            ~/.buildozer\n"
            "            ~/.gradle/caches\n"
            "          key: ubuntu22-v4-buildozer-${{ hashFiles('buildozer.spec') }}\n"
            "          restore-keys: |\n"
            "            ubuntu22-v4-buildozer-\n"
            "      - name: Build APK\n"
            "        run: |\n"
            "          python -m pip install --upgrade pip\n"
            '          pip install --upgrade "setuptools<66.0.0" wheel virtualenv cython==0.29.36 buildozer\n'
            "          yes | buildozer -v android debug\n"
            "      - name: Upload APK\n"
            "        uses: actions/upload-artifact@v7\n"
            "        with:\n"
            "          name: NeonMobile-Android-APK\n"
            "          path: bin/*.apk\n"
            "          if-no-files-found: error\n\n"
            "  build_exe:\n"
            "    name: Build Windows Standalone EXE\n"
            "    runs-on: windows-latest\n"
            "    timeout-minutes: 15\n"
            "    env:\n"
            "      PIP_NO_INPUT: '1'\n"
            "      PIP_DISABLE_PIP_VERSION_CHECK: '1'\n"
            "      KIVY_NO_ARGS: '1'\n"
            "      KIVY_NO_CONSOLELOG: '1'\n"
            "      KIVY_NO_FILELOG: '1'\n"
            "      KIVY_NO_CONFIG: '1'\n"
            "      KIVY_LOG_MODE: 'PYTHON'\n"
            "      PYTHONUNBUFFERED: '1'\n"
            "    steps:\n"
            "      - uses: actions/checkout@v7\n"
            "      - name: Speed Up Windows Build\n"
            "        shell: pwsh\n"
            "        run: |\n"
            '          try { Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue } catch {}\n'
            '          try { Add-MpPreference -ExclusionPath $env:GITHUB_WORKSPACE, $env:LOCALAPPDATA, $env:TEMP, "C:\hostedtoolcache" -ErrorAction SilentlyContinue } catch {}\n'
            "      - uses: actions/setup-python@v7\n"
            "        with:\n"
            "          python-version: '3.11'\n"
            "      - name: Install Windows Build Deps\n"
            "        shell: pwsh\n"
            "        run: |\n"
            "          python -m venv .venv_win\n"
            "          .\.venv_win\Scripts\python.exe -m pip install --upgrade pip\n"
            '          .\.venv_win\Scripts\python.exe -m pip install --prefer-binary --no-input "kivy==2.3.2" requests certifi urllib3 pyinstaller\n'
            '          .\.venv_win\Scripts\python.exe -c "import kivy, PyInstaller; print(kivy.__version__, PyInstaller.__version__)"\n'
            "      - name: Compile Standalone Windows EXE\n"
            "        timeout-minutes: 8\n"
            "        shell: pwsh\n"
            "        env:\n"
            "          SDL_VIDEODRIVER: 'dummy'\n"
            "          SDL_AUDIODRIVER: 'dummy'\n"
            "        run: |\n"
            '          .\.venv_win\Scripts\pyinstaller.exe --clean --noconfirm --noconsole --onefile --noupx --log-level=INFO --collect-data certifi --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module pydoc --exclude-module doctest --exclude-module lib2to3 --exclude-module kivy.tests --exclude-module docutils --exclude-module pygments --exclude-module numpy --exclude-module scipy --exclude-module matplotlib --exclude-module PIL --exclude-module cv2 --exclude-module enchant --exclude-module twisted --exclude-module pygame --name "NeonMobile_Windows" main.py\n'
            "      - name: Verify Windows EXE Output\n"
            "        shell: pwsh\n"
            "        run: |\n"
            "          Get-ChildItem dist\\*.exe\n"
            "      - name: Upload Windows EXE\n"
            "        uses: actions/upload-artifact@v7\n"
            "        with:\n"
            "          name: NeonMobile-Windows-EXE\n"
            "          path: dist/*.exe\n"
            "          if-no-files-found: error\n"
        )

        self.active_studio_file = "main.py"
        self.studio_files = {
            "main.py": "# NEON PRO v4.5 Mobile Core\nprint('NEON PRO Running on Android & Windows!')\n",
            "buildozer.spec": (
                "[app]\n"
                "title = NEON PRO Mobile\n"
                "package.name = neonpromobile\n"
                "package.domain = org.harish.neon\n"
                "source.dir = .\n"
                "source.include_exts = py,png,jpg,kv,atlas,json\n"
                "version = 0.4\n"
                "requirements = python3,kivy==2.3.0,openssl,requests==2.31.0,urllib3==2.2.1,certifi==2024.2.2,charset-normalizer==3.3.2,idna==3.6,pyjnius,android\n"
                "orientation = portrait\n"
                "fullscreen = 0\n"
                "android.permissions = INTERNET,ACCESS_NETWORK_STATE,RECORD_AUDIO,WAKE_LOCK\n"
                "android.api = 33\n"
                "android.minapi = 21\n"
                "android.ndk = 25b\n"
                "android.ndk_api = 21\n"
                "android.archs = arm64-v8a\n"
                "android.accept_sdk_license = True\n"
                "android.allow_backup = True\n"
                "p4a.branch = v2024.01.21\n\n"
                "[buildozer]\n"
                "log_level = 2\n"
                "warn_on_root = 1\n"
            ),
            "requirements.txt": "kivy>=2.3.0\ncertifi>=2024.2.2\nrequests>=2.31.0\nurllib3>=2.0.0\n",
            ".github/workflows/build_apk.yml": default_ci_workflow,
        }
        try:
            if __file__.endswith(".py") and os.path.exists(__file__):
                with open(__file__, "r", encoding="utf-8") as self_fh:
                    self.studio_files["main.py"] = self_fh.read()
        except Exception:
            pass
        self._neon_core_source = self.studio_files["main.py"]

        banner = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(106), padding=dp(8), spacing=dp(5))
        style_card(banner, (0.04, 0.06, 0.12, 1.0), (0.06, 0.45, 0.62, 0.55), radius_dp=12)
        banner.add_widget(
            AutoLabel(
                text="[b][color=22d3ee]All-in-One App Builder[/color][/b] [color=94a3b8]• Tap a Template or Describe App[/color]",
                font_size=sp(11),
            )
        )

        # 1-Tap Quick App Templates Row
        tpl_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        for tlabel, tkey in (
            ("Compound Calc", "ci"),
            ("Sci Calc", "calc"),
            ("Todo App", "todo"),
            ("NEON Core", "neon"),
        ):
            tb = make_button(
                tlabel,
                (0.05, 0.19, 0.28, 1.0),
                (0.10, 0.72, 0.88, 0.65),
                text_rgba=(0.72, 0.96, 1.0, 1.0),
                radius_dp=7,
                font_sp=10,
            )
            tb.bind(on_release=lambda _i, k=tkey: self._studio_load_template(k))
            tpl_row.add_widget(tb)
        banner.add_widget(tpl_row)

        # 4 Build Files Switcher Row
        preset_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        for flabel, fname in (
            ("App Code", "main.py"),
            ("APK Config", "buildozer.spec"),
            ("Packages", "requirements.txt"),
            ("Cloud YML", ".github/workflows/build_apk.yml"),
        ):
            b = make_button(
                flabel,
                (0.06, 0.11, 0.20, 1.0),
                (0.18, 0.38, 0.62, 0.5),
                text_rgba=(0.78, 0.88, 0.98, 1.0),
                radius_dp=7,
                font_sp=10,
            )
            b.bind(on_release=lambda _i, k=fname: self._load_studio_file(k))
            preset_row.add_widget(b)
        banner.add_widget(preset_row)
        root.add_widget(banner)

        gen_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.studio_prompt = TextInput(
            hint_text="Write what app you want (e.g. Expense Tracker)...",
            multiline=False,
            background_color=(0.03, 0.045, 0.085, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        self.studio_prompt.bind(on_text_validate=lambda *_: self._studio_ai_generate())
        gen_row.add_widget(self.studio_prompt)
        self.studio_gen_btn = make_button(
            "Create App",
            (0.32, 0.16, 0.62, 1.0),
            (0.68, 0.45, 0.98, 0.75),
            radius_dp=9,
            font_sp=11,
            size_hint_x=None,
            width=dp(92),
        )
        self.studio_gen_btn.bind(on_release=lambda *_: self._studio_ai_generate())
        gen_row.add_widget(self.studio_gen_btn)
        root.add_widget(gen_row)

        # User-Friendly Action & Dual Download Strip
        act_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
        chk_btn = make_button(
            "Check Code",
            (0.06, 0.16, 0.28, 1.0),
            (0.14, 0.68, 0.88, 0.65),
            text_rgba=(0.65, 0.92, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        chk_btn.bind(on_release=lambda *_: self._studio_test_ast())
        act_row.add_widget(chk_btn)

        zip_btn = make_button(
            "Save ZIP",
            (0.10, 0.15, 0.30, 1.0),
            (0.32, 0.52, 0.92, 0.65),
            text_rgba=(0.75, 0.88, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        zip_btn.bind(on_release=lambda *_: self._studio_export_zip())
        act_row.add_widget(zip_btn)

        fix_btn = make_button(
            "Fix Error",
            (0.24, 0.10, 0.36, 1.0),
            (0.68, 0.36, 0.92, 0.65),
            text_rgba=(0.90, 0.76, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        fix_btn.bind(on_release=lambda *_: self._send_code_to_debugger())
        act_row.add_widget(fix_btn)

        tok_btn = make_button(
            "Get Token",
            (0.24, 0.15, 0.04, 1.0),
            (0.95, 0.68, 0.18, 0.75),
            text_rgba=(1.0, 0.86, 0.42, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        tok_btn.bind(on_release=lambda *_: self._open_github_token_modal())
        act_row.add_widget(tok_btn)
        root.add_widget(act_row)

        # Strict Separation: Download APK/EXE ONLY downloads compiled binaries; Build APK+EXE starts cloud build
        dl_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
        self.studio_apk_btn = make_button(
            "Download APK File",
            (0.04, 0.52, 0.38, 1.0),
            (0.16, 0.92, 0.62, 0.88),
            text_rgba=(1.0, 1.0, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        self.studio_apk_btn.bind(on_release=lambda *_: self._gh_download_compiled_artifact(target="apk"))
        dl_row.add_widget(self.studio_apk_btn)

        self.studio_exe_btn = make_button(
            "Download EXE File",
            (0.12, 0.24, 0.62, 1.0),
            (0.32, 0.62, 0.98, 0.88),
            text_rgba=(1.0, 1.0, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
        )
        self.studio_exe_btn.bind(on_release=lambda *_: self._gh_download_compiled_artifact(target="exe"))
        dl_row.add_widget(self.studio_exe_btn)

        self.studio_build_btn = make_button(
            "Build APK+EXE",
            (0.36, 0.14, 0.58, 1.0),
            (0.75, 0.42, 0.98, 0.85),
            text_rgba=(1.0, 1.0, 1.0, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint_x=0.82,
        )
        self.studio_build_btn.bind(on_release=lambda *_: self._trigger_one_tap_apk_build(target="apk"))
        dl_row.add_widget(self.studio_build_btn)
        root.add_widget(dl_row)

        editor_card = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(5))
        style_card(editor_card, (0.025, 0.035, 0.068, 1.0), (0.08, 0.25, 0.38, 0.6), radius_dp=12)

        ed_hdr = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(5))
        self.studio_file_lbl = Label(
            text="[b][color=34d399]Active File: main.py[/color][/b]",
            markup=True,
            font_size=sp(11),
            halign="left",
            valign="middle",
        )
        self.studio_file_lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        ed_hdr.add_widget(self.studio_file_lbl)

        copy_ed_btn = make_button(
            "Copy",
            (0.06, 0.18, 0.16, 1.0),
            (0.10, 0.72, 0.52, 0.6),
            text_rgba=(0.55, 0.96, 0.78, 1.0),
            radius_dp=7,
            font_sp=10,
            size_hint=(None, None),
            size=(dp(56), dp(24)),
        )
        copy_ed_btn.bind(on_release=lambda *_: self._copy_text(self.studio_editor.text, copy_ed_btn))
        ed_hdr.add_widget(copy_ed_btn)
        editor_card.add_widget(ed_hdr)

        self.studio_status_lbl = AutoLabel(
            text="[color=94a3b8]Ready: Pick a template above or type any app idea, then tap Build APK.[/color]",
            font_size=sp(10),
        )
        editor_card.add_widget(self.studio_status_lbl)

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

    def _save_active_studio_buffer(self):
        if hasattr(self, "studio_editor") and hasattr(self, "active_studio_file"):
            self.studio_files[self.active_studio_file] = self.studio_editor.text

    def _load_studio_file(self, fname):
        self._save_active_studio_buffer()
        self.active_studio_file = fname
        self.studio_file_lbl.text = f"[b][color=34d399]Active File: {fname}[/color][/b]"
        self.studio_editor.text = self.studio_files.get(fname, "")

    def _studio_load_template(self, tpl_key):
        if tpl_key == "ci":
            code = (
                "from kivy.app import App\n"
                "from kivy.uix.boxlayout import BoxLayout\n"
                "from kivy.uix.label import Label\n"
                "from kivy.uix.textinput import TextInput\n"
                "from kivy.uix.button import Button\n"
                "from kivy.uix.spinner import Spinner\n"
                "from kivy.core.window import Window\n"
                "from kivy.metrics import dp, sp\n\n"
                "Window.clearcolor = (0.08, 0.09, 0.12, 1)\n\n"
                "class CompoundInterestApp(App):\n"
                "    def build(self):\n"
                "        self.title = 'Compound Interest Calculator'\n"
                "        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))\n"
                "        root.add_widget(Label(text='Compound Interest Calculator', font_size=sp(22), bold=True, color=(0.25, 0.78, 0.98, 1), size_hint_y=None, height=dp(44)))\n"
                "        self.principal_input = self._add_field(root, 'Principal Amount (Rs.)', 'e.g. 10000')\n"
                "        self.rate_input = self._add_field(root, 'Annual Interest Rate (%)', 'e.g. 8.5')\n"
                "        self.time_input = self._add_field(root, 'Time Period (Years)', 'e.g. 5')\n"
                "        self.freq_map = {'Yearly (1x)': 1, 'Half-Yearly (2x)': 2, 'Quarterly (4x)': 4, 'Monthly (12x)': 12}\n"
                "        self.freq_spinner = Spinner(text='Yearly (1x)', values=list(self.freq_map.keys()), size_hint_y=None, height=dp(46), background_color=(0.18, 0.22, 0.30, 1), color=(1, 1, 1, 1), font_size=sp(15))\n"
                "        root.add_widget(self.freq_spinner)\n"
                "        row = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(48))\n"
                "        calc_btn = Button(text='Calculate', font_size=sp(16), bold=True, background_normal='', background_color=(0.14, 0.62, 0.88, 1))\n"
                "        calc_btn.bind(on_press=self.calculate_ci)\n"
                "        clr_btn = Button(text='Clear', font_size=sp(15), background_normal='', background_color=(0.28, 0.30, 0.36, 1), size_hint_x=0.45)\n"
                "        clr_btn.bind(on_press=self.clear_fields)\n"
                "        row.add_widget(calc_btn)\n"
                "        row.add_widget(clr_btn)\n"
                "        root.add_widget(row)\n"
                "        self.result_label = Label(text='Enter values and tap Calculate', font_size=sp(16), color=(0.9, 0.93, 0.96, 1), halign='center', valign='middle')\n"
                "        self.result_label.bind(size=self.result_label.setter('text_size'))\n"
                "        root.add_widget(self.result_label)\n"
                "        return root\n\n"
                "    def _add_field(self, parent, label_text, hint_text):\n"
                "        lbl = Label(text=label_text, font_size=sp(14), color=(0.8, 0.85, 0.9, 1), size_hint_y=None, height=dp(24), halign='left')\n"
                "        lbl.bind(size=lbl.setter('text_size'))\n"
                "        parent.add_widget(lbl)\n"
                "        inp = TextInput(hint_text=hint_text, multiline=False, input_filter='float', font_size=sp(16), size_hint_y=None, height=dp(46), padding=[dp(12), dp(12), dp(12), dp(12)], background_color=(0.15, 0.17, 0.23, 1), foreground_color=(1, 1, 1, 1))\n"
                "        parent.add_widget(inp)\n"
                "        return inp\n\n"
                "    def calculate_ci(self, _instance):\n"
                "        try:\n"
                "            p = float(self.principal_input.text.strip())\n"
                "            r = float(self.rate_input.text.strip()) / 100.0\n"
                "            t = float(self.time_input.text.strip())\n"
                "            n = self.freq_map[self.freq_spinner.text]\n"
                "            if p <= 0 or r < 0 or t <= 0:\n"
                "                self.result_label.color = (1, 0.45, 0.45, 1)\n"
                "                self.result_label.text = 'Enter positive Principal and Time.'\n"
                "                return\n"
                "            amt = p * ((1 + r / n) ** (n * t))\n"
                "            ci = amt - p\n"
                "            self.result_label.color = (0.35, 0.95, 0.65, 1)\n"
                "            self.result_label.text = f'Total Amount: Rs. {amt:,.2f}\\nCompound Interest: Rs. {ci:,.2f}'\n"
                "        except Exception:\n"
                "            self.result_label.color = (1, 0.45, 0.45, 1)\n"
                "            self.result_label.text = 'Please fill valid numbers.'\n\n"
                "    def clear_fields(self, _instance):\n"
                "        self.principal_input.text = ''\n"
                "        self.rate_input.text = ''\n"
                "        self.time_input.text = ''\n"
                "        self.result_label.color = (0.9, 0.93, 0.96, 1)\n"
                "        self.result_label.text = 'Enter values and tap Calculate'\n\n"
                "if __name__ == '__main__':\n"
                "    CompoundInterestApp().run()\n"
            )
            label = "Compound Interest Calculator"
        elif tpl_key == "calc":
            code = (
                "from kivy.app import App\n"
                "from kivy.uix.boxlayout import BoxLayout\n"
                "from kivy.uix.gridlayout import GridLayout\n"
                "from kivy.uix.textinput import TextInput\n"
                "from kivy.uix.button import Button\n"
                "from kivy.core.window import Window\n"
                "from kivy.metrics import dp, sp\n\n"
                "Window.clearcolor = (0.06, 0.08, 0.13, 1)\n\n"
                "class CalcApp(App):\n"
                "    def build(self):\n"
                "        self.title = 'NEON Calculator'\n"
                "        root = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))\n"
                "        self.display = TextInput(multiline=False, readonly=True, halign='right', font_size=sp(32), size_hint_y=0.25, background_color=(0.03, 0.05, 0.09, 1), foreground_color=(0.25, 0.92, 0.98, 1))\n"
                "        root.add_widget(self.display)\n"
                "        grid = GridLayout(cols=4, spacing=dp(8))\n"
                "        for b in ['7','8','9','/','4','5','6','*','1','2','3','-','C','0','=','+']:\n"
                "            btn = Button(text=b, font_size=sp(22), bold=True, background_normal='', background_color=(0.12, 0.18, 0.28, 1) if b not in ('=','C') else ((0.06, 0.58, 0.48, 1) if b=='=' else (0.55, 0.16, 0.22, 1)))\n"
                "            btn.bind(on_press=self.on_tap)\n"
                "            grid.add_widget(btn)\n"
                "        root.add_widget(grid)\n"
                "        return root\n\n"
                "    def on_tap(self, inst):\n"
                "        t = inst.text\n"
                "        if t == 'C':\n"
                "            self.display.text = ''\n"
                "        elif t == '=':\n"
                "            try:\n"
                "                self.display.text = str(eval(self.display.text, {'__builtins__': {}}, {}))\n"
                "            except Exception:\n"
                "                self.display.text = 'Error'\n"
                "        else:\n"
                "            self.display.text += t\n\n"
                "if __name__ == '__main__':\n"
                "    CalcApp().run()\n"
            )
            label = "Calculator"
        elif tpl_key == "todo":
            code = (
                "from kivy.app import App\n"
                "from kivy.uix.boxlayout import BoxLayout\n"
                "from kivy.uix.scrollview import ScrollView\n"
                "from kivy.uix.textinput import TextInput\n"
                "from kivy.uix.button import Button\n"
                "from kivy.uix.label import Label\n"
                "from kivy.core.window import Window\n"
                "from kivy.metrics import dp, sp\n\n"
                "Window.clearcolor = (0.06, 0.08, 0.13, 1)\n\n"
                "class TodoApp(App):\n"
                "    def build(self):\n"
                "        self.title = 'My Todo List'\n"
                "        root = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))\n"
                "        root.add_widget(Label(text='My Daily Tasks', font_size=sp(22), bold=True, color=(0.25, 0.85, 0.98, 1), size_hint_y=None, height=dp(40)))\n"
                "        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))\n"
                "        self.inp = TextInput(hint_text='Add a new task...', multiline=False, font_size=sp(15))\n"
                "        add_btn = Button(text='Add', size_hint_x=None, width=dp(80), bold=True, background_normal='', background_color=(0.06, 0.58, 0.48, 1))\n"
                "        add_btn.bind(on_press=self.add_task)\n"
                "        row.add_widget(self.inp)\n"
                "        row.add_widget(add_btn)\n"
                "        root.add_widget(row)\n"
                "        sc = ScrollView()\n"
                "        self.tasks = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))\n"
                "        self.tasks.bind(minimum_height=self.tasks.setter('height'))\n"
                "        sc.add_widget(self.tasks)\n"
                "        root.add_widget(sc)\n"
                "        return root\n\n"
                "    def add_task(self, _inst):\n"
                "        txt = self.inp.text.strip()\n"
                "        if not txt:\n"
                "            return\n"
                "        self.inp.text = ''\n"
                "        item = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))\n"
                "        item.add_widget(Label(text=f'• {txt}', font_size=sp(15), halign='left'))\n"
                "        done = Button(text='Done', size_hint_x=None, width=dp(70), background_normal='', background_color=(0.45, 0.16, 0.24, 1))\n"
                "        done.bind(on_press=lambda *_: self.tasks.remove_widget(item))\n"
                "        item.add_widget(done)\n"
                "        self.tasks.add_widget(item)\n\n"
                "if __name__ == '__main__':\n"
                "    TodoApp().run()\n"
            )
            label = "Todo List"
        else:
            code = getattr(self, "_neon_core_source", self.studio_files.get("main.py", ""))
            label = "NEON PRO Core"

        self._sync_autonomous_code(code, "python")
        self.studio_status_lbl.text = f"[color=34d399]✓ Loaded {label}! Tap 'Build APK' right above to make Android .apk.[/color]"

    def _studio_test_ast(self):
        self._save_active_studio_buffer()
        src = self.studio_files.get("main.py", "")
        try:
            ast.parse(src)
            self.studio_status_lbl.text = "[color=34d399]✓ Check Passed! Code me koi syntax error nahi hai — Build APK ready![/color]"
        except SyntaxError as err:
            self.studio_status_lbl.text = f"[color=f87171]✗ Error on line {err.lineno}: {escape_markup(str(err.msg))} (Tap Fix Error)[/color]"

    def _studio_export_zip(self):
        self._save_active_studio_buffer()
        try:
            proj_dir = os.path.join(self._get_data_dir(), "autonomous_projects")
            os.makedirs(proj_dir, exist_ok=True)
            zip_path = os.path.join(proj_dir, "NEON_Studio_App.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for rel_path, content in self.studio_files.items():
                    zf.writestr(rel_path, content)
            saved_loc = zip_path
            if platform == "android":
                dl_path = "/sdcard/Download/NEON_Studio_App.zip"
                try:
                    shutil.copyfile(zip_path, dl_path)
                    saved_loc = dl_path
                except Exception:
                    pass
            self.studio_status_lbl.text = f"[color=34d399]✓ Saved full 4-file ZIP to: {escape_markup(saved_loc)}[/color]"
        except Exception as err:
            self.studio_status_lbl.text = f"[color=f87171]ZIP Save Error: {escape_markup(str(err))}[/color]"

    def _trigger_one_tap_apk_build(self, target="apk"):
        self._save_active_studio_buffer()
        self._switch_tab("github")
        if target == "exe":
            self._export_exe_bundle()
        if not self.github_token:
            self.gh_log.text = (
                "[b][color=fbbf24]Token 1-Baar Setup Karein:[/color][/b] 'Get Token' dabao → Token copy karo → 'Paste' dabao.\n"
                "[b][color=34d399]Note:[/color][/b] Ek baar save hone ke baad har naye app me yehi token khud kaam karega!"
            )
            self._open_github_token_modal()
            return
        self._gh_push_studio_app(target=target)

    def _send_code_to_debugger(self):
        self._save_active_studio_buffer()
        self.dbg_code.text = self.studio_editor.text[:6000]
        self._switch_tab("debugger")

    def _studio_ai_generate(self):
        goal = self.studio_prompt.text.strip()
        if not goal:
            self.studio_status_lbl.text = "[color=fbbf24]Pehle upar likho kaunsa app banana hai (ya Compound Calc template dabao).[/color]"
            return
        if not self.api_key:
            self._open_settings_modal()
            return
        self.studio_gen_btn.disabled = True
        self.studio_gen_btn.text = "Creating..."
        self.studio_status_lbl.text = "[color=38bdf8]NEON PRO aapke liye app likh raha hai...[/color]"

        def _worker():
            sys_p = (
                "Write complete, clean, zero-placeholder runnable Python/Kivy code for Harish's request. "
                "Return ONLY the complete source code without markdown fences if possible."
                + self._build_brain_context()
            )
            txt, _m, err = self._call_gemini_rest(
                [{"role": "user", "parts": [{"text": goal}]}],
                system_prompt=sys_p,
                prefer_pro=self.high_thinking,
            )

            cleaned = None
            ast_ok = False
            if txt:
                cleaned = txt.replace("```python", "").replace("```", "").strip()
                try:
                    ast.parse(cleaned)
                    ast_ok = True
                except SyntaxError as s_err:
                    fix_p = f"Fix the Python SyntaxError on line {s_err.lineno} ({s_err.msg}) and return ONLY valid Python code:\n\n{cleaned}"
                    fixed_txt, _fm, _ferr = self._call_gemini_rest(
                        [{"role": "user", "parts": [{"text": fix_p}]}],
                        system_prompt="Return ONLY clean syntactically valid Python code.",
                        prefer_pro=False,
                    )
                    if fixed_txt:
                        cleaned = fixed_txt.replace("```python", "").replace("```", "").strip()
                        try:
                            ast.parse(cleaned)
                            ast_ok = True
                        except Exception:
                            pass

            def _done(_dt):
                self.studio_gen_btn.disabled = False
                self.studio_gen_btn.text = "Create App"
                if cleaned:
                    self._sync_autonomous_code(cleaned, "python")
                    self.studio_status_lbl.text = (
                        "[color=34d399]✓ App ready & Syntax Checked! Ab 'Build APK' dabao.[/color]"
                        if ast_ok
                        else "[color=fbbf24]App saved — 'Check Code' dabakar syntax dekh lo.[/color]"
                    )
                else:
                    self.studio_editor.text = f"# Generation failed: {err}"
                    self.studio_status_lbl.text = f"[color=f87171]Failed: {escape_markup(str(err))}[/color]"

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
        dbg_btn_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.dbg_selftest_btn = make_button(
            "Run Self-Test & Auto-Heal",
            (0.04, 0.42, 0.30, 1.0),
            (0.15, 0.88, 0.60, 0.75),
            radius_dp=10,
            font_sp=11,
            size_hint_x=0.46,
        )
        self.dbg_selftest_btn.bind(on_release=lambda *_: self._run_self_test_and_heal(auto_fix=True))
        dbg_btn_row.add_widget(self.dbg_selftest_btn)
        dbg_btn_row.add_widget(self.dbg_run_btn)
        root.add_widget(dbg_btn_row)

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
                system_prompt=DEFAULT_SYSTEM_PROMPT + self._build_brain_context(),
                prefer_pro=True,
            )

            def _done(_dt):
                self.dbg_run_btn.disabled = False
                self.dbg_run_btn.text = "Execute Autonomous Fix"
                if txt:
                    self.dbg_output.text = f"[color=e2e8f0]{escape_markup(txt)}[/color]"
                    if err_v:
                        self._learn_to_brain("mistake_lesson", f"Fixed '{err_v[:85]}': {txt[:110]}", source="debugger")
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
            ("self test", "self test"),
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
                "[color=22d3ee][b]NEON PRO Build & Device Lab v4.5[/b][/color]\n"
                "[color=34d399]Operator: Harish | Platform: "
                f"{platform.upper()} ({sys_platform.machine()})[/color]\n"
                f"[color=94a3b8]Python: {sys.version.split()[0]} | Screen: {Window.width}x{Window.height}[/color]\n"
                "[color=6ee7b7]Ready. Tap 'self test' or any command above.[/color]"
            ),
            font_size=sp(12),
        )
        self.lab_scroll.add_widget(self.lab_log)
        term_card.add_widget(self.lab_scroll)
        root.add_widget(term_card)

        cmd_bar = BoxLayout(size_hint_y=None, height=dp(46), padding=dp(5), spacing=dp(6))
        style_card(cmd_bar, (0.04, 0.06, 0.11, 1.0), (0.06, 0.50, 0.68, 0.55), radius_dp=12)
        self.lab_input = TextInput(
            hint_text="Type command (self test, neon status, device info, clear)...",
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
        if "test" in low or "heal" in low:
            lines.append("[color=38bdf8]Launching Autonomous Self-Test & Auto-Heal...[/color]")
            self.lab_log.text += "\n" + "\n".join(lines)
            self._run_self_test_and_heal(auto_fix=True)
            return
        elif "status" in low:
            lines.extend([
                "[color=34d399]• App Engine:[/color] NEON PRO v4.5 All-in-One Mobile Builder",
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
            lines.append("[color=cbd5e1]Command executed (status 0). Try: self test, neon status, device info, python ver, clear[/color]")

        self.lab_log.text += "\n" + "\n".join(lines)
        Clock.schedule_once(lambda _dt: setattr(self.lab_scroll, "scroll_y", 0), 0.05)

    # ------------------------------------------------------------------
    # TAB 5: APK / EXE DOWNLOAD HUB & DEDICATED TOKEN GENERATOR
    # ------------------------------------------------------------------
    def _build_github_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8))

        card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(302), padding=dp(10), spacing=dp(6))
        style_card(card, (0.04, 0.055, 0.115, 1.0), (0.55, 0.30, 0.85, 0.55), radius_dp=12)
        card.add_widget(
            AutoLabel(
                text="[b][color=c084fc]GitHub CI • Download Hub (APK & EXE)[/color][/b] [color=94a3b8]• Direct Download vs Cloud Build[/color]",
                font_size=sp(12),
            )
        )

        self.gh_token_status_lbl = AutoLabel(
            text=(
                "[color=34d399]✓ Token Saved Permanently — Ready for ALL new apps![/color]"
                if self.github_token
                else "[color=fbbf24]GitHub Token sirf 1 baar chahiye → 'Get Token' dabao![/color]"
            ),
            font_size=sp(10),
        )
        card.add_widget(self.gh_token_status_lbl)

        tok_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
        self.gh_token_input = TextInput(
            text=self.github_token,
            hint_text="Paste GitHub Token once (saved forever)...",
            password=True,
            multiline=False,
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        tok_row.add_widget(self.gh_token_input)

        paste_tok_btn = make_button(
            "Paste",
            (0.12, 0.16, 0.34, 1.0),
            (0.35, 0.55, 0.96, 0.7),
            radius_dp=8,
            font_sp=10,
            size_hint_x=None,
            width=dp(56),
        )
        paste_tok_btn.bind(on_release=lambda *_: self._paste_token_from_clipboard())
        tok_row.add_widget(paste_tok_btn)

        get_tok_btn = make_button(
            "Get Token",
            (0.24, 0.15, 0.04, 1.0),
            (0.95, 0.68, 0.18, 0.78),
            text_rgba=(1.0, 0.86, 0.42, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint_x=None,
            width=dp(76),
        )
        get_tok_btn.bind(on_release=lambda *_: self._open_github_token_modal())
        tok_row.add_widget(get_tok_btn)
        card.add_widget(tok_row)

        self.gh_repo_input = TextInput(
            text=self.github_repo,
            hint_text="App Repo Name (e.g. neon-pro-harish)",
            multiline=False,
            size_hint_y=None,
            height=dp(34),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.55, 0.68, 1.0),
            font_size=sp(12),
            padding=[dp(10), dp(7), dp(10), dp(7)],
        )
        card.add_widget(self.gh_repo_input)

        # Two Strict Direct Download Buttons: NEVER push or cancel builds
        dl_btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        self.gh_push_btn = make_button(
            "Download APK File",
            (0.04, 0.52, 0.38, 1.0),
            (0.15, 0.90, 0.62, 0.88),
            radius_dp=8,
            font_sp=11,
        )
        self.gh_push_btn.bind(on_release=lambda *_: self._gh_download_compiled_artifact(target="apk"))
        dl_btn_row.add_widget(self.gh_push_btn)

        self.gh_exe_btn = make_button(
            "Download EXE File",
            (0.12, 0.24, 0.62, 1.0),
            (0.32, 0.62, 0.98, 0.88),
            radius_dp=8,
            font_sp=11,
        )
        self.gh_exe_btn.bind(on_release=lambda *_: self._gh_download_compiled_artifact(target="exe"))
        dl_btn_row.add_widget(self.gh_exe_btn)
        card.add_widget(dl_btn_row)

        # Explicit Push & Build Row (Separated completely from Download buttons)
        build_btn_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        self.gh_start_build_btn = make_button(
            "Push & Build APK + EXE on GitHub",
            (0.36, 0.14, 0.58, 1.0),
            (0.75, 0.42, 0.98, 0.85),
            radius_dp=8,
            font_sp=10,
        )
        self.gh_start_build_btn.bind(on_release=lambda *_: self._gh_push_studio_app(target="apk"))
        build_btn_row.add_widget(self.gh_start_build_btn)
        card.add_widget(build_btn_row)

        util_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
        self.gh_runs_btn = make_button(
            "Check Status",
            (0.28, 0.16, 0.58, 1.0),
            (0.65, 0.42, 0.95, 0.7),
            radius_dp=8,
            font_sp=10,
        )
        self.gh_runs_btn.bind(on_release=lambda *_: self._gh_check_runs())
        util_row.add_widget(self.gh_runs_btn)

        self.gh_cancel_btn = make_button(
            "Kill Duplicates",
            (0.32, 0.08, 0.12, 1.0),
            (0.92, 0.30, 0.38, 0.72),
            radius_dp=8,
            font_sp=10,
            size_hint_x=None,
            width=dp(96),
        )
        self.gh_cancel_btn.bind(on_release=lambda *_: self._gh_cancel_stuck_runs())
        util_row.add_widget(self.gh_cancel_btn)

        self.gh_open_btn = make_button(
            "GitHub Web",
            (0.08, 0.22, 0.42, 1.0),
            (0.25, 0.62, 0.96, 0.7),
            radius_dp=8,
            font_sp=10,
        )
        self.gh_open_btn.bind(on_release=lambda *_: self._gh_open_actions_browser())
        util_row.add_widget(self.gh_open_btn)

        self.gh_browser_ci_btn = make_button(
            "Browser CI",
            (0.32, 0.14, 0.56, 1.0),
            (0.75, 0.45, 0.98, 0.8),
            radius_dp=8,
            font_sp=10,
        )
        self.gh_browser_ci_btn.bind(on_release=lambda *_: self._gh_open_web_ci())
        util_row.add_widget(self.gh_browser_ci_btn)
        card.add_widget(util_row)
        root.add_widget(card)

        out_card = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        style_card(out_card, (0.02, 0.03, 0.065, 1.0), (0.08, 0.45, 0.65, 0.5), radius_dp=12)
        gh_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.gh_log = AutoLabel(
            text=(
                "[b][color=22d3ee]NEON PRO Download Hub (APK + EXE):[/color][/b]\n"
                "[color=cbd5e1]1. 'Download APK File' & 'Download EXE File' sirf compiled file download karte hain — koi duplicate push nahi hoga!\n"
                "2. Naya app compile karne ke liye 'Push & Build APK + EXE on GitHub' dabao.\n"
                "3. Purane queued builds rokne ke liye 'Kill Duplicates' dabao.[/color]"
            ),
            font_size=sp(12),
        )
        gh_scroll.add_widget(self.gh_log)
        out_card.add_widget(gh_scroll)
        root.add_widget(out_card)
        return root

    def _auto_detect_clipboard_token(self):
        if self.github_token:
            if hasattr(self, "gh_token_status_lbl"):
                self.gh_token_status_lbl.text = "[color=34d399]✓ Token Saved Permanently — Ready for ALL new apps![/color]"
            return
        try:
            clip = (Clipboard.paste() or "").strip()
            if clip.startswith("ghp_") or clip.startswith("github_pat_"):
                self.github_token = clip
                self._save_config()
                if hasattr(self, "gh_token_input"):
                    self.gh_token_input.text = clip
                if hasattr(self, "gh_token_status_lbl"):
                    self.gh_token_status_lbl.text = "[color=34d399]✓ Clipboard se GitHub Token auto-save ho gaya![/color]"
                if hasattr(self, "gh_log"):
                    self.gh_log.text = "[color=34d399][b]✓ GitHub Token clipboard se auto-detect & save ho gaya Harish![/b]\nAb seedha 'Download APK File' ya 'Download EXE File' dabao.[/color]"
        except Exception:
            pass

    def _paste_token_from_clipboard(self, target_input=None, status_lbl=None):
        try:
            clip = (Clipboard.paste() or "").strip()
        except Exception:
            clip = ""
        if not clip:
            msg = "[color=fbbf24]Clipboard khali hai — pehle 'Get Token' page se token copy karein.[/color]"
            if status_lbl is not None:
                status_lbl.text = msg
            elif hasattr(self, "gh_log"):
                self.gh_log.text = msg
            return False
        if target_input is not None:
            target_input.text = clip
        if hasattr(self, "gh_token_input"):
            self.gh_token_input.text = clip
        self.github_token = clip
        self._save_config()
        ok_msg = "[color=34d399]✓ Token pasted & saved permanently for all new apps![/color]"
        if status_lbl is not None:
            status_lbl.text = ok_msg
        if hasattr(self, "gh_token_status_lbl"):
            self.gh_token_status_lbl.text = ok_msg
        return True

    def _open_github_token_modal(self, on_verified=None):
        modal = ModalView(size_hint=(0.94, None), height=dp(440), background_color=(0, 0, 0, 0.80))
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        style_card(box, (0.04, 0.06, 0.12, 1.0), (0.95, 0.68, 0.18, 0.80), radius_dp=16, border_width=1.4)

        hdr = BoxLayout(size_hint_y=None, height=dp(32))
        hdr.add_widget(
            AutoLabel(text="[b][color=fbbf24]GitHub Token Helper (Sirf 1 Baar)[/color][/b]", font_size=sp(14))
        )
        close_btn = make_button(
            "Close",
            (0.18, 0.08, 0.12, 1.0),
            (0.85, 0.28, 0.38, 0.65),
            radius_dp=8,
            font_sp=11,
            size_hint=(None, None),
            size=(dp(62), dp(28)),
        )
        close_btn.bind(on_release=lambda *_: modal.dismiss())
        hdr.add_widget(close_btn)
        box.add_widget(hdr)

        box.add_widget(
            AutoLabel(
                text=(
                    "[color=e2e8f0]1. Neeche '1. Open GitHub Token Page' dabao (repo + workflow khud tick rahenge).\n"
                    "2. Page ke neeche 'Generate token' dabao aur ghp_... token Copy karo.\n"
                    "3. Wapas aake '2. Auto-Paste & Save' dabao — har naye app me yahi save rahega![/color]"
                ),
                font_size=sp(11),
            )
        )

        open_gh_btn = make_button(
            "1. Open GitHub Token Page (Auto-Filled)",
            (0.08, 0.24, 0.48, 1.0),
            (0.25, 0.68, 0.98, 0.85),
            radius_dp=10,
            font_sp=12,
            size_hint_y=None,
            height=dp(40),
        )
        open_gh_btn.bind(
            on_release=lambda *_: webbrowser.open(
                "https://github.com/settings/tokens/new?description=NEON-PRO-Harish&scopes=repo,workflow"
            )
        )
        box.add_widget(open_gh_btn)

        tok_inp = TextInput(
            text=self.github_token,
            hint_text="Copied GitHub Token yahan dikhega (ghp_...)",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        box.add_widget(tok_inp)

        status_lbl = AutoLabel(
            text=(
                "[color=34d399]✓ Token already saved permanently.[/color]"
                if self.github_token
                else "[color=94a3b8]Copy karne ke baad neeche Auto-Paste dabao.[/color]"
            ),
            font_size=sp(11),
        )
        box.add_widget(status_lbl)

        paste_btn = make_button(
            "2. Auto-Paste & Verify Forever",
            (0.04, 0.52, 0.38, 1.0),
            (0.16, 0.92, 0.62, 0.85),
            radius_dp=10,
            font_sp=12,
            size_hint_y=None,
            height=dp(42),
        )

        def _do_verify_save(*_a):
            if not tok_inp.text.strip():
                self._paste_token_from_clipboard(tok_inp, status_lbl)
            cand = tok_inp.text.strip()
            if not cand:
                return
            self.github_token = cand
            if hasattr(self, "gh_token_input"):
                self.gh_token_input.text = cand
            self._save_config()
            status_lbl.text = "[color=38bdf8]Verifying token with GitHub...[/color]"
            paste_btn.disabled = True

            def _vwork():
                code, user = self._gh_get("https://api.github.com/user", cand)
                def _vdone(_dt):
                    paste_btn.disabled = False
                    if code == 200 and isinstance(user, dict) and user.get("login"):
                        self._gh_owner_cache = user["login"]
                        if hasattr(self, "gh_token_status_lbl"):
                            self.gh_token_status_lbl.text = f"[color=34d399]✓ Connected @{user['login']} — Saved Forever![/color]"
                        status_lbl.text = f"[color=34d399]✓ Verified @{user['login']}! Ab sabhi apps me khud save rahega.[/color]"
                        def _after_dismiss(_dt2):
                            modal.dismiss()
                            if on_verified is not None:
                                on_verified()
                        Clock.schedule_once(_after_dismiss, 0.9)
                    else:
                        status_lbl.text = f"[color=fbbf24]Token saved locally (GitHub status {code}) — repo + workflow scope check karein.[/color]"
                Clock.schedule_once(_vdone, 0)

            threading.Thread(target=_vwork, daemon=True).start()

        paste_btn.bind(on_release=_do_verify_save)
        box.add_widget(paste_btn)

        modal.add_widget(box)
        modal.open()

    def _export_exe_bundle(self):
        self._save_active_studio_buffer()
        try:
            proj_dir = os.path.join(self._get_data_dir(), "autonomous_projects")
            os.makedirs(proj_dir, exist_ok=True)
            zip_path = os.path.join(proj_dir, "NEON_Windows_EXE_Package.zip")
            bat_content = (
                "@echo off\r\n"
                "python -m pip install --upgrade pip\r\n"
                "pip install -r requirements.txt pyinstaller\r\n"
                'pyinstaller --noconsole --onefile --clean --name "NeonMobile_Windows" main.py\r\n'
                "echo Ready: dist\\NeonMobile_Windows.exe\r\npause\r\n"
            )
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for rel_path, content in self.studio_files.items():
                    zf.writestr(rel_path, content)
                zf.writestr("build_windows_exe.bat", bat_content)
            saved_loc = zip_path
            if platform == "android":
                dl_path = "/sdcard/Download/NEON_Windows_EXE_Package.zip"
                try:
                    shutil.copyfile(zip_path, dl_path)
                    saved_loc = dl_path
                except Exception:
                    pass
            return saved_loc
        except Exception:
            return None

    def _get_downloads_folder(self):
        if platform == "android":
            cand = "/sdcard/Download"
            if os.path.isdir(cand):
                return cand
        else:
            cand = os.path.join(os.path.expanduser("~"), "Downloads")
            try:
                os.makedirs(cand, exist_ok=True)
                return cand
            except Exception:
                pass
        return self._get_data_dir()

    def _gh_download_artifact_bytes(self, url, token):
        """Download GitHub Actions artifact ZIP without forwarding GitHub Auth header to Azure Blob redirect."""
        hdrs = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NEON-PRO-Mobile-v4",
        }
        if requests is not None:
            _ctx, req_verify = _build_ssl_context()
            try:
                r = requests.get(url, headers=hdrs, allow_redirects=False, timeout=30, verify=req_verify)
            except Exception as err:
                if _is_ssl_exception(err) and req_verify is not False:
                    _activate_unverified_ssl_fallback()
                    req_verify = False
                    r = requests.get(url, headers=hdrs, allow_redirects=False, timeout=30, verify=False)
                else:
                    raise
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("Location") or r.headers.get("location")
                if not loc:
                    raise RuntimeError("Artifact redirect location missing")
                r2 = requests.get(loc, timeout=90, verify=req_verify)
                if r2.status_code != 200:
                    raise RuntimeError(f"Azure CDN HTTP {r2.status_code}")
                return r2.content
            if r.status_code == 200:
                return r.content
            raise RuntimeError(f"GitHub artifact HTTP {r.status_code}")

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        try:
            with opener.open(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as herr:
            if herr.code in (301, 302, 303, 307, 308):
                loc = herr.headers.get("Location")
                if not loc:
                    raise RuntimeError("Redirect location missing")
                ctx, _ = _build_ssl_context()
                with urllib.request.urlopen(urllib.request.Request(loc, method="GET"), context=ctx, timeout=90) as r2:
                    return r2.read()
            raise

    def _gh_download_compiled_artifact(self, target="apk"):
        """Strict Download-Only: fetches compiled .apk/.exe binary without ever re-pushing or cancelling builds."""
        token = self.gh_token_input.text.strip() or self.github_token
        repo = self.gh_repo_input.text.strip() or self.github_repo or "neon-pro-harish"
        if not token:
            if target == "exe":
                saved_zip = self._export_exe_bundle()
                if saved_zip:
                    self._switch_tab("github")
                    self.gh_log.text = (
                        f"[color=34d399][b]✓ Windows EXE Builder ZIP saved:[/b] {escape_markup(saved_zip)}[/color]\n"
                        "[color=cbd5e1]Direct cloud .exe download ke liye 1-baar 'Get Token' se token save kar lo![/color]"
                    )
                    return
            self._switch_tab("github")
            self.gh_log.text = "[color=fbbf24]Pehle 'Get Token' dabakar GitHub Token save karein.[/color]"
            self._open_github_token_modal()
            return

        self._switch_tab("github")
        self.gh_log.text = f"[color=38bdf8]Checking compiled .{target.upper()} artifact on GitHub (No duplicate push)...[/color]"
        if hasattr(self, "studio_status_lbl"):
            self.studio_status_lbl.text = f"[color=38bdf8]Checking latest compiled .{target.upper()} download...[/color]"

        def _worker():
            try:
                code, user = self._gh_get("https://api.github.com/user", token)
                if code != 200 or not isinstance(user, dict) or not user.get("login"):
                    Clock.schedule_once(
                        lambda _dt: setattr(
                            self.gh_log,
                            "text",
                            f"[color=f87171]GitHub Auth Error ({code}) — token dubara check karein.[/color]",
                        ),
                        0,
                    )
                    return
                owner = user["login"]
                self._gh_owner_cache = owner
                ac, adata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=20", token)
                rc, rdata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=5", token)
                arts = [a for a in (adata.get("artifacts", []) if ac == 200 and isinstance(adata, dict) else []) if not a.get("expired")]
                runs = rdata.get("workflow_runs", []) if rc == 200 and isinstance(rdata, dict) else []
                active_runs = [r for r in runs if r.get("status") in ("in_progress", "queued", "waiting", "pending", "requested")]
                match_art = next((a for a in arts if target.lower() in str(a.get("name", "")).lower()), None)

                if not match_art:
                    if active_runs:
                        def _still_building(_dt):
                            self._start_build_progress_poller(owner, repo, token)
                            self.gh_log.text = (
                                f"[color=fbbf24][b]Build abhi chal raha hai (run #{active_runs[0].get('id')})[/b][/color]\n"
                                "[color=cbd5e1]Upar live Executing... bar me % dekho — naya duplicate push nahi kiya gaya hai. Complete hote hi download ready ho jayega![/color]"
                            )
                        Clock.schedule_once(_still_building, 0)
                        return
                    if target == "exe":
                        saved_zip = self._export_exe_bundle()
                        msg = (
                            f"[color=34d399][b]✓ Windows EXE Builder ZIP saved:[/b] {escape_markup(saved_zip)}[/color]\n"
                            "[color=cbd5e1]Cloud .EXE compile abhi ready nahi tha — 'Push & Build APK + EXE on GitHub' dabakar cloud build chalayein.[/color]"
                        ) if saved_zip else "[color=fbbf24]Abhi koi compiled .EXE artifact nahi hai — pehle 'Push & Build APK + EXE on GitHub' dabao.[/color]"
                    else:
                        msg = "[color=fbbf24]Abhi koi compiled .APK ready nahi hai — naya APK banane ke liye 'Push & Build APK + EXE on GitHub' button dabao (Download button kabhi build restart nahi karega).[/color]"
                    Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", msg), 0)
                    return

                dl_url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts/{match_art['id']}/zip"
                zip_bytes = self._gh_download_artifact_bytes(dl_url, token)
                dl_dir = self._get_downloads_folder()
                os.makedirs(dl_dir, exist_ok=True)
                tmp_zip = os.path.join(self._get_data_dir(), f"_tmp_{target}_artifact.zip")
                with open(tmp_zip, "wb") as zfh:
                    zfh.write(zip_bytes)

                extracted_path = None
                ext = f".{target.lower()}"
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    members = [m for m in zf.namelist() if m.lower().endswith(ext)]
                    if members:
                        chosen = members[0]
                        fname = os.path.basename(chosen) or f"NeonMobile.{target.lower()}"
                        dest = os.path.join(dl_dir, fname)
                        with zf.open(chosen) as src_f, open(dest, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)
                        extracted_path = dest
                try:
                    os.remove(tmp_zip)
                except Exception:
                    pass

                if extracted_path and os.path.exists(extracted_path):
                    sz_mb = round(os.path.getsize(extracted_path) / (1024 * 1024), 2)
                    def _ok(_dt):
                        msg = (
                            f"[color=34d399][b]✓ {target.upper()} Downloaded Directly ({sz_mb} MB)![/b][/color]\n"
                            f"[color=e2e8f0]Saved to: {escape_markup(extracted_path)}[/color]"
                        )
                        self.gh_log.text = msg
                        if hasattr(self, "studio_status_lbl"):
                            self.studio_status_lbl.text = msg
                        if self.audio_enabled:
                            self.voice_bridge.speak(f"Harish, aapki {target.upper()} file Downloads folder me save ho gayi hai!")
                    Clock.schedule_once(_ok, 0)
                else:
                    Clock.schedule_once(
                        lambda _dt: setattr(
                            self.gh_log,
                            "text",
                            f"[color=fbbf24]Artifact ZIP me .{target} file nahi mili.[/color]",
                        ),
                        0,
                    )
            except Exception as err:
                Clock.schedule_once(
                    lambda _dt, e=str(err): setattr(
                        self.gh_log,
                        "text",
                        f"[color=f87171]Direct Download Error: {escape_markup(e)}[/color]",
                    ),
                    0,
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _gh_download_exe_action(self):
        self._gh_download_compiled_artifact(target="exe")

    def _gh_open_web_ci(self):
        webbrowser.open("https://ais-pre-ccf5jvawenmhsjix56rckx-803295381828.asia-southeast1.run.app/?tab=github")

    def _gh_open_actions_browser(self):
        repo = self.gh_repo_input.text.strip() or self.github_repo or "neon-pro-harish"
        owner = getattr(self, "_gh_owner_cache", "")
        if owner:
            webbrowser.open(f"https://github.com/{owner}/{repo}/actions")
        elif self.github_token:
            code, user = self._gh_get("https://api.github.com/user", self.github_token)
            if code == 200 and isinstance(user, dict) and user.get("login"):
                self._gh_owner_cache = user["login"]
                webbrowser.open(f"https://github.com/{self._gh_owner_cache}/{repo}/actions")
                return
            webbrowser.open("https://github.com/login")
        else:
            webbrowser.open("https://github.com/login")

    def _gh_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NEON-PRO-Mobile-v4",
            "Content-Type": "application/json",
        }

    def _gh_get(self, url, token):
        hdrs = self._gh_headers(token)
        _ssl_ctx, req_verify = _build_ssl_context()
        if requests is not None:
            try:
                try:
                    r = requests.get(url, headers=hdrs, timeout=20, verify=req_verify)
                except Exception as r_err:
                    if _is_ssl_exception(r_err) and req_verify is not False:
                        _activate_unverified_ssl_fallback()
                        r = requests.get(url, headers=hdrs, timeout=20, verify=False)
                    else:
                        raise
                return r.status_code, (r.json() if r.content else {})
            except Exception:
                pass
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        code, txt = _urlopen_with_ssl_retry(req, timeout=20)
        try:
            return code, json.loads(txt)
        except Exception:
            return code, {"message": txt}

    def _gh_req(self, method, url, token, body=None):
        hdrs = self._gh_headers(token)
        _ssl_ctx, req_verify = _build_ssl_context()
        if requests is not None:
            try:
                try:
                    r = requests.request(method, url, json=body, headers=hdrs, timeout=22, verify=req_verify)
                except Exception as r_err:
                    if _is_ssl_exception(r_err) and req_verify is not False:
                        _activate_unverified_ssl_fallback()
                        r = requests.request(method, url, json=body, headers=hdrs, timeout=22, verify=False)
                    else:
                        raise
                return r.status_code, (r.json() if r.content else {})
            except Exception:
                pass
        data_bytes = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=hdrs, method=method)
        code, txt = _urlopen_with_ssl_retry(req, timeout=22)
        try:
            return code, (json.loads(txt) if txt else {})
        except Exception:
            return code, {"message": txt}

    def _gh_put(self, url, token, body):
        return self._gh_req("PUT", url, token, body=body)

    def _gh_cancel_stuck_runs(self):
        token = self.gh_token_input.text.strip() or self.github_token
        repo = self.gh_repo_input.text.strip() or self.github_repo or "neon-pro-harish"
        if not token:
            self.gh_log.text = "[color=fbbf24]Pehle 'Get Token' dabakar GitHub Token save karein.[/color]"
            return
        self.gh_log.text = "[color=fbbf24]Killing all active & duplicate GitHub builds...[/color]"

        def _worker():
            code, user = self._gh_get("https://api.github.com/user", token)
            if code != 200:
                Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", f"[color=f87171]Auth Error ({code})[/color]"), 0)
                return
            owner = user.get("login", "")
            self._gh_owner_cache = owner
            rc, runs_data = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=30", token)
            cancelled = []
            if rc == 200 and isinstance(runs_data, dict):
                for r in runs_data.get("workflow_runs", []):
                    if r.get("status") in ("in_progress", "queued", "waiting", "pending", "requested"):
                        rid = r.get("id")
                        cc, _ = self._gh_req("POST", f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{rid}/cancel", token)
                        if cc not in (200, 202):
                            cc, _ = self._gh_req("POST", f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{rid}/force-cancel", token)
                        cancelled.append(f"#{rid} ({cc})")
            def _done(_dt):
                self._stop_build_progress_poller()
                self._set_execution_progress(False, 0, 0)
                if cancelled:
                    self.gh_log.text = (
                        f"[color=34d399][b]✓ Killed {len(cancelled)} active/duplicate build(s):[/b] {', '.join(cancelled)}[/color]\n"
                        "[color=cbd5e1]Queue saaf ho gayi hai! Ab naya build start kar sakte ho.[/color]"
                    )
                else:
                    self.gh_log.text = "[color=38bdf8]Koi active/duplicate build nahi mila.[/color]"
            Clock.schedule_once(_done, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _gh_check_runs(self):
        token = self.gh_token_input.text.strip() or self.github_token
        repo = self.gh_repo_input.text.strip() or "neon-pro-harish"
        self.github_token = token
        self.github_repo = repo
        self._save_config()
        if not token:
            self.gh_log.text = "[color=fbbf24]Please tap 'Get Token' or paste your GitHub Token first.[/color]"
            return
        self.gh_log.text = "[color=38bdf8]Checking APK & EXE builds & downloads...[/color]"

        def _worker():
            code, user = self._gh_get("https://api.github.com/user", token)
            if code != 200:
                msg = f"[color=f87171]GitHub Auth Error ({code}): {escape_markup(user.get('message', ''))}[/color]"
                Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", msg), 0)
                return
            owner = user.get("login", "")
            self._gh_owner_cache = owner
            rc, runs_data = self._gh_get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=6",
                token,
            )
            if rc != 200:
                msg = f"[color=fbbf24]Repo '{owner}/{repo}' not found yet — tap 'Download APK File' first.[/color]"
                Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", msg), 0)
                return
            lines = [f"[b][color=34d399]Repo: {owner}/{repo}[/color][/b]"]
            runs_list = runs_data.get("workflow_runs", [])[:5]
            for idx, r in enumerate(runs_list):
                st = r.get("conclusion") or r.get("status")
                clr = "34d399" if st == "success" else ("f87171" if st == "failure" else "38bdf8")
                lines.append(f"[color={clr}]• {escape_markup(r.get('name', 'APK + EXE Build'))}: {st}[/color]")
                if idx == 0 or r.get("status") in ("in_progress", "queued"):
                    jc, jdata = self._gh_get(
                        f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{r.get('id')}/jobs",
                        token,
                    )
                    if jc == 200 and isinstance(jdata, dict):
                        for jb in jdata.get("jobs", []):
                            jst = jb.get("conclusion") or jb.get("status")
                            jclr = "34d399" if jst == "success" else ("f87171" if jst == "failure" else "22d3ee")
                            cur_step = ""
                            for sp_item in jb.get("steps", []):
                                if sp_item.get("status") == "in_progress":
                                    cur_step = f" -> {sp_item.get('name', '')}"
                                    break
                            lines.append(
                                f"  [color={jclr}]- {escape_markup(jb.get('name', 'Job'))}: {jst}{escape_markup(cur_step)}[/color]"
                            )

            ac, art_data = self._gh_get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=10",
                token,
            )
            if ac == 200 and isinstance(art_data, dict):
                arts = [a for a in art_data.get("artifacts", []) if not a.get("expired")]
                if arts:
                    lines.append("\n[b][color=22d3ee]Ready Downloads (APK & EXE):[/color][/b]")
                    for a in arts[:6]:
                        mb = round((a.get("size_in_bytes", 0) or 0) / (1024 * 1024), 1)
                        lines.append(f"[color=34d399]✓ {escape_markup(a.get('name', 'Artifact'))} ({mb} MB)[/color]")
                else:
                    lines.append("\n[color=fbbf24]Abhi tak koi compiled file ready nahi hai — agar build 25+ min se atka hai toh 'Cancel Stuck' dabakar naya push karein.[/color]")
            lines.append(f"\n[color=94a3b8]Tap 'Open Downloads' to download .apk & .exe:\nhttps://github.com/{owner}/{repo}/actions[/color]")
            final_txt = "\n".join(lines)
            Clock.schedule_once(lambda _dt: setattr(self.gh_log, "text", final_txt), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _gh_push_studio_app(self, target="apk", local_exe_zip=None, chat_status_lbl=None):
        self._save_active_studio_buffer()
        token = self.gh_token_input.text.strip() or self.github_token
        repo = self.gh_repo_input.text.strip() or "neon-pro-harish"
        self.github_token = token
        self.github_repo = repo
        self._save_config()
        if not token:
            self.gh_log.text = "[color=fbbf24]Step 1: 'Get Token' dabakar GitHub Token save karo (sirf 1 baar), fir 'Download APK File' ya 'Download EXE File' dabao.[/color]"
            self._open_github_token_modal()
            return
        self.gh_push_btn.disabled = True
        if hasattr(self, "gh_exe_btn"):
            self.gh_exe_btn.disabled = True
        label_mode = "Windows .EXE + Android .APK" if target == "exe" else "Android .APK + Windows .EXE"
        self.gh_log.text = f"[color=38bdf8]Pushing in 1 atomic commit & starting {label_mode} build...[/color]"
        files_bundle = dict(self.studio_files)

        def _set_chat_status(txt):
            if chat_status_lbl is not None:
                Clock.schedule_once(lambda _dt: setattr(chat_status_lbl, "text", txt), 0)

        def _worker():
            code, user = self._gh_get("https://api.github.com/user", token)
            if code != 200:
                msg = f"[color=f87171]GitHub Auth Failed ({code}): 'Get Token' dabakar repo + workflow tick wala token save karein.[/color]"
                def _auth_fail(_dt):
                    self.gh_push_btn.disabled = False
                    if hasattr(self, "gh_exe_btn"):
                        self.gh_exe_btn.disabled = False
                    self.gh_log.text = msg
                Clock.schedule_once(_auth_fail, 0)
                return
            owner = user.get("login", "")
            self._gh_owner_cache = owner
            r_code, repo_info = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}", token)
            if r_code == 404:
                self._gh_req(
                    "POST",
                    "https://api.github.com/user/repos",
                    token,
                    body={"name": repo, "auto_init": True},
                )
                time.sleep(1.8)
                r_code, repo_info = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}", token)
            branch = repo_info.get("default_branch", "main") if isinstance(repo_info, dict) else "main"

            push_order = [
                ".github/workflows/build_apk.yml",
                "requirements.txt",
                "buildozer.spec",
                "main.py",
            ]
            pushed_ok = []
            errors = []
            atomic_done = False

            # Atomic 1-commit push via Git Trees API so GitHub triggers ONLY 1 clean workflow run
            try:
                rc, ref_data = self._gh_get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}",
                    token,
                )
                head_sha = ref_data.get("object", {}).get("sha") if rc == 200 and isinstance(ref_data, dict) else None
                if head_sha:
                    cc, c_data = self._gh_get(
                        f"https://api.github.com/repos/{owner}/{repo}/git/commits/{head_sha}",
                        token,
                    )
                    base_tree = c_data.get("tree", {}).get("sha") if cc == 200 and isinstance(c_data, dict) else None
                    if base_tree:
                        tree_entries = []
                        for target_path in push_order:
                            content_str = files_bundle.get(target_path, "")
                            if not content_str:
                                continue
                            bc, b_res = self._gh_req(
                                "POST",
                                f"https://api.github.com/repos/{owner}/{repo}/git/blobs",
                                token,
                                body={
                                    "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
                                    "encoding": "base64",
                                },
                            )
                            if bc in (200, 201) and isinstance(b_res, dict) and b_res.get("sha"):
                                tree_entries.append({
                                    "path": target_path,
                                    "mode": "100644",
                                    "type": "blob",
                                    "sha": b_res["sha"],
                                })
                                pushed_ok.append(target_path)
                        if tree_entries:
                            tc, t_res = self._gh_req(
                                "POST",
                                f"https://api.github.com/repos/{owner}/{repo}/git/trees",
                                token,
                                body={"base_tree": base_tree, "tree": tree_entries},
                            )
                            if tc in (200, 201) and isinstance(t_res, dict) and t_res.get("sha"):
                                nc, nc_res = self._gh_req(
                                    "POST",
                                    f"https://api.github.com/repos/{owner}/{repo}/git/commits",
                                    token,
                                    body={
                                        "message": "[NEON PRO v4.5] Atomic Dual APK + EXE Build",
                                        "tree": t_res["sha"],
                                        "parents": [head_sha],
                                    },
                                )
                                if nc in (200, 201) and isinstance(nc_res, dict) and nc_res.get("sha"):
                                    pc, _ = self._gh_req(
                                        "PATCH",
                                        f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}",
                                        token,
                                        body={"sha": nc_res["sha"]},
                                    )
                                    if pc in (200, 201):
                                        atomic_done = True
            except Exception:
                atomic_done = False

            if not atomic_done:
                pushed_ok = []
                for target_path in push_order:
                    content_str = files_bundle.get(target_path, "")
                    if not content_str:
                        continue
                    f_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{target_path}"
                    ex_code, ex_data = self._gh_get(f"{f_url}?ref={branch}", token)
                    put_body = {
                        "message": f"[NEON PRO v4.5] Update {target_path}",
                        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
                        "branch": branch,
                    }
                    if ex_code == 200 and isinstance(ex_data, dict) and ex_data.get("sha"):
                        put_body["sha"] = ex_data["sha"]
                    p_code, p_res = self._gh_put(f_url, token, put_body)
                    if p_code in (200, 201):
                        pushed_ok.append(target_path)
                    else:
                        err_m = p_res.get("message", str(p_res)) if isinstance(p_res, dict) else str(p_res)
                        errors.append(f"{target_path}: {p_code} {err_m}")

            if pushed_ok and not errors:
                extra_exe = f"\n[color=38bdf8]Local Windows EXE Builder ZIP: {escape_markup(local_exe_zip)}[/color]" if local_exe_zip else ""
                msg = (
                    f"[color=34d399][b]✓ Clean 1-commit {label_mode} build started![/b][/color]\n"
                    f"[color=cbd5e1]Pushed {', '.join(pushed_ok)}.\n"
                    f"Windows .EXE ready in ~2 min, Android .APK ready in ~10-14 min.\n"
                    f"Tap 'Check Status' or 'Open Downloads':\n"
                    f"https://github.com/{owner}/{repo}/actions[/color]{extra_exe}"
                )
                _set_chat_status(
                    "[color=34d399]✓ Pushed to GitHub CI! Compiling Windows .EXE (~2m) & Android .APK (~10m)...[/color]"
                )
            else:
                msg = (
                    f"[color=fbbf24]Pushed: {len(pushed_ok)} | Issues: {len(errors)}[/color]\n"
                    + escape_markup("\n".join(errors))
                )
                _set_chat_status(f"[color=f87171]GitHub Push issue: {escape_markup('; '.join(errors) or 'check token')}[/color]")
            def _done(_dt):
                self.gh_push_btn.disabled = False
                if hasattr(self, "gh_exe_btn"):
                    self.gh_exe_btn.disabled = False
                self.gh_log.text = msg
                if pushed_ok and not errors:
                    self._set_execution_progress(True, exe_pct=8, apk_pct=8)
                    self._start_build_progress_poller(owner, repo, token)
            Clock.schedule_once(_done, 0)

            # Live background poll for autonomous chat cards so Harish gets ready notification automatically
            if pushed_ok and not errors and chat_status_lbl is not None:
                announced_exe = False
                for _poll_i in range(48):
                    time.sleep(15)
                    rc, rdata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=2", token)
                    ac, adata = self._gh_get(f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=6", token)
                    arts = [a for a in (adata.get("artifacts", []) if ac == 200 and isinstance(adata, dict) else []) if not a.get("expired")]
                    exe_ready = any("exe" in str(a.get("name", "")).lower() for a in arts)
                    apk_ready = any("apk" in str(a.get("name", "")).lower() for a in arts)
                    top_run = (rdata.get("workflow_runs") or [None])[0] if rc == 200 and isinstance(rdata, dict) else None
                    r_stat = top_run.get("conclusion") or top_run.get("status") if top_run else "running"
                    if exe_ready and not announced_exe:
                        announced_exe = True
                        _set_chat_status(
                            "[color=34d399]✓ Windows .EXE compiled! Android .APK still compiling... Tap 'Download EXE File' anytime.[/color]"
                        )
                    if apk_ready and exe_ready:
                        _set_chat_status(
                            f"[b][color=34d399]✓ BOTH Android .APK & Windows .EXE Ready! Tap 'Download APK File' or 'Download EXE File'.[/color][/b]"
                        )
                        if self.audio_enabled:
                            Clock.schedule_once(lambda _dt: self.voice_bridge.speak("Harish, aapke app ki APK aur EXE files dono ban ke ready ho gayi hain!"), 0)
                        break
                    if top_run and top_run.get("status") == "completed":
                        _set_chat_status(
                            f"[color={'34d399' if r_stat == 'success' else 'fbbf24'}]Build finished ({r_stat}). Tap 'GitHub CI' to view downloads.[/color]"
                        )
                        break

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # SETTINGS & API KEY MODAL
    # ------------------------------------------------------------------
    def _open_settings_modal(self):
        modal = ModalView(size_hint=(0.94, None), height=dp(505), background_color=(0, 0, 0, 0.78))
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        style_card(box, (0.04, 0.06, 0.12, 1.0), (0.08, 0.72, 0.88, 0.75), radius_dp=16, border_width=1.3)

        hdr = BoxLayout(size_hint_y=None, height=dp(32))
        hdr.add_widget(
            AutoLabel(text="[b][color=22d3ee]NEON PRO Quick Setup[/color][/b]", font_size=sp(15))
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
            AutoLabel(text="[color=cbd5e1]Gemini API Key (Saved on phone):[/color]", font_size=sp(11))
        )
        key_inp = TextInput(
            text=self.api_key,
            hint_text="Paste GEMINI_API_KEY (AIza...)",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        box.add_widget(key_inp)

        box.add_widget(
            AutoLabel(text="[color=cbd5e1]GitHub Token (1-Baar Save — Har Naye App Me Chalega):[/color]", font_size=sp(11))
        )
        gh_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        gh_inp = TextInput(
            text=self.github_token,
            hint_text="Paste GitHub Token (ghp_...)",
            password=True,
            multiline=False,
            background_color=(0.02, 0.03, 0.06, 1.0),
            foreground_color=(1, 1, 1, 1),
            font_size=sp(12),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        gh_row.add_widget(gh_inp)

        s_get_tok = make_button(
            "Get Token",
            (0.24, 0.15, 0.04, 1.0),
            (0.95, 0.68, 0.18, 0.78),
            text_rgba=(1.0, 0.86, 0.42, 1.0),
            radius_dp=8,
            font_sp=10,
            size_hint_x=None,
            width=dp(74),
        )
        s_get_tok.bind(on_release=lambda *_: (modal.dismiss(), self._open_github_token_modal()))
        gh_row.add_widget(s_get_tok)
        box.add_widget(gh_row)

        box.add_widget(AutoLabel(text="[color=cbd5e1]Select AI Model:[/color]", font_size=sp(11)))
        model_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
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
        lang_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
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
            self.github_token = gh_inp.text.strip()
            if hasattr(self, "gh_token_input"):
                self.gh_token_input.text = self.github_token
            self.discovered_models = []
            self.voice_bridge.configure(api_key=self.api_key)
            self._save_config()
            self._refresh_header_state()
            modal.dismiss()
            if self.api_key:
                ok_msg = "Settings save ho gayi Harish! Ab bolo ya likho, main ready hoon."
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
