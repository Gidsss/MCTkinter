# Markov Chain-Based Linguistic Steganography with Binary Encoding

This project implements a desktop-based steganographic system using Markov Chains to encode and decode binary bitstreams into natural-language-like text. It is part of the thesis:

**"Enhancement of Markov Chain-Based Linguistic Steganography with Binary Encoding for Securing Legal Documents."**

## Description

The system enhances traditional linguistic steganography by:

- Converting binary data into syntactically plausible text using Markov Chains.
- Supporting two algorithms:
  - **Existing Algorithm** – Original implementation without validation for tail bits.
  - **Enhanced Algorithm** – Improved version that injects an end key to ensure complete decodability.

### SOP-Based Behavior

- The Existing Algorithm does not handle incomplete bit groups, potentially resulting in gibberish output or decoding errors, as documented in the SOP.
- The Enhanced Algorithm prevents this by appending a marker for the final bit group.

## GUI Features (Tkinter)

- Upload `.txt`, `.pdf`, or `.docx` files.
- Automatically encode them using the selected algorithm.
- View all uploaded and processed files in a table.
- Decode selected files and view the generated steganographic text.
- See real-time encoding progress and elapsed time via a progress window.
- Alerts if encoding fails (as expected in the SOP for the existing algorithm).

## Project Structure

```
project/
├── thesis_toolkit.pyx                    # Core Cython source for encoders/decoders
├── steganography.db                      # Local database for encoded file history
├── markov_models/
│   └── legal_corpus.json                # Pre-trained Markov model for legal documents
├── media/                               # Optional media assets (if used)
├── src/
│   ├── main.py                          # Main Tkinter GUI application
│   └── db_utils.py                      # SQLite-based database helper functions
├── venv/                                # Python virtual environment
├── README.md                            # Project description and usage guide
├── requirements.txt                     # List of Python dependencies
├── setup.py                             # Build configuration for Cython
└── .gitignore                           # Git ignored files
```

## Installation

### Prerequisites

- Python 3.12+
- pip
- Cython
- Required Python packages

### Setup

1. Clone the repository:

```bash
git clone https://github.com/Gidsss/MCTkinter
cd MCTkinter
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Compile the Cython module:

```bash
python setup.py build_ext --inplace
```

5. Run the application:

```bash
python src/main.py
```

