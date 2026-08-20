import os
import json
from typing import Dict, Any

_DEFAULT_CONFIG: Dict[str, Any] = {
    "system_prompt": "You are the eSim AI Assistant, an expert in Electronics Design Automation (EDA), NgSpice, and KiCad.",
    "vision_system_prompt": "You are an expert circuit design AI analyzing schematic images and circuit diagrams.",
    "num_ctx": 4096,
    "max_predict": 512,
    "repeat_penalty": 1.15,
    "vision_temperature": 0.2,
    "keep_alive": "5m",
    "max_history_lines": 30,
    "default_model": "llama3.2:3b",
    "default_vision_model": "moondream:latest",
    "embedding_model": "nomic-embed-text",
    "ollama_base_url": "http://localhost:11434",
    "autosave_debounce_sec": 5.0,
    "rag_l2_threshold": 500.0,
    "rag_top_k": 4
}

def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge configuration dictionary ensuring all required keys exist."""
    out = dict(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

class AppConfig:
    """Self-healing application configuration and runtime directory manager."""
    
    def __init__(self):
        self.user_home = os.path.expanduser("~")
        self.esim_home = os.path.join(self.user_home, ".esim")
        self.sessions_dir = os.path.join(self.esim_home, "chat_sessions")
        self.chroma_dir = os.path.join(self.esim_home, "chroma_db")
        self.app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.app_root, "config.json")
        
        # Self-healing bootstrap: ensure directory tree exists
        self._ensure_runtime_dirs()
        self.config = self._load_config()

    def _ensure_runtime_dirs(self):
        """Create runtime hidden directories if absent (Self-Healing Runtime)."""
        for path in [self.esim_home, self.sessions_dir, self.chroma_dir]:
            os.makedirs(path, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Load config.json with deep-merge fallback."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                return _deep_merge(_DEFAULT_CONFIG, user_cfg)
            except Exception:
                return dict(_DEFAULT_CONFIG)
        else:
            # Serialise default configuration to disk
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(_DEFAULT_CONFIG, f, indent=2)
            except Exception:
                pass
            return dict(_DEFAULT_CONFIG)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

CONFIG = AppConfig()
