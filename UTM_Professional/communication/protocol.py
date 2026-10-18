import re
import struct
import logging

logger = logging.getLogger(__name__)

class Protocol:
    """
    Robust Universal Testing Machine Protocol Layer.
    Parses incoming serial streams (ASCII, CSV, Fixed-Frame, and Binary 0x55...0x5D).
    """
    
    # Internal tracking for single-value alternating streams
    _last_load = 0.0
    _last_ext = 0.0
    _packet_count = 0

    @staticmethod
    def encode_command(command_type: str, payload: dict = None) -> bytes:
        """Encodes commands for the serial connection."""
        cmd = f"CMD:{command_type}"
        if payload:
            cmd += f"|{payload}"
        cmd += "\r\n"
        return cmd.encode('ascii')

    @classmethod
    def decode_packet(cls, packet: bytes) -> dict:
        """
        Decodes raw byte packets from RS-232 into structured data dicts.
        Handles:
        1. Formatted strings: 'DATA:LOAD=12.5,EXT=3.2'
        2. Framed binary/hex (0x55 ... 0x5D)
        3. Plain ASCII numbers (single or multi-column)
        """
        if not packet:
            return {'type': 'empty'}

        try:
            # 1. Check for Standard Key-Value format
            decoded_ascii = packet.decode('ascii', errors='ignore').strip()
            
            if decoded_ascii.startswith("DATA:"):
                parts = decoded_ascii[5:].split(',')
                result = {'type': 'data', 'LOAD': cls._last_load, 'EXT': cls._last_ext}
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        if k in ['LOAD', 'EXT', 'POS']:
                            result[k] = float(v)
                cls._last_load = result.get('LOAD', cls._last_load)
                cls._last_ext = result.get('EXT', cls._last_ext)
                return result

            if decoded_ascii.startswith("ACK") or decoded_ascii == "OK":
                return {'type': 'ack'}

            # 2. Check for 10-byte Frame: 0x55 ('U') ... 0x5D (']')
            if len(packet) >= 4 and (packet[0] == 0x55 or packet[-1] == 0x5D):
                # Check for binary integer payload in bytes 2..6
                if len(packet) >= 10:
                    try:
                        # Extract 16-bit or 32-bit values from payload
                        val1 = struct.unpack('<H', packet[2:4])[0]
                        val2 = struct.unpack('<H', packet[4:6])[0]
                        if val1 > 0 or val2 > 0:
                            cls._last_load = float(val1)
                            cls._last_ext = float(val2) / 100.0
                            return {
                                'type': 'data',
                                'LOAD': cls._last_load,
                                'EXT': cls._last_ext,
                                'raw': packet.hex()
                            }
                    except Exception:
                        pass

            # 3. Universal Number Extraction (ASCII digits / decimals)
            numbers = re.findall(r"[-+]?\d*\.?\d+", decoded_ascii)
            if len(numbers) >= 2:
                # 2 or more numbers found: First is Load, Second is Extension
                cls._last_load = float(numbers[0])
                cls._last_ext = float(numbers[1])
                return {
                    'type': 'data',
                    'LOAD': cls._last_load,
                    'EXT': cls._last_ext,
                    'raw': decoded_ascii
                }
            elif len(numbers) == 1:
                # 1 number found: Treat as live reading
                val = float(numbers[0])
                cls._packet_count += 1
                cls._last_load = val
                return {
                    'type': 'data',
                    'LOAD': cls._last_load,
                    'EXT': cls._last_ext,
                    'raw': decoded_ascii
                }

            # 4. Binary Fallback: if non-empty, try raw integer extraction
            if len(packet) >= 2:
                raw_int = int.from_bytes(packet[1:3], byteorder='little')
                if raw_int > 0:
                    cls._last_load = float(raw_int)
                    return {
                        'type': 'data',
                        'LOAD': cls._last_load,
                        'EXT': cls._last_ext,
                        'raw': packet.hex()
                    }

            return {'type': 'unknown', 'raw': decoded_ascii}

        except Exception as e:
            logger.debug(f"Protocol decode error: {e}")
            return {'type': 'error', 'message': str(e)}

    @staticmethod
    def calculate_checksum(data: bytes) -> int:
        return sum(data) % 256
