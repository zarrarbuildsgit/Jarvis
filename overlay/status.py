"""
JARVIS Desktop Overlay Module
Transparent always-on-top window showing agent status
"""

import sys
import threading
from pathlib import Path
from loguru import logger

class JARVISOverlay:
    """Transparent overlay widget showing JARVIS status and thoughts"""
    
    def __init__(self):
        self.status_text = "JARVIS: Initializing..."
        self.is_running = False
        self.thought_buffer = []
        self.max_thoughts = 10
        self.root = None
    
    def start(self):
        """Start the overlay in a separate thread"""
        self.is_running = True
        
        try:
            import customtkinter as ctk
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            self.root = ctk.CTk()
            self.root.geometry("320x180")
            self.root.title("JARVIS Status")
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.9)
            self.root.resizable(False, False)
            
            # Remove window decorations on Windows
            if sys.platform == "win32":
                self.root.overrideredirect(True)
            
            # Main frame
            frame = ctk.CTkFrame(self.root, corner_radius=15)
            frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Status label
            self.status_label = ctk.CTkLabel(
                frame,
                text=f"🤖 {self.status_text}",
                font=("Segoe UI", 14, "bold")
            )
            self.status_label.pack(pady=(15, 5))
            
            # Thought display
            self.thought_label = ctk.CTkLabel(
                frame,
                text="Awaiting commands...",
                font=("Segoe UI", 11),
                text_color="gray",
                wraplength=280
            )
            self.thought_label.pack(pady=5)
            
            # Trust level indicator
            self.trust_label = ctk.CTkLabel(
                frame,
                text="Trust Level: 1 (New)",
                font=("Segoe UI", 10),
                text_color="orange"
            )
            self.trust_label.pack(pady=(5, 15))
            
            self.root.protocol("WM_DELETE_WINDOW", self.stop)
            logger.info("Overlay UI initialized")
            
        except ImportError:
            logger.warning("customtkinter not available, overlay disabled")
            self.is_running = False
        except Exception as e:
            logger.error(f"Overlay initialization failed: {e}")
            self.is_running = False
    
    def run(self):
        """Run the overlay UI loop (call from main thread)"""
        if self.root:
            self.root.mainloop()
    
    def stop(self):
        """Stop the overlay"""
        self.is_running = False
        if self.root:
            self.root.destroy()
    
    def update_status(self, text: str):
        """Update the status text"""
        self.status_text = text
        if hasattr(self, 'status_label') and self.root:
            self.root.after(0, lambda: self.status_label.configure(text=f"🤖 {text}"))
    
    def update_thought(self, thought: str):
        """Update the thought display"""
        self.thought_buffer.append(thought)
        if len(self.thought_buffer) > self.max_thoughts:
            self.thought_buffer.pop(0)
        
        display_text = "\n".join(self.thought_buffer[-3:])
        if hasattr(self, 'thought_label') and self.root:
            self.root.after(0, lambda: self.thought_label.configure(text=display_text))
    
    def update_trust(self, level: int):
        """Update the trust level indicator"""
        descriptions = {
            1: "New (Read-only)",
            2: "Proven (Basic ops)",
            3: "Trusted (System mods)",
            4: "Full (Unrestricted)"
        }
        desc = descriptions.get(level, "Unknown")
        if hasattr(self, 'trust_label') and self.root:
            self.root.after(0, lambda: self.trust_label.configure(text=f"Trust Level: {level} ({desc})"))
    
    def show_advisory(self, title: str, message: str):
        """Show an advisory message (when user asks for guidance)"""
        if hasattr(self, 'thought_label') and self.root:
            self.root.after(0, lambda: self.thought_label.configure(
                text=f"💡 {title}\n{message}"
            ))
