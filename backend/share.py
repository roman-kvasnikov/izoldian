"""Share token management — JSON file-based storage per user."""

import json
import os
import secrets
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


def _tokens_file(data_dir: str) -> str:
    return os.path.join(data_dir, ".share-tokens.json")


def _load_tokens(data_dir: str) -> dict:
    path = _tokens_file(data_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tokens(data_dir: str, tokens: dict):
    path = _tokens_file(data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def generate_token(length: int = 16) -> str:
    return secrets.token_urlsafe(length)[:length]


def create_share_token(data_dir: str, note_path: str) -> str:
    """Create or return existing share token for a note."""
    with _lock:
        tokens = _load_tokens(data_dir)
        # Check if already shared
        for token, info in tokens.items():
            if info["path"] == note_path:
                return token
        # Create new
        token = generate_token()
        tokens[token] = {
            "path": note_path,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        _save_tokens(data_dir, tokens)
        return token


def get_share_token(data_dir: str, note_path: str) -> str | None:
    """Get existing token for a note, or None."""
    tokens = _load_tokens(data_dir)
    for token, info in tokens.items():
        if info["path"] == note_path:
            return token
    return None


def get_share_info(data_dir: str, note_path: str) -> dict | None:
    """Get full share info for a note."""
    tokens = _load_tokens(data_dir)
    for token, info in tokens.items():
        if info["path"] == note_path:
            return {"token": token, **info}
    return None


def get_note_by_token(token: str, all_data_dirs: str) -> tuple[str, str] | None:
    """Find note path and user data dir by token. Scans all user dirs."""
    if not os.path.exists(all_data_dirs):
        return None
    for user_dir in os.listdir(all_data_dirs):
        data_dir = os.path.join(all_data_dirs, user_dir)
        if not os.path.isdir(data_dir):
            continue
        tokens = _load_tokens(data_dir)
        if token in tokens:
            note_path = tokens[token]["path"]
            full_path = os.path.join(data_dir, note_path)
            if os.path.exists(full_path):
                return (data_dir, note_path)
            else:
                # Orphaned token — clean up
                del tokens[token]
                _save_tokens(data_dir, tokens)
    return None


def get_all_shared_paths(data_dir: str) -> list[str]:
    """Return all shared note paths for a user."""
    tokens = _load_tokens(data_dir)
    return [info["path"] for info in tokens.values()]


def revoke_share_token(data_dir: str, note_path: str) -> bool:
    """Revoke sharing for a note."""
    with _lock:
        tokens = _load_tokens(data_dir)
        to_delete = None
        for token, info in tokens.items():
            if info["path"] == note_path:
                to_delete = token
                break
        if to_delete:
            del tokens[to_delete]
            _save_tokens(data_dir, tokens)
            return True
        return False


def update_token_path(data_dir: str, old_path: str, new_path: str):
    """Update note path in share tokens (for rename)."""
    with _lock:
        tokens = _load_tokens(data_dir)
        changed = False
        for token, info in tokens.items():
            if info["path"] == old_path:
                info["path"] = new_path
                changed = True
        if changed:
            _save_tokens(data_dir, tokens)


def delete_token_for_note(data_dir: str, note_path: str):
    """Delete share token when note is deleted."""
    revoke_share_token(data_dir, note_path)
