[app]
title = NEON PRO Mobile
package.name = neonpromobile
package.domain = org.harish.neon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.4
requirements = python3,kivy==2.3.0,openssl,requests==2.31.0,urllib3==2.2.1,certifi==2024.2.2,charset-normalizer==3.3.2,idna==3.6,pyjnius,android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,RECORD_AUDIO,WAKE_LOCK
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
