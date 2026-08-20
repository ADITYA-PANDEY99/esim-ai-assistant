import os
import sys
import json
import base64
import subprocess
import requests
from typing import List, Dict, Any, Optional

try:
    from PyQt5.QtCore import QThread, pyqtSignal
except ImportError:
    # Graceful fallback for non-GUI environments
    class QThread:
        def __init__(self, parent=None): pass
        def start(self): self.run()
        def wait(self): pass
    def pyqtSignal(*args):
        class Signal:
            def connect(self, fn): self.fn = fn
            def emit(self, *a): 
                if hasattr(self, 'fn'): self.fn(*a)
        return Signal()

from chatbot.Appconfig import CONFIG
from chatbot.chatbot_core import smart_num_predict, SemanticRouter

class OllamaWorker(QThread):
    """
    Background QThread worker for Text LLM Chat with token streaming.
    Decoupled from main UI thread to achieve 0 ms typing lag.
    """
    token_received = pyqtSignal(str)
    finished_response = pyqtSignal(str, int) # text, token_count
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt: str, conversation_history: List[Dict[str, str]], model: Optional[str] = None):
        super().__init__()
        self.prompt = prompt
        self.history = conversation_history
        self.model = model or CONFIG.get("default_model", "llama3.2:3b")
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _get_rag_context_isolated(self, query: str) -> str:
        """
        Listing 4.1: Thread-Safe RAG Subprocess Isolation via Base64 Streams.
        Eliminates C++ SQLite/ChromaDB memory violations on Windows.
        """
        try:
            cmd = [
                sys.executable, "-c",
                "import sys, base64; "
                "from chatbot.knowledge_base import search_knowledge; "
                "query = base64.b64decode(sys.stdin.read().encode('utf-8')).decode('utf-8'); "
                "result = search_knowledge(query); "
                "print(base64.b64encode(result.encode('utf-8')).decode('utf-8'))"
            ]
            q_b64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, _ = proc.communicate(input=q_b64, timeout=10)
            if proc.returncode == 0 and stdout.strip():
                return base64.b64decode(stdout.strip().encode('utf-8')).decode('utf-8')
        except Exception:
            pass
        return ""

    def run(self):
        # 1. RAG retrieval via subprocess isolation
        rag_context = self._get_rag_context_isolated(self.prompt)
        
        # 2. Build system prompt
        base_sys = CONFIG.get("system_prompt", "You are the eSim AI Assistant.")
        system_content = base_sys
        if rag_context:
            system_content += "\n" + rag_context

        # 3. Dynamic token budgeting (Smart num_predict)
        budget = smart_num_predict(self.prompt)
        
        messages = [{"role": "system", "content": system_content}]
        # Append recent history (up to max_history_lines)
        messages.extend(self.history[-CONFIG.get("max_history_lines", 30):])
        messages.append({"role": "user", "content": self.prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": CONFIG.get("num_ctx", 4096),
                "num_predict": budget,
                "repeat_penalty": CONFIG.get("repeat_penalty", 1.15)
            },
            "keep_alive": CONFIG.get("keep_alive", "5m")
        }

        full_text = []
        token_count = 0
        base_url = CONFIG.get("ollama_base_url", "http://localhost:11434")

        try:
            resp = requests.post(f"{base_url}/api/chat", json=payload, stream=True, timeout=30)
            if resp.status_code != 200:
                self.error_occurred.emit(f"Ollama server error (HTTP {resp.status_code}): {resp.text}")
                return

            for line in resp.iter_lines():
                if self._is_cancelled:
                    break
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    msg_content = chunk.get("message", {}).get("content", "")
                    if msg_content:
                        full_text.append(msg_content)
                        token_count += 1
                        self.token_received.emit(msg_content)

            self.finished_response.emit("".join(full_text), token_count)
        except Exception as e:
            # Fallback offline simulation if Ollama server is offline
            static_intent = SemanticRouter.classify_intent(self.prompt)
            advice = SemanticRouter.get_static_advice(static_intent)
            if advice:
                self.token_received.emit(advice)
                self.finished_response.emit(advice, len(advice.split()))
            else:
                self.error_occurred.emit(f"Connection failed to Ollama: {str(e)}")


class OllamaVisionWorker(QThread):
    """
    Background QThread worker for Multimodal Image+Text Analysis.
    """
    token_received = pyqtSignal(str)
    finished_response = pyqtSignal(str, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt: str, b64_images: List[str], model: Optional[str] = None):
        super().__init__()
        self.prompt = prompt
        self.images = b64_images
        self.model = model or CONFIG.get("default_vision_model", "moondream:latest")
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        base_url = CONFIG.get("ollama_base_url", "http://localhost:11434")
        sys_prompt = CONFIG.get("vision_system_prompt", "Analyze the circuit image accurately.")
        
        # User question is primary instruction
        user_message = {
            "role": "user",
            "content": f"User Query: {self.prompt}\nAnalyze the attached schematic:",
            "images": self.images
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                user_message
            ],
            "stream": True,
            "options": {
                "temperature": CONFIG.get("vision_temperature", 0.2),
                "num_ctx": CONFIG.get("num_ctx", 4096)
            }
        }

        try:
            resp = requests.post(f"{base_url}/api/chat", json=payload, stream=True, timeout=40)
            if resp.status_code != 200:
                self.error_occurred.emit(f"Vision model error: {resp.text}")
                return

            full_text = []
            token_count = 0
            for line in resp.iter_lines():
                if self._is_cancelled:
                    break
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        full_text.append(content)
                        token_count += 1
                        self.token_received.emit(content)

            self.finished_response.emit("".join(full_text), token_count)
        except Exception as e:
            self.error_occurred.emit(f"Vision analysis failed: {str(e)}")


class OllamaStatusWorker(QThread):
    """Polls Ollama daemon status on port 11434."""
    status_checked = pyqtSignal(bool, list)

    def run(self):
        base_url = CONFIG.get("ollama_base_url", "http://localhost:11434")
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                self.status_checked.emit(True, models)
                return
        except Exception:
            pass
        self.status_checked.emit(False, [])
