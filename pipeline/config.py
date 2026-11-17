"""Settings shared by every pipeline step. Change values here, not inside the steps."""

from pathlib import Path

# Project folders
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# The raw chats live outside the project so they can never be committed by accident.
# Same friend (Indu, saved as "Mustang" later); 2024 export plus the merged 2025-26 exports.
CHAT_DIR = Path.home() / "Downloads" / "Mustang_Chats"
RAW_CHATS = [
    CHAT_DIR / "Indu_2024-01-22_to_2024-10-24.txt",
    CHAT_DIR / "Mustang_2025-05-06_to_2026-07-23_merged.txt",
]

# Your display name(s) in the exports ("Yaswanth" in 2024, "Prosessor" later).
# Messages from these names become sender "me"; every other name becomes "friend".
ME_NAMES = {"Prosessor", "Yaswanth"}

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
# RAG only: oldest 90% is the retrieval index, newest 10% is the held-out test set.
# (0.8, 0.1, 0.1) adds a validation split if fine-tuning is picked up again later.
SPLIT = (0.9, 0.0, 0.1)           # index / validation / test, oldest to newest, cut at session boundaries

# Who the twin is talking to. All the data is with Indu, so it is named here; the app changes it
# at runtime (for example "someone new") so the tone can depend on the person.
CHAT_PARTNER = "Indu, a close friend"

# System prompt shared by the baselines, the Java app and (optionally) fine-tuning.
SYSTEM_PROMPT = (
    f"You are Yaswanth, chatting on WhatsApp with {CHAT_PARTNER}. "
    "Reply exactly the way Yaswanth would: casual Telugu-English in Latin letters, short when the chat is short, "
    "line breaks between quick thoughts."
)

# Step 5/6. Baseline (prompt-only and prompt + RAG) settings, same idea as AI Twin 4.
RAG_TOP_K = 4

# Step 6. Generation model candidates (OpenAI pricing page, checked 2026-11-17, $ per 1M tokens).
# gpt-4o shuts down 2027-01-14; gpt-6-luna is OpenAI's listed replacement.
MODEL_PRICES = {             # (input, output)
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-4o": (2.50, 10.00),
}
# Reasoning models think before answering (hidden tokens: slower, costlier). A chat reply does not need it.
REASONING_EFFORT = {"gpt-6-luna": "none", "gpt-6.1-terra": "none"}  # gpt-4o has no reasoning setting
GENERATION_MODEL = "gpt-6-luna"  # provisional; confirmed by the step 6 pilot
EVAL_SAMPLE = 40                 # test messages per model in the pilot
PERSONA_RULES = (
    " Never say you are an AI, a model or an assistant. Never use bullet lists or formal phrases. "
    "If examples of Yaswanth's past replies are given, copy their tone and wording, never their content."
)
