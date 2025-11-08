.PHONY: help install test clean run docker-build docker-run setup-emulator

help:
	@echo "Android Emulator MCP Server - Available Commands:"
	@echo ""
	@echo "  make install          Install dependencies"
	@echo "  make test             Run functionality tests"
	@echo "  make run              Start the MCP server"
	@echo "  make clean            Clean temporary files"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-run       Run in Docker container"
	@echo "  make setup-emulator   Check emulator setup"
	@echo "  make install-cert     Install mitmproxy certificate"
	@echo ""

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

test:
	@echo "Running functionality tests..."
	python test_functionality.py

run:
	@echo "Starting MCP server..."
	python server.py

clean:
	@echo "Cleaning temporary files..."
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf /tmp/android_*.png
	rm -rf /tmp/android_*.xml
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	@echo "✓ Cleaned"

docker-build:
	@echo "Building Docker image..."
	docker build -t android-emulator-mcp .
	@echo "✓ Docker image built"

docker-run:
	@echo "Running Docker container..."
	docker-compose up -d
	@echo "✓ Container started"

docker-stop:
	@echo "Stopping Docker container..."
	docker-compose down
	@echo "✓ Container stopped"

setup-emulator:
	@echo "Checking emulator setup..."
	@echo ""
	@echo "ADB Version:"
	@adb version || echo "✗ ADB not found"
	@echo ""
	@echo "Connected Devices:"
	@adb devices
	@echo ""
	@echo "If no devices listed, start an emulator first."

install-cert:
	@echo "Installing mitmproxy certificate..."
	@if [ -f ~/.mitmproxy/mitmproxy-ca-cert.pem ]; then \
		python cert_installer.py ~/.mitmproxy/mitmproxy-ca-cert.pem; \
	else \
		echo "✗ mitmproxy certificate not found at ~/.mitmproxy/mitmproxy-ca-cert.pem"; \
		echo "  Run 'mitmproxy' first to generate the certificate."; \
	fi

list-devices:
	@echo "Available Android devices:"
	@adb devices -l

screenshot:
	@echo "Taking screenshot..."
	@adb shell screencap -p /sdcard/screenshot.png
	@adb pull /sdcard/screenshot.png /tmp/android_screenshot.png
	@echo "✓ Screenshot saved to /tmp/android_screenshot.png"

shell:
	@echo "Opening ADB shell..."
	@adb shell

logcat:
	@echo "Showing device logs (Ctrl+C to stop)..."
	@adb logcat

dev:
	@echo "Setting up development environment..."
	python -m venv venv
	@echo "Activate with: source venv/bin/activate"
	@echo "Then run: make install"
