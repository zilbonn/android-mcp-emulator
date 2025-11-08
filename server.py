#!/usr/bin/env python3
"""
Android Emulator MCP Server
Provides tools for Claude to interact with Android emulators like a human would.
"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("android-emulator-mcp")


class AndroidEmulatorMCP:
    """MCP Server for Android Emulator interaction."""
    
    def __init__(self):
        self.server = Server("android-emulator")
        self.current_device = None
        self.adb_path = self._find_adb()
        
        # Setup tool handlers
        self.setup_handlers()
        
    def _find_adb(self) -> str:
        """Find ADB executable in system PATH or Android SDK."""
        # Try common locations
        adb_locations = [
            "adb",  # In PATH
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            "/usr/local/bin/adb",
        ]
        
        for location in adb_locations:
            try:
                result = subprocess.run(
                    [location, "version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"Found ADB at: {location}")
                    return location
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
                
        logger.warning("ADB not found in standard locations")
        return "adb"  # Default, will fail if not in PATH
    
    def _run_adb(self, args: List[str], timeout: int = 30) -> Tuple[str, str, int]:
        """Execute ADB command and return stdout, stderr, returncode."""
        cmd = [self.adb_path]
        
        # Add device serial if set
        if self.current_device:
            cmd.extend(["-s", self.current_device])
            
        cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {timeout}s", 1
        except Exception as e:
            return "", str(e), 1
    
    def setup_handlers(self):
        """Register all MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                # Device Management
                Tool(
                    name="list_devices",
                    description="List all available Android devices and emulators",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                Tool(
                    name="select_device",
                    description="Select a specific device/emulator to interact with",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number (e.g., emulator-5554)"
                            }
                        },
                        "required": ["serial"]
                    }
                ),
                Tool(
                    name="get_device_info",
                    description="Get detailed information about the current device",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                
                # Screen Inspection
                Tool(
                    name="capture_screenshot",
                    description="Capture a screenshot of the current screen",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "save_path": {
                                "type": "string",
                                "description": "Optional path to save screenshot locally"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_ui_hierarchy",
                    description="Get the XML hierarchy of the current screen UI",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                Tool(
                    name="find_element",
                    description="Find UI element by text, resource-id, or other attributes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Element text"},
                            "resource_id": {"type": "string", "description": "Resource ID"},
                            "class_name": {"type": "string", "description": "Class name"},
                            "content_desc": {"type": "string", "description": "Content description"}
                        }
                    }
                ),
                
                # UI Interaction
                Tool(
                    name="tap_coordinates",
                    description="Tap at specific screen coordinates",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "x": {"type": "number", "description": "X coordinate"},
                            "y": {"type": "number", "description": "Y coordinate"}
                        },
                        "required": ["x", "y"]
                    }
                ),
                Tool(
                    name="tap_element",
                    description="Tap on a UI element by finding it first",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Element text"},
                            "resource_id": {"type": "string", "description": "Resource ID"},
                            "content_desc": {"type": "string", "description": "Content description"}
                        }
                    }
                ),
                Tool(
                    name="swipe",
                    description="Perform a swipe gesture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_x": {"type": "number"},
                            "start_y": {"type": "number"},
                            "end_x": {"type": "number"},
                            "end_y": {"type": "number"},
                            "duration": {"type": "number", "description": "Duration in ms", "default": 300}
                        },
                        "required": ["start_x", "start_y", "end_x", "end_y"]
                    }
                ),
                Tool(
                    name="input_text",
                    description="Input text into the currently focused field",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to input"}
                        },
                        "required": ["text"]
                    }
                ),
                Tool(
                    name="press_key",
                    description="Press a system key (back, home, recent, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "enum": ["back", "home", "recent", "menu", "power", "volume_up", "volume_down"],
                                "description": "Key to press"
                            }
                        },
                        "required": ["key"]
                    }
                ),
                
                # App Management
                Tool(
                    name="install_app",
                    description="Install an APK on the device",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "apk_path": {"type": "string", "description": "Path to APK file"}
                        },
                        "required": ["apk_path"]
                    }
                ),
                Tool(
                    name="launch_app",
                    description="Launch an app by package name",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "package": {"type": "string", "description": "Package name (e.g., com.android.settings)"}
                        },
                        "required": ["package"]
                    }
                ),
                Tool(
                    name="stop_app",
                    description="Force stop an app",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "package": {"type": "string", "description": "Package name"}
                        },
                        "required": ["package"]
                    }
                ),
                Tool(
                    name="clear_app_data",
                    description="Clear app data and cache",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "package": {"type": "string", "description": "Package name"}
                        },
                        "required": ["package"]
                    }
                ),
                Tool(
                    name="list_packages",
                    description="List installed packages",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Optional filter string"}
                        }
                    }
                ),
                
                # Network Configuration
                Tool(
                    name="setup_proxy",
                    description="Configure HTTP proxy settings",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "host": {"type": "string", "description": "Proxy host"},
                            "port": {"type": "number", "description": "Proxy port"}
                        },
                        "required": ["host", "port"]
                    }
                ),
                Tool(
                    name="clear_proxy",
                    description="Remove proxy settings",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                Tool(
                    name="install_certificate",
                    description="Install a CA certificate on the device",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cert_path": {"type": "string", "description": "Path to certificate file (.pem or .crt)"}
                        },
                        "required": ["cert_path"]
                    }
                ),
                
                # Advanced Operations
                Tool(
                    name="execute_shell",
                    description="Execute a shell command on the device",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Shell command to execute"}
                        },
                        "required": ["command"]
                    }
                ),
                Tool(
                    name="pull_file",
                    description="Pull a file from the device to local system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "remote_path": {"type": "string", "description": "Path on device"},
                            "local_path": {"type": "string", "description": "Local destination path"}
                        },
                        "required": ["remote_path", "local_path"]
                    }
                ),
                Tool(
                    name="push_file",
                    description="Push a file from local system to device",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "local_path": {"type": "string", "description": "Local file path"},
                            "remote_path": {"type": "string", "description": "Destination path on device"}
                        },
                        "required": ["local_path", "remote_path"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent | ImageContent]:
            """Handle tool calls."""
            try:
                if name == "list_devices":
                    return await self._list_devices()
                elif name == "select_device":
                    return await self._select_device(arguments["serial"])
                elif name == "get_device_info":
                    return await self._get_device_info()
                elif name == "capture_screenshot":
                    return await self._capture_screenshot(arguments.get("save_path"))
                elif name == "get_ui_hierarchy":
                    return await self._get_ui_hierarchy()
                elif name == "find_element":
                    return await self._find_element(arguments)
                elif name == "tap_coordinates":
                    return await self._tap_coordinates(arguments["x"], arguments["y"])
                elif name == "tap_element":
                    return await self._tap_element(arguments)
                elif name == "swipe":
                    return await self._swipe(
                        arguments["start_x"], arguments["start_y"],
                        arguments["end_x"], arguments["end_y"],
                        arguments.get("duration", 300)
                    )
                elif name == "input_text":
                    return await self._input_text(arguments["text"])
                elif name == "press_key":
                    return await self._press_key(arguments["key"])
                elif name == "install_app":
                    return await self._install_app(arguments["apk_path"])
                elif name == "launch_app":
                    return await self._launch_app(arguments["package"])
                elif name == "stop_app":
                    return await self._stop_app(arguments["package"])
                elif name == "clear_app_data":
                    return await self._clear_app_data(arguments["package"])
                elif name == "list_packages":
                    return await self._list_packages(arguments.get("filter"))
                elif name == "setup_proxy":
                    return await self._setup_proxy(arguments["host"], arguments["port"])
                elif name == "clear_proxy":
                    return await self._clear_proxy()
                elif name == "install_certificate":
                    return await self._install_certificate(arguments["cert_path"])
                elif name == "execute_shell":
                    return await self._execute_shell(arguments["command"])
                elif name == "pull_file":
                    return await self._pull_file(arguments["remote_path"], arguments["local_path"])
                elif name == "push_file":
                    return await self._push_file(arguments["local_path"], arguments["remote_path"])
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error executing {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    # Device Management Implementation
    
    async def _list_devices(self) -> List[TextContent]:
        """List all connected devices."""
        stdout, stderr, code = self._run_adb(["devices", "-l"])
        
        if code != 0:
            return [TextContent(type="text", text=f"Error listing devices: {stderr}")]
        
        lines = stdout.strip().split("\n")[1:]  # Skip header
        devices = []
        
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    state = parts[1]
                    extra_info = " ".join(parts[2:]) if len(parts) > 2 else ""
                    devices.append(f"Serial: {serial}, State: {state}, Info: {extra_info}")
        
        if not devices:
            result = "No devices found. Make sure an emulator is running or a device is connected."
        else:
            result = "Available devices:\n" + "\n".join(devices)
            
        return [TextContent(type="text", text=result)]
    
    async def _select_device(self, serial: str) -> List[TextContent]:
        """Select a device to interact with."""
        self.current_device = serial
        return [TextContent(type="text", text=f"Selected device: {serial}")]
    
    async def _get_device_info(self) -> List[TextContent]:
        """Get device information."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected. Use list_devices and select_device first.")]
        
        info = {}
        
        # Get various device properties
        properties = [
            "ro.product.model",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.product.cpu.abi",
        ]
        
        for prop in properties:
            stdout, _, code = self._run_adb(["shell", "getprop", prop])
            if code == 0:
                info[prop] = stdout.strip()
        
        # Get screen resolution
        stdout, _, code = self._run_adb(["shell", "wm", "size"])
        if code == 0:
            info["screen_size"] = stdout.strip()
        
        result = json.dumps(info, indent=2)
        return [TextContent(type="text", text=f"Device Information:\n{result}")]
    
    # Screen Inspection Implementation
    
    async def _capture_screenshot(self, save_path: Optional[str] = None) -> List[TextContent | ImageContent]:
        """Capture screenshot."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        # Capture screenshot on device
        remote_path = "/sdcard/screenshot.png"
        stdout, stderr, code = self._run_adb(["shell", "screencap", "-p", remote_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to capture screenshot: {stderr}")]
        
        # Pull screenshot to local
        local_path = save_path or "/tmp/android_screenshot.png"
        stdout, stderr, code = self._run_adb(["pull", remote_path, local_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to pull screenshot: {stderr}")]
        
        # Read and encode as base64
        try:
            with open(local_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            return [
                TextContent(type="text", text=f"Screenshot captured successfully. Saved to: {local_path}"),
                ImageContent(type="image", data=image_data, mimeType="image/png")
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading screenshot: {e}")]
    
    async def _get_ui_hierarchy(self) -> List[TextContent]:
        """Get UI hierarchy XML."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        # Dump UI hierarchy
        stdout, stderr, code = self._run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to dump UI: {stderr}")]
        
        # Pull the XML file
        local_path = "/tmp/ui_hierarchy.xml"
        stdout, stderr, code = self._run_adb(["pull", "/sdcard/window_dump.xml", local_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to pull UI dump: {stderr}")]
        
        try:
            with open(local_path, "r") as f:
                xml_content = f.read()
            
            return [TextContent(type="text", text=f"UI Hierarchy:\n{xml_content}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading UI hierarchy: {e}")]
    
    async def _find_element(self, criteria: Dict[str, str]) -> List[TextContent]:
        """Find element in UI hierarchy."""
        # First get the UI hierarchy
        hierarchy_result = await self._get_ui_hierarchy()
        
        if not hierarchy_result or "Error" in hierarchy_result[0].text:
            return hierarchy_result
        
        xml_content = hierarchy_result[0].text.replace("UI Hierarchy:\n", "")
        
        try:
            root = ET.fromstring(xml_content)
            matches = []
            
            # Search for elements matching criteria
            for elem in root.iter():
                match = True
                
                if "text" in criteria and elem.get("text") != criteria["text"]:
                    match = False
                if "resource_id" in criteria and elem.get("resource-id") != criteria["resource_id"]:
                    match = False
                if "class_name" in criteria and elem.get("class") != criteria["class_name"]:
                    match = False
                if "content_desc" in criteria and elem.get("content-desc") != criteria["content_desc"]:
                    match = False
                
                if match and any(k in criteria for k in ["text", "resource_id", "class_name", "content_desc"]):
                    bounds = elem.get("bounds")
                    matches.append({
                        "text": elem.get("text"),
                        "resource-id": elem.get("resource-id"),
                        "class": elem.get("class"),
                        "bounds": bounds,
                        "clickable": elem.get("clickable"),
                        "enabled": elem.get("enabled"),
                    })
            
            if matches:
                result = f"Found {len(matches)} matching element(s):\n" + json.dumps(matches, indent=2)
            else:
                result = "No matching elements found."
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error parsing UI hierarchy: {e}")]
    
    # UI Interaction Implementation
    
    async def _tap_coordinates(self, x: float, y: float) -> List[TextContent]:
        """Tap at coordinates."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb(["shell", "input", "tap", str(int(x)), str(int(y))])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to tap: {stderr}")]
        
        # Add small delay for UI to respond
        await asyncio.sleep(0.5)
        
        return [TextContent(type="text", text=f"Tapped at coordinates ({int(x)}, {int(y)})")]
    
    async def _tap_element(self, criteria: Dict[str, str]) -> List[TextContent]:
        """Find and tap an element."""
        # First find the element
        find_result = await self._find_element(criteria)
        
        if "No matching elements" in find_result[0].text or "Error" in find_result[0].text:
            return find_result
        
        # Parse the result to get bounds
        try:
            result_text = find_result[0].text
            matches = json.loads(result_text.split(":\n", 1)[1])
            
            if not matches:
                return [TextContent(type="text", text="No elements found to tap.")]
            
            # Get bounds of first match
            bounds = matches[0].get("bounds")
            if not bounds:
                return [TextContent(type="text", text="Element has no bounds information.")]
            
            # Parse bounds [x1,y1][x2,y2]
            import re
            coords = re.findall(r'\d+', bounds)
            if len(coords) >= 4:
                x1, y1, x2, y2 = map(int, coords[:4])
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                return await self._tap_coordinates(center_x, center_y)
            else:
                return [TextContent(type="text", text=f"Could not parse bounds: {bounds}")]
                
        except Exception as e:
            return [TextContent(type="text", text=f"Error tapping element: {e}")]
    
    async def _swipe(self, start_x: float, start_y: float, end_x: float, end_y: float, duration: int = 300) -> List[TextContent]:
        """Perform swipe gesture."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb([
            "shell", "input", "swipe",
            str(int(start_x)), str(int(start_y)),
            str(int(end_x)), str(int(end_y)),
            str(duration)
        ])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to swipe: {stderr}")]
        
        await asyncio.sleep(0.5)
        
        return [TextContent(type="text", text=f"Swiped from ({int(start_x)}, {int(start_y)}) to ({int(end_x)}, {int(end_y)})")]
    
    async def _input_text(self, text: str) -> List[TextContent]:
        """Input text."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        # Escape special characters
        escaped_text = text.replace(" ", "%s").replace("'", "\\'")
        
        stdout, stderr, code = self._run_adb(["shell", "input", "text", escaped_text])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to input text: {stderr}")]
        
        return [TextContent(type="text", text=f"Entered text: {text}")]
    
    async def _press_key(self, key: str) -> List[TextContent]:
        """Press system key."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        key_codes = {
            "back": "4",
            "home": "3",
            "recent": "187",
            "menu": "82",
            "power": "26",
            "volume_up": "24",
            "volume_down": "25",
        }
        
        key_code = key_codes.get(key)
        if not key_code:
            return [TextContent(type="text", text=f"Unknown key: {key}")]
        
        stdout, stderr, code = self._run_adb(["shell", "input", "keyevent", key_code])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to press key: {stderr}")]
        
        await asyncio.sleep(0.3)
        
        return [TextContent(type="text", text=f"Pressed {key} key")]
    
    # App Management Implementation
    
    async def _install_app(self, apk_path: str) -> List[TextContent]:
        """Install APK."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        if not os.path.exists(apk_path):
            return [TextContent(type="text", text=f"APK file not found: {apk_path}")]
        
        stdout, stderr, code = self._run_adb(["install", "-r", apk_path], timeout=120)
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to install app: {stderr}")]
        
        return [TextContent(type="text", text=f"Successfully installed: {apk_path}\n{stdout}")]
    
    async def _launch_app(self, package: str) -> List[TextContent]:
        """Launch app."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        # Use monkey to launch the app
        stdout, stderr, code = self._run_adb([
            "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"
        ])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to launch app: {stderr}")]
        
        await asyncio.sleep(2)  # Wait for app to launch
        
        return [TextContent(type="text", text=f"Launched app: {package}")]
    
    async def _stop_app(self, package: str) -> List[TextContent]:
        """Stop app."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb(["shell", "am", "force-stop", package])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to stop app: {stderr}")]
        
        return [TextContent(type="text", text=f"Stopped app: {package}")]
    
    async def _clear_app_data(self, package: str) -> List[TextContent]:
        """Clear app data."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb(["shell", "pm", "clear", package])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to clear app data: {stderr}")]
        
        return [TextContent(type="text", text=f"Cleared data for: {package}\n{stdout}")]
    
    async def _list_packages(self, filter_str: Optional[str] = None) -> List[TextContent]:
        """List installed packages."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        cmd = ["shell", "pm", "list", "packages"]
        if filter_str:
            cmd.extend(["|", "grep", filter_str])
        
        stdout, stderr, code = self._run_adb(cmd)
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to list packages: {stderr}")]
        
        packages = [line.replace("package:", "") for line in stdout.strip().split("\n") if line]
        
        result = f"Found {len(packages)} package(s):\n" + "\n".join(packages[:100])
        if len(packages) > 100:
            result += f"\n... and {len(packages) - 100} more"
        
        return [TextContent(type="text", text=result)]
    
    # Network Configuration Implementation
    
    async def _setup_proxy(self, host: str, port: int) -> List[TextContent]:
        """Setup HTTP proxy."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        proxy_string = f"{host}:{port}"
        
        stdout, stderr, code = self._run_adb([
            "shell", "settings", "put", "global", "http_proxy", proxy_string
        ])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to set proxy: {stderr}")]
        
        return [TextContent(type="text", text=f"Proxy configured: {proxy_string}\nNote: You may need to restart apps or reboot for changes to take effect.")]
    
    async def _clear_proxy(self) -> List[TextContent]:
        """Clear proxy settings."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb([
            "shell", "settings", "put", "global", "http_proxy", ":0"
        ])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to clear proxy: {stderr}")]
        
        return [TextContent(type="text", text="Proxy settings cleared.")]
    
    async def _install_certificate(self, cert_path: str) -> List[TextContent]:
        """Install CA certificate."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        if not os.path.exists(cert_path):
            return [TextContent(type="text", text=f"Certificate file not found: {cert_path}")]
        
        # Push certificate to device
        remote_path = "/sdcard/Download/ca_cert.crt"
        stdout, stderr, code = self._run_adb(["push", cert_path, remote_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to push certificate: {stderr}")]
        
        instructions = f"""Certificate pushed to device: {remote_path}

To complete installation:
1. Open Settings app
2. Navigate to Security > Encryption & credentials > Install a certificate
3. Select 'CA certificate'
4. Browse to Downloads folder
5. Select the certificate file
6. Confirm installation

For Android 11+, you may need to:
- Use adb root access for system certificate installation, or
- Install as user certificate (apps may not trust it by default)

Alternative automated approach:
Use 'tap_element' and other UI tools to navigate through Settings automatically.
"""
        
        return [TextContent(type="text", text=instructions)]
    
    # Advanced Operations Implementation
    
    async def _execute_shell(self, command: str) -> List[TextContent]:
        """Execute shell command."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb(["shell", command], timeout=60)
        
        result = f"Command: {command}\nReturn Code: {code}\n\nOutput:\n{stdout}"
        if stderr:
            result += f"\n\nError Output:\n{stderr}"
        
        return [TextContent(type="text", text=result)]
    
    async def _pull_file(self, remote_path: str, local_path: str) -> List[TextContent]:
        """Pull file from device."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        stdout, stderr, code = self._run_adb(["pull", remote_path, local_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to pull file: {stderr}")]
        
        return [TextContent(type="text", text=f"File pulled successfully:\nFrom: {remote_path}\nTo: {local_path}\n{stdout}")]
    
    async def _push_file(self, local_path: str, remote_path: str) -> List[TextContent]:
        """Push file to device."""
        if not self.current_device:
            return [TextContent(type="text", text="No device selected.")]
        
        if not os.path.exists(local_path):
            return [TextContent(type="text", text=f"Local file not found: {local_path}")]
        
        stdout, stderr, code = self._run_adb(["push", local_path, remote_path])
        
        if code != 0:
            return [TextContent(type="text", text=f"Failed to push file: {stderr}")]
        
        return [TextContent(type="text", text=f"File pushed successfully:\nFrom: {local_path}\nTo: {remote_path}\n{stdout}")]


async def main():
    """Main entry point for the MCP server."""
    mcp = AndroidEmulatorMCP()
    
    async with stdio_server() as (read_stream, write_stream):
        await mcp.server.run(
            read_stream,
            write_stream,
            mcp.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
