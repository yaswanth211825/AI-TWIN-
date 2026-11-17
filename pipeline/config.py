"""Settings shared by every pipeline step. Change values here, not inside the steps."""

from pathlib import Path

# Project folders
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# The raw chat lives outside the project so it can never be committed by accident.
RAW_CHAT = Path.home() / "Downloads" / "Mustang_Chats" / "Mustang_2025-05-06_to_2026-07-23_merged.txt"

# Your display name(s) in the export. Messages from these names become sender "me";
# every other name becomes "friend".
ME_NAMES = {"Prosessor"}

# WhatsApp writes dates in the phone's region format. Indian phones use day/month/year.
DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y")
