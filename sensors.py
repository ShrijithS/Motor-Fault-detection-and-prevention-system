import math


class Sensor:
    def __init__(self, field):
        self.field = field
        self.source = 'simulated'

    def read(self, readings, source='simulated'):
        self.source = source
        value = readings[self.field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid ' + self.field)
        return value


class CurrentSensor(Sensor):
    def __init__(self):
        super().__init__('current_a')


class TemperatureSensor(Sensor):
    def __init__(self):
        super().__init__('temperature_c')
