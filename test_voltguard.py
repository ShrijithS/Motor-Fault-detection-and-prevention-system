"""Run with python -m unittest -v. No Arduino or energized relay required."""
import json
import unittest
from unittest.mock import Mock, patch
from server import Simulation, ArduinoMotorSystem, create_app
from arduino import ArduinoCommunication


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation()
        self.client = create_app(self.sim).test_client()

    def command(self, command, **kwargs):
        return self.client.post('/api/action', json=dict(command=command, **kwargs))

    def advance(self, seconds):
        for _ in range(int(seconds * 10)):
            self.sim.tick(0.1)

    def test_dashboard_and_contract(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="rotor"', response.data)
        response.close()
        state = self.client.get('/api/state').json
        self.assertFalse(state['connected'])
        self.assertEqual(state['mode'], 'simulation')
        for key in ('relay_on', 'current_a', 'temperature_c', 'sensor_valid',
                    'fault_latched', 'fault', 'history', 'messages'):
            self.assertIn(key, state)

    def test_normal_load_and_coasting(self):
        self.assertEqual(self.command('ON').status_code, 200)
        self.advance(8)
        normal = self.sim.state()
        self.assertGreater(normal['rpm'], 2500)
        self.assertGreater(normal['current_a'], 0)
        self.assertGreater(normal['temperature_c'], 25)
        self.command('LOAD', load=0.7)
        self.advance(8)
        loaded = self.sim.state()
        self.assertGreater(loaded['current_a'], normal['current_a'])
        self.assertLess(loaded['rpm'], normal['rpm'])
        self.command('OFF')
        self.assertEqual(self.sim.state()['current_a'], 0)
        self.assertGreater(self.sim.state()['rpm'], 0)
        self.advance(12)
        self.assertEqual(self.sim.state()['rpm'], 0)

    def test_faults_and_reset_interlocks(self):
        for command, reason in [('TESTI', 'OVERCURRENT'), ('TESTSC', 'SHORT CIRCUIT'),
                                ('TESTT', 'OVERHEATING')]:
            with self.subTest(command=command):
                self.setUp()
                self.command('ON')
                self.advance(5)
                self.command(command)
                self.advance(5)
                state = self.sim.state()
                self.assertTrue(state['fault_latched'])
                self.assertEqual(state['fault'], reason)
                self.assertFalse(state['relay_on'])
                self.assertEqual(self.command('ON').status_code, 400)
                self.assertEqual(self.command('RESET').status_code, 400)
                self.command('CLEAR')
                if command == 'TESTT':
                    self.assertEqual(self.command('RESET').status_code, 400)
                    self.advance(40)
                self.assertEqual(self.command('RESET').status_code, 200)
                self.assertFalse(self.sim.state()['relay_on'])
                self.assertEqual(self.command('ON').status_code, 200)

    def test_short_sample_and_validation(self):
        self.command('ON')
        self.command('TESTSC')
        self.advance(0.1)
        self.assertEqual(self.sim.history[-1]['a'], 15)
        for payload in (None, [], {}, {'command': 3}, {'command': 'bad'}):
            self.assertEqual(self.client.post('/api/action', json=payload).status_code, 400)
        for load in (-1, 2, 'heavy', True):
            self.assertEqual(self.command('LOAD', load=load).status_code, 400)
        self.assertEqual(self.client.post('/api/action', json={'command': 'ON'},
                                         headers={'Origin': 'http://evil.example'}).status_code, 403)

    def test_simulation_never_opens_usb(self):
        with patch('arduino.serial.Serial') as port:
            sim = Simulation()
            sim.action('ON', {})
            sim.tick(0.1)
            self.assertFalse(sim.state()['connected'])
            self.assertFalse(hasattr(sim, 'arduino'))
            port.assert_not_called()

    def test_hardware_uses_actual_readings_and_confirmation(self):
        import time
        system = ArduinoMotorSystem('MOCK')
        client = create_app(system).test_client()
        board = system.arduino
        board.serial = Mock()
        board.serial.in_waiting = 0
        board.serial.read.return_value = b''
        board.serial.write.side_effect = lambda message: len(message)
        board.last_received = time.monotonic()
        board.telemetry = dict(relay_on=False, fault_latched=False, sensor_valid=True,
                               fault='NONE', current_a=0.06, temperature_c=31.5)
        system.tick(0.1)
        self.assertFalse(hasattr(system, 'motor'))
        self.assertEqual(system.state()['temperature_c'], 31.5)
        self.assertIsNone(system.state()['rpm'])
        self.assertEqual(client.post('/api/action', json={'command':'ON'}).status_code, 200)
        self.assertFalse(system.state()['relay_on'])
        board.telemetry['relay_on'] = True
        system.tick(0.1)
        self.assertTrue(system.state()['relay_on'])
        board.telemetry.update(relay_on=False, fault_latched=True, fault='OVERCURRENT')
        system.tick(0.1)
        self.assertTrue(system.state()['fault_latched'])
        self.assertEqual(client.post('/api/action', json={'command':'ON'}).status_code, 400)
        system.action('RESET', {})
        self.assertTrue(system.state()['fault_latched'])
        board.telemetry.update(fault_latched=False, fault='NONE')
        self.assertFalse(system.state()['fault_latched'])
        for call in board.serial.write.call_args_list:
            self.assertEqual(json.loads(call.args[0])['type'], 'command')
        board.last_received = 0
        system.tick(0.1)
        self.assertFalse(system.state()['connected'])
        self.assertIsNone(system.state()['current_a'])
        self.assertEqual(client.post('/api/action', json={'command':'ON'}).status_code, 400)

    def test_hardware_rejects_simulation_controls_and_write_failure(self):
        import time
        system = ArduinoMotorSystem('MOCK')
        for command in ('TESTI','TESTT','TESTSC','TESTS','CLEAR','LOAD'):
            with self.assertRaises(ValueError):
                system.action(command, {})
        system.arduino.serial = Mock()
        system.arduino.last_received = time.monotonic()
        system.arduino.telemetry = dict(relay_on=False, fault_latched=False, sensor_valid=True)
        system.arduino.serial.write.return_value = 0
        with self.assertRaises(ValueError):
            system.action('ON', {})
        self.assertFalse(system.arduino.is_connected())

    def test_bad_serial_is_reported(self):
        board = ArduinoCommunication()
        board.serial = Mock()
        board.serial.in_waiting = 100
        board.serial.read.return_value = b'not JSON\n'
        board.poll()
        self.assertFalse(board.is_connected())
        self.assertIn('Serial protocol', board.error)
        data = dict(protocol='voltguard-hardware-v1', mode='hardware', relay_on=True,
                    fault_latched=True, sensor_valid=True, fault='SHORT CIRCUIT')
        board.serial.read.return_value = (json.dumps(data) + '\n').encode()
        board.poll()
        self.assertIn('Unsafe', board.error)

    def test_hardware_protocol_requires_real_finite_readings(self):
        board = ArduinoCommunication()
        board.serial = Mock()
        board.serial.in_waiting = 1000
        valid = dict(protocol='voltguard-hardware-v1', mode='hardware', relay_on=False,
                     fault_latched=False, sensor_valid=True, fault='NONE',
                     current_a=0.2, temperature_c=27.8)
        for changes in ({'mode':'simulation'}, {'current_a':None}, {'temperature_c':float('nan')},
                        {'rpm':-1}, {'current_a':True}):
            board.serial.read.return_value = (json.dumps(dict(valid, **changes))+'\n').encode()
            board.poll()
            self.assertFalse(board.is_connected())
        board.serial.read.return_value = (json.dumps(valid)+'\n').encode()
        board.poll()
        self.assertTrue(board.is_connected())


if __name__ == '__main__':
    unittest.main()
