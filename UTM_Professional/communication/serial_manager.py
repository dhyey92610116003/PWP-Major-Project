import serial
import serial.tools.list_ports
import threading
import time
import logging
from PySide6.QtCore import QObject, Signal

from communication.protocol import Protocol

logger = logging.getLogger(__name__)

class SerialManager(QObject):
    """
    Manages RS232 Communication on a dedicated background thread to prevent UI freezing.
    """
    
    # Signals for UI communication
    connection_status_changed = Signal(bool, str) # (isConnected, portName)
    data_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, port=None, baudrate=9600, timeout=0.1):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        self.serial_conn = None
        self.is_connected = False
        
        self._thread = None
        self._stop_event = threading.Event()
        
    @staticmethod
    def get_available_ports():
        """Returns a list of available COM ports."""
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port=None):
        if port:
            self.port = port
            
        if not self.port:
            self.error_occurred.emit("No COM port selected.")
            return False
            
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            # Use UI-defined DTR and RTS states
            self.serial_conn.dtr = getattr(self, 'dtr_state', True)
            self.serial_conn.rts = getattr(self, 'rts_state', False)
            
            self.is_connected = True
            self.connection_status_changed.emit(True, self.port)
            
            # Start background polling thread
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"Connected to {self.port} at {self.baudrate} baud.")
            return True
            
        except serial.SerialException as e:
            self.is_connected = False
            self.connection_status_changed.emit(False, "")
            self.error_occurred.emit(f"Failed to connect to {self.port}: {str(e)}")
            logger.error(f"Serial connection error: {e}")
            return False

    def disconnect(self):
        self.is_connected = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            
        self.connection_status_changed.emit(False, "")
        logger.info("Disconnected from serial port.")

    def _read_loop(self):
        """
        Background loop reading data from the serial port.
        """
        buf = bytearray()
        while not self._stop_event.is_set():
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    n_avail = self.serial_conn.in_waiting
                    if n_avail > 0:
                        raw_chunk = self.serial_conn.read(n_avail)
                        buf.extend(raw_chunk)
                        
                        # Process all frames from the buffer
                        while len(buf) > 0:
                            # Frame Type 1: Samarth / Electronic DAQ frame: 0x55 ('U') ... 0x5D (']')
                            if buf[0] == 0x55:
                                end_idx = buf.find(b']')
                                if end_idx != -1:
                                    packet = bytes(buf[:end_idx + 1])
                                    del buf[:end_idx + 1]
                                    parsed_data = Protocol.decode_packet(packet)
                                    if parsed_data.get('type') == 'data':
                                        self.data_received.emit(parsed_data)
                                    continue
                                else:
                                    # Wait for end byte, but pop stray byte if buffer gets stuck
                                    if len(buf) > 100:
                                        buf.pop(0)
                                    break
                            
                            # Frame Type 2: Standard ASCII line ending in \n or \r
                            elif b'\n' in buf or b'\r' in buf:
                                nl_idx = -1
                                for idx, b in enumerate(buf):
                                    if b in (0x0A, 0x0D):
                                        nl_idx = idx
                                        break
                                line = bytes(buf[:nl_idx + 1])
                                del buf[:nl_idx + 1]
                                clean_line = line.strip()
                                if clean_line:
                                    parsed_data = Protocol.decode_packet(clean_line)
                                    if parsed_data.get('type') == 'data':
                                        self.data_received.emit(parsed_data)
                                continue
                                
                            else:
                                # Leading garbage: discard if buffer grows large
                                if len(buf) > 256:
                                    next_u = buf.find(b'U')
                                    next_nl = buf.find(b'\n')
                                    candidates = [i for i in [next_u, next_nl] if i > 0]
                                    if candidates:
                                        del buf[:min(candidates)]
                                    else:
                                        buf.clear()
                                break
                    else:
                        time.sleep(0.01)
                except serial.SerialException as e:
                    self.error_occurred.emit(f"Serial Read Error: {str(e)}")
                    self.disconnect()
                    break
            else:
                time.sleep(0.1)

    def send_command(self, command_type: str, payload: dict = None):
        if self.serial_conn and self.is_connected:
            try:
                packet = Protocol.encode_command(command_type, payload)
                self.serial_conn.write(packet)
                # Removed flush() because it causes UI freezing if the machine is offline
                logger.debug(f"Sent: {packet}")
            except serial.SerialException as e:
                self.error_occurred.emit(f"Serial Write Error: {str(e)}")
                self.disconnect()
