name: Build CRYPTO BOT PRO APK

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-22.04

    steps:
      - name: Checkout project
        uses: actions/checkout@v4

      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            git zip unzip \
            autoconf libtool pkg-config \
            zlib1g-dev libffi-dev libssl-dev \
            build-essential cmake

      - name: Configure Android SDK Paths
        run: |
          set -e
          SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
          echo "ANDROID_HOME=$SDK" >> "$GITHUB_ENV"
          echo "ANDROID_SDK_ROOT=$SDK" >> "$GITHUB_ENV"
          echo "ANDROIDSDK=$SDK" >> "$GITHUB_ENV"
          
          # Fix command-line tools path for buildozer/sdkmanager
          CMDLINE_TOOLS="$SDK/cmdline-tools/latest/bin"
          if [ ! -d "$CMDLINE_TOOLS" ]; then
            CMDLINE_TOOLS=$(find "$SDK/cmdline-tools" -type d -name "bin" | head -n 1)
          fi
          echo "PATH=$PATH:$CMDLINE_TOOLS" >> "$GITHUB_ENV"

      - name: Install Buildozer and Cython
        run: |
          python -m pip install --upgrade pip
          pip install --upgrade buildozer cython==0.29.36

      - name: Build Android APK
        run: |
          buildozer -v android debug

      - name: Upload APK Artifact
        uses: actions/upload-artifact@v4
        with:
          name: CRYPTO-BOT-PRO-APK
          path: bin/*.apk
          if-no-files-found: error
