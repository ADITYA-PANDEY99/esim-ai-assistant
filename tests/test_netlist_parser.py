import unittest
from chatbot.chatbot_core import NetlistParser

SAMPLE_NETLIST = """* Test RC Circuit
V1 in 0 5V
R1 in out 10k
C1 out 0 100n
.tran 1u 10m
.end
"""

class TestNetlistParser(unittest.TestCase):
    def test_deterministic_parser_components(self):
        matrix = NetlistParser.parse_netlist_text(SAMPLE_NETLIST)
        self.assertEqual(matrix["total_components"], 3)
        self.assertTrue(matrix["has_ground"])
        self.assertIn("0", matrix["unique_nodes"])
        self.assertIn("in", matrix["unique_nodes"])
        self.assertIn("out", matrix["unique_nodes"])
        self.assertEqual(matrix["component_counts"]["Resistor"], 1)
        self.assertEqual(matrix["component_counts"]["Capacitor"], 1)
        self.assertEqual(matrix["component_counts"]["Voltage Source"], 1)
        self.assertEqual(len(matrix["analysis_directives"]), 1)

    def test_missing_ground_detection(self):
        netlist_no_gnd = """* No Ground Circuit
R1 nodeA nodeB 1k
C1 nodeB nodeC 10u
.end
"""
        matrix = NetlistParser.parse_netlist_text(netlist_no_gnd)
        self.assertFalse(matrix["has_ground"])

if __name__ == "__main__":
    unittest.main()
