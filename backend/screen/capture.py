"""
JARVIS Screen Capture Module
DXCam (Windows) + mss (cross-platform fallback)
"""

import numpy as np
from PIL import Image
import time
from pathlib import Path
from loguru import logger

class ScreenCapture:
    def __init__(self):
        self.backend = None
        self.backend_type = None
        self.last_screenshot = None
        self.last_timestamp = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Try to initialize the best available screen capture backend"""
        try:
            import dxcam
            self.backend = dxcam.create()
            self.backend_type = "dxcam"
            logger.info("DXCam backend initialized")
        except Exception as e:
            logger.warning(f"DXCam failed: {e}, falling back to mss")
            try:
                import mss
                self.backend = mss.mss()
                self.backend_type = "mss"
                logger.info("mss backend initialized")
            except Exception as e2:
                logger.error(f"All screen capture backends failed: {e2}")
                self.backend = None
    
    def capture(self, region=None):
        """Capture screenshot. Returns PIL Image."""
        try:
            if self.backend is None:
                logger.error("No screen capture backend available")
                return None
            
            if self.backend_type == "mss":
                if region:
                    monitor = {"top": region[1], "left": region[0], 
                               "width": region[2], "height": region[3]}
                else:
                    monitor = self.backend.monitors[0]
                sct_img = self.backend.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            else:
                if region:
                    frame = self.backend.grab(region=region)
                else:
                    frame = self.backend.grab()
                img = Image.fromarray(frame) if frame is not None else None
            
            self.last_screenshot = img
            self.last_timestamp = time.time()
            return img
            
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None
    
    def capture_region(self, x, y, width, height):
        """Capture specific region of screen"""
        return self.capture(region=(x, y, width, height))
    
    def get_last_screenshot(self):
        return self.last_screenshot
    
    def save_screenshot(self, filepath=None):
        """Save last screenshot to file"""
        if self.last_screenshot is None:
            logger.warning("No screenshot to save")
            return None
        
        if filepath is None:
            filepath = f"data/screenshots/screenshot_{int(time.time())}.png"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self.last_screenshot.save(filepath)
        logger.info(f"Screenshot saved to {filepath}")
        return filepath
    
    def get_screen_info(self):
        """Get screen resolution and monitor info"""
        try:
            if self.backend_type == "mss":
                monitors = self.backend.monitors
                primary = monitors[0]
                return {
                    "monitors": len(monitors) - 1,
                    "primary": {"width": primary["width"], "height": primary["height"],
                                "left": primary["left"], "top": primary["top"]}
                }
            elif self.backend_type == "dxcam":
                return {"width": self.backend.width, "height": self.backend.height, "fps": self.backend.fps}
        except Exception as e:
            logger.error(f"Failed to get screen info: {e}")
        return {"error": "Could not determine screen info"}
