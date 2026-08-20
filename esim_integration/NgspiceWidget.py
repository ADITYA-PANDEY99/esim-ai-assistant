import os
import time
from typing import Optional

class NgspiceErrorInterceptor:
    """
    Simulation Error Interception (Chapter 6.3)
    On simulation failure, captures stderr to ngspice_error.log and triggers AI debugging.
    """
    def __init__(self, chatbot_gui=None):
        self.chatbot_gui = chatbot_gui
        self.log_path = os.path.expanduser("~/.esim/ngspice_error.log")

    def on_simulation_failed(self, stderr_output: str, netlist_path: Optional[str] = None):
        """Captured simulation crash handler."""
        # 1. Log error to file
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"--- NGSPICE SIMULATION ERROR ({time.ctime()}) ---\n")
            f.write(stderr_output)
            
        # 2. Schedule automated debug prompt in AI Assistant
        if self.chatbot_gui and hasattr(self.chatbot_gui, "input_field"):
            prompt = f"NgSpice simulation failed with error:\n```\n{stderr_output.strip()}\n```\nHow do I fix this in eSim?"
            self.chatbot_gui.input_field.setText(prompt)
            self.chatbot_gui.send_message()
