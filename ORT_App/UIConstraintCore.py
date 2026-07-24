import json
import os
import textwrap

class UIConstraintCore:
    def __init__(self):
        print("[UI-C] Initializing Layout Engine v1.1 (FIXED)...")
        self.config_file = "ui_constraints.json"
        self.config = {}

    def fit_text(self, text):
        if not text: return ""
        width = 60
        max_lines = 3
        wrapped_lines = textwrap.wrap(text, width=width)
        
        # INI PERBAIKANNYA (ADA TITIK DUA)
        if len(wrapped_lines) > max_lines:
            wrapped_lines = wrapped_lines[:max_lines]
            wrapped_lines[-1] += "..."
            
        return "<br>".join(wrapped_lines)
