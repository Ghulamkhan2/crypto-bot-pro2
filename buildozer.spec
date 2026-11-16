[app]

title = CRYPTO BOT PRO
package.name = cryptobotpro
package.domain = org.cryptobot
source.dir = .
source.include_exts = py,json
version = 1.0

# The app uses urllib for Binance public data. Kivy's optional UrlRequest
# dependencies are not needed and can trigger incompatible Android wheels.
requirements = python3==3.11.9,hostpython3==3.11.9,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.archs = arm64-v8a

[buildozer]

log_level = 2
warn_on_root = 1

# Local Kivy recipe disables unused requests/charset-normalizer dependencies.
p4a.local_recipes = p4a-recipes

# Pin python-for-android to a stable release to avoid its newer Python 3.14 default.
p4a.branch = v2024.01.21
