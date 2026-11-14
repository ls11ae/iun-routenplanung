#!/bin/sh
# Richtet MOTIS ein (beim ersten Mal: laden und importieren) und startet den Server.
# Aufruf: ./starten.sh oder sh starten.sh – beenden mit Strg+C.
cd "$(dirname "$0")" || exit 1
exec python3 motis_einrichten.py --server
