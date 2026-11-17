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

# Step 1. Overlapping exports record the same message with timestamps 1-5 s apart.
# The same sender sending the exact same text again within this window is treated as a copy.
DUPLICATE_WINDOW_SECONDS = 10

# Step 2. Chosen from the gap histogram of the real chat (see lesson 1c):
# 81% of gaps are under 1 minute; the turn count barely changes between 1 and 5 minutes.
BURST_GAP_MINUTES = 2     # same sender, next message within this -> same turn
SESSION_GAP_MINUTES = 60  # silence longer than this -> new conversation

# Step 3. Exchange = up to CONTEXT_TURNS earlier turns -> your reply turn.
CONTEXT_TURNS = 3         # 95% of replies have 3 earlier turns in their session
MAX_SAME_REPLY = 5        # one reply text appears 36 times; keep at most 5 copies of any reply
MAX_REPLY_CHARS = 1200    # 99% of replies are under 400 chars; longer ones are usually pasted text
