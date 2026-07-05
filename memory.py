from collections import defaultdict, deque

MAX_HISTORY_TURNS = 10  # keep last 10 exchanges (10 user + 10 model messages)

_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_TURNS * 2))


def get_history(phone: str) -> list[dict]:
    """Return this user's history in the shape google.generativeai's
    start_chat(history=...) expects: [{"role": ..., "parts": [text]}, ...]"""
    return list(_store[phone])


def add_message(phone: str, role: str, text: str):
    _store[phone].append({"role": role, "parts": [text]})


def clear_history(phone: str):
    _store[phone].clear()
