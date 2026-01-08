#!/usr/bin/env python3
"""
IRWP v2.5 Complete Controller with Firmware Flashing
All-in-one application for ESP32, Pi Pico, Arduino Nano, STM32
"""

import sys
import time
import json
import random
import queue
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QTextCursor

# ============================================================================
# Logger
# ============================================================================
class SimpleLogger(QObject):
    def __init__(self, log_file: str):
        super().__init__()
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        with open(self.log_file, "a") as f:
            f.write(f"\n[SESSION START] {datetime.now()}\n")
    
    def log(self, event: str, data: dict):
        entry = {
            "timestamp": time.time(),
            "event": event,
            "data": data
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

# ============================================================================
# Firmware Flasher (Multi-Platform)
# ============================================================================
class FirmwareFlasher(QObject):
    progress_signal = pyqtSignal(str, int)  # message, percent
    error_signal = pyqtSignal(str)
    success_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.logger = SimpleLogger("logs/flasher.log")
        self.platform_tools = {
            "ESP32": self.flash_esp32,
            "PICO": self.flash_pico,
            "ARDUINO": self.flash_arduino,
            "STM32": self.flash_stm32
        }
        
        # Firmware file mapping
        self.firmware_files = {
            "ESP32": "firmware/esp32_firmware.bin",
            "PICO": "firmware/pico_firmware.uf2",
            "ARDUINO": "firmware/nano_firmware.hex",
            "STM32": "firmware/stm32_firmware.bin"
        }
    
    def detect_platform(self, port) -> str:
        """Auto-detect microcontroller platform from VID/PID"""
        if port.vid == 0x10C4 or "CP210" in port.description:
            return "ESP32"
        elif port.vid == 0x2E8A or "Pico" in port.description:
            return "PICO"
        elif port.vid in [0x2341, 0x2A03] or "Arduino" in port.description:
            return "ARDUINO"
        elif "STM32" in port.description or port.vid == 0x0483:
            return "STM32"
        return "UNKNOWN"
    
    def flash(self, platform: str, port: str):
        """Flash firmware for detected platform"""
        if platform not in self.platform_tools:
            self.error_signal.emit(f"Unsupported platform: {platform}")
            return
        
        firmware_file = Path(self.firmware_files[platform])
        if not firmware_file.exists():
            self.error_signal.emit(f"Firmware not found: {firmware_file}")
            return
        
        self.progress_signal.emit(f"Flashing {platform} on {port}", 0)
        self.logger.log("FLASH_START", {"platform": platform, "port": port})
        
        # Execute platform-specific flash
        try:
            self.platform_tools[platform](port, firmware_file)
        except Exception as e:
            self.error_signal.emit(f"Flash failed: {e}")
            self.logger.log("FLASH_ERROR", {"error": str(e)})
    
    def flash_esp32(self, port: str, firmware: Path):
        """Flash ESP32 using esptool.py"""
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp32",
            "--port", port,
            "--baud", "921600",
            "write_flash", "-z",
            "0x1000", str(firmware)
        ]
        self._run_flash_command(cmd, "ESP32")
    
    def flash_pico(self, port: str, firmware: Path):
        """Flash Pi Pico by copying UF2 to bootloader"""
        self.progress_signal.emit("Put Pico in bootloader mode...", 10)
        
        # Find bootloader drive (varies by OS)
        if sys.platform == "win32":
            # Windows: Look for RPI-RP2 drive
            bootloader = self._find_bootloader_drive("RPI-RP2")
        elif sys.platform == "darwin":
            # macOS: Look for volume
            bootloader = Path("/Volumes/RPI-RP2")
        else:
            # Linux: Look for mount point
            bootloader = self._find_bootloader_linux()
        
        if not bootloader:
            # Fallback: Use picotool
            cmd = ["picotool", "load", "-x", str(firmware)]
            self._run_flash_command(cmd, "PICO")
        else:
            # Copy UF2 file
            dest = bootloader / firmware.name
            cmd = ["cp", str(firmware), str(dest)]
            self._run_flash_command(cmd, "PICO", use_shell=True)
    
    def flash_arduino(self, port: str, firmware: Path):
        """Flash Arduino using avrdude"""
        cmd = [
            "avrdude",
            "-C", "avrdude.conf",
            "-v", "-p", "atmega328p", "-c", "arduino",
            "-P", port,
            "-b", "115200",
            "-D", "-U", f"flash:w:{firmware}:i"
        ]
        self._run_flash_command(cmd, "ARDUINO")
    
    def flash_stm32(self, port: str, firmware: Path):
        """Flash STM32 using st-flash"""
        cmd = ["st-flash", "write", str(firmware), "0x8000000"]
        self._run_flash_command(cmd, "STM32")
    
    def _find_bootloader_drive(self, name: str) -> Path:
        """Find mounted bootloader drive"""
        for drive in Path("/media").iterdir():
            if name in drive.name:
                return drive
        return None
    
    def _find_bootloader_linux(self) -> Path:
        """Find Pico bootloader on Linux"""
        # Check common mount points
        for path in [Path("/media"), Path("/mnt"), Path.home() / "media"]:
            if path.exists():
                for child in path.iterdir():
                    if "RPI-RP2" in child.name:
                        return child
        return None
    
    def _run_flash_command(self, cmd: list, platform: str, use_shell: bool = False):
        """Execute flashing command with progress monitoring"""
        try:
            self.progress_signal.emit(f"Running: {' '.join(cmd)}", 20)
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=use_shell
            )
            
            # Monitor output
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    self.logger.log("FLASH_OUTPUT", {"line": line})
                    
                    # Parse progress
                    if "Writing" in line:
                        self.progress_signal.emit(line, 50)
                    elif "Hash of data verified" in line:
                        self.progress_signal.emit(line, 90)
                    
                    # Check for errors
                    if "error" in line.lower() or "failed" in line.lower():
                        self.error_signal.emit(line)
                        process.kill()
                        return
            
            process.wait()
            if process.returncode == 0:
                self.progress_signal.emit("Flash complete!", 100)
                self.success_signal.emit(platform)
                self.logger.log("FLASH_SUCCESS", {"platform": platform})
            else:
                self.error_signal.emit(f"Process exited with code {process.returncode}")
        
        except FileNotFoundError:
            self.error_signal.emit(f"Tool not found. Install platform flashing utility.")
        except Exception as e:
            self.error_signal.emit(f"Exception: {e}")

# ============================================================================
# Serial Worker (Non-blocking)
# ============================================================================
class SerialWorker(QThread):
    data_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    disconnected = pyqtSignal()
    
    def __init__(self, port: str, baud_rate: int = 115200):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.serial = None
        self.running = False
        self.command_queue = queue.Queue()
        self.logger = SimpleLogger("logs/serial.log")
    
    def run(self):
        try:
            self.serial = serial.Serial(self.port, self.baud_rate, timeout=0.1)
            time.sleep(2)  # Arduino reset
            
            if not self.serial.is_open:
                self.error_occurred.emit("Failed to open serial port")
                return
            
            self.running = True
            self.logger.log("SERIAL_OPEN", {"port": self.port, "baud": self.baud_rate})
            
            while self.running:
                # Send queued commands
                try:
                    while True:
                        cmd = self.command_queue.get_nowait()
                        self.serial.write(json.dumps(cmd).encode() + b'\n')
                        self.logger.log("SERIAL_WRITE", cmd)
                except queue.Empty:
                    pass
                
                # Read responses
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline()
                        if line:
                            data = json.loads(line.decode().strip())
                            self.data_received.emit(data)
                            self.logger.log("SERIAL_READ", data)
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        self.error_occurred.emit(f"Parse error: {e}")
                
                # Check for disconnect
                if not self.serial.is_open:
                    self.disconnected.emit()
                    break
                
                time.sleep(0.01)
                
        except serial.SerialException as e:
            self.error_occurred.emit(f"Serial error: {e}")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.logger.log("SERIAL_CLOSED", {})
    
    def send_command(self, cmd: dict):
        self.command_queue.put(cmd)
    
    def stop(self):
        self.running = False
        self.wait()

# ============================================================================
# Arduino Interface
# ============================================================================
class ArduinoInterface(QObject):
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    response_received = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.logger = SimpleLogger("logs/arduino.log")
        self.worker = None
        self.platform = "unknown"
        self._connected = False
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    def detect_and_connect(self) -> bool:
        """Auto-detect and connect to microcontroller"""
        self.logger.log("AUTOCONNECT_START", {})
        
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            self.logger.log("NO_PORTS_FOUND", {})
            return False
        
        # Platform detection by VID/PID
        for port in ports:
            platform = self._detect_platform(port)
            if platform != "UNKNOWN":
                try:
                    self.worker = SerialWorker(port.device)
                    self.worker.data_received.connect(self._handle_response)
                    self.worker.error_occurred.connect(self._handle_error)
                    self.worker.disconnected.connect(self._handle_disconnect)
                    self.worker.start()
                    
                    self.platform = platform
                    self._connected = True
                    self.connected.emit(platform)
                    self.logger.log("CONNECTED", {"platform": platform, "port": port.device})
                    
                    # Send identification command
                    self.send_command("IDENTIFY")
                    return True
                    
                except Exception as e:
                    self.logger.log("CONNECTION_FAILED", {"error": str(e)})
        
        return False
    
    def _detect_platform(self, port) -> str:
        """Detect microcontroller platform"""
        if port.vid == 0x10C4 or "CP210" in port.description:
            return "ESP32"
        elif port.vid == 0x2E8A or "Pico" in port.description:
            return "PICO"
        elif port.vid in [0x2341, 0x2A03] or "Arduino" in port.description:
            return "ARDUINO"
        elif port.vid == 0x0483 or "STM32" in port.description:
            return "STM32"
        return "UNKNOWN"
    
    def connect_manual(self, port: str, baud: int = 115200) -> bool:
        """Manual connection to specific port"""
        try:
            self.worker = SerialWorker(port, baud)
            self.worker.data_received.connect(self._handle_response)
            self.worker.error_occurred.connect(self._handle_error)
            self.worker.disconnected.connect(self._handle_disconnect)
            self.worker.start()
            
            self._connected = True
            self.connected.emit("MANUAL")
            self.logger.log("MANUAL_CONNECTED", {"port": port, "baud": baud})
            return True
        except Exception as e:
            self.logger.log("MANUAL_CONNECTION_FAILED", {"error": str(e)})
            return False
    
    def _handle_response(self, data: dict):
        self.response_received.emit(data)
    
    def _handle_error(self, error: str):
        self.logger.log("SERIAL_ERROR", {"error": error})
    
    def _handle_disconnect(self):
        self._connected = False
        self.worker = None
        self.disconnected.emit()
        self.logger.log("DISCONNECTED", {})
    
    def send_command(self, cmd: str, params: dict = None):
        """Send command to microcontroller"""
        if self.worker and self._connected:
            payload = {"cmd": cmd, "params": params or {}}
            self.worker.send_command(payload)
            self.logger.log("COMMAND_SENT", payload)
        else:
            self.logger.log("COMMAND_FAILED", {"cmd": cmd, "reason": "not_connected"})
    
    def disconnect(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self._connected = False
        self.logger.log("DISCONNECTED_MANUAL", {})

# ============================================================================
# Pattern Loader
# ============================================================================
class PatternLoader(QObject):
    pattern_loaded = pyqtSignal(str, dict)
    pattern_error = pyqtSignal(str)
    
    def __init__(self, patterns_dir="user_attacks"):
        super().__init__()
        self.patterns_dir = Path(patterns_dir)
        self.patterns = {}
        self.logger = SimpleLogger("logs/patterns.log")
        self.load_patterns()
    
    def load_patterns(self):
        """Load all attack patterns from directory"""
        self.patterns_dir.mkdir(exist_ok=True)
        
        # Built-in patterns
        self.patterns = {
            "AGC_LOCK": {
                "name": "AGC Lock",
                "sequence": [{"group": 4, "intensity": 255, "duration_ms": 50}] * 8 + [{"group": 4, "intensity": 0, "duration_ms": 50}] * 8,
                "repeat": 1
            },
            "SATURATION": {
                "name": "Sensor Saturation",
                "sequence": [{"group": 4, "intensity": 255, "duration_ms": 5000}],
                "repeat": 1
            },
            "FLICKER": {
                "name": "Rolling Shutter",
                "sequence": [{"group": 5, "intensity": 200, "duration_ms": 100}],
                "repeat": 3
            }
        }
        
        # Load custom patterns
        for file in self.patterns_dir.glob("*.json"):
            try:
                with open(file) as f:
                    self.patterns[file.stem.upper()] = json.load(f)
                self.logger.log("PATTERN_LOADED", {"name": file.stem})
            except Exception as e:
                self.logger.log("PATTERN_LOAD_ERROR", {"file": str(file), "error": str(e)})
                self.pattern_error.emit(f"Failed to load {file.name}: {e}")
    
    def get_pattern(self, name: str) -> dict:
        return self.patterns.get(name.upper(), {})
    
    def list_patterns(self) -> list:
        return list(self.patterns.keys())

# ============================================================================
# Attack Orchestrator
# ============================================================================
class AttackOrchestrator(QThread):
    status_signal = pyqtSignal(str)
    cycle_signal = pyqtSignal(int)
    phase_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, arduino: ArduinoInterface, pattern_loader: PatternLoader):
        super().__init__()
        self.arduino = arduino
        self.patterns = pattern_loader
        self.logger = SimpleLogger("logs/attacks.log")
        
        self.running = False
        self.safety_engaged = False
        self.config_queue = queue.Queue()
        self.pattern_queue = queue.Queue()
        
        # Default configuration
        self.config = {
            "targets": [],
            "camera_duration": 5000,
            "injection_duration": 3000,
            "jitter_range": 0.2,
            "max_cycles": 100,
            "pattern_name": "AGC_LOCK"
        }
        
        self.current_cycle = 0
        self.attack_queue = []
    
    def engage_safety(self):
        self.safety_engaged = True
        self.status_signal.emit("SAFETY ENGAGED")
        self.logger.log("SAFETY", {"state": "ENGAGED"})
    
    def disengage_safety(self):
        self.safety_engaged = False
        self.status_signal.emit("SAFETY DISENGAGED")
        self.logger.log("SAFETY", {"state": "DISENGAGED"})
        if self.running:
            self.stop_cycling()
    
    def update_config(self, config: dict):
        """Thread-safe config update"""
        self.config_queue.put(config)
        self.logger.log("CONFIG_UPDATE", config)
    
    def load_pattern(self, pattern_name: str):
        """Load attack pattern by name"""
        self.pattern_queue.put(pattern_name)
        self.logger.log("PATTERN_REQUEST", {"name": pattern_name})
    
    def start_cycling(self):
        """Start autonomous attack cycling"""
        if not self.arduino.connected:
            self.error_signal.emit("Arduino not connected")
            return
        
        if not self.safety_engaged:
            self.error_signal.emit("Safety not engaged")
            return
        
        if not self.config["targets"]:
            self.error_signal.emit("No targets configured")
            return
        
        self.running = True
        self.current_cycle = 0
        self.start()
        self.status_signal.emit("ATTACK CYCLING STARTED")
        self.logger.log("CYCLING_START", self.config)
    
    def stop_cycling(self):
        """Stop attack cycling"""
        self.running = False
        self.arduino.send_command("DISARM")
        self.status_signal.emit("ATTACK CYCLING STOPPED")
        self.logger.log("CYCLING_STOP", {"cycles": self.current_cycle})
    
    def run(self):
        """Main attack loop - runs in separate thread"""
        self.build_attack_queue()
        
        while self.running:
            # Process config updates
            try:
                while True:
                    new_config = self.config_queue.get_nowait()
                    self.config.update(new_config)
                    self.build_attack_queue()
                    self.status_signal.emit("Config updated")
            except queue.Empty:
                pass
            
            # Process pattern changes
            try:
                while True:
                    pattern_name = self.pattern_queue.get_nowait()
                    if self.patterns.get_pattern(pattern_name):
                        self.config["pattern_name"] = pattern_name
                        self.build_attack_queue()
                        self.status_signal.emit(f"Pattern: {pattern_name}")
            except queue.Empty:
                pass
            
            # Check safety
            if not self.safety_engaged:
                self.error_signal.emit("SAFETY BREACH - ABORTING")
                self.running = False
                break
            
            # Execute attack queue
            for attack in self.attack_queue:
                if not self.running:
                    break
                
                self.execute_attack(attack)
                
                # Jittered delay between attacks
                jitter = random.uniform(
                    1 - self.config["jitter_range"],
                    1 + self.config["jitter_range"]
                )
                sleep_time = attack["duration"] / 1000 * jitter
                time.sleep(sleep_time)
                
                # Brief rest
                time.sleep(0.5)
                
                self.current_cycle += 1
                self.cycle_signal.emit(self.current_cycle)
                
                # Check cycle limit
                if self.current_cycle >= self.config["max_cycles"]:
                    self.status_signal.emit("MAX CYCLES REACHED")
                    self.running = False
                    break
            
            # Rebuild queue for next iteration
            if self.running:
                self.build_attack_queue()
        
        # Cleanup
        self.arduino.send_command("ALL_OFF")
        self.status_signal.emit("ORCHESTRATOR STOPPED")
        self.logger.log("ORCHESTRATOR_STOP", {})
    
    def build_attack_queue(self):
        """Build attack queue from current config and pattern"""
        pattern = self.patterns.get_pattern(self.config["pattern_name"])
        if not pattern:
            self.error_signal.emit(f"Pattern not found: {self.config['pattern_name']}")
            return
        
        self.attack_queue = []
        
        # Build sequence for each target
        for target in self.config["targets"]:
            for repeat in range(pattern.get("repeat", 1)):
                for phase in pattern["sequence"]:
                    self.attack_queue.append({
                        "target": target,
                        "group": phase["group"],
                        "intensity": phase["intensity"],
                        "duration": phase.get("duration_ms", 1000),
                        "name": f"{target}_{pattern['name']}"
                    })
        
        random.shuffle(self.attack_queue)
        self.status_signal.emit(f"Queue: {len(self.attack_queue)} attacks")
    
    def execute_attack(self, attack: dict):
        """Execute single attack phase"""
        self.phase_signal.emit(attack)
        self.status_signal.emit(f"[C{self.current_cycle}] {attack['name']}")
        self.logger.log("PHASE_EXEC", attack)
        
        # Send to Arduino
        self.arduino.send_command("SET_GROUP", {
            "group": attack["group"],
            "intensity": attack["intensity"]
        })
        
        # Duration is handled by sleep in main loop

# ============================================================================
# Main Window
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.logger = SimpleLogger("logs/gui.log")
        self.arduino = ArduinoInterface()
        self.patterns = PatternLoader()
        self.flasher = FirmwareFlasher()
        self.orchestrator = AttackOrchestrator(self.arduino, self.patterns)
        
        # Connect signals
        self.arduino.connected.connect(self.on_arduino_connected)
        self.arduino.disconnected.connect(self.on_arduino_disconnected)
        self.arduino.response_received.connect(self.on_arduino_response)
        
        self.orchestrator.status_signal.connect(self.update_status)
        self.orchestrator.cycle_signal.connect(self.update_cycle)
        self.orchestrator.error_signal.connect(self.show_error)
        self.orchestrator.phase_signal.connect(self.on_phase)
        
        self.flasher.progress_signal.connect(self.on_flash_progress)
        self.flasher.error_signal.connect(self.on_flash_error)
        self.flasher.success_signal.connect(self.on_flash_success)
        
        # UI state
        self.connected_platform = None
        
        self.init_ui()
        
        # Auto-connect timer
        QTimer.singleShot(1000, self.auto_connect)
    
    def init_ui(self):
        self.setWindowTitle("IRWP v2.5 - Multi-Platform Controller & Flasher")
        self.setGeometry(100, 100, 1600, 900)
        
        # Dark theme
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ffffff; }
            QGroupBox { border: 2px solid #555; margin-top: 10px; padding-top: 10px; }
            QPushButton { background-color: #3c3c3c; border: 1px solid #555; padding: 8px; }
            QPushButton:hover { background-color: #4c4c4c; }
            QPushButton:checked { background-color: #d32f2f; }
            QTextEdit { background-color: #1e1e1e; border: 1px solid #555; font-family: monospace; }
            QProgressBar { background-color: #1e1e1e; border: 1px solid #555; }
            QProgressBar::chunk { background-color: #4fc3f7; }
        """)
        
        central = QWidget()
        layout = QVBoxLayout(central)
        
        # Banner
        banner = QLabel(ASCII_BANNER)
        banner.setFont(QFont("Courier", 9))
        layout.addWidget(banner)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = self.create_left_panel()
        center_panel = self.create_center_panel()
        right_panel = self.create_right_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 750, 500])
        
        layout.addWidget(splitter)
        self.setCentralWidget(central)
    
    def create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Connection Section
        conn_group = QGroupBox("🔌 Microcontroller Connection")
        conn_layout = QVBoxLayout()
        
        # Auto-connect button
        self.auto_connect_btn = QPushButton("Auto-Detect & Connect")
        self.auto_connect_btn.clicked.connect(self.auto_connect)
        conn_layout.addWidget(self.auto_connect_btn)
        
        # Manual port selection
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        manual_layout.addWidget(self.port_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        manual_layout.addWidget(self.refresh_btn)
        
        conn_layout.addLayout(manual_layout)
        
        # Connect/Disconnect
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.manual_connect)
        conn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_arduino)
        self.disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self.disconnect_btn)
        
        # Connection status
        self.conn_status = QLabel("Status: Disconnected")
        self.conn_status.setStyleSheet("color: #ff5555; font-weight: bold;")
        conn_layout.addWidget(self.conn_status)
        
        # Platform info
        self.platform_info = QLabel("Platform: None")
        conn_layout.addWidget(self.platform_info)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Firmware Flashing Section
        flash_group = QGroupBox("⚡ Firmware Flashing")
        flash_layout = QVBoxLayout()
        
        # Platform selection for flashing
        self.flash_platform_combo = QComboBox()
        self.flash_platform_combo.addItems(["ESP32", "PICO", "ARDUINO", "STM32"])
        flash_layout.addWidget(self.flash_platform_combo)
        
        # Flash button
        self.flash_btn = QPushButton("Flash Selected Platform")
        self.flash_btn.clicked.connect(self.flash_firmware)
        self.flash_btn.setStyleSheet("background-color: #f57f17; color: white; font-weight: bold;")
        flash_layout.addWidget(self.flash_btn)
        
        # Progress bar
        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        flash_layout.addWidget(self.flash_progress)
        conn_layout.addWidget(self.connect Flash status
        self.flash_status = QLabel("Ready_btn = QPush")
        flash_layout.addWidget(self.flash_status)
        
        flashButton(".set")
Layout(f_btn.cl_layout)
_arduino layout self.disconnect_btn.setEnabled(False)
        conn_layout)
        
       Widget Safety_btn)
        
        # Connection safety        self.conn_status = QLabel("StatusGroup DisBox        self🛡.conn Hardware_status.setStyleSheet")
: #ff555 safety_layout = QVBoxLayout()
5;        font self.safety_btn")
 QPushButton(" conn_layout.addETYWidget OFF(self.conn_btn.setCheckable # Platform info
        self.platform_info =.toggled.connect(self.toggle_s("afety:        self.s conn_layout.addWidget(selfSheet("""
            Q        conn_group.setLayout background-color: #        layoutd.addfWidget(conn_group)
; font-weight: Firmware Flash padding Section 15px_group = QGroup QPushButton:checked { background-color")
       :_layout =388VBoxLayout()
        
        # }
        """)
        safety
       .addWidget(self_platform_combo = Q.sCombo_btn self.flash_platform_combo.add        
        self.s "PICO", "ARD QLabel("INO", "STM32"])
")
        safety_layout.addWidget(selfWidgetafety.flash_status_combo)
        
        # Flash button
        self.flash_btn(safety_layoutButton("Flash.addWidget Platform(s        self.flash)
.clicked       (self.flash_firmware)
Stretch()
        return panel
    
   Sheet create("_centerbackground-color(self #        panel = QWidget17; layout color: white; font-weight: # Pattern;")
        flash        pattern_group_btn)
 Q       Group Progress bar
        Pattern.flash        = QProgressBar Q        self()
        
       Range.pattern0, QCombo)
()
 flash self.pattern_combo.addItems(self_progressatterns.list        # Flash status_layout.add self.flash.pattern_combo QLabel        
        to flash")
        =_layoutPushWidget(".flash_status)
")
        
               self.load_pattern.setLayout(flashicked.connect       (self.addWidget(flash_group)
)
        pattern       .add # Safety.load
_pattern safety_group        
 QGroupBox("🛡.setLayout(pattern")
       )
_layout layout QVBoxLayout_group)
              .safety Target = Q SelectionButton("SA        target_group OFF")
        self("afety_btn")
Check target_layout)
        self Qafety_btn.t selfoggled_checks.connect {}
       afety targets =afety_btnWalmart("" "Target           ", "Cost Q",Button { backgroundKroger", "2f; font        bold; padding target15px;:
 }
 Q QPush(target)
            self:_checks[target]388
e target3.addWidget; }
        
        btn "" =")
       ()
        safety_layout_all = QPushButton("Select All")
        select_all.clicked.connect(lambda self.s_targets(True_status))
 QLabel       System btn SAFE_layout        safetyWidgetWidget(select.s_all_status)
        
              _group.set_allafety = Q layoutPushButton(".addWidget All")
        clear_all layout.add.cl       icked.connect
    
    self create_center_all_targets):
(False panel = QWidget()
 btn layout = QVBoxLayout(panel(clear_all)
 # Pattern       
 target pattern_group_layout Q.addBox("_layout)
 Pattern target_group pattern.set =LayoutVBox(target_layout        
        self.pattern_combo(target QCombo)
        
()
        #.pattern_combo.addItems
.p configatterns_group_patterns =        Q patternGroup.addWidget(self.pattern Attack)
")
        self_layout = Q_btnLayout()
        
       ("_layout.addWidget(QLabel("Camera Duration.clicked.connect(selfms.load_selected_pattern)
 0_layout .addWidget self.cam_spin = Q_pattern_btn()
)
 self.cam        patternRange(100Layout,(pattern600_layout)
)
 self.cam_spin.setWidgetValue(5000)
               
_layout.add #(self Target_spin,  target_group =, QGroup        
("        Targets")
        target_layout = QVBoxLayout()
        
        self.target(" =Data Duration ( {}
ms        targets),  ["1almart,",  "0Target)
        selfCostco = QSpinroger        "Custom"]
       .set forRange target500,  targets:
            cb30000 Q)
Box        self           .data_spin.targetValue_checks([target)
            target.addWidget.add.data_spin, )
        
        btn_layout = config_layout.addHBox(QL()
        select_allycles:"),Push, 0(" self.c All")
_spin select =.cl Q.connectSpinBox()
 self self.setycle_spin_allRange_targets1,(True999))
              .c_layoutycle.add_spinWidget.set_allValue        
       100_all = Q       Button("_layout.add AllWidget")
(self.c clear_all_spin,.cl icked,.connect1(lambda        
: self.set.add_allWidget_targetsabel("Jitter        %_layout:"), (c3,_all 0        
               target self_layout.additter_spinLayout = Q_layout)
Spin target_groupBox()
.setLayout(target_layout)
       itter_spin.add.setRange_group(0.0, Configuration
       0_group5 = QGroup       (" self.j Attack Parametersitter       _spin.set_layoutValue Q0Grid.()
2        
        config_layout selfWidget.jitter_spin.set("Camera DurationStep(0ms.):"),)
        config, 0)
.addWidget.cam(self = Qitter_spin()
, self 3_spin.set1)
        
        config_group.set1000, layout.addWidget(config_group)
        
        layout.addStretch()
_spin returnValue(5000)
        config_layout_panel(self(self.cam        panel =, ()
1)
 =       VBox_layout.add)
(QL       ("Data Duration (
        master_group1, Box("        self Control")
        = Q =Box Q       VBox.dataLayout.set()
        
(500 self .arm00)
        =.data QPush(300(")
SYSTEM config ARM.addWidget(self")
,  self, _btn)
.set        config_layout.addable(QLabel("Max Cycles:".arm_btn.clicked.connect0)
_arm)
        self.arm = QStyleSheet("""
            QPushButton { backgroundycle:_spin.seteRangec; font-size: 20  font-weight)
        bold.c;_spin.set:(10025        config;.add }
           yclePushButton 2, 1-color        
        #_layout.add32f2fJitter }
:"       ),")
        master3,Widget .arm)
        self.jitter        
       _spin.arm_status = QLabel QDoubleSpin SAFE()
              .j master_layout.set.add(Widget0,.arm 0.5)
        self.j_group.setLayout(master_layout)
Value.add((master0._group)
        
        #itter_spin CycleSingleStep(
       )
 counter config_group.addWidget(self.jGroup_spin(" 📊3 Cycle, Counter         counter)
 =        
 Q configVBox_groupLayout.set()
Layout       (config self_layout.c)
ycle_display = QLabel("0 / (config")
)
        
 self layout.cStretchycle_display.set()
StyleSheet panel("font-size create_right_panel(selfpx;):
 font       : bold = color QWidget()
4 layout =fcVBoxfLayout(panel")
       )
        
.addWidget(self Master.cycle Control_display       )
_group        =_group Q.setGroupLayoutBox(counter("_layout Master Control               master_layout = QVBox(counter()
_group        self.arm        # = Feed
PushButton_group = ARMED")
        self.arm_btn.setCheckable        feed_layout = QVBoxLayout()
.arm       .cl selficked.connect_feed(self.toggle QText_arm)
               self.arm_btn_feed.set.setReadOnly(True("""
 self.status Q.setMaximumButton {300 background-color feed #_layouteWidgetc;_feed font-size: _group.setLayout(feed font-weight        layout paddingWidget:_group         
25px; Emergency }
 Stop            Q       Button:checked { background-color = # Q32Pushf2f;🛑 EM        """)
        master_layout.addWidget(self.connect(self.emergency_stop)
        emergency_status = QLabel("Status:("""
            QPushButton master {_layout background.add-colorWidget:(self.arm000)
 color: #_groupf00;(master:)
 3px solid(master #f00        font-size Cycle Counter         counterpx = font Q-weight:Group;Box("📊: Counter")
20 counter_layout = QVBox }
Layout()
        self.cycle_display = layout QLabel.addWidget(em0ergency _btn")
               
ycle_display layoutStyleSheet("Stretch-size()
        return panel24px
    
 font   : bold; color
: # #4 &fc3 Flashfing Methods7;
    #        =========================================================================
   .add defWidget refresh_ports(self(selfycle):
)
       _group """Layout(counter_layout available serial ports"""
        layout selfWidget.port_group_combo        
.clear       ()
        # ports Feed = serial
.tools       _ports.comports()
_group =        QGroup for portBox in(" ports📜            self.port_combo       .addItem(f"{ = QVBoxLayout - {port.description}")
    
    defEdit_connect(self        self        """Auto-d.set and connect toOnly microcontroller(True        self       ("Auto-connecting...")
        if self.arduino.detect_andHeight( self.update_status        feed".addAuto-connected(self.status_feedself)
arduino.platform}")
 feed_group.set           Layout(feed("Auto)
 failed")
    
   .add manual_connect(self):
        """)
        
ually        # selected Emergency port
"""
               emergency port_text =PushButton_combo.current🛑()
       ENCY STOP")
_text emergency            self.show_error(self.emergency_stop)
 selected emergency")
.set           Sheet return
        
        port = port_text.split(" - ")[0]
        self.update_status(f"Connecting to {port}...")
 color        if self #arduinof00;.connect_manual(port):
            self.connect_btn.setEnabled(False:            3.disconnectpx.setEnabled(True)
f self00;_btn.set: 22px(True;)
 font-weight else bold:
 padding: self 20("; failed")
 }
    
        """)
 disconnect        layoutarduino(self):
(em       ergency_btn)
 from microcontroller        
        layout.addStretch.disconnect       ()
 return self.connect   _btn =========================================================================.set    #(True & Flashing Methods
 self # =========================================================================
_btn def.set_ports(self(False       )
Refresh        serial ports.flash       _btn.setEnabled.port_combo)
()
        ports self.update serial.tools.list   _ports def on_arduino_connected(self,ports platform: str for port in ports:
            """ self.port_combo.add connectionItem(f"""
        self.connected_platform = - platformport.description}")

        self   .conn auto_status_connect.set):
Text       (fAuto"etectConnected: connect {platform microcontroller}")
               self_status.setStyleSheet("Autocolor:ing...")
       00 if00;. font-weight.detect_and: bold_connect       ():
 self self.update_status_info(f.setText(f"Platform: { {platformself}")
        selfarduino.connect.platform.set}")
       (False           )
 self       .update self.disconnect_btn.setEnabled(True failed       ")
    
   .flash def_btn.setEnabled(True(self):
        
               #Man platformually-specific to selected
 port if platform == "ESP port_text":
            self.current_statusText("ESP()
32        detected - notFi_textT enabled")
    
   .show def_error on("No_ portarduino selected_dis")
           (self return):
               """ portHandle = dis portconnection_text.split(" - "_platform = None
]
        self self.update_status.set"Text("Disconnected")
}...")
        
       .set ifStyle self.("arduino.connectcolor: #ff5555; font(port-weight):
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.flash_btn.setEnabled(True)
        else:
            self.show_error("Connection failed")
    
    def disconnect_arduino(self):
        """Disconnect from microcontroller"""
        self.arduino.disconnect()
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
        self.update_status("Disconnected")
    
    def on_arduino_connected(self, platform: str):
        """Handle successful connection"""
        self.connected_platform = platform
        self.conn_status.setText(f"Connected: {platform}")
        self.conn_status.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.platform_info.setText(f"Platform: {platform}")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.flash_btn.setEnabled(True)
        
        # Enable platform-specific features
        if platform == "ESP32":
            self.update_status("ESP32 detected - WiFi/BT enabled")
    
    def on_arduino_disconnected(self):
        """Handle disconnection"""
        self.connected_platform = None
        self.conn_status.setText("Disconnected")
        self.conn_status.setStyleSheet("color: #ff5555; font-weight: bold;")
        self.platform_info.setText("Platform: None")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
    
    def on_arduino_response(self, data: dict):
        """Handle response from Arduino"""
        if data.get("type") == "status":
            self.update_status(f"Arduino: {data}")
    
    # =========================================================================
    # Firmware Flashing
    # =========================================================================
    def flash_firmware(self):
        """Flash firmware to selected platform"""
        platform = self.flash_platform_combo.currentText()
        
        # Confirm dialog
        reply = QMessageBox.question(
            self, "Flash Firmware",
            f"Flash {platform} firmware?\nThis will overwrite existing firmware!",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        
        if reply != QMessageBox.StandardButton.Ok:
            return
        
        # Find port
        port = None
        if self.arduino.connected and self.arduino.platform == platform:
            port = "CURRENT"
        else:
            # Find first matching port
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                if self.flasher.detect_platform(p) == platform:
                    port = p.device
                    break
        
        if not port:
            self.show_error(f"No {platform} found")
            return
        
        self.flash_progress.setValue(0)
        self.flash_btn.setEnabled(False)
        self.flasher.flash(platform, port)
    
    def on_flash_progress(self, message: str, percent: int):
        """Update flash progress"""
        self.flash_status.setText(message)
        self.flash_progress.setValue(percent)
        self.update_status(f"Flash: {message}")
    
    def on_flash_error(self, error: str):
        """Handle flash error"""
        self.show_error(f"Flash error: {error}")
        self.flash_status.setText(error)
        self.flash_btn.setEnabled(True)
        self.flash_progress.setValue(0)
    
    def on_flash_success(self, platform: str):
        """Handle successful flash"""
        self.flash_status.setText(f"{platform} flashed successfully!")
        self.flash_btn.setEnabled(True)
        self.flash_progress.setValue(100)
        self.update_status(f"{platform} firmware updated")
        QMessageBox.information(self, "Success", f"{platform} firmware flashed!")
        
        # Auto-reconnect after flash
        QTimer.singleShot(3000, self.auto_connect)
    
    # =========================================================================
    # Control Methods
    # =========================================================================
    def toggle_safety(self, engaged: bool):
        """Hardware safety switch"""
        if engaged:
            self.orchestrator.engage_safety()
            self.safety_btn.setText("SAFETY ENGAGED")
            self.safety_status.setText("System: ARMED")
            self.safety_status.setStyleSheet("color: #00ff00; font-weight: bold;")
        else:
            self.orchestrator.disengage_safety()
            self.safety_btn.setText("SAFETY OFF")
            self.safety_status.setText("System: SAFE")
            self.safety_status.setStyleSheet("color: #ff5555; font-weight: bold;")
            
            if self.arm_btn.isChecked():
                self.arm_btn.setChecked(False)
    
    def load_selected_pattern(self):
        """Load selected attack pattern"""
        pattern_name = self.pattern_combo.currentText()
        self.orchestrator.load_pattern(pattern_name)
        self.update_status(f"Pattern loaded: {pattern_name}")
    
    def set_all_targets(self, checked: bool):
        """Select/clear all targets"""
        for cb in self.target_checks.values():
            cb.setChecked(checked)
    
    def toggle_arm(self):
        """Arm/disarm attack system"""
        if self.arm_btn.isChecked():
            # Check preconditions
            if not self.arduino.connected:
                self.show_error("Arduino not connected")
                self.arm_btn.setChecked(False)
                return
            
            if not self.orchestrator.safety_engaged:
                self.show_error("Safety not engaged")
                self.arm_btn.setChecked(False)
                return
            
            # Get targets
            targets = [t for t, cb in self.target_checks.items() if cb.isChecked()]
            if not targets:
                self.show_error("No targets selected")
                self.arm_btn.setChecked(False)
                return
            
            # Update configuration
            config = {
                "targets": targets,
                "camera_duration": self.cam_spin.value(),
                "injection_duration": self.data_spin.value(),
                "max_cycles": self.cycle_spin.value(),
                "jitter_range": self.jitter_spin.value(),
                "pattern_name": self.pattern_combo.currentText()
            }
            self.orchestrator.update_config(config)
            
            # Start
            self.arm_btn.setText("DISARM SYSTEM")
            self.arm_status.setText("Status: ATTACKING")
            self.arm_status.setStyleSheet("color: #ff0000; font-weight: bold; font-size: 18px;")
            self.orchestrator.start_cycling()
            self.update_status("SYSTEM ARMED")
            
        else:
            # Disarm
            self.orchestrator.stop_cycling()
            self.arm_btn.setText("ARM SYSTEM")
            self.arm_status.setText("Status: SAFE")
            self.arm_status.setStyleSheet("color: #00ff00; font-weight: bold;")
            self.update_status("SYSTEM DISARMED")
    
    def emergency_stop(self):
        """Emergency stop all operations"""
        self.orchestrator.stop_cycling()
        self.arm_btn.setChecked(False)
        self.safety_btn.setChecked(False)
        self.arduino.send_command("EMERGENCY")
        self.update_status("EMERGENCY STOP ACTIVATED")
        QMessageBox.critical(self, "EMERGENCY", "All systems halted!")
    
    # =========================================================================
    # Status & Logging
    # =========================================================================
    def update_status(self, message: str):
        """Update status feed with memory leak prevention"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Prevent memory leak
        if self.status_feed.document().blockCount() > 1000:
            cursor = self.status_feed.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, 100)
            cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        
        self.status_feed.append(f"[{timestamp}] {message}")
    
    def update_cycle(self, count: int):
        """Update cycle counter"""
        self.cycle_display.setText(f"{count} / {self.cycle_spin.value()}")
        
        # Auto-disarm at max cycles
        if count >= self.cycle_spin.value() and self.arm_btn.isChecked():
            self.arm_btn.setChecked(False)
            self.toggle_arm()
            self.update_status("Auto-disarmed: Max cycles reached")
    
    def on_phase(self, phase: dict):
        """Display current attack phase"""
        self.update_status(f"Phase: {phase['name']} | Group: {phase['group']} | Duration: {phase['duration']}ms")
    
    def show_error(self, error: str):
        """Display error message"""
        QMessageBox.critical(self, "Error", error)
        self.update_status(f"ERROR: {error}")

# ============================================================================
# Entry Point
# ============================================================================
def main():
    # Create directories
    Path("logs").mkdir(exist_ok=True)
    Path("firmware").mkdir(exist_ok=True)
    Path("user_attacks").mkdir(exist_ok=True)
    
    app = QApplication(sys.argv)
    
    # Check for required tools
    if sys.platform != "win32":
        # Add tools to PATH if in local directory
        tools_dir = Path("tools")
        if tools_dir.exists():
            os.environ["PATH"] = str(tools_dir.absolute()) + os.pathsep + os.environ["PATH"]
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
