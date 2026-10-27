import math


class DCMotor:
    def __init__(self, voltage=12.0, rated_rpm=3000.0, resistance=12.0,
                 ambient_c=25.0, time_constant=1.0, thermal_capacity=18.0,
                 cooling=0.18, speed_load_factor=0.65, back_emf_factor=0.85,
                 load_current_factor=0.8, short_resistance=0.8, test_temperature=50.0):
        self.voltage = voltage
        self.rated_rpm = rated_rpm
        self.resistance = resistance
        self.ambient_c = ambient_c
        self.time_constant = time_constant
        self.thermal_capacity = thermal_capacity
        self.cooling = cooling
        self.speed_load_factor = speed_load_factor
        self.back_emf_factor = back_emf_factor
        self.load_current_factor = load_current_factor
        self.short_resistance = short_resistance
        self.test_temperature = test_temperature
        self._running = False
        self._rpm = 0.0
        self._temperature = ambient_c
        self._current = 0.0
        self._load = 0.15
        self.injected_fault = None

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
        self._current = 0.0

    def apply_load(self, load):
        if not 0 <= load <= 1:
            raise ValueError('Load must be between 0 and 1')
        self._load = float(load)

    def inject_fault(self, fault):
        self.injected_fault = fault
        if fault == 'overheating':
            self._temperature = self.test_temperature

    def clear_fault(self):
        # Removing the heater/short/load does not instantly cool the motor.
        self.injected_fault = None
        self.apply_load(0.15)

    def update_rpm(self, dt):
        load = 1.0 if self.injected_fault == 'overcurrent' else self._load
        target = self.rated_rpm * (1 - self.speed_load_factor * load) if self._running else 0
        self._rpm += (target - self._rpm) * (1 - math.exp(-dt / self.time_constant))
        if self._rpm < 0.5:
            self._rpm = 0.0

    def calculate_current(self):
        if not self._running:
            return 0.0
        if self.injected_fault == 'short_circuit':
            return self.voltage / self.short_resistance  # Explicit low resistance path.
        # Back EMF increases with RPM; higher load lowers RPM and raises current.
        back_emf = self.back_emf_factor * self.voltage * self._rpm / self.rated_rpm
        load = 1.0 if self.injected_fault == 'overcurrent' else self._load
        return max(0.0, (self.voltage - back_emf) / self.resistance + self.load_current_factor * load)

    def update_temperature(self, dt):
        copper_loss = self._current ** 2 * self.resistance
        heat_out = self.cooling * (self._temperature - self.ambient_c)
        self._temperature += (copper_loss - heat_out) * dt / self.thermal_capacity

    def update(self, dt):
        self.update_rpm(dt)
        self._current = self.calculate_current()
        self.update_temperature(dt)

    def status(self):
        return dict(rpm=round(self._rpm, 1), current_a=round(self._current, 3),
                    temperature_c=round(self._temperature, 2), load=self._load,
                    running=self._running, injected_fault=self.injected_fault)
