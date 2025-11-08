from setuptools import setup, find_packages

setup(
    name="android-emulator-mcp",
    version="1.0.0",
    description="MCP Server for Android Emulator interaction",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "mcp>=0.9.0",
        "adb-shell>=0.4.4",
        "Pillow>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "android-emulator-mcp=server:main",
        ],
    },
    python_requires=">=3.10",
)
