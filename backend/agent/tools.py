"""
JARVIS Agent Tools
Terminal, file, and screen control tools for the agent
"""

import subprocess
import os
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

class TerminalTool:
    """Execute terminal commands safely"""
    
    def __init__(self, trust_level: int = 1):
        self.trust_level = trust_level
        self.blocked_commands = [
            "rm -rf /", "del /f /s /q", "format",
            "shutdown", "shutdown /s", "shutdown /r",
            "taskkill /f /im", "reg delete", "diskpart", "net user"
        ]
    
    def _is_safe(self, command: str) -> bool:
        cmd_lower = command.lower()
        return not any(blocked in cmd_lower for blocked in self.blocked_commands)
    
    def execute(self, command: str, working_dir: Optional[str] = None) -> str:
        """Execute a terminal command and return output"""
        if not self._is_safe(command):
            return f"❌ Command blocked for safety: {command}"
        
        try:
            if working_dir:
                os.chdir(working_dir)
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            
            return output.strip() or "✓ Command executed successfully (no output)"
        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after 30 seconds: {command}"
        except Exception as e:
            return f"❌ Command execution failed: {str(e)}"


class FileTool:
    """File management tools"""
    
    def list_files(self, directory: str, pattern: str = "*") -> str:
        """List files in a directory"""
        try:
            path = Path(directory)
            if not path.exists():
                return f"❌ Directory not found: {directory}"
            
            files = list(path.glob(pattern))
            if not files:
                return f"📁 No files matching '{pattern}' in {directory}"
            
            output = [f"📁 Contents of {directory}:"]
            for f in sorted(files):
                file_type = "📄" if f.is_file() else "📁"
                size = f"{f.stat().st_size / 1024:.1f}KB" if f.is_file() else ""
                output.append(f"  {file_type} {f.name} {size}")
            
            return "\n".join(output)
        except Exception as e:
            return f"❌ Error listing files: {str(e)}"
    
    def read_file(self, filepath: str, max_lines: int = 100) -> str:
        """Read file contents"""
        try:
            path = Path(filepath)
            if not path.exists():
                return f"❌ File not found: {filepath}"
            if not path.is_file():
                return f"❌ Not a file: {filepath}"
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:max_lines]
            
            content = "".join(lines)
            if len(lines) == max_lines:
                content += f"\n\n... (showing first {max_lines} lines)"
            
            return content
        except Exception as e:
            return f"❌ Error reading file: {str(e)}"
    
    def write_file(self, filepath: str, content: str) -> str:
        """Write content to a file"""
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"✓ File written: {filepath} ({len(content)} bytes)"
        except Exception as e:
            return f"❌ Error writing file: {str(e)}"


class ScreenTool:
    """Screen control tools for the agent"""
    
    def __init__(self, screen_control, screen_capture, vision_router):
        self.control = screen_control
        self.capture = screen_capture
        self.vision = vision_router
    
    def analyze_screen(self, query: str = "What is on the screen?") -> str:
        """Analyze current screen content"""
        screenshot = self.capture.capture()
        if screenshot is None:
            return "❌ Failed to capture screenshot"
        
        result = self.vision.route_query(query, screenshot)
        return (
            f"Model: {result.get('model', 'unknown')}\n"
            f"Inference: {result.get('inference_time_ms', 'N/A')}ms\n\n"
            f"{result.get('result', 'No result')}"
        )
    
    def find_element(self, element_name: str) -> str:
        """Find a UI element by name"""
        info = self.control.get_element_info(element_name=element_name)
        if not info:
            return f"❌ Element '{element_name}' not found"
        return "✓ Element found:\n" + "\n".join(f"  {k}: {v}" for k, v in info.items())
    
    def click_element(self, x: int, y: int, button: str = "left") -> str:
        """Click at specific coordinates"""
        success = self.control.click(x=x, y=y, button=button)
        return f"✓ Clicked at ({x}, {y})" if success else f"❌ Failed to click at ({x}, {y})"
    
    def type_text(self, text: str) -> str:
        """Type text into the focused element"""
        success = self.control.type_text(text)
        return f"✓ Typed: {text}" if success else "❌ Failed to type text"
    
    def press_key(self, key: str, ctrl: bool = False, shift: bool = False, alt: bool = False) -> str:
        """Press a keyboard key"""
        modifiers = []
        if ctrl: modifiers.append("ctrl")
        if shift: modifiers.append("shift")
        if alt: modifiers.append("alt")
        
        success = self.control.press_key(key, modifiers if modifiers else None)
        key_combo = "+".join(modifiers + [key])
        return f"✓ Pressed: {key_combo}" if success else f"❌ Failed to press {key_combo}"
