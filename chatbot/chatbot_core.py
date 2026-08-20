import re
from typing import Dict, List, Any, Optional

class NetlistParser:
    """
    Deterministic Netlist Pre-Parsing Matrix (Chapter 4.1.2)
    Parses SPICE netlists (.cir, .cir.out, .net) without model inference cost
    to extract a ground-truth circuit component matrix and analysis directives.
    """
    
    COMPONENT_TYPES = {
        'R': 'Resistor',
        'C': 'Capacitor',
        'L': 'Inductor',
        'V': 'Voltage Source',
        'I': 'Current Source',
        'D': 'Diode',
        'Q': 'BJT Transistor',
        'M': 'MOSFET',
        'J': 'JFET',
        'X': 'Subcircuit / IC',
        'U': 'IC Module',
        'K': 'Coupled Inductor'
    }

    @classmethod
    def parse_netlist_text(cls, netlist_content: str) -> Dict[str, Any]:
        lines = [line.strip() for line in netlist_content.splitlines()]
        title = lines[0] if lines else "Untitled Circuit"
        
        components: List[Dict[str, Any]] = []
        analysis_directives: List[str] = []
        models: List[str] = []
        includes: List[str] = []
        all_nodes = set()
        
        for line in lines[1:]:
            # Skip empty lines and comment lines
            if not line or line.startswith('*') or line.startswith(';'):
                continue
                
            tokens = line.split()
            first_token = tokens[0].upper()
            
            # Directives
            if first_token.startswith('.'):
                directive = first_token.lower()
                if directive in ['.tran', '.ac', '.dc', '.op', '.noise', '.pz']:
                    analysis_directives.append(line)
                elif directive in ['.model']:
                    models.append(line)
                elif directive in ['.include', '.lib', '.subckt']:
                    includes.append(line)
                continue
                
            # Component parsing
            prefix = first_token[0]
            if prefix in cls.COMPONENT_TYPES:
                comp_type = cls.COMPONENT_TYPES[prefix]
                name = tokens[0]
                
                # Two-terminal devices (R, C, L, V, I, D)
                if prefix in ['R', 'C', 'L', 'V', 'I', 'D'] and len(tokens) >= 3:
                    node1, node2 = tokens[1], tokens[2]
                    value = " ".join(tokens[3:]) if len(tokens) > 3 else "N/A"
                    all_nodes.update([node1, node2])
                    components.append({
                        "name": name,
                        "type": comp_type,
                        "nodes": [node1, node2],
                        "value": value,
                        "raw": line
                    })
                # Three/Four-terminal active devices (Q, M, J)
                elif prefix in ['Q', 'M', 'J'] and len(tokens) >= 4:
                    nodes = tokens[1:-1]
                    model = tokens[-1]
                    all_nodes.update(nodes)
                    components.append({
                        "name": name,
                        "type": comp_type,
                        "nodes": nodes,
                        "model": model,
                        "raw": line
                    })
                # Subcircuits (X)
                elif prefix == 'X' and len(tokens) >= 3:
                    subckt_name = tokens[-1]
                    nodes = tokens[1:-1]
                    all_nodes.update(nodes)
                    components.append({
                        "name": name,
                        "type": comp_type,
                        "nodes": nodes,
                        "subcircuit": subckt_name,
                        "raw": line
                    })
                else:
                    components.append({
                        "name": name,
                        "type": comp_type,
                        "tokens": tokens[1:],
                        "raw": line
                    })

        # Ground detection: '0' or 'GND'
        has_ground = any(n in ['0', 'GND', 'gnd'] for n in all_nodes)
        
        # Summary counts
        counts: Dict[str, int] = {}
        for c in components:
            counts[c["type"]] = counts.get(c["type"], 0) + 1

        return {
            "title": title,
            "total_components": len(components),
            "component_counts": counts,
            "components": components,
            "analysis_directives": analysis_directives,
            "models": models,
            "includes": includes,
            "unique_nodes": sorted(list(all_nodes)),
            "has_ground": has_ground
        }

    @classmethod
    def generate_summary_prompt(cls, matrix: Dict[str, Any]) -> str:
        """Formats deterministic parsed matrix into context for LLM."""
        summary_lines = [
            f"=== DETERMINISTIC NETLIST PRE-PARSING MATRIX ===",
            f"Title: {matrix['title']}",
            f"Total Components: {matrix['total_components']}",
            f"Component Counts: {matrix['component_counts']}",
            f"Ground Reference (Node 0/GND): {'Present' if matrix['has_ground'] else 'MISSING'}",
            f"Unique Nodes: {', '.join(matrix['unique_nodes'])}",
            f"Analysis Directives: {matrix['analysis_directives'] if matrix['analysis_directives'] else 'None'}",
            f"Components Breakdown:"
        ]
        for c in matrix['components']:
            summary_lines.append(f" - {c['name']} ({c['type']}): Nodes {c.get('nodes', [])}, Value/Model: {c.get('value', c.get('model', c.get('subcircuit', 'N/A')))}")
        summary_lines.append("================================================")
        return "\n".join(summary_lines)


class SemanticRouter:
    """
    Semantic Router and Error Filtering (Chapter 4.7)
    Classifies queries and provides deterministic eSim workflow knowledge.
    """
    
    WORKFLOW_KNOWLEDGE = {
        "ground": "In eSim / KiCad, ensure node 0 or a 'GND' symbol is placed. Every SPICE circuit requires a common ground reference (Node 0) for nodal voltage equations.",
        "missing_model": "Missing SPICE Model error: In eSim, open KiCad, right-click the component -> Edit Properties -> Edit Spice Model -> Select Model File (.lib / .sub / .mod).",
        "floating_node": "Floating node detected: Check for unconnected pins in KiCad schematic. All IC and subcircuit pins must either connect to a net or have a 'No Connect' flag.",
        "convergence": "NgSpice Convergence Failure: Try adding '.options rtol=1e-3 abstol=1e-12 vntol=1e-6' or set initial conditions using '.ic V(node)=0'.",
        "shortcuts": "KiCad Key Shortcuts:\n - 'A': Add Symbol\n - 'W': Add Wire\n - 'R': Rotate Component\n - 'M': Move Component\n - 'C': Copy / Duplicate\n - 'E': Edit Component Properties"
    }

    @classmethod
    def classify_intent(cls, user_text: str) -> str:
        text = user_text.lower()
        if any(k in text for k in ["shortcut", "hotkey", "keybind"]):
            return "shortcuts"
        elif any(k in text for k in ["ground", "gnd", "node 0", "reference node"]):
            return "ground"
        elif any(k in text for k in ["missing model", "missing spice model", "model not found", "spice model", ".lib", "subckt"]):
            return "missing_model"
        elif any(k in text for k in ["floating", "singular matrix", "unconnected pin"]):
            return "floating_node"
        elif any(k in text for k in ["convergence", "timestep too small", "iteration limit"]):
            return "convergence"
        return "general"

    @classmethod
    def get_static_advice(cls, intent: str) -> Optional[str]:
        return cls.WORKFLOW_KNOWLEDGE.get(intent)


def smart_num_predict(user_query: str) -> int:
    """
    Smart Token Budgeting (Chapter 4.6)
    128 tokens for simple definitional queries, 256 for general, 512 for complex SPICE.
    """
    text = user_query.lower()
    complex_keywords = ["netlist", "convergence", "simulation", "tran", "transient", "bjt", "mosfet", "subcircuit", "schematic"]
    simple_keywords = ["what is", "define", "shortcut", "version", "who made", "help", "who is"]
    
    if any(k in text for k in simple_keywords) and len(text.split()) < 8:
        return 128
    elif any(k in text for k in complex_keywords) or len(text.split()) > 15:
        return 512
    return 256


def detect_topic_switch(prev_text: str, current_text: str, threshold: float = 0.15) -> bool:
    """
    Topic switch detection using Jaccard similarity (Chapter 4.6).
    Returns True if similarity < 0.15.
    """
    stopwords = {"a", "an", "the", "in", "on", "of", "for", "to", "is", "it", "this", "that", "and", "or", "how", "what", "my"}
    def tokenize(s: str):
        words = re.findall(r"\w+", s.lower())
        return set(w for w in words if w not in stopwords)
        
    set1 = tokenize(prev_text)
    set2 = tokenize(current_text)
    if not set1 or not set2:
        return False
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    similarity = intersection / union if union > 0 else 1.0
    return similarity < threshold


def filter_hallucinated_errors(errors: List[str], ocr_or_netlist_text: str) -> List[str]:
    """
    Smart Error Filtering (Chapter 4.7):
    Suppresses hallucinated errors (e.g. 'missing ground' if GND is present).
    """
    filtered = []
    text_lower = ocr_or_netlist_text.lower()
    for err in errors:
        err_lower = err.lower()
        if "missing ground" in err_lower and ("gnd" in text_lower or "ground" in text_lower or "node 0" in text_lower):
            continue
        filtered.append(err)
    return filtered
