"""
eSim AI Assistant - Main Application Entrypoint
FOSSEE Summer Fellowship 2026
Author: Aditya Pandey
"""
import sys
import os

def main():
    print("==================================================")
    print("       eSim AI Assistant - FOSSEE Fellowship     ")
    print("           Author: Aditya Pandey                  ")
    print("==================================================")
    
    try:
        from PyQt5.QtWidgets import QApplication
        from chatbot.Chatbot import ChatbotGUI
        
        app = QApplication(sys.argv)
        gui = ChatbotGUI()
        gui.show()
        sys.exit(app.exec_())
    except ImportError:
        print("[Notice] PyQt5 is not installed in the active environment.")
        print("Running CLI Interactive Demonstration Mode...")
        from chatbot.chatbot_core import NetlistParser, SemanticRouter
        
        sample_file = os.path.join("sample_data", "circuits", "rc_lowpass.cir")
        if os.path.exists(sample_file):
            with open(sample_file, "r") as f:
                content = f.read()
            matrix = NetlistParser.parse_netlist_text(content)
            print("\n[Deterministic Netlist Parser Demonstration]:")
            print(NetlistParser.generate_summary_prompt(matrix))
        
        print("\n[Semantic Router Demonstration]:")
        intent = SemanticRouter.classify_intent("How do I fix missing SPICE model?")
        print(f"Intent: {intent}")
        print(f"Guidance: {SemanticRouter.get_static_advice(intent)}")

if __name__ == "__main__":
    main()
