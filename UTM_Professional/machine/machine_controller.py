import logging
import math
from PySide6.QtCore import QObject, Signal, QTimer
from machine.machine_state import MachineState
from communication.serial_manager import SerialManager

logger = logging.getLogger(__name__)

class MachineController(QObject):
    state_changed = Signal(MachineState)
    data_updated = Signal(dict)
    alarm_triggered = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.state = MachineState.IDLE
        self.serial_manager = SerialManager()
        
        self.serial_manager.connection_status_changed.connect(self._on_connection_changed)
        self.serial_manager.data_received.connect(self._on_data_received)
        self.serial_manager.error_occurred.connect(self._on_serial_error)
        
        self.mock_mode = False
        self.mock_timer = QTimer()
        self.mock_timer.timeout.connect(self._generate_mock_data)
        self.mock_time = 0.0
        
        # Specimen dimensions
        self.width = 10.0
        self.thickness = 5.0
        self.gauge_length = 50.0
        
        # Peaks
        self.peak_load = 0.0
        self.peak_stress = 0.0
        self.test_data = []
        
        # --- NEW FEATURES ---
        # 1. TARE / Zeroing offsets
        self.load_offset = 0.0
        self.ext_offset = 0.0
        self.current_raw_load = 0.0
        self.current_raw_ext = 0.0
        
        # 2. Moving Average Filter (Data Smoothing)
        self.load_history = []
        
        # 3. Auto-Break Detection
        self.auto_break_enabled = True

    def tare(self):
        """Zero out the sensors (Tare)"""
        self.load_offset = self.current_raw_load
        self.ext_offset = self.current_raw_ext
        self.peak_load = 0.0
        self.peak_stress = 0.0
        self.test_data = []

    def set_sample_dimensions(self, width: float, thickness: float, gauge: float):
        self.width = width
        self.thickness = thickness
        self.gauge_length = gauge

    def start(self):
        self.set_state(MachineState.INITIALIZING)
        self.set_state(MachineState.IDLE)

    def set_state(self, new_state: MachineState):
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(self.state)

    def emergency_stop(self):
        self.serial_manager.send_command('E_STOP')
        self.set_state(MachineState.EMERGENCY_STOP)
        self.alarm_triggered.emit("EMERGENCY STOP")
        if self.mock_mode:
            self.mock_timer.stop()

    def start_test(self):
        if self.state in [MachineState.IDLE, MachineState.READY, MachineState.COMPLETED]:
            self.peak_load = 0.0
            self.peak_stress = 0.0
            self.test_data = []
            self.set_state(MachineState.RUNNING)
            # Send a battery of common wake-up commands
            if self.serial_manager.is_connected and self.serial_manager.serial_conn:
                try:
                    cmds = [
                        b'\r\n',
                        b'\x05',
                        b'S\r\n', b'S',        # Very common for Start
                        b'CMDSTART\r\n',
                        b'START\r\n',         
                        b'?\r\n',
                        b'T\r\n'              # Tare / wake up
                    ]
                    for cmd in cmds:
                        self.serial_manager.serial_conn.write(cmd)
                    # flush() removed because it blocks the UI thread if DTR/RTS is misconfigured
                except Exception as e:
                    logger.error(f"Failed to send wake up cmds: {e}")
            else:
                self.serial_manager.send_command('START_TEST')
            if self.mock_mode:
                self.mock_time = 0.0
                self.mock_timer.start(100)

    def stop_test(self):
        if self.state == MachineState.RUNNING:
            self.serial_manager.send_command('STOP_TEST')
            self.set_state(MachineState.COMPLETED)
            if self.mock_mode:
                self.mock_timer.stop()

    def _on_connection_changed(self, connected: bool, port: str):
        if not connected and self.state == MachineState.RUNNING:
            self.set_state(MachineState.COMMUNICATION_LOST)
            self.alarm_triggered.emit("Communication Lost during active test!")

    def _process_and_emit(self, load_N: float, ext_mm: float, time_s: float):
        """Calculates derived values and emits."""
        self.current_raw_load = load_N
        self.current_raw_ext = ext_mm
        
        # 1. Apply Tare Offsets
        net_load = load_N - self.load_offset
        net_ext = ext_mm - self.ext_offset
        if net_load < 0: net_load = 0.0 # Prevent negative loads
        if net_ext < 0: net_ext = 0.0
        
        # 2. Smooth data (Moving Average Filter)
        self.load_history.append(net_load)
        if len(self.load_history) > 5:
            self.load_history.pop(0)
        smoothed_load = sum(self.load_history) / len(self.load_history)
        
        # Convert Load N to kN
        load_kN = smoothed_load / 1000.0
        
        # Calculate Stress (MPa = N / mm^2)
        area = self.width * self.thickness
        stress = smoothed_load / area if area > 0 else 0.0
        
        # Calculate Strain (%)
        strain = (net_ext / self.gauge_length) * 100.0 if self.gauge_length > 0 else 0.0
        
        # Peaks
        if load_kN > self.peak_load:
            self.peak_load = load_kN
        if stress > self.peak_stress:
            self.peak_stress = stress
            
        # 3. Auto-Break Detection (Stop if load drops by 40% from peak)
        if self.auto_break_enabled and self.peak_load > 0.5:
            if load_kN < (self.peak_load * 0.6):
                logger.info("Auto-Break Detected! Stopping test.")
                self.stop_test()
                self.alarm_triggered.emit("Sample Break Detected! Test Auto-Stopped.")
                
        data = {
            'time': time_s,
            'LOAD_kN': load_kN,
            'EXT': net_ext,
            'STRESS': stress,
            'STRAIN': strain,
            'PEAK_LOAD': self.peak_load,
            'PEAK_STRESS': self.peak_stress
        }
        self.test_data.append(data)
        self.data_updated.emit(data)

    def export_to_csv(self, filepath: str):
        if not self.test_data:
            return False
            
        import csv
        try:
            with open(filepath, 'w', newline='') as csvfile:
                fieldnames = ['Time (s)', 'Load (kN)', 'Extension (mm)', 'Stress (MPa)', 'Strain (%)']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in self.test_data:
                    writer.writerow({
                        'Time (s)': f"{row['time']:.2f}",
                        'Load (kN)': f"{row['LOAD_kN']:.3f}",
                        'Extension (mm)': f"{row['EXT']:.3f}",
                        'Stress (MPa)': f"{row['STRESS']:.2f}",
                        'Strain (%)': f"{row['STRAIN']:.2f}"
                    })
            return True
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return False

    def _on_data_received(self, data: dict):
        if self.state == MachineState.RUNNING:
            # Assuming hardware sends LOAD in Newtons and EXT in mm
            load = data.get('LOAD', 0.0)
            ext = data.get('EXT', 0.0)
            time_val = data.get('time', 0.0) # Hardware should ideally send timestamp
            self._process_and_emit(load, ext, time_val)

    def _on_serial_error(self, err_msg: str):
        self.alarm_triggered.emit(err_msg)

    def enable_mock_mode(self, enable: bool = True):
        self.mock_mode = enable

    def _generate_mock_data(self):
        if self.state != MachineState.RUNNING:
            return
            
        self.mock_time += 0.1
        extension = self.mock_time * 2.0  # 20mm/s
        
        if extension < 5:
            load = extension * 1000 # 1000 N/mm
        elif extension < 15:
            load = 5000 + math.sin((extension - 5) * 0.2) * 500
        else:
            self.stop_test()
            return
            
        import random
        load += random.uniform(-20.0, 20.0)
        
        self._process_and_emit(load, extension, self.mock_time)
