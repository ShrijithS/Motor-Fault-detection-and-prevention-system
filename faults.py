"""Fault objects share one interface, with different detection rules."""


class MotorFault:
    def __init__(self, name):
        self.name = name

    def detect(self, readings):
        raise NotImplementedError('Subclasses implement detect')


class OverCurrentFault(MotorFault):
    def __init__(self, threshold=1.4):
        super().__init__('OVERCURRENT')
        self.threshold = threshold

    def detect(self, readings):
        return readings['current_a'] > self.threshold


class ShortCircuitFault(MotorFault):
    def __init__(self):
        super().__init__('SHORT CIRCUIT')

    def detect(self, readings):
        return readings['injected_fault'] == 'short_circuit'


class OverHeatingFault(MotorFault):
    def __init__(self, threshold=45.0):
        super().__init__('OVERHEATING')
        self.threshold = threshold

    def detect(self, readings):
        return readings['temperature_c'] >= self.threshold
