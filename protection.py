from datetime import datetime
from faults import OverCurrentFault, ShortCircuitFault, OverHeatingFault
from sensors import CurrentSensor, TemperatureSensor


class MotorProtectionSystem:
    def __init__(self, motor):
        self.motor = motor
        # The explicit short detector takes priority over overcurrent.
        self.faults = [ShortCircuitFault(), OverCurrentFault(), OverHeatingFault()]
        self.current_sensor = CurrentSensor()
        self.temperature_sensor = TemperatureSensor()
        self.fault_latched = False
        self.fault = 'NONE'
        self.history = []

    def record(self, message):
        self.history.append(dict(time=datetime.now().isoformat(timespec='seconds'), message=message))
        self.history = self.history[-100:]

    def active_fault(self):
        readings = self.motor.status()
        self.current_sensor.read(readings)
        self.temperature_sensor.read(readings)
        for fault in self.faults:
            if fault.detect(readings):
                return fault.name
        # Injection remains unsafe even after opening the relay drops current.
        if readings['injected_fault']:
            return readings['injected_fault'].upper()
        if readings['load'] > 0.9:
            return 'EXCESSIVE LOAD'
        return None

    def trip(self, reason):
        if not self.fault_latched or self.fault != reason:
            self.record('TRIPPED: ' + reason)
        self.fault_latched = True
        self.fault = reason
        self.motor.stop()

    def monitor(self):
        reason = self.active_fault()
        if reason:
            self.trip(reason)
        if self.fault_latched:
            self.motor.stop()

    def start(self):
        if self.fault_latched or self.active_fault():
            raise ValueError('Clear the condition and reset protection before starting')
        self.motor.start()
        self.record('Motor ON')

    def stop(self):
        self.motor.stop()
        self.record('Motor OFF')

    def reset(self):
        if self.active_fault():
            raise ValueError('Fault still active; CLEAR injection and wait for temperature below 45 C')
        self.fault_latched = False
        self.fault = 'NONE'
        self.motor.stop()
        self.record('Protection reset; motor remains OFF')
