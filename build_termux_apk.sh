#!/data/data/com.termux/files/usr/bin/bash
# NEON PRO - Direct Android Termux Runner for Harish
echo "=================================================="
echo "  NEON PRO: Setting up Termux Python + Kivy + Voice"
echo "=================================================="
pkg update -y && pkg upgrade -y
pkg install -y python python-pip clang libffi openssl termux-api
pip install --upgrade pip
pip install kivy requests certifi urllib3
echo ">> Launching NEON PRO..."
python main.py
