# NEON PRO Dual-Platform Application (Mobile APK & Windows EXE)

Engineered by NEON PRO specifically for **Harish**.

---

## 📱 1. HOW TO GET THE ANDROID APK FILE

### Option A: Free Cloud Build via GitHub Actions (Recommended)
1. Push this folder to a GitHub repository using the NEON PRO GitHub CI Hub.
2. Go to the **Actions** tab on your GitHub repository.
3. The workflow `NEON PRO - Auto Build Android APK` automatically compiles the APK!
4. Download the attached `NeonMobile-Android-APK.zip` from Artifacts, install the `.apk` directly onto your phone.

### Option B: Local Buildozer (Linux / WSL / Ubuntu)
```bash
pip install buildozer cython==0.29.36
buildozer android debug
# Output APK: bin/neonmobile-0.1-debug.apk
```

---

## 💻 2. HOW TO GET THE STANDALONE WINDOWS EXECUTABLE (.EXE)

1. On your Windows PC, double-click **`build_windows_exe.bat`**
2. Your standalone, double-clickable Windows app will be created at:
   ```
   dist\NeonMobile_Windows.exe
   ```
