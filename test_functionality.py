#!/usr/bin/env python3
"""
Test script for Android Emulator MCP Server.
Tests basic functionality without running the full MCP protocol.
"""

import subprocess
import sys
import time
from pathlib import Path


class AndroidEmulatorTester:
    """Test Android emulator connection and basic operations."""
    
    def __init__(self, adb_path="adb"):
        self.adb_path = adb_path
        self.device_serial = None
        
    def run_adb(self, args, timeout=30):
        """Execute ADB command."""
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
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
    
    def test_adb_available(self):
        """Test if ADB is available."""
        print("Testing ADB availability...")
        stdout, stderr, code = self.run_adb(["version"])
        
        if code == 0:
            print(f"✓ ADB is available")
            print(f"  Version: {stdout.strip().split()[4]}")
            return True
        else:
            print(f"✗ ADB not found: {stderr}")
            return False
    
    def test_list_devices(self):
        """Test listing devices."""
        print("\nTesting device listing...")
        stdout, stderr, code = self.run_adb(["devices", "-l"])
        
        if code != 0:
            print(f"✗ Failed to list devices: {stderr}")
            return False
        
        lines = stdout.strip().split("\n")[1:]
        devices = [line.split()[0] for line in lines if line.strip() and "device" in line]
        
        if devices:
            print(f"✓ Found {len(devices)} device(s):")
            for device in devices:
                print(f"  - {device}")
            
            # Select first device for testing
            self.device_serial = devices[0]
            return True
        else:
            print("✗ No devices found")
            print("  Please start an Android emulator or connect a device")
            return False
    
    def test_device_info(self):
        """Test getting device info."""
        print(f"\nTesting device info (device: {self.device_serial})...")
        
        # Get model
        stdout, _, code = self.run_adb(["shell", "getprop", "ro.product.model"])
        if code == 0:
            model = stdout.strip()
            print(f"✓ Model: {model}")
        
        # Get Android version
        stdout, _, code = self.run_adb(["shell", "getprop", "ro.build.version.release"])
        if code == 0:
            version = stdout.strip()
            print(f"✓ Android version: {version}")
        
        # Get SDK version
        stdout, _, code = self.run_adb(["shell", "getprop", "ro.build.version.sdk"])
        if code == 0:
            sdk = stdout.strip()
            print(f"✓ SDK version: {sdk}")
        
        # Get screen size
        stdout, _, code = self.run_adb(["shell", "wm", "size"])
        if code == 0:
            size = stdout.strip()
            print(f"✓ Screen: {size}")
        
        return True
    
    def test_screenshot(self):
        """Test taking screenshot."""
        print("\nTesting screenshot capture...")
        
        # Take screenshot on device
        stdout, stderr, code = self.run_adb([
            "shell", "screencap", "-p", "/sdcard/test_screenshot.png"
        ])
        
        if code != 0:
            print(f"✗ Failed to capture screenshot: {stderr}")
            return False
        
        # Pull screenshot
        local_path = "/tmp/android_test_screenshot.png"
        stdout, stderr, code = self.run_adb([
            "pull", "/sdcard/test_screenshot.png", local_path
        ])
        
        if code != 0:
            print(f"✗ Failed to pull screenshot: {stderr}")
            return False
        
        # Check file exists
        if Path(local_path).exists():
            size = Path(local_path).stat().st_size
            print(f"✓ Screenshot captured successfully")
            print(f"  Saved to: {local_path}")
            print(f"  Size: {size:,} bytes")
            return True
        else:
            print("✗ Screenshot file not found")
            return False
    
    def test_ui_hierarchy(self):
        """Test dumping UI hierarchy."""
        print("\nTesting UI hierarchy dump...")
        
        # Dump UI
        stdout, stderr, code = self.run_adb([
            "shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"
        ])
        
        if code != 0:
            print(f"✗ Failed to dump UI: {stderr}")
            return False
        
        # Pull dump
        local_path = "/tmp/android_ui_dump.xml"
        stdout, stderr, code = self.run_adb([
            "pull", "/sdcard/ui_dump.xml", local_path
        ])
        
        if code != 0:
            print(f"✗ Failed to pull UI dump: {stderr}")
            return False
        
        # Parse and show some info
        if Path(local_path).exists():
            import xml.etree.ElementTree as ET
            tree = ET.parse(local_path)
            root = tree.getroot()
            
            # Count elements
            element_count = len(list(root.iter()))
            
            # Find some interesting elements
            buttons = [e for e in root.iter() if e.get('class') == 'android.widget.Button']
            texts = [e for e in root.iter() if e.get('class') == 'android.widget.TextView']
            
            print(f"✓ UI hierarchy dumped successfully")
            print(f"  Total elements: {element_count}")
            print(f"  Buttons: {len(buttons)}")
            print(f"  TextViews: {len(texts)}")
            return True
        else:
            print("✗ UI dump file not found")
            return False
    
    def test_tap(self):
        """Test tapping."""
        print("\nTesting tap input...")
        
        # Tap at center of screen
        stdout, stderr, code = self.run_adb(["shell", "wm", "size"])
        if code == 0:
            import re
            match = re.search(r'(\d+)x(\d+)', stdout)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                
                center_x = width // 2
                center_y = height // 2
                
                stdout, stderr, code = self.run_adb([
                    "shell", "input", "tap", str(center_x), str(center_y)
                ])
                
                if code == 0:
                    print(f"✓ Tapped at ({center_x}, {center_y})")
                    return True
        
        print("✗ Failed to tap")
        return False
    
    def test_key_press(self):
        """Test key press."""
        print("\nTesting key press...")
        
        # Press home key
        stdout, stderr, code = self.run_adb(["shell", "input", "keyevent", "3"])
        
        if code == 0:
            print("✓ Pressed HOME key")
            return True
        else:
            print(f"✗ Failed to press key: {stderr}")
            return False
    
    def test_app_list(self):
        """Test listing apps."""
        print("\nTesting app listing...")
        
        stdout, stderr, code = self.run_adb(["shell", "pm", "list", "packages"])
        
        if code != 0:
            print(f"✗ Failed to list packages: {stderr}")
            return False
        
        packages = [line.replace("package:", "") for line in stdout.strip().split("\n")]
        
        print(f"✓ Found {len(packages)} installed packages")
        print(f"  Sample packages:")
        for pkg in packages[:5]:
            print(f"    - {pkg}")
        
        return True
    
    def test_shell_command(self):
        """Test shell command execution."""
        print("\nTesting shell command execution...")
        
        stdout, stderr, code = self.run_adb(["shell", "echo", "Hello from Android"])
        
        if code == 0 and "Hello from Android" in stdout:
            print(f"✓ Shell command executed successfully")
            print(f"  Output: {stdout.strip()}")
            return True
        else:
            print("✗ Failed to execute shell command")
            return False
    
    def test_file_operations(self):
        """Test file push/pull."""
        print("\nTesting file operations...")
        
        # Create a test file
        test_file = "/tmp/android_test_file.txt"
        with open(test_file, "w") as f:
            f.write("Test content from MCP server")
        
        # Push file
        remote_path = "/sdcard/test_file.txt"
        stdout, stderr, code = self.run_adb(["push", test_file, remote_path])
        
        if code != 0:
            print(f"✗ Failed to push file: {stderr}")
            return False
        
        print(f"✓ File pushed to device")
        
        # Pull file back
        pull_path = "/tmp/android_test_file_pulled.txt"
        stdout, stderr, code = self.run_adb(["pull", remote_path, pull_path])
        
        if code != 0:
            print(f"✗ Failed to pull file: {stderr}")
            return False
        
        # Verify content
        with open(pull_path, "r") as f:
            content = f.read()
        
        if content == "Test content from MCP server":
            print(f"✓ File pulled and verified")
            return True
        else:
            print("✗ File content mismatch")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        print("="*60)
        print("Android Emulator MCP Server - Functionality Test")
        print("="*60)
        
        tests = [
            ("ADB Available", self.test_adb_available),
            ("List Devices", self.test_list_devices),
            ("Device Info", self.test_device_info),
            ("Screenshot", self.test_screenshot),
            ("UI Hierarchy", self.test_ui_hierarchy),
            ("Tap Input", self.test_tap),
            ("Key Press", self.test_key_press),
            ("App Listing", self.test_app_list),
            ("Shell Commands", self.test_shell_command),
            ("File Operations", self.test_file_operations),
        ]
        
        results = {}
        
        for name, test_func in tests:
            try:
                # Skip tests after device listing if no device
                if name != "ADB Available" and name != "List Devices":
                    if not self.device_serial:
                        print(f"\n⊘ Skipping {name} (no device available)")
                        results[name] = "skipped"
                        continue
                
                results[name] = test_func()
            except Exception as e:
                print(f"\n✗ {name} failed with exception: {e}")
                results[name] = False
            
            time.sleep(0.5)  # Brief pause between tests
        
        # Print summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        
        passed = sum(1 for v in results.values() if v is True)
        failed = sum(1 for v in results.values() if v is False)
        skipped = sum(1 for v in results.values() if v == "skipped")
        
        for name, result in results.items():
            if result is True:
                status = "✓ PASS"
            elif result is False:
                status = "✗ FAIL"
            else:
                status = "⊘ SKIP"
            
            print(f"{status:10s} {name}")
        
        print(f"\nTotal: {len(results)} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        
        if failed == 0 and passed > 0:
            print("\n✓ All tests passed! MCP server should work correctly.")
        elif skipped > 0 and failed == 0:
            print("\n⚠ Tests passed but device-specific tests were skipped.")
            print("  Start an emulator and run tests again.")
        else:
            print("\n✗ Some tests failed. Check the output above.")
        
        return failed == 0


def main():
    """Main entry point."""
    tester = AndroidEmulatorTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
