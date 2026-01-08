#!/usr/bin/env python3
"""
IRWP Firmware Builder
Automatically compiles all platform firmware using PlatformIO

### How to Generate Your Binaries:

# Navigate to firmware directory
cd Micro-Controlers/Firmware

# Place all source files in their folders first, then run:
python build_firmware.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

def check_toolchain():
    """Verify PlatformIO is installed"""
    if not shutil.which("pio"):
        print("❌ PlatformIO not found!")
        print("Install: pip install platformio")
        sys.exit(1)
    print("✅ PlatformIO found")

def build_platform(platform_dir: str, env_name: str):
    """Build firmware for a specific platform"""
    print(f"\n{'='*50}")
    print(f"Building {platform_dir.upper()}...")
    print(f"{'='*50}")
    
    try:
        # Change to platform directory
        platform_path = Path(platform_dir)
        
        # Create platformio.ini if it doesn't exist
        if not (platform_path / "platformio.ini").exists():
            create_platformio_ini(platform_dir)
        
        # Run PlatformIO build
        result = subprocess.run(
            ["pio", "run", "-e", env_name],
            cwd=platform_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {platform_dir.upper()} build successful!")
            
            # Copy binary to firmware root
            binary = find_binary(platform_path, env_name)
            if binary:
                dest = Path(f"../{platform_dir}_firmware{binary.suffix}")
                shutil.copy2(binary, dest)
                print(f"📦 Binary copied to: {dest}")
                return True
        else:
            print(f"❌ {platform_dir.upper()} build failed!")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error building {platform_dir}: {e}")
        return False

def create_platformio_ini(platform: str):
    """Create platformio.ini for each platform"""
    configs = {
        "esp32": """
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    adafruit/Adafruit MPU6050@^2.2.4
    adafruit/Adafruit BusIO@^1.14.1
    adafruit/Adafruit Unified Sensor@^1.1.9
build_flags = -O2
""",
        "pico": """
[env:pico]
platform = raspberrypi
board = pico
framework = arduino
lib_deps = 
    adafruit/Adafruit MPU6050@^2.2.4
    adafruit/Adafruit BusIO@^1.14.1
build_flags = -O2
""",
        "nano": """
[env:nanoatmega328]
platform = atmelavr
board = nanoatmega328
framework = arduino
lib_deps = 
    adafruit/Adafruit MPU6050@^2.2.4
    adafruit/Adafruit BusIO@^1.14.1
build_flags = -O2
""",
        "stm32": """
[env:bluepill_f103c8]
platform = ststm32
board = bluepill_f103c8
framework = arduino
upload_protocol = stlink
lib_deps = 
    adafruit/Adafruit MPU6050@^2.2.4
    adafruit/Adafruit BusIO@^1.14.1
build_flags = -O2
"""
    }
    
    Path(platform).mkdir(exist_ok=True)
    Path(f"{platform}/platformio.ini").write_text(configs[platform].strip())
    Path(f"{platform}/src").mkdir(exist_ok=True)
    
    # Copy source file
    if platform == "nano":
        shutil.copy("../nano_firmware.ino", f"{platform}/src/main.cpp")
    else:
        shutil.copy(f"../{platform}_firmware.cpp", f"{platform}/src/main.cpp")

def find_binary(build_dir: Path, env_name: str):
    """Find compiled binary in PlatformIO build directory"""
    binary_dir = build_dir / ".pio" / "build" / env_name
    
    # Try common binary names
    extensions = {
        "esp32": ".bin",
        "pico": ".uf2",
        "nano": ".hex",
        "stm32": ".bin"
    }
    
    for platform, ext in extensions.items():
        binary = binary_dir / f"firmware{ext}"
        if binary.exists():
            return binary
        
        # Alternative names
        binary = binary_dir / f"main{ext}"
        if binary.exists():
            return binary
    
    return None

def main():
    print("IRWP Firmware Builder")
    print("This script will compile all platform firmware")
    
    check_toolchain()
    
    # Build each platform
    platforms = [
        ("esp32", "esp32dev"),
        ("pico", "pico"),
        ("nano", "nanoatmega328"),
        ("stm32", "bluepill_f103c8")
    ]
    
    results = {}
    for platform, env in platforms:
        results[platform] = build_platform(platform, env)
    
    # Summary
    print("\n" + "="*50)
    print("BUILD SUMMARY")
    print("="*50)
    for platform, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{platform.upper()}: {status}")

if __name__ == "__main__":
    main()
