"""Opt-in adapter for the PROPOSED VoltGuard real-hardware protocol."""
import json
import math
import time
import serial


class ArduinoCommunication:
    def __init__(self, port=None, baud=115200):
        self.port = port
        self.baud = baud
        self.serial = None
        self.telemetry = None
        self.last_received = 0.0
        self.buffer = b''
        self.error = ''

    def connect(self):
        if not self.port:
            return
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=0, write_timeout=0.2)
        except (serial.SerialException, OSError) as exc:
            self.error = str(exc)

    def is_connected(self):
        return self.serial is not None and self.telemetry is not None and time.monotonic() - self.last_received < 2

    def close(self):
        if self.serial:
            self.serial.close()
        self.serial = None
        self.telemetry = None

    def send(self, payload):
        if not self.serial:
            self.error = 'Serial port is not open'
            return False
        try:
            message = (json.dumps(payload) + '\n').encode('ascii')
            if self.serial.write(message) != len(message):
                raise serial.SerialException('Incomplete serial write')
            return True
        except (serial.SerialException, OSError) as exc:
            self.error = str(exc)
            self.close()
            return False

    def send_command(self, command):
        return self.send(dict(type='command', command=command, protocol='voltguard-hardware-v1'))

    def poll(self):
        if not self.serial:
            return
        try:
            self.buffer += self.serial.read(min(self.serial.in_waiting, 4096))
            if len(self.buffer) > 8192:
                self.buffer = b''
                raise ValueError('Serial line too long')
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise ValueError('Telemetry must be an object')
                if data.get('protocol') != 'voltguard-hardware-v1' or data.get('mode') != 'hardware':
                    raise ValueError('Incompatible firmware or mode')
                for key in ('relay_on', 'fault_latched', 'sensor_valid'):
                    if type(data.get(key)) is not bool:
                        raise ValueError('Invalid telemetry field: ' + key)
                if not isinstance(data.get('fault'), str):
                    raise ValueError('Invalid fault field')
                if data['relay_on'] and (data['fault_latched'] or not data['sensor_valid']):
                    raise ValueError('Unsafe relay telemetry')
                for key in ('current_a', 'temperature_c'):
                    value = data.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('Invalid measured field: ' + key)
                rpm = data.get('rpm')
                if rpm is not None and (type(rpm) not in (int, float) or not math.isfinite(rpm) or rpm < 0):
                    raise ValueError('Invalid measured RPM')
                self.telemetry = data
                self.last_received = time.monotonic()
                self.error = ''
        except (ValueError, UnicodeError) as exc:
            self.error = 'Serial protocol: ' + str(exc)
            self.telemetry = None
        except (serial.SerialException, OSError) as exc:
            self.error = str(exc)
            self.close()
