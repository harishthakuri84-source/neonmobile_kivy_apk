"""
NEON PRO - Autonomous Android Mobile Application
Architected for: Harish
Framework: Kivy (Mobile UI)
"""
import sys
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

# Sleek cyber-dark mobile palette
Window.clearcolor = (0.02, 0.03, 0.06, 1.0)

class NeonMobileUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=15, **kwargs)

        # Header Title
        self.header = Label(
            text="[b]NEON PRO[/b] [color=06b6d4]MOBILE[/color]",
            markup=True,
            font_size='24sp',
            size_hint_y=None,
            height=60,
            color=(0.9, 0.95, 1.0, 1.0)
        )
        self.add_widget(self.header)

        # Subtitle
        self.sub_label = Label(
            text="Autonomous Android Terminal for Harish",
            font_size='14sp',
            size_hint_y=None,
            height=30,
            color=(0.4, 0.5, 0.65, 1.0)
        )
        self.add_widget(self.sub_label)

        # Task Input
        self.input_field = TextInput(
            hint_text="Enter prompt or autonomous command...",
            multiline=False,
            size_hint_y=None,
            height=50,
            background_color=(0.06, 0.08, 0.14, 1.0),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0.02, 0.71, 0.83, 1),
            padding=[12, 12, 12, 12]
        )
        self.add_widget(self.input_field)

        # Action Buttons Layout
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)

        self.exec_btn = Button(
            text="EXECUTE TASK",
            background_normal='',
            background_color=(0.02, 0.71, 0.83, 1.0),
            color=(1, 1, 1, 1),
            bold=True
        )
        self.exec_btn.bind(on_release=self.execute_command)
        btn_layout.add_widget(self.exec_btn)

        self.clear_btn = Button(
            text="CLEAR LOGS",
            background_normal='',
            background_color=(0.12, 0.16, 0.24, 1.0),
            color=(0.8, 0.85, 0.9, 1.0)
        )
        self.clear_btn.bind(on_release=self.clear_logs)
        btn_layout.add_widget(self.clear_btn)

        self.add_widget(btn_layout)

        # Output Terminal Scroll
        self.scroll = ScrollView(size_hint=(1, 1))
        self.log_label = Label(
            text="[color=10b981]>> NEON PRO Android Core initialized successfully.[/color]\n[color=64748b]>> Standing by for Harish's directives...[/color]\n",
            markup=True,
            font_size='13sp',
            size_hint_y=None,
            halign='left',
            valign='top',
            color=(0.8, 0.9, 1.0, 1.0)
        )
        self.log_label.bind(texture_size=self.update_log_height)
        self.scroll.add_widget(self.log_label)
        self.add_widget(self.scroll)

    def update_log_height(self, instance, size):
        instance.height = max(size[1], self.scroll.height)
        instance.text_size = (instance.width, None)

    def execute_command(self, instance):
        query = self.input_field.text.strip()
        if not query:
            return
        self.log_label.text += f"\n[color=06b6d4]>> Command queued:[/color] {query}\n"
        self.log_label.text += "[color=a855f7]>> Autonomous pipeline processing... OK.[/color]\n"
        self.input_field.text = ""

    def clear_logs(self, instance):
        self.log_label.text = "[color=64748b]>> Logs cleared.[/color]\n"

class NeonApp(App):
    def build(self):
        self.title = "NEON PRO Mobile"
        return NeonMobileUI()

if __name__ == '__main__':
    NeonApp().run()
