#!/bin/zsh
# สร้าง InstantLore.app สำหรับ macOS 26 ขึ้นไป
set -e
cd "$(dirname "$0")"
APP=InstantLore.app
rm -rf $APP
mkdir -p $APP/Contents/MacOS
swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos26" \
  -framework Cocoa -framework Carbon -framework ScreenCaptureKit -framework Vision -framework Translation \
  main.swift -o $APP/Contents/MacOS/InstantLore
cat > $APP/Contents/Info.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>local.instantlore</string>
  <key>CFBundleName</key><string>InstantLore</string>
  <key>CFBundleExecutable</key><string>InstantLore</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.3</string>
  <key>NSHumanReadableCopyright</key><string>Developed by Soulrose</string>
  <key>LSMinimumSystemVersion</key><string>26.0</string>
  <key>LSUIElement</key><true/>
  <key>NSScreenCaptureUsageDescription</key><string>Reads subtitles from the game screen to translate them.</string>
</dict></plist>
EOF
codesign --force --sign - $APP
echo "✅ สร้างเสร็จ: $(pwd)/$APP"

# แพ็กเป็นไฟล์ .dmg (ลากไอคอนไปใส่ Applications ได้): ./build.sh dmg
if [[ "$1" == "dmg" ]]; then
  VER=$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" $APP/Contents/Info.plist)
  STAGE=$(mktemp -d)
  cp -R $APP "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  DMG="InstantLore-$VER.0-mac.dmg"
  rm -f "$DMG"
  hdiutil create -volname "InstantLore" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
  rm -rf "$STAGE"
  echo "✅ สร้าง $DMG แล้ว"
fi
