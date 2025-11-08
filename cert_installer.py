#!/usr/bin/env python3
"""
Helper script for automated certificate installation on Android.
This demonstrates how to automate the Settings navigation for certificate installation.
"""

import asyncio
import sys
import time
from pathlib import Path


class CertificateInstaller:
    """Automates CA certificate installation on Android."""
    
    def __init__(self, adb_path="adb", device_serial=None):
        self.adb_path = adb_path
        self.device_serial = device_serial
        
    def run_adb(self, args):
        """Execute ADB command."""
        import subprocess
        
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(args)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    
    def wait_for_ui(self, text, timeout=10):
        """Wait for UI element with text to appear."""
        start = time.time()
        while time.time() - start < timeout:
            stdout, _, _ = self.run_adb(["shell", "uiautomator", "dump", "/dev/tty"])
            if text in stdout:
                return True
            time.sleep(0.5)
        return False
    
    def find_element_bounds(self, text):
        """Find bounds of element with given text."""
        stdout, _, _ = self.run_adb(["shell", "uiautomator", "dump", "/dev/tty"])
        
        # Parse bounds from dump
        import re
        pattern = rf'text="{re.escape(text)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        match = re.search(pattern, stdout)
        
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            return center_x, center_y
        return None
    
    def tap(self, x, y):
        """Tap at coordinates."""
        self.run_adb(["shell", "input", "tap", str(x), str(y)])
        time.sleep(0.5)
    
    def tap_text(self, text, timeout=10):
        """Find and tap element with text."""
        if not self.wait_for_ui(text, timeout):
            print(f"Could not find element with text: {text}")
            return False
        
        coords = self.find_element_bounds(text)
        if coords:
            self.tap(*coords)
            return True
        return False
    
    def scroll_down(self):
        """Scroll down in current view."""
        # Get screen size
        stdout, _, _ = self.run_adb(["shell", "wm", "size"])
        # Parse: Physical size: 1080x2400
        import re
        match = re.search(r'(\d+)x(\d+)', stdout)
        if match:
            width = int(match.group(1))
            height = int(match.group(2))
            
            # Swipe from bottom to top
            start_x = width // 2
            start_y = int(height * 0.8)
            end_y = int(height * 0.2)
            
            self.run_adb([
                "shell", "input", "swipe",
                str(start_x), str(start_y),
                str(start_x), str(end_y),
                "300"
            ])
            time.sleep(0.5)
    
    def install_certificate(self, cert_path, cert_name="mitmproxy-ca"):
        """
        Automated certificate installation workflow.
        
        Args:
            cert_path: Local path to certificate file (.pem or .crt)
            cert_name: Name to give the certificate
        """
        print("Starting automated certificate installation...")
        
        # Step 1: Convert certificate to DER format if needed
        if cert_path.endswith('.pem'):
            print("Converting PEM to DER format...")
            import subprocess
            der_path = cert_path.replace('.pem', '.crt')
            result = subprocess.run([
                'openssl', 'x509',
                '-inform', 'PEM',
                '-in', cert_path,
                '-outform', 'DER',
                '-out', der_path
            ], capture_output=True)
            
            if result.returncode == 0:
                cert_path = der_path
                print(f"Converted to: {der_path}")
            else:
                print("Warning: Could not convert certificate format")
        
        # Step 2: Push certificate to device
        print("Pushing certificate to device...")
        remote_path = f"/sdcard/Download/{cert_name}.crt"
        stdout, stderr, code = self.run_adb(["push", cert_path, remote_path])
        
        if code != 0:
            print(f"Error pushing certificate: {stderr}")
            return False
        
        print(f"Certificate pushed to: {remote_path}")
        
        # Step 3: Open Settings app
        print("Opening Settings...")
        self.run_adb(["shell", "am", "start", "-a", "android.settings.SETTINGS"])
        time.sleep(2)
        
        # Step 4: Navigate to Security settings
        print("Navigating to Security...")
        
        # Search for "Security" or "Biometrics and security"
        if not self.tap_text("Security", timeout=5):
            self.tap_text("Biometrics and security", timeout=5)
        
        time.sleep(1)
        
        # Step 5: Find "Encryption & credentials" or similar
        print("Looking for credential settings...")
        
        # May need to scroll to find it
        for _ in range(3):
            if self.tap_text("Encryption & credentials"):
                break
            if self.tap_text("Credential storage"):
                break
            self.scroll_down()
        
        time.sleep(1)
        
        # Step 6: Select "Install a certificate"
        print("Selecting certificate installation...")
        
        for _ in range(3):
            if self.tap_text("Install a certificate"):
                break
            if self.tap_text("Install from SD card"):
                break
            if self.tap_text("Install from storage"):
                break
            self.scroll_down()
        
        time.sleep(1)
        
        # Step 7: Select CA certificate type
        print("Selecting CA certificate...")
        self.tap_text("CA certificate")
        time.sleep(1)
        
        # Step 8: Handle "Install anyway" warning if present
        if self.wait_for_ui("Install anyway", timeout=3):
            print("Confirming certificate installation warning...")
            self.tap_text("Install anyway")
            time.sleep(1)
        
        # Step 9: Navigate to Downloads folder
        print("Navigating to certificate file...")
        
        # Tap the menu icon to show navigation drawer
        self.tap(50, 150)  # Top-left menu icon (approximate)
        time.sleep(1)
        
        if self.tap_text("Downloads"):
            time.sleep(1)
        
        # Step 10: Select the certificate file
        print(f"Selecting certificate: {cert_name}.crt...")
        if self.tap_text(f"{cert_name}.crt"):
            time.sleep(1)
            
            # Step 11: Name the certificate
            print("Naming certificate...")
            self.run_adb(["shell", "input", "text", cert_name.replace(" ", "%s")])
            time.sleep(0.5)
            
            # Step 12: Confirm installation
            print("Confirming installation...")
            self.tap_text("OK")
            time.sleep(1)
            
            print("✓ Certificate installation complete!")
            return True
        else:
            print("✗ Could not find certificate file")
            return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python cert_installer.py <certificate_path> [device_serial]")
        print("\nExample:")
        print("  python cert_installer.py mitmproxy-ca-cert.pem")
        print("  python cert_installer.py mitmproxy-ca-cert.pem emulator-5554")
        sys.exit(1)
    
    cert_path = sys.argv[1]
    device_serial = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(cert_path).exists():
        print(f"Error: Certificate file not found: {cert_path}")
        sys.exit(1)
    
    installer = CertificateInstaller(device_serial=device_serial)
    
    success = installer.install_certificate(cert_path)
    
    if success:
        print("\n" + "="*50)
        print("Certificate installed successfully!")
        print("="*50)
        print("\nNote: Some apps may still not trust user certificates.")
        print("For system-wide trust, you may need:")
        print("1. Rooted device/emulator")
        print("2. Install as system certificate")
        print("3. Use Magisk module for certificate injection")
    else:
        print("\n" + "="*50)
        print("Certificate installation failed or incomplete")
        print("="*50)
        print("\nYou may need to complete the installation manually.")
        print("The certificate has been pushed to: /sdcard/Download/")


if __name__ == "__main__":
    main()
