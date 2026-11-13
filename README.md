# NEON PRO Dual-Platform Application (Installable Android APK & Windows EXE)

Engineered by NEON PRO specifically for **Harish**.

---

## Why "There was a problem parsing the package" happens & how to prevent it

Android OS strictly verifies 3 things before allowing an `.apk` to install:
1. **Binary AXML Compilation**: `AndroidManifest.xml` must be compiled into Android Binary XML by `aapt2` (plain-text XML fails with Parse Error).
2. **Compiled DEX & Native Libraries**: `classes.dex` and `libpython3.so`/`arm64-v8a` must be compiled for Android NDK.
3. **APK Signature Scheme v2/v3**: Android 11–15 rejects unsigned or zip-only archives; it must be aligned with `zipalign` and signed with `apksigner`.

---

## 📱 1. HOW TO BUILD A 100% INSTALLABLE ANDROID APK (NO PARSE ERROR)

### Method A: Free Cloud Build via GitHub Actions (Easiest & Guaranteed)
1. Open the **GitHub CI** tab in NEON PRO and push this project (with `.github/workflows/build_apk.yml`).
2. GitHub Actions automatically runs Ubuntu + Android SDK/NDK + Buildozer + `apksigner`.
3. Download **`NeonMobile-Android-APK`** from the workflow **Artifacts**, unzip it, and tap the `.apk` file on your Android phone — it installs cleanly with zero Parse Error!

### Method B: Local Ubuntu / WSL2 Build
```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
pip3 install --user --upgrade buildozer cython==0.29.36
buildozer android debug
# Installable signed APK output: ./bin/neonpromobile-0.1-arm64-v8a_armeabi-v7a-debug.apk
```

### Method C: Direct Execution in Termux (Zero APK Build Needed)
```bash
chmod +x build_termux_apk.sh
./build_termux_apk.sh
```

---

## 💻 2. STANDALONE WINDOWS EXECUTABLE (.EXE)

1. Double-click **`build_windows_exe.bat`** on Windows.
2. Output executable: **`dist\NeonMobile_Windows.exe`**
