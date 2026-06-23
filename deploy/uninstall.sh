#!/bin/bash
# Detiene y desinstala el LaunchAgent.
PLIST="com.loupdeck.controller.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST"

launchctl unload "$DEST" 2>/dev/null || true
rm -f "$DEST"
echo "Desinstalado. El daemon ya no arranca solo."
