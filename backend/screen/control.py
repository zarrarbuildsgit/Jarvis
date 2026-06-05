"""
JARVIS Screen Control Module
pywinauto + uiautomation + PyDirectInput combo
"""

import time
from loguru import logger
from typing import Optional, List, Dict

class ScreenControl:
    def __init__(self):
        self.pywinauto_initialized = False
        self.uia_initialized = False
        self.direct_input_initialized = False
        self.pywinauto_app = None
        self.desktop = None
        self.auto = None
        self.direct_input = None
        self._initialize_libraries()
    
    def _initialize_libraries(self):
        """Initialize screen control libraries"""
        try:
            from pywinauto import Application, Desktop
            self.pywinauto_app = Application(backend="uia")
            self.desktop = Desktop(backend="uia")
            self.pywinauto_initialized = True
            logger.info("pywinauto initialized")
        except Exception as e:
            logger.warning(f"pywinauto failed: {e}")
        
        try:
            import uiautomation as auto
            self.auto = auto
            self.uia_initialized = True
            logger.info("uiautomation initialized")
        except Exception as e:
            logger.warning(f"uiautomation failed: {e}")
        
        try:
            import pydirectinput
            pydirectinput.FAILSAFE = True
            self.direct_input = pydirectinput
            self.direct_input_initialized = True
            logger.info("PyDirectInput initialized")
        except Exception as e:
            logger.warning(f"PyDirectInput failed: {e}")
    
    def click(self, x: int = None, y: int = None, button: str = "left", element_name: str = None):
        """Click at coordinates or on a UI element"""
        if element_name and self.uia_initialized:
            return self._click_element(element_name)
        elif x is not None and y is not None:
            return self._click_coordinates(x, y, button)
        else:
            logger.error("Need either coordinates or element_name")
            return False
    
    def _click_element(self, element_name: str):
        """Click a UI element by name using uiautomation"""
        try:
            element = self.auto.Control(Name=element_name)
            if element.Exists(maxSearchSeconds=2):
                element.Click()
                logger.info(f"Clicked element: {element_name}")
                return True
            else:
                logger.warning(f"Element not found: {element_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to click element {element_name}: {e}")
            return False
    
    def _click_coordinates(self, x: int, y: int, button: str):
        """Click at specific coordinates"""
        try:
            if self.direct_input_initialized:
                self.direct_input.click(x, y, button=button)
            else:
                import pyautogui
                pyautogui.click(x, y, button=button)
            logger.info(f"Clicked at ({x}, {y}) with {button} button")
            return True
        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            return False
    
    def move_to(self, x: int, y: int, duration: float = 0.3):
        """Move mouse to coordinates"""
        try:
            if self.direct_input_initialized:
                self.direct_input.moveTo(x, y, duration=duration)
            else:
                import pyautogui
                pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            logger.error(f"Failed to move to ({x}, {y}): {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.05):
        """Type text character by character"""
        try:
            if self.direct_input_initialized:
                self.direct_input.typewrite(text, interval=interval)
            else:
                import pyautogui
                pyautogui.typewrite(text, interval=interval)
            logger.info(f"Typed text: {text}")
            return True
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False
    
    def press_key(self, key: str, modifiers: List[str] = None):
        """Press a keyboard key with optional modifiers"""
        try:
            keys = (modifiers or []) + [key]
            if self.direct_input_initialized:
                self.direct_input.hotkey(*keys)
            else:
                import pyautogui
                pyautogui.hotkey(*keys)
            logger.info(f"Pressed key combination: {keys}")
            return True
        except Exception as e:
            logger.error(f"Failed to press key: {e}")
            return False
    
    def get_element_info(self, element_name: str = None, x: int = None, y: int = None) -> Dict:
        """Get information about a UI element"""
        info = {}
        if element_name and self.uia_initialized:
            try:
                element = self.auto.Control(Name=element_name)
                if element.Exists(maxSearchSeconds=2):
                    info.update({
                        "name": element.Name,
                        "type": element.ControlTypeName,
                        "rect": element.BoundingRectangle,
                        "enabled": element.IsEnabled(),
                        "visible": element.IsVisible()
                    })
            except Exception as e:
                logger.error(f"Failed to get element info: {e}")
        
        if x is not None and y is not None and self.pywinauto_initialized:
            try:
                control = self.desktop.FromPoint(x, y)
                info["control_at_point"] = {
                    "name": control.Name,
                    "type": control.ControlTypeName,
                    "rect": control.BoundingRectangle
                }
            except Exception as e:
                logger.warning(f"Could not get control at ({x}, {y}): {e}")
        
        return info
    
    def wait_for_element(self, element_name: str, timeout: float = 10.0) -> bool:
        """Wait for a UI element to appear"""
        if not self.uia_initialized:
            logger.error("uiautomation not available for element waiting")
            return False
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                element = self.auto.Control(Name=element_name)
                if element.Exists(maxSearchSeconds=0.5):
                    return True
            except Exception:
                pass
            time.sleep(0.1)
        return False
    
    def get_all_windows(self) -> List[Dict]:
        """Get list of all open windows"""
        windows = []
        if self.pywinauto_initialized:
            try:
                for window in self.desktop.windows():
                    windows.append({
                        "title": window.window_text(),
                        "handle": window.handle,
                        "class": window.class_name()
                    })
            except Exception as e:
                logger.error(f"Failed to get windows: {e}")
        return windows
    
    def focus_window(self, window_title: str) -> bool:
        """Focus a window by title"""
        if self.pywinauto_initialized:
            try:
                window = self.desktop.window(title=window_title)
                if window.exists():
                    window.set_focus()
                    return True
            except Exception as e:
                logger.error(f"Failed to focus window: {e}")
        return False
