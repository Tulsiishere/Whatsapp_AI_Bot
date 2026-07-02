from collections import defaultdict, deque

# Per-user sliding window of messages
# Each entry: {"role": "user" | "model", "parts": [{"text": "..."}]}
HISTORY_LIMIT = 10  # last 10 turns (5 user + 5 model)

_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LIMIT))


def get_history(phone: str) -> list[dict]:
    return list(_store[phone])


def add_message(phone: str, role: str, text: str):
    _store[phone].append({
        "role": role,
        "parts": [{"text": text}]
    })


def clear_history(phone: str):
    _store[phone].clear()