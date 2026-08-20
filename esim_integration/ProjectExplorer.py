import os
from typing import Optional
from chatbot.chatbot_core import NetlistParser

class ProjectExplorerContextMenuHooks:
    """
    Project Explorer Context Menu Hooks (Chapter 6.3)
    Right-click options: 'Analyse Project Netlist' and 'Analyse this Netlist'.
    """
    @staticmethod
    def analyse_netlist(netlist_path: str, chatbot_gui) -> bool:
        if not os.path.exists(netlist_path): return False
        try:
            with open(netlist_path, "r", encoding="utf-8") as f:
                content = f.read()
            matrix = NetlistParser.parse_netlist_text(content)
            summary = NetlistParser.generate_summary_prompt(matrix)
            
            if chatbot_gui and hasattr(chatbot_gui, "input_field"):
                chatbot_gui.input_field.setText(f"Please analyse this circuit netlist:\n{summary}")
                chatbot_gui.send_message()
            return True
        except Exception:
            return False
