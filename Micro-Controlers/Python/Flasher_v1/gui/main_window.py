import sys
import time
import random
import subprocess
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QTextCursor

from core.arduino_interface import ArduinoInterface
from gui.orchestrator import AttackOrchestrator
from core.pattern_loader import PatternLoader
from utils.logger import SimpleLogger
from utils.validators import validate_config

# Flashing support
import serial.tools.list_ports

ASCII_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║     ██████╗ ██╗██████╗ ██████╗  ██████╗██╗██╗     ██╗██╗    ║
║     ██╔══██╗██║██╔══██╗██╔══██╗██╔════╝██║██║     ██║██║    ║
║     ██████╔╝██║██████╔╝██║  ██║██║     ██║██║     ██║██║    ║
║     ██╔═══╝ ██║██╔═══╝ ██║  ██║██║     ██║██║     ██║██║    ║
║     ██║     ██║██║     ██████╔╝╚██████╗██║███████╗██║██████╗║
║     ╚═╝     ╚═╝╚═╝     ╚═════╝  ╚═════╝╚═╝╚══════╝╚═╝╚═════╝║
║           IRWP v2.5 - Multi-Platform Controller              ║
╚══════════════════════════════════════════════════════════════╝
"""

class FirmwareFlasher(QObject):
    progress_signal = pyqtSignal(str, int)
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
        
        self.firmware_files = {
            "ESP32": "firmware/esp32_firmware.bin",
            "PICO": "firmware/pico_firmware.uf2",
            "ARDUINO": "firmware/nano_firmware.hex",
            "STM32": "firmware/stm32_firmware.bin"
        }
    
    def detect_platform(self, port) -> str:
        if port.vid == 0x10C4 or "CP210" in port.description:
            return "ESP32"
        elif port.vid == 0x2E8A or "Pico" in port.description:
            return "PICO"
        elif port.vid in [0x2341, 0x2A03] or "Arduino" in port.description:
            return "ARDUINO"
        elif port.vid == 0x0483 or "STM32" in port.description:
            return "STM32"
        return "UNKNOWN"
    
    def flash(self, platform: str, port: str):
        if platform not in self.platform_tools:
            self.error_signal.emit(f"Unsupported platform: {platform}")
            return
        
        firmware_file = Path(self.firmware_files[platform])
        if not firmware_file.exists():
            self.error_signal.emit(f"Firmware not found: {firmware_file}")
            return
        
        self.progress_signal.emit(f"Flashing {platform} on {port}", 0)
        self.logger.log("FLASH_START", {"platform": platform, "port": port})
        
        try:
            self.platform_tools[platform](port, firmware_file)
        except Exception as e:
            self.error_signal.emit(f"Flash failed: {e}")
            self.logger.log("FLASH_ERROR", {"error": str(e)})
    
    def flash_esp32(self, port: str, firmware: Path):
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
        self.progress_signal.emit("Put Pico in bootloader mode...", 10)
        
        if sys.platform == "win32":
            bootloader = self._find_bootloader_drive("RPI-RP2")
        elif sys.platform == "darwin":
            bootloader = Path("/Volumes/RPI-RP2")
        else:
            bootloader = self._find_bootloader_linux()
        
        if not bootloader:
            cmd = ["picotool", "load", "-x", str(firmware)]
            self._run_flash_command(cmd, "PICO")
        else:
            dest = bootloader / firmware.name
            cmd = ["cp", str(firmware), str(dest)]
            self._run_flash_command(cmd, "PICO", use_shell=True)
    
    def flash_arduino(self, port: str, firmware: Path):
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
        cmd = ["st-flash", "write", str(firmware), "0x8000000"]
        self._run_flash_command(cmd, "STM32")
    
    def _find_bootloader_drive(self, name: str):
        for drive in Path("/media").iterdir():
            if name in drive.name:
                return drive
        return None
    
    def _find_bootloader_linux(self):
        for path in [Path("/media"), Path("/mnt"), Path.home() / "media"]:
            if path.exists():
                for child in path.iterdir():
                    if "RPI-RP2" in child.name:
                        return child
        return None
    
    def _run_flash_command(self, cmd: list, platform: str, use_shell: bool = False):
        try:
            self.progress_signal.emit(f"Running: {' '.join(cmd)}", 20)
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=use_shell
            )
            
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    self.logger.log("FLASH_OUTPUT", {"line": line})
                    
                    if "Writing" in line:
                        self.progress_signal.emit(line, 50)
                    elif "Hash of data verified" in line:
                        self.progress_signal.emit(line, 90)
                    
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
            self.error_signal.emit("Tool not found. Install platform flashing utility.")
        except Exception as e:
            self.error_signal.emit(f"Exception: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
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
        
        self.connected_platform = None
        
        self.init_ui()
        QTimer.singleShot(1000, self.auto_connect)
    
    def init_ui(self):
        self.setWindowTitle("IRWP v2.5 - Multi-Platform Controller & Flasher")
        self.setGeometry(100, 100, 1600, 900)
        
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
        
        banner = QLabel(ASCII_BANNER)
        banner.setFont(QFont("Courier", 9))
        layout.addWidget(banner)
        
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
        
        # Connection
        conn_group = QGroupBox("🔌 Microcontroller Connection")
        conn_layout = QVBoxLayout()
        
        self.auto_connect_btn = QPushButton("Auto-Detect & Connect")
        self.auto_connect_btn.clicked.connect(self.auto_connect)
        conn_layout.addWidget(self.auto_connect_btn)
        
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        manual_layout.addWidget(self.port_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        manual_layout.addWidget(self.refresh_btn)
        conn_layout.addLayout(manual_layout)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.manual_connect)
        conn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_arduino)
        self.disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self.disconnect_btn)
        
        self.conn_status = QLabel("Status: Disconnected")
        self.conn_status.setStyleSheet("color: #ff5555; font-weight: bold;")
        conn_layout.addWidget(self.conn_status)
        
        self.platform_info = QLabel("Platform: None")
        conn_layout.addWidget(self.platform_info)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Firmware Flashing
        flash_group = QGroupBox("⚡ Firmware Flashing")
        flash_layout = QVBoxLayout()
        
        self.flash_platform_combo = QComboBox()
        self.flash_platform_combo.addItems(["ESP32", "PICO", "ARDUINO", "STM32"])
        flash_layout.addWidget(self.flash_platform_combo)
        
        self.flash_btn = QPushButton("Flash Selected Platform")
        self.flash_btn.clicked.connect(self.flash_firmware)
        self.flash_btn.setStyleSheet("background-color: #f57f17; color: white; font-weight: bold;")
        flash_layout.addWidget(self.flash_btn)
        
        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        flash_layout.addWidget(self.flash_progress)
        
        self.flash_status = QLabel("Ready to flash")
        flash_layout.addWidget(self.flash_status)
        
        flash_group.setLayout(flash_layout)
        layout.addWidget(flash_group)
        
        # Safety
        safety_group = QGroupBox("🛡️ Hardware Safety")
        safety_layout = QVBoxLayout()
        
        self.safety_btn = QPushButton("SAFETY OFF")
        self.safety_btn.setCheckable(True)
        self.safety_btn.toggled.connect(self.toggle_safety)
        self.safety_btn.setStyleSheet("""
            QPushButton { background-color: #d32f2f; font-weight: bold; padding: 15px; }
            QPushButton:checked { background-color: #388e3c; }
        """)
        safety_layout.addWidget(self.safety_btn)
        
        self.safety_status = QLabel("System: SAFE")
        safety_layout.addWidget(self.safety_status)
        
        safety_group.setLayout(safety_layout)
        layout.addWidget(safety_group)
        
        layout.addStretch()
        return panel
    
    def create_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Pattern Selection
        pattern_group = QGroupBox("🎯 Attack Pattern")
        pattern_layout = QVBoxLayout()
        
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(self.patterns.list_patterns())
        pattern_layout.addWidget(self.pattern_combo)
        
        self.load_pattern_btn = QPushButton("Load Pattern")
        self.load_pattern_btn.clicked.connect(self.load_selected_pattern)
        pattern_layout.addWidget(self.load_pattern_btn)
        
        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)
        
        # Targets
        target_group = QGroupBox("🎯 Targets")
        target_layout = QVBoxLayout()
        
        self.target_checks = {}
        targets = ["Walmart", "Target", "Costco", "Kroger", "Custom"]
        for target in targets:
            cb = QCheckBox(target)
            self.target_checks[target] = cb
            target_layout.addWidget(cb)
        
        btn_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self.set_all_targets(True))
        btn_layout.addWidget(select_all)
        
        clear_all = QPushButton("Clear All")
        clear_all.clicked.connect(lambda: self.set_all_targets(False))
        btn_layout.addWidget(clear_all)
        
        target_layout.addLayout(btn_layout)
        target_group.setLayout(target_layout)
        layout.addWidget(target_group)
        
        # Configuration
        config_group = QGroupBox("⚙️ Attack Parameters")
        config_layout = QGridLayout()
        
        config_layout.addWidget(QLabel("Camera Duration (ms):"), 0, 0)
        self.cam_spin = QSpinBox()
        self.cam_spin.setRange(1000, 60000)
        self.cam_spin.setValue(5000)
        config_layout.addWidget(self.cam_spin, 0, 1)
        
        config_layout.addWidget(QLabel("Data Duration (ms):"), 1, 0)
        self.data_spin = QSpinBox()
        self.data_spin.setRange(500, 30000)
        self.data_spin.setValue(3000)
        config_layout.addWidget(self.data_spin, 1, 1)
        
        config_layout.addWidget(QLabel("Max Cycles:"), 2, 0)
        self.cycle_spin = QSpinBox()
        self.cycle_spin.setRange(1, 999)
        self.cycle_spin.setValue(100)
        config_layout.addWidget(self.cycle_spin, 2, 1)
        
        config_layout.addWidget(QLabel("Jitter %:"), 3, 0)
        self.jitter_spin = QDoubleSpinBox()
        self.jitter_spin.setRange(0.0, 0.5)
        self.jitter_spin.setValue(0.2)
        self.jitter_spin.setSingleStep(0.05)
        config_layout.addWidget(self.jitter_spin, 3, 1)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        layout.addStretch()
        return panel
    
    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Master Control
        master_group = QGroupBox("⚡ Master Control")
        master_layout = QVBoxLayout()
        
        self.arm_btn = QPushButton("SYSTEM ARMED")
        self.arm_btn.setCheckable(True)
        self.arm_btn.clicked.connect(self.toggle_arm)
        self.arm_btn.setStyleSheet("""
            QPushButton { background-color: #388e3c; font-size: 20px; font-weight: bold; padding: 25px; }
            QPushButton:checked { background-color: #d32f2f; }
        """)
        master_layout.addWidget(self.arm_btn)
        
        self.arm_status = QLabel("Status: SAFE")
        master_layout.addWidget(self.arm_status)
        
        master_group.setLayout(master_layout)
        layout.addWidget(master_group)
        
        # Cycle Counter
        counter_group = QGroupBox("📊 Cycle Counter")
        counter_layout = QVBoxLayout()
        self.cycle_display = QLabel("0 / 0")
        self.cycle_display.setStyleSheet("font-size: 24px; font-weight: bold; color: #4fc3f7;")
        counter_layout.addWidget(self.cycle_display)
        counter_group.setLayout(counter_layout)
        layout.addWidget(counter_group)
        
        # Status Feed
        feed_group = QGroupBox("📜 Live Feed")
        feed_layout = QVBoxLayout()
        self.status_feed = QTextEdit()
        self.status_feed.setReadOnly(True)
        self.status_feed.setMaximumHeight(300)
        feed_layout.addWidget(self.status_feed)
        feed_group.setLayout(feed_layout)
        layout.addWidget(feed_group)
        
        # Emergency Stop
        emergency_btn = QPushButton("🛑 EMERGENCY STOP")
        emergency_btn.clicked.connect(self.emergency_stop)
        emergency_btn.setStyleSheet("""
            QPushButton { background-color: #000; color: #f00; border: 3px solid #f00; font-size: 22px; font-weight: bold; padding: 20px; }
        """)
        layout.addWidget(emergency_btn)
        
        layout.addStretch()
        return panel
    
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")
    
    def auto_connect(self):
        self.update_status("Auto-connecting...")
        if self.arduino.detect_and_connect():
            self.update_status(f"Auto-connected: {self.arduino.platform}")
        else:
            self.update_status("Auto-connect failed")
    
    def manual_connect(self):
        port_text = self.port_combo.currentText()
        if not port_text:
            self.show_error("No port selected")
            return
        
        port = port_text.split(" - ")[0]
        self.update_status(f"Connecting to {port}...")
        
        if self.arduino.connect_manual(port):
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.flash_btn.setEnabled(True)
        else:
            self.show_error("Connection failed")
    
    def disconnect_arduino(self):
        self.arduino.disconnect()
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
        self.update_status("Disconnected")
    
    def on_arduino_connected(self, platform: str):
        self.connected_platform = platform
        self.conn_status.setText(f"Connected: {platform}")
        self.conn_status.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.platform_info.setText(f"Platform: {platform}")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.flash_btn.setEnabled(True)
        
        if platform == "ESP32":
            self.update_status("ESP32 detected - WiFi/BT enabled")
    
    def on_arduino_disconnected(self):
        self.connected_platform = None
        self.conn_status.setText("Disconnected")
        self.conn_status.setStyleSheet("color: #ff5555; font-weight: bold;")
        self.platform_info.setText("Platform: None")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.flash_btn.setEnabled(False)
    
    def on_arduino_response(self, data: dict):
        if data.get("type") == "status":
            self.update_status(f"Arduino: {data}")
    
    def flash_firmware(self):
        platform = self.flash_platform_combo.currentText()
        
        reply = QMessageBox.question(
            self, "Flash Firmware",
            f"Flash {platform} firmware?\nThis will overwrite existing firmware!",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        
        if reply != QMessageBox.StandardButton.Ok:
            return
        
        port = None
        if self.arduino.connected and self.arduino.platform == platform:
            port = "CURRENT"
        else:
            ports = serial.tools.list_ports.comports()
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
        self.flash_status.setText(message)
        self.flash_progress.setValue(percent)
        self.update_status(f"Flash: {message}")
    
    def on_flash_error(self, error: str):
        self.show_error(f"Flash error: {error}")
        self.flash_status.setText(error)
        self.flash_btn.setEnabled(True)
        self.flash_progress.setValue(0)
    
    def on_flash_success(self, platform: str):
        self.flash_status.setText(f"{platform} flashed successfully!")
        self.flash_btn.setEnabled(True)
        self.flash_progress.setValue(100)
        self.update_status(f"{platform} firmware updated")
        QMessageBox.information(self, "Success", f"{platform} firmware flashed!")
        QTimer.singleShot(3000, self.auto_connect)
    
    def toggle_safety(self, engaged: bool):
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
        pattern_name = self.pattern_combo.currentText()
        self.orchestrator.load_pattern(pattern_name)
        self.update_status(f"Pattern loaded: {pattern_name}")
    
    def set_all_targets(self, checked: bool):
        for cb in self.target_checks.values():
            cb.setChecked(checked)
    
    def toggle_arm(self):
        if self.arm_btn.isChecked():
            if not self.arduino.connected:
                self.show_error("Arduino not connected")
                self.arm_btn.setChecked(False)
                return
            
            if not self.orchestrator.safety_engaged:
                self.show_error("Safety not engaged")
                self.arm_btn.setChecked(False)
                return
            
            targets = [t for t, cb in self.target_checks.items() if cb.isChecked()]
            if not targets:
                self.show_error("No targets selected")
                self.arm_btn.setChecked(False)
                return
            
            config = {
                "targets": targets,
                "camera_duration": self.cam_spin.value(),
                "injection_duration": self.data_spin.value(),
                "max_cycles": self.cycle_spin.value(),
                "jitter_range": self.jitter_spin.value(),
                "pattern_name": self.pattern_combo.currentText()
            }
            self.orchestrator.update_config(config)
            
            self.arm_btn.setText("DISARM SYSTEM")
            self.arm_status.setText("Status: ATTACKING")
            self.arm_status.setStyleSheet("color: #ff0000; font-weight: bold; font-size: 18px;")
            self.orchestrator.start_cycling()
            self.update_status("SYSTEM ARMED")
            
        else:
            self.orchestrator.stop_cycling()
            self.arm_btn.setText("ARM SYSTEM")
            self.arm_status.setText("Status: SAFE")
            self.arm_status.setStyleSheet("color: #00ff00; font-weight: bold;")
            self.update_status("SYSTEM DISARMED")
    
    def emergency_stop(self):
        self.orchestrator.stop_cycling()
        self.arm_btn.setChecked(False)
        self.safety_btn.setChecked(False)
        self.arduino.send_command("EMERGENCY")
        self.update_status("EMERGENCY STOP ACTIVATED")
        QMessageBox.critical(self, "EMERGENCY", "All systems halted!")
    
    def update_status(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if self.status_feed.document().blockCount() > 1000:
            cursor = self.status_feed.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, 100)
            cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        
        self.status_feed.append(f"[{timestamp}] {message}")
    
    def update_cycle(self, count: int):
        self.cycle_display.setText(f"{count} / {self.cycle_spin.value()}")
        
        if count >= self.cycle_spin.value() and self.arm_btn.isChecked():
            self.arm_btn.setChecked(False)
            self.toggle_arm()
            self.update_status("Auto-disarmed: Max cycles reached")
    
    def on_phase(self, phase: dict):
        self.update_status(f"Phase: {phase['name']} | Group: {phase['group']} | Duration: {phase['duration']}ms")
    
    def show_error(self, error: str):
        QMessageBox.critical(self, "Error", error)
        self.update_status(f"ERROR: {error}")
