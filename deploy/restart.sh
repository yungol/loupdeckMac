#!/bin/bash
# Reinicia el daemon para que tome cambios de codigo/layout.
# Si no estaba cargado, lo instala.
LABEL="com.loupdeck.controller"

if launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null; then
    echo "Daemon reiniciado (cambios aplicados)."
else
    echo "No estaba cargado; instalando..."
    "$(cd "$(dirname "$0")" && pwd)/install.sh"
fi
