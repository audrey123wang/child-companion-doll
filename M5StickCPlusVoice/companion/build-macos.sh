#!/bin/sh
set -eu
cd "$(dirname "$0")"
app="M5StickC Voice.app"
mkdir -p "$app/Contents/MacOS" "../../../work/swift-cache"
cp Info-macOS.plist "$app/Contents/Info.plist"
swiftc -parse-as-library -module-cache-path ../../../work/swift-cache VoiceCompanion.swift \
  -o "$app/Contents/MacOS/M5StickCVoice"
codesign --force --sign - "$app"
echo "Built $PWD/$app"
