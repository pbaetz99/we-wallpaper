#!/usr/bin/env bash
# Fuehrt die Test-Suite aus (nur Standardbibliothek + PySide6, kein pytest noetig).
cd "$(dirname "${BASH_SOURCE[0]}")" && QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s . -p 'test_*.py' -v
