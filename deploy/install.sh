#!/bin/bash
# Instala el LaunchAgent: el daemon arranca solo al iniciar sesion.
set -e

PLIST="com.loupdeck.controller.plist"
SRC="$(cd "$(dirname "$0")" && pwd)/$PLIST"
DEST="$HOME/Library/LaunchAgents/$PLIST"

mkdir -p "$HOME/Library/LaunchAgents"
# Symlink: editar el plist del repo se refleja sin reinstalar.
ln -sf "$SRC" "$DEST"

# Recargar limpio (por si ya estaba).
launchctl unload "$DEST" 2>/dev/null || true
launchctl load -w "$DEST"

echo "Instalado y cargado."
echo "Estado (PID si esta corriendo):"
launchctl list | grep loupdeck || echo "  (no aparece; revisa logs/daemon.err)"
