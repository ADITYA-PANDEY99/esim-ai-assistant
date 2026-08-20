import unittest
from chatbot.chatbot_core import SemanticRouter, smart_num_predict, detect_topic_switch

class TestSemanticRouter(unittest.TestCase):
    def test_intent_classification(self):
        self.assertEqual(SemanticRouter.classify_intent("What is the shortcut for adding wire in KiCad?"), "shortcuts")
        self.assertEqual(SemanticRouter.classify_intent("My simulation has a floating node error"), "floating_node")
        self.assertEqual(SemanticRouter.classify_intent("How to fix singular matrix and ground?"), "ground")

    def test_smart_token_budget(self):
        self.assertEqual(smart_num_predict("What is eSim?"), 128)
        self.assertEqual(smart_num_predict("Explain NgSpice transient analysis simulation convergence issue on BJT amplifier"), 512)

    def test_topic_switch(self):
        s1 = "How do I configure transient analysis in NgSpice?"
        s2 = "What is the shortcut key to rotate a resistor in KiCad?"
        self.assertTrue(detect_topic_switch(s1, s2))

if __name__ == "__main__":
    unittest.main()
