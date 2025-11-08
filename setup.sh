#!/bin/bash
################################################################################
# Android MCP Emulator - Automated Setup Script
################################################################################
#
# This script automates the complete setup of the Android MCP Emulator.
#
# Prerequisites (automatically checked):
#   - Python 3.10+ installed
#   - ADB (Android Debug Bridge) installed
#   - Android emulator running (started via Android Studio)
#
# Usage:
#   ./setup.sh
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
CLAUDE_CONFIG_MAC="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_CONFIG_LINUX="$HOME/.config/Claude/claude_desktop_config.json"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

################################################################################
# Prerequisite Checks
################################################################################

check_prerequisites() {
    print_header "Checking Prerequisites"

    local all_good=true

    # Check Python 3
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_success "Python 3 found: $PYTHON_VERSION"

        # Check if Python >= 3.10
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
            print_error "Python 3.10+ required, found $PYTHON_VERSION"
            all_good=false
        fi
    else
        print_error "Python 3 not found. Please install Python 3.10+"
        all_good=false
    fi

    # Check ADB
    if check_command adb; then
        ADB_VERSION=$(adb version | head -n1 | awk '{print $5}')
        print_success "ADB found: Version $ADB_VERSION"
    else
        print_error "ADB not found. Please install Android SDK Platform Tools"
        print_info "Install with: brew install android-platform-tools"
        all_good=false
    fi

    # Check for running emulator
    DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device" | wc -l | xargs)
    if [ "$DEVICE_COUNT" -gt 0 ]; then
        print_success "Android emulator detected ($DEVICE_COUNT device(s) connected)"
        adb devices | grep "device" | grep -v "List" | while read line; do
            echo "  → $line"
        done
    else
        print_warning "No Android emulator detected"
        print_info "Please start an emulator in Android Studio before continuing"
        echo ""
        read -p "Press Enter once the emulator is running, or Ctrl+C to exit..."

        # Re-check
        DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device" | wc -l | xargs)
        if [ "$DEVICE_COUNT" -eq 0 ]; then
            print_error "Still no emulator detected. Exiting."
            exit 1
        else
            print_success "Emulator detected!"
        fi
    fi

    if [ "$all_good" = false ]; then
        echo ""
        print_error "Prerequisites not met. Please fix the issues above and try again."
        exit 1
    fi

    echo ""
}

################################################################################
# Virtual Environment Setup
################################################################################

setup_virtualenv() {
    print_header "Setting Up Python Virtual Environment"

    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists at: $VENV_DIR"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            print_info "Using existing virtual environment"
            return
        fi
    fi

    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created at: $VENV_DIR"
    echo ""
}

################################################################################
# Install Dependencies
################################################################################

install_dependencies() {
    print_header "Installing Python Dependencies"

    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet

    print_info "Installing requirements from requirements.txt..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

    print_success "All dependencies installed successfully"
    echo ""
}

################################################################################
# Test Functionality
################################################################################

test_functionality() {
    print_header "Testing MCP Server Functionality"

    print_info "Running test suite..."
    source "$VENV_DIR/bin/activate"

    if python3 "$SCRIPT_DIR/test_functionality.py"; then
        print_success "All tests passed!"
    else
        print_error "Some tests failed. Please check the output above."
        exit 1
    fi
    echo ""
}

################################################################################
# Configure Claude Desktop
################################################################################

configure_claude_desktop() {
    print_header "Configuring Claude Desktop"

    # Determine OS and config path
    if [[ "$OSTYPE" == "darwin"* ]]; then
        CLAUDE_CONFIG="$CLAUDE_CONFIG_MAC"
        CONFIG_DIR="$(dirname "$CLAUDE_CONFIG_MAC")"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        CLAUDE_CONFIG="$CLAUDE_CONFIG_LINUX"
        CONFIG_DIR="$(dirname "$CLAUDE_CONFIG_LINUX")"
    else
        print_warning "Unsupported OS: $OSTYPE"
        print_info "Please manually configure Claude Desktop"
        print_manual_config
        return
    fi

    # Create config directory if it doesn't exist
    if [ ! -d "$CONFIG_DIR" ]; then
        print_warning "Claude config directory not found: $CONFIG_DIR"
        print_info "Creating directory..."
        mkdir -p "$CONFIG_DIR"
    fi

    # Backup existing config
    if [ -f "$CLAUDE_CONFIG" ]; then
        BACKUP_FILE="$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
        print_info "Backing up existing config to: $BACKUP_FILE"
        cp "$CLAUDE_CONFIG" "$BACKUP_FILE"
    fi

    # Generate MCP server config
    PYTHON_PATH=$(which python3)
    SERVER_PATH="$SCRIPT_DIR/server.py"

    # Get PATH for ADB
    ADB_PATH=$(which adb)
    ADB_DIR=$(dirname "$ADB_PATH")
    PLATFORM_TOOLS_DIR="$ADB_DIR"

    # Build the config JSON
    print_info "Generating MCP server configuration..."

    # Check if config already exists and has mcpServers
    if [ -f "$CLAUDE_CONFIG" ]; then
        # Config exists, merge with existing
        print_info "Merging with existing configuration..."

        # Use Python to safely merge JSON
        python3 << EOF
import json
import sys

config_path = "$CLAUDE_CONFIG"
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
except:
    config = {}

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['android-emulator'] = {
    "command": "$PYTHON_PATH",
    "args": ["$SERVER_PATH"],
    "env": {
        "PATH": "$PLATFORM_TOOLS_DIR:/usr/local/bin:/usr/bin:/bin"
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print("Configuration updated successfully")
EOF
    else
        # Create new config
        cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "android-emulator": {
      "command": "$PYTHON_PATH",
      "args": [
        "$SERVER_PATH"
      ],
      "env": {
        "PATH": "$PLATFORM_TOOLS_DIR:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
EOF
    fi

    print_success "Claude Desktop configured successfully"
    print_info "Config file location: $CLAUDE_CONFIG"
    echo ""

    print_warning "Please restart Claude Desktop for changes to take effect"
    echo ""
}

print_manual_config() {
    echo ""
    echo -e "${YELLOW}Manual Configuration Instructions:${NC}"
    echo ""
    echo "1. Open your Claude Desktop config file:"
    echo "   macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json"
    echo "   Linux:   ~/.config/Claude/claude_desktop_config.json"
    echo "   Windows: %APPDATA%\\Claude\\claude_desktop_config.json"
    echo ""
    echo "2. Add this configuration:"
    echo ""
    echo "{"
    echo "  \"mcpServers\": {"
    echo "    \"android-emulator\": {"
    echo "      \"command\": \"$(which python3)\","
    echo "      \"args\": ["
    echo "        \"$SCRIPT_DIR/server.py\""
    echo "      ]"
    echo "    }"
    echo "  }"
    echo "}"
    echo ""
}

################################################################################
# Create Convenience Scripts
################################################################################

create_helper_scripts() {
    print_header "Creating Helper Scripts"

    # Create start script
    cat > "$SCRIPT_DIR/start_server.sh" << 'EOF'
#!/bin/bash
# Start the MCP server manually for testing

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/server.py"
EOF
    chmod +x "$SCRIPT_DIR/start_server.sh"
    print_success "Created: start_server.sh (manually start MCP server)"

    # Create test script
    cat > "$SCRIPT_DIR/run_tests.sh" << 'EOF'
#!/bin/bash
# Run functionality tests

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/test_functionality.py"
EOF
    chmod +x "$SCRIPT_DIR/run_tests.sh"
    print_success "Created: run_tests.sh (run tests)"

    echo ""
}

################################################################################
# Print Final Instructions
################################################################################

print_final_instructions() {
    print_header "Setup Complete! 🎉"

    echo -e "${GREEN}The Android MCP Emulator is now ready to use!${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Restart Claude Desktop (if installed)"
    echo ""
    echo "2. In Claude Desktop, try these commands:"
    echo "   • 'Take a screenshot of my Android emulator'"
    echo "   • 'List all installed apps'"
    echo "   • 'Show me device information'"
    echo ""
    echo "Useful commands:"
    echo "   • Test functionality:  ./run_tests.sh"
    echo "   • Start server:        ./start_server.sh"
    echo "   • Run setup again:     ./setup.sh"
    echo ""
    echo "Documentation:"
    echo "   • Quick Start:   QUICKSTART.md"
    echo "   • Examples:      EXAMPLES.md"
    echo "   • Full Docs:     README.md"
    echo ""
    echo -e "${BLUE}Configuration Details:${NC}"
    echo "   Virtual Environment: $VENV_DIR"
    echo "   MCP Server:          $SCRIPT_DIR/server.py"
    echo "   Claude Config:       $([ -f "$CLAUDE_CONFIG" ] && echo "$CLAUDE_CONFIG" || echo "Not configured")"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    clear

    print_header "Android MCP Emulator - Automated Setup"

    echo "This script will:"
    echo "  1. Check prerequisites (Python, ADB, Emulator)"
    echo "  2. Create Python virtual environment"
    echo "  3. Install all dependencies"
    echo "  4. Test the MCP server functionality"
    echo "  5. Configure Claude Desktop"
    echo "  6. Create helper scripts"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to cancel..."

    check_prerequisites
    setup_virtualenv
    install_dependencies
    test_functionality
    configure_claude_desktop
    create_helper_scripts
    print_final_instructions
}

# Run main function
main
