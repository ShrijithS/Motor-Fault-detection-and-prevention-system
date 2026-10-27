"""One small simulation loop; Flask requests share its state through a lock."""
import logging
import math
import threading
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from motor import DCMotor
from protection import MotorProtectionSystem
from arduino import ArduinoCommunication


class Simulation:
    """Standalone virtual motor: never opens or writes to a USB port."""
    def __init__(self):
        self.motor = DCMotor()
        self.protection = MotorProtectionSystem(self.motor)
        self.lock = threading.Lock()
        self.history = []
        self.stopped = threading.Event()
        self.last_error = ''

    def tick(self, dt):
        self.motor.update(dt)
        sample = self.motor.status()
        self.history.append(dict(t=time.time(), a=sample['current_a']))
        self.history = self.history[-100:]
        self.protection.monitor()

    def handle_error(self, exc):
        self.last_error = str(exc)
        self.protection.trip('APPLICATION ERROR')

    def state(self):
        values = self.motor.status()
        return dict(**values, connected=False, relay_on=values['running'],
                    sensor_valid=True, fault_latched=self.protection.fault_latched,
                    fault=self.protection.fault, history=list(self.history),
                    messages=list(reversed(self.protection.history)),
                    mode='simulation', source='simulated', error=self.last_error)

    def action(self, command, data):
        if command == 'CLEAR':
            self.motor.clear_fault()
            self.protection.record('Injected fault cleared; cooling continues')
            return 'Injection cleared. Wait for safe temperature, then RESET.'
        if command == 'LOAD':
            value = data.get('load')
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('load must be a finite number between 0 and 1')
            self.motor.apply_load(value)
            return 'Mechanical load updated'
        if command == 'ON':
            self.protection.start()
        elif command == 'OFF':
            self.protection.stop()
        elif command == 'RESET':
            self.protection.reset()
        elif command == 'TESTS':
            self.protection.trip('SENSOR INVALID (TEST)')
        elif command in ('TESTI', 'TESTT', 'TESTSC'):
            fault = dict(TESTI='overcurrent', TESTT='overheating', TESTSC='short_circuit')[command]
            self.motor.inject_fault(fault)
        else:
            raise ValueError('Unknown command')
        return 'Command accepted'


class ArduinoMotorSystem:
    """Real motor mode: all displayed measurements come from the board."""
    def __init__(self, port, baud=115200):
        self.arduino = ArduinoCommunication(port, baud)
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.history = []
        self.messages = []
        self.last_error = ''
        self.last_status = None
        self.last_sample = 0

    def record(self, message):
        self.messages.append(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'), message=message))
        self.messages = self.messages[-100:]

    def tick(self, dt):
        self.arduino.poll()
        if not self.arduino.is_connected():
            if self.last_status is not None:
                self.record('Arduino telemetry lost; physical relay state unknown')
            self.last_status = None
            return
        board = self.arduino.telemetry
        status = (board['relay_on'], board['fault_latched'], board['fault'], board['sensor_valid'])
        if status != self.last_status:
            self.record('Arduino: ' + ('TRIPPED: ' + board['fault'] if board['fault_latched']
                                      else 'relay ON' if board['relay_on'] else 'relay OFF'))
            self.last_status = status
        if self.last_sample != self.arduino.last_received:
            self.history.append(dict(t=time.time(), a=board['current_a']))
            self.history = self.history[-100:]
            self.last_sample = self.arduino.last_received

    def handle_error(self, exc):
        self.last_error = str(exc)
        self.arduino.send_command('OFF')
        self.arduino.telemetry = None
        self.record('Application error; OFF requested, verify hardware independently')

    def state(self):
        online = self.arduino.is_connected()
        board = self.arduino.telemetry if online else {}
        return dict(connected=online, relay_on=board.get('relay_on', False),
                    current_a=board.get('current_a'), temperature_c=board.get('temperature_c'),
                    rpm=board.get('rpm'), sensor_valid=board.get('sensor_valid', False),
                    fault_latched=board.get('fault_latched', False), fault=board.get('fault', 'UNKNOWN'),
                    history=list(self.history), messages=list(reversed(self.messages)),
                    mode='hardware', source='arduino', error=self.last_error or self.arduino.error)

    def action(self, command, data):
        # Simulation injections never reach a real motor.
        if command not in ('ON', 'OFF', 'RESET'):
            raise ValueError('Fault injection and simulated load controls are available only in main2.py')
        if not self.arduino.is_connected():
            raise ValueError('Compatible Arduino hardware telemetry unavailable')
        board = self.arduino.telemetry
        if command == 'ON' and (board['fault_latched'] or not board['sensor_valid']):
            raise ValueError('Arduino reports a fault or invalid sensors; clear the physical cause first')
        if command == 'RESET' and board['relay_on']:
            raise ValueError('Turn the motor OFF before requesting reset')
        if not self.arduino.send_command(command):
            raise ValueError('Serial write failed; command was not confirmed')
        self.record(command + ' requested; awaiting Arduino telemetry')
        return command + ' requested; Arduino must confirm relay and protection state'


def run_application(system, http_port):
    """Shared web startup; each system supplies its own tick/state/action methods."""
    def update_loop():
        previous = time.monotonic()
        while not system.stopped.wait(0.1):
            now = time.monotonic()
            with system.lock:
                try:
                    system.tick(min(now - previous, 0.5))
                except Exception as exc:
                    logging.exception('VoltGuard update failed')
                    system.handle_error(exc)
            previous = now

    worker = threading.Thread(target=update_loop, daemon=True)
    worker.start()
    print('Open http://127.0.0.1:' + str(http_port))
    try:
        create_app(system).run(host='127.0.0.1', port=http_port, debug=False, use_reloader=False)
    finally:
        system.stopped.set()
        worker.join(timeout=2)
        if isinstance(system, ArduinoMotorSystem):
            system.arduino.send_command('OFF')
            system.arduino.close()


def create_app(simulation):
    app = Flask(__name__)

    @app.get('/')
    def dashboard():
        return send_file(Path(__file__).with_name('index.html'))

    @app.get('/api/state')
    def state():
        with simulation.lock:
            return jsonify(simulation.state())

    @app.post('/api/action')
    def action():
        # Reject browser requests originating from another website.
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            return jsonify(error='Cross-origin control is disabled'), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('command'), str):
            return jsonify(error='Expected JSON object with a command string'), 400
        with simulation.lock:
            try:
                return jsonify(note=simulation.action(data['command'].upper(), data))
            except ValueError as exc:
                return jsonify(error=str(exc)), 400

    return app
