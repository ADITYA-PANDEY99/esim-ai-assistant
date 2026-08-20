# eSim AI Assistant ⚡🤖

> **Intelligent, Offline, Deterministic AI Assistant for eSim EDA & NgSpice Simulation**  
> *Developed for the FOSSEE Summer Fellowship 2026 at IIT Bombay*  
> **Author:** Aditya Pandey

---

## 📖 Overview

The **eSim AI Assistant** is a multimodal, offline, zero-latency artificial intelligence assistant embedded directly into **eSim** (the open-source EDA suite developed by FOSSEE, IIT Bombay). It bridges the cognitive gap for engineering students and circuit designers by providing automated SPICE netlist parsing, vision-based schematic defect detection, contextual RAG documentation search, and NgSpice simulation crash diagnostics.

---

## 🚀 Key Architectural Features

### 1. Deterministic Netlist Pre-Parsing Matrix
- Rule-based state machine that parses `.cir`, `.cir.out`, and `.net` files offline.
- Extracts reference designators, node connections, component parameters, and analysis directives (`.tran`, `.ac`, `.dc`, `.op`).
- Ground-truth circuit representations prevent LLM hallucination of component counts and net connectivity.

### 2. Multi-Modal Vision Analysis Pipeline (VLM + Safe OCR)
- Supports drag-and-drop and clipboard schematic screenshots.
- Downscales images to $336 \times 336$ via LANCZOS interpolation and converts to JPEG quality 70.
- Implements strict **11-point security hardening** against decompression bombs, prompt injection, and untrusted JSON outputs.

### 3. Thread-Safe Subprocess RAG Pipeline
- Retrieves contextual documentation from eSim and NgSpice manuals stored in **ChromaDB** with `nomic-embed-text` embeddings.
- Executes vector search in an **isolated Python subprocess** via Base64 streams, preventing SQLite C++ threading crashes on Windows.

### 4. Smart Token Budgeting & Dynamic Topic Detection
- Dynamically allocates token budgets ($128$, $256$, or $512$ tokens) based on query complexity, cutting response latency by ~50%.
- Jaccard similarity topic switch detection ($< 0.15$ threshold) resets sliding context windows cleanly.

### 5. PyQt5 UI with Anchor-Based Animation
- Clean HTML table chat bubbles (User, Bot with Markdown & action links `retry:///`, `copy:///`, System).
- Uses named HTML anchors (`_typing_anchor_`) to prevent chat text corruption during window resizing or reflow.
- Debounced 5-second session autosave prevents disk I/O bottlenecks.

---

## 🛠️ Security Hardening (Chapter 5)

| Vulnerability / Defect | Mitigation Implemented |
| :--- | :--- |
| **1. Decompression Bomb Susceptibility** | 512 KB (`MAX_IMAGE_BYTES`) file size limit before decompression |
| **2. Prompt Injection via OCR Text** | Injected under isolated, data-only `CONTEXT FROM OCR SCAN` block |
| **3. Validation Ordering Race Conditions** | Strict sequence: Existence $\to$ File Size $\to$ Image Decoding |
| **4. Uncontrolled Image Color Formats** | Explicit conversion to RGB / Greyscale |
| **5. Unbounded Retry Loops** | Bounded retries ($\le 2$) with 2-second delay |
| **6. PaddleOCR MKLDNN VM Crash** | `enable_mkldnn=False`, `use_angle_cls=False` |
| **7. Malformed Model JSON Output** | Strips markdown fences, verifies 5 required root keys |
| **8. Incomplete Error Structures** | Guaranteed 6-key structured error dictionary returns |
| **9. Duplicate Component Dumps** | In-order deduplication via `dict.fromkeys()` |
| **10. Zero-Count Fallback Anomalies** | Fallback count synthesis from reference designator prefixes |
| **11. Low-Confidence OCR Noise** | Discards OCR predictions with confidence score $< 0.6$ |

---

## 📁 Repository Structure

```
esim-ai-assistant/
├── chatbot/
│   ├── __init__.py
│   ├── Appconfig.py           # Self-healing runtime & deep-merge configuration
│   ├── chatbot_core.py        # Netlist parser, semantic router, token budgeting
│   ├── chatbot_thread.py      # QThread background workers & isolated RAG subprocess
│   ├── image_handler.py       # Safe image processing & security hardening
│   ├── knowledge_base.py      # ChromaDB vector store & paragraph chunker
│   ├── speech_recognizer.py   # Dual-pathway speech-to-text (Vosk + SpeechRecognition)
│   └── Chatbot.py             # PyQt5 GUI, bubble rendering, debounced autosave
├── esim_integration/
│   ├── __init__.py
│   ├── Application.py         # Main window QDockWidget integration
│   ├── NgspiceWidget.py       # Simulation failure & stderr interception
│   └── ProjectExplorer.py     # Netlist analysis context menu hooks
├── sample_data/
│   ├── circuits/              # Sample SPICE netlists (.cir)
│   └── manuals/               # eSim documentation & troubleshooting guides
├── tests/                     # Comprehensive pytest test suite
├── config.json                # Runtime configuration defaults
├── requirements.txt           # Python dependencies
├── main.py                    # Standalone executable launcher
└── README.md
```

---

## ⚡ Installation & Usage

### 1. Clone the repository
```bash
git clone https://github.com/ADITYA-PANDEY99/esim-ai-assistant.git
cd esim-ai-assistant
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the AI Assistant
```bash
python main.py
```

### 4. Run Automated Test Suite
```bash
pytest tests/
```

---

## 📜 License & Acknowledgments
Developed as part of the **FOSSEE Summer Fellowship 2026** under the guidance of **Prof. Prabhu Ramachandran** (Principal Investigator, FOSSEE, IIT Bombay) and **Sumanto Kar** (Mentor, FOSSEE Project, IIT Bombay).
