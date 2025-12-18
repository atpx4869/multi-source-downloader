import sys
import os

# The structure is:
# root/ppllocr/ (this file)
# root/ppllocr/ppllocr-main/ppllocr/__init__.py
# root/ppllocr/ppllocr-main/ppllocr/inference.py

current_dir = os.path.dirname(os.path.abspath(__file__))
inner_root = os.path.join(current_dir, "ppllocr-main")

if inner_root not in sys.path:
    sys.path.insert(0, inner_root)

try:
    from ppllocr.inference import OCR
except (ImportError, SystemError):
    # Try absolute path if relative fails
    sys.path.append(os.path.join(inner_root, "ppllocr"))
    try:
        from inference import OCR
    except (ImportError, SystemError):
        OCR = None
