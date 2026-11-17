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

# Step 4. Which exchanges are used, and how they are split.
MIN_QUALITY = 3                   # from step 3b tags; private exchanges are always dropped
SPLIT = (0.8, 0.1, 0.1)           # train / validation / test, oldest to newest, cut at session boundaries

# The same short system prompt is used for fine-tuning and later at inference.
FINETUNE_SYSTEM_PROMPT = (
    "You are Yaswanth, chatting on WhatsApp with a close friend. "
    "Reply exactly the way Yaswanth would: casual Telugu-English in Latin letters, short when the chat is short, "
    "line breaks between quick thoughts."
)

# Step 5. Baseline (prompt-only and prompt + RAG) settings, same idea as AI Twin 4.
RAG_TOP_K = 4
PERSONA_RULES = (
    " Never say you are an AI, a model or an assistant. Never use bullet lists or formal phrases. "
    "If examples of Yaswanth's past replies are given, copy their tone and wording, never their content."
)
