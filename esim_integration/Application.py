import os
from typing import Optional

try:
    from PyQt5.QtWidgets import QMainWindow, QDockWidget, QPushButton
    from PyQt5.QtCore import Qt
    from chatbot.Chatbot import ChatbotGUI
except ImportError:
    QMainWindow = object
    QDockWidget = object

class ESimMainWindowIntegration:
    """
    Main Window Integration (Chapter 6.3)
    Instantiates ChatbotGUI wrapped inside a QDockWidget pinned to the right edge.
    """
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
        self.chatbot_widget: Optional[ChatbotGUI] = None
        self.dock: Optional[QDockWidget] = None
        self._setup_dock()

    def _setup_dock(self):
        if not hasattr(self.main_window, "addDockWidget"): return
        
        self.chatbot_widget = ChatbotGUI(self.main_window)
        self.dock = QDockWidget("eSim AI Assistant", self.main_window)
        self.dock.setObjectName("ESimAIAssistantDock")
        self.dock.setWidget(self.chatbot_widget)
        self.dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.dock)

    def toggle_assistant(self):
        if self.dock:
            self.dock.setVisible(not self.dock.isVisible())
