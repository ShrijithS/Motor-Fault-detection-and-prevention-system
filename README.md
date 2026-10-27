# VOLTGUARD — two independent startup files

## Choose the program

| Run | Purpose | USB needed? | Readings / relay authority |
| --- | --- | --- | --- |
| `python main.py --port COM11` | Real DC motor connected through Arduino | Yes | Arduino sensors and Arduino relay protection |
| `python main2.py` | Standalone virtual motor | No | Python motor model and virtual relay |

Both serve the existing dashboard at http://127.0.0.1:5000. Run one at a time, or give them different `--http-port` values. Do not open index.html directly. Ctrl+C stops the chosen server.

Install the two required dependencies using Python 3.10 or newer:

```powershell
python -m pip install -r requirements.txt
```

### main.py — real motor / Arduino

```powershell
python main.py --port COM11 --baud 115200
```

COM11 and 115200 are defaults. This program opens USB, receives actual current/temperature, reads board fault and relay status, and sends ON/OFF/RESET requests. It does not instantiate a virtual motor, calculate synthetic readings or send simulated sensor samples. Arduino remains responsible for independently checking sensors, latching faults and opening the relay. A successful command response means a request was written; the dashboard waits for fresh board telemetry before changing relay/fault state.

Missing or invalid telemetry displays disconnection and unknown physical relay state, with no substituted readings. Simulation controls are disabled and also rejected by the API. Reset is a request to Arduino, never a local bypass. Without a shaft sensor, RPM is shown as NOT MEASURED; the existing rotor is only a relay-status illustration. Even with optional RPM telemetry, the physical relay contacts are not independently verified.

**Firmware is still required:** the supplied `VoltGuard_Simple_ON_OFF.ino` contains an incomplete, unrelated smart-dustbin program with conflicting pins and syntax errors. It is preserved unchanged. Do not upload it for VoltGuard. This Python hardware path implements the proposed contract in ARDUINO_PROTOCOL.md; it cannot operate that unrelated sketch. Real motor, sensor calibration, Arduino protection and physical relay behavior have not been tested.

### main2.py — standalone simulation

```powershell
python main2.py
```

No Arduino, USB cable, power supply or physical motor is needed. This program never opens a serial port. The dashboard says SIMULATION MODE and ARDUINO DISCONNECTED. Startup and reset leave its virtual relay OFF. To use another web port:

```powershell
python main2.py --http-port 5056
```

Open http://127.0.0.1:5056 for that command. The previous optional Arduino-connected virtual-motor mode has been replaced by the two programs above.

## What the files do / OOP viva explanation

| File | Responsibility |
| --- | --- |
| main.py | Real-motor startup, USB port and baud options. |
| main2.py | USB-free virtual-motor startup. |
| motor.py | DCMotor encapsulates simulated RPM, current, temperature and load. |
| sensors.py | Sensor parent and current/temperature subclasses; readings have a source label. |
| faults.py | MotorFault parent with OverCurrentFault, ShortCircuitFault and OverHeatingFault children. |
| protection.py | Contains motor, sensors and fault objects; monitors conditions, stops motor, latches and logs faults. |
| arduino.py | Validates measured serial telemetry and sends real-motor control requests. |
| server.py | Separate Simulation and ArduinoMotorSystem classes sharing the same Flask endpoints and small update-loop function. |
| test_voltguard.py | Motor, protection, API, USB isolation and mocked hardware tests. |

Encapsulation: motor state belongs to DCMotor; use methods instead of changing underscore-prefixed internal variables. Inheritance: fault subclasses inherit from MotorFault. Method overriding: each provides its own detect(). Polymorphism: protection loops over different fault objects and calls detect() in the same way. Abstraction: callers use start(), stop(), monitor() and status() without knowing the equations. Composition: MotorProtectionSystem contains the motor, sensors and fault list. The two server-system classes also provide the same state/action/tick interface for the shared dashboard.

There is one 0.1-second update thread with a lock around shared state; the browser polls every 0.6 seconds. Unexpected update errors are logged with a traceback. Simulation latches an application fault; hardware mode requests OFF and invalidates telemetry. A failed USB link cannot guarantee the physical relay opened, so independent board protection remains essential. History is bounded and stored in memory.

## Virtual motor equations (main2.py only)

This is an educational model, not a calibrated physical prediction. Configurable defaults in DCMotor.__init__ include 12 V, 3000 RPM, 12 ohm armature resistance, 25 C ambient, 1 second speed time constant, 18 J/C thermal capacity and 0.18 W/C cooling. Normal mechanical load is 0.15 on a 0–1 scale.

* Target RPM = rated RPM × (1 − speed_load_factor × load), with speed_load_factor = 0.65. Target is zero when OFF.
* Speed approaches target each step by the fraction `1 − exp(−dt / time_constant)`. This creates gradual acceleration and coasting.
* Back EMF = back_emf_factor × voltage × RPM / rated RPM, with back_emf_factor = 0.85.
* Powered current = `(voltage − back_emf) / resistance + load_current_factor × load`, with load_current_factor = 0.8. This empirical load term is a teaching approximation.
* Copper heating = current² × resistance. Temperature change = `(copper heating − cooling × (temperature − ambient)) × dt / thermal_capacity`.

Higher load reduces speed and raises current. Relay OFF makes current zero immediately, while RPM coasts down. Normal operation settles near 2708 RPM and 0.35 A. The graphic runs at 1/12 of model speed for visibility; its RPM display shows the model value.

## Simulation demonstration

1. Run main2.py. Show the simulation label and OFF relay. TURN ON: watch RPM increase, current settle and temperature change gradually. TURN OFF: current becomes zero and speed decays.
2. Start again and click TEST I. The excessive-load injection eventually pushes current over 1.4 A. Protection trips, opens the virtual relay and records OVERCURRENT.
3. Restart and RESET are blocked while the injection remains. CLEAR FAULT removes the cause; RESET clears the latch and keeps motor OFF. TURN ON is a separate step.
4. Repeat with TEST SHORT. This explicitly injects a low-resistance path (default 0.8 ohm = 15 A at 12 V) and trips on the next 0.1-second step. A current threshold alone is not claimed to identify a physical short.
5. Repeat with TEST T. Temperature is raised to 50 C; the 45 C protection trips. CLEAR removes the injection but does not instantly cool the motor. Wait for below 45 C, then RESET and restart.
6. TEST SENSOR is a separate one-shot simulated sensor failure. RESET clears this test latch.

The graph stores pre-trip samples so a brief fault spike remains visible after present current becomes zero. The first fault remains latched until safe reset. You can apply a moderate load through the API while simulating:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/action -Method Post -ContentType application/json -Body '{"command":"LOAD","load":0.7}'
```

LOAD accepts finite values between 0 and 1. Load above 0.9 blocks restart until lowered; CLEAR restores normal load. Excessive load and injected faults are simulation demonstrations only.

## API compatibility

GET /api/state retains connected, relay_on, current_a, temperature_c, sensor_valid, fault_latched, fault, history and messages. Added fields include mode (`hardware` or `simulation`), source (`arduino` or `simulated`), rpm and error. Hardware disconnected readings are null; physical relay state is unknown even though relay_on is false for the inactive display. Never infer physical safety from stale or absent telemetry.

POST /api/action takes `{ "command": "ON" }` and returns `{ "note": "..." }` or HTTP 400 with `{ "error": "..." }`. Simulation accepts ON/OFF/RESET/TESTI/TESTT/TESTS/TESTSC/CLEAR/LOAD. Hardware accepts ON/OFF/RESET only. Both bind to 127.0.0.1 and reject cross-origin browser control.

## Verification

```powershell
python -m unittest -v
```

Nine tests cover the model, all three faults, cooldown/reset/restart, API validation, no USB access in simulation, actual hardware-reading passthrough, confirmed relay/fault state, rejected simulation commands, serial write failure, disconnects, incompatible modes and invalid numeric telemetry. Arduino tests use mocks; no physical hardware has been verified. Firmware, wiring and independently tested protection are prerequisites for a real motor demonstration.
