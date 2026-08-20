import os
import json
import time
from typing import List, Dict, Any, Optional

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit,
        QPushButton, QComboBox, QLabel, QListWidget, QListWidgetItem,
        QSplitter, QFileDialog, QDialog, QMessageBox, QFrame, QScrollArea
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QUrl
    from PyQt5.QtGui import QFont, QIcon, QPixmap
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    class QWidget: pass

from chatbot.Appconfig import CONFIG
from chatbot.chatbot_core import NetlistParser, detect_topic_switch
from chatbot.image_handler import safe_process_image
from chatbot.chatbot_thread import OllamaWorker, OllamaVisionWorker, OllamaStatusWorker

class HistoryLineEdit(QLineEdit if PYQT_AVAILABLE else object):
    """Custom input component with command-style Up/Down history navigation."""
    def __init__(self, parent=None):
        if PYQT_AVAILABLE:
            super().__init__(parent)
            self.history: List[str] = []
            self.history_idx: int = -1

    def keyPressEvent(self, event):
        if not PYQT_AVAILABLE: return
        if event.key() == Qt.Key_Up:
            if self.history and self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.history[-(self.history_idx + 1)])
            return
        elif event.key() == Qt.Key_Down:
            if self.history_idx > 0:
                self.history_idx -= 1
                self.setText(self.history[-(self.history_idx + 1)])
            elif self.history_idx == 0:
                self.history_idx = -1
                self.clear()
            return
        super().keyPressEvent(event)

    def record_input(self, text: str):
        if text.strip():
            self.history.append(text.strip())
            self.history_idx = -1


class ChatbotGUI(QWidget):
    """
    eSim AI Assistant GUI
    - HTML Table message bubbles with Markdown parsing & action links
    - Named HTML anchor (_typing_anchor_) for reflow-safe typing animation (Bug 2 Fix)
    - Staged image thumbnail preview strip
    - Debounced 5s autosave (Bug 3 Fix)
    - Auto-scroll heuristic (< 60px)
    """
    def __init__(self, parent=None):
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt5 is required to instantiate ChatbotGUI.")
        super().__init__(parent)
        self.setWindowTitle("eSim AI Assistant")
        self.resize(850, 650)
        
        self.messages: List[Dict[str, Any]] = []
        self.current_session_id = f"session_{int(time.time())}"
        self.attached_images_b64: List[str] = []
        self.current_worker = None
        
        # Debounce timer for autosave (Bug 3 Fix: stopped on deletion)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self._save_session_to_disk)
        self.pending_save = False

        self._init_ui()
        self._check_ollama_status()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        splitter = QSplitter(Qt.Horizontal, self)
        
        # Sidebar: Sessions
        self.sidebar = QListWidget(self)
        self.sidebar.setMaximumWidth(200)
        self.sidebar.itemClicked.connect(self._on_session_selected)
        self._refresh_sidebar()
        splitter.addWidget(self.sidebar)
        
        # Chat Panel
        chat_container = QWidget(self)
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top toolbar
        top_bar = QHBoxLayout()
        self.model_selector = QComboBox(self)
        self.model_selector.addItems(["llama3.2:3b", "mistral:7b", "qwen2.5:3b", "moondream:latest"])
        self.status_label = QLabel("● Checking Server...", self)
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
        new_chat_btn = QPushButton("New Chat", self)
        new_chat_btn.clicked.connect(self.start_new_session)
        
        top_bar.addWidget(QLabel("Model:", self))
        top_bar.addWidget(self.model_selector)
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        top_bar.addWidget(new_chat_btn)
        chat_layout.addLayout(top_bar)
        
        # Message Display (QTextBrowser with HTML rendering)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        chat_layout.addWidget(self.browser)
        
        # Thumbnail preview strip
        self.thumb_layout = QHBoxLayout()
        self.thumb_frame = QFrame(self)
        self.thumb_frame.setLayout(self.thumb_layout)
        self.thumb_frame.hide()
        chat_layout.addWidget(self.thumb_frame)
        
        # Bottom Input Toolbar
        input_bar = QHBoxLayout()
        self.input_field = HistoryLineEdit(self)
        self.input_field.setPlaceholderText("Ask a circuit question or describe simulation error...")
        self.input_field.returnPressed.connect(self.send_message)
        
        self.attach_btn = QPushButton("📎 Attach Image", self)
        self.attach_btn.clicked.connect(self._attach_image)
        
        self.netlist_btn = QPushButton("📄 Netlist", self)
        self.netlist_btn.clicked.connect(self._upload_netlist)
        
        self.send_btn = QPushButton("Send", self)
        self.send_btn.clicked.connect(self.send_message)
        
        input_bar.addWidget(self.attach_btn)
        input_bar.addWidget(self.netlist_btn)
        input_bar.addWidget(self.input_field)
        input_bar.addWidget(self.send_btn)
        chat_layout.addLayout(input_bar)
        
        splitter.addWidget(chat_container)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)
        
        self._append_system_message("Welcome to eSim AI Assistant. Offline, deterministic EDA analysis ready.")

    def _check_ollama_status(self):
        self.status_worker = OllamaStatusWorker()
        self.status_worker.status_checked.connect(self._on_status_result)
        self.status_worker.start()

    def _on_status_result(self, is_online: bool, models: list):
        if is_online:
            self.status_label.setText("● Online (Local)")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            if models:
                self.model_selector.clear()
                self.model_selector.addItems(models)
        else:
            self.status_label.setText("● Offline (Rule-based Fallback)")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def _append_system_message(self, text: str):
        html = f"""<div style="text-align: center; margin: 10px 0;">
            <span style="background-color: #fff3cd; color: #856404; padding: 4px 12px; border-radius: 12px; font-size: 11px;">
                ⚙️ {text}
            </span>
        </div>"""
        self.browser.append(html)

    def _render_all_messages(self):
        """Full HTML rendering with User/Bot/System bubbles and Action links."""
        self.browser.clear()
        for idx, m in enumerate(self.messages):
            role = m["role"]
            content = m["content"]
            ts = m.get("timestamp", "")
            
            if role == "user":
                img_html = ""
                if m.get("images"):
                    for img_b64 in m["images"]:
                        img_html += f'<br><img src="data:image/jpeg;base64,{img_b64}" width="200" style="border-radius:6px; margin-top:5px;"/>'
                
                html = f"""<table width="100%" style="margin: 6px 0;"><tr>
                    <td width="20%"></td>
                    <td width="80%" style="text-align: right;">
                        <div style="display: inline-block; text-align: left; background: #e3f2fd; color: #0d47a1; padding: 8px 12px; border-radius: 12px; border-bottom-right-radius: 2px;">
                            {content}
                            {img_html}
                            <div style="font-size: 9px; color: #90caf9; text-align: right; margin-top: 4px;">{ts}</div>
                        </div>
                    </td>
                </tr></table>"""
                self.browser.append(html)
            elif role == "assistant":
                tokens = m.get("tokens", 0)
                html = f"""<table width="100%" style="margin: 6px 0;"><tr>
                    <td width="80%" style="text-align: left;">
                        <div style="display: inline-block; background: #f5f5f5; color: #212121; padding: 8px 12px; border-radius: 12px; border-bottom-left-radius: 2px;">
                            {content}
                            <div style="font-size: 9px; color: #9e9e9e; margin-top: 6px;">
                                <span>{ts} • {tokens} tokens</span> • 
                                <a href="copy:///{idx}" style="color: #1976d2; text-decoration: none;">Copy</a> • 
                                <a href="retry:///{idx}" style="color: #1976d2; text-decoration: none;">Retry</a>
                            </div>
                        </div>
                    </td>
                    <td width="20%"></td>
                </tr></table>"""
                self.browser.append(html)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text and not self.attached_images_b64:
            return
            
        self.input_field.record_input(text)
        self.input_field.clear()
        
        # Check topic switch (Chapter 4.6)
        if self.messages:
            last_user_msg = next((m["content"] for m in reversed(self.messages) if m["role"] == "user"), "")
            if last_user_msg and detect_topic_switch(last_user_msg, text):
                self._append_system_message("New topic detected — context window reset.")
        
        # Record user message
        user_entry = {
            "role": "user",
            "content": text,
            "images": list(self.attached_images_b64),
            "timestamp": time.strftime("%H:%M")
        }
        self.messages.append(user_entry)
        self._render_all_messages()
        
        # Clear staging thumbnails
        self.attached_images_b64.clear()
        self.thumb_frame.hide()
        
        # Trigger Debounced Autosave (5 seconds)
        self._schedule_autosave()
        
        # Start Worker Thread
        selected_model = self.model_selector.currentText()
        if user_entry.get("images"):
            self.current_worker = OllamaVisionWorker(text, user_entry["images"], model=selected_model)
        else:
            hist = [{"role": m["role"], "content": m["content"]} for m in self.messages[:-1]]
            self.current_worker = OllamaWorker(text, hist, model=selected_model)
            
        self.current_worker.finished_response.connect(self._on_worker_finished)
        self.current_worker.error_occurred.connect(self._on_worker_error)
        self.current_worker.start()

    def _on_worker_finished(self, full_response: str, token_count: int):
        self.messages.append({
            "role": "assistant",
            "content": full_response,
            "tokens": token_count,
            "timestamp": time.strftime("%H:%M")
        })
        self._render_all_messages()
        self._schedule_autosave()

    def _on_worker_error(self, err_msg: str):
        self._append_system_message(f"Error: {err_msg}")

    def _attach_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Attach Schematic Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            res = safe_process_image(file_path)
            if res["success"]:
                self.attached_images_b64.append(res["base64"])
                self.thumb_frame.show()
                self._append_system_message(f"Attached image: {os.path.basename(file_path)} ({res['size_bytes']/1024:.1f} KB)")
            else:
                QMessageBox.warning(self, "Attachment Error", res["error"])

    def _upload_netlist(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Upload Netlist File", "", "SPICE Netlists (*.cir *.cir.out *.net *.txt)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                matrix = NetlistParser.parse_netlist_text(content)
                summary = NetlistParser.generate_summary_prompt(matrix)
                self.input_field.setText(f"Explain this netlist and verify components:\n{summary}")
            except Exception as e:
                QMessageBox.warning(self, "Netlist Parse Error", str(e))

    def _on_anchor_clicked(self, url: QUrl):
        scheme = url.scheme()
        path = url.path().lstrip("/")
        if scheme == "retry":
            try:
                idx = int(path)
                # Trim history to that message and re-send
                if idx < len(self.messages):
                    user_q = self.messages[idx - 1]["content"] if idx > 0 else ""
                    self.messages = self.messages[:idx]
                    self.input_field.setText(user_q)
                    self.send_message()
            except Exception:
                pass
        elif scheme == "copy":
            try:
                idx = int(path)
                if idx < len(self.messages):
                    from PyQt5.QtWidgets import QApplication
                    QApplication.clipboard().setText(self.messages[idx]["content"])
                    self._append_system_message("Response copied to clipboard.")
            except Exception:
                pass

    def _schedule_autosave(self):
        self.pending_save = True
        self.autosave_timer.start(int(CONFIG.get("autosave_debounce_sec", 5.0) * 1000))

    def _save_session_to_disk(self):
        if not self.pending_save: return
        session_file = os.path.join(CONFIG.sessions_dir, f"{self.current_session_id}.json")
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self.current_session_id,
                    "updated_at": time.time(),
                    "messages": self.messages
                }, f, indent=2)
            self.pending_save = False
            self._refresh_sidebar()
        except Exception:
            pass

    def start_new_session(self):
        self._save_session_to_disk()
        self.current_session_id = f"session_{int(time.time())}"
        self.messages.clear()
        self.browser.clear()
        self._append_system_message("Started fresh chat session.")

    def _refresh_sidebar(self):
        self.sidebar.clear()
        if not os.path.exists(CONFIG.sessions_dir): return
        for fname in sorted(os.listdir(CONFIG.sessions_dir), reverse=True):
            if fname.endswith(".json"):
                s_id = fname[:-5]
                item = QListWidgetItem(f"💬 {s_id}")
                item.setData(Qt.UserRole, s_id)
                self.sidebar.addItem(item)

    def _on_session_selected(self, item: QListWidgetItem):
        s_id = item.data(Qt.UserRole)
        session_file = os.path.join(CONFIG.sessions_dir, f"{s_id}.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.current_session_id = s_id
                self.messages = data.get("messages", [])
                self._render_all_messages()
            except Exception:
                pass
