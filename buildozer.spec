
[app]

title = CRYPTO BOT PRO
package.name = cryptobotpro
package.domain = org.cryptobot

source.dir = .
source.include_exts = py,json

version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.archs = arm64-v8a

android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724
android.accept_sdk_license = True

[buildozer]

log_level = 2
warn_on_root = 1
