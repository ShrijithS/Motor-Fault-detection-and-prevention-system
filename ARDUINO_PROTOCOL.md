# Proposed real-motor USB protocol for main.py

The supplied .ino is an unrelated, incomplete smart-dustbin program and does not support this protocol. It is unchanged. The correct VoltGuard firmware, sensor calibration and LCD wiring must be supplied before physical integration can be completed. This document defines the Python adapter contract; no physical relay/motor test has been performed.

main2.py never uses serial communication. The former voltguard-sim-v1 protocol is no longer used by either startup program.

## Serial format

Configurable COM port (default COM11), 115200 baud by default, 8N1. One ASCII JSON object per line followed by newline. Python polls at 0.1 second intervals; firmware should transmit complete status at least every 500 ms. Python marks status disconnected after 2 seconds without valid telemetry. Maximum received line is 8192 bytes; Uno firmware should use much smaller bounded buffers and reject oversized/malformed commands.

## Arduino → Python: real measured telemetry

```json
{"protocol":"voltguard-hardware-v1","mode":"hardware","relay_on":false,"fault_latched":false,"fault":"NONE","sensor_valid":true,"current_a":0.02,"temperature_c":27.5}
```

All fields shown are required. Boolean fields must contain JSON booleans. current_a and temperature_c must be finite JSON numbers from actual sensors, not Python calculations. Sensor validity is determined independently by the board; never substitute simulated values in hardware mode. fault is a string such as NONE, OVERCURRENT, OVERHEATING or SENSOR INVALID. Do not label every high-current reading as a uniquely identified physical short.

Optional `rpm` must be a finite nonnegative number from an actual shaft sensor, or null/omitted if no RPM sensor is available. The specified ACS712 and LM35 do not measure RPM. The dashboard says RPM NOT MEASURED when absent and uses its rotor only as an illustrative relay indicator.

Python rejects relay_on=true together with fault_latched=true or sensor_valid=false. Rejected or stale status makes physical relay state unknown; the dashboard never treats this as confirmed physical shutdown. Fault thresholds/calibration belong to board firmware and are not the virtual motor's demo settings.

## Python → Arduino: requests only

```json
{"type":"command","protocol":"voltguard-hardware-v1","command":"ON"}
```

Only ON, OFF and RESET are sent. These names preserve the intended operator actions; the JSON envelope is proposed because the correct sketch is missing. Adapt the Python transport to a verified existing VoltGuard protocol if that sketch is recovered. Python sends no sensor sample packets in hardware mode.

* ON: board checks independent sensor validity, active abnormal conditions and its fault latch before energizing the relay. Reject unsafe requests.
* OFF: open the relay, then report its new commanded state. This reports output logic, not measured contact continuity.
* RESET: only clear the latch after the real cause is removed and sensors are safe. Leave relay OFF. No auto-start on reset.

The dashboard changes relay and latch status only from subsequent valid telemetry. Sending RESET does not clear Python's display independently of the board. Simulation test/load/clear commands are rejected by the hardware API, so no synthetic fault is applied to a real motor.

## Firmware and wiring requirements before use

* Current sensor A0, LM35 A1, active-LOW relay D7, buzzer D8. Preserve the correct existing LCD pin configuration once verified; the supplied sketch cannot establish it.
* Boot safely with relay D7 HIGH/OFF before enabling output, and buzzer OFF. No automatic start after USB reset, power restoration or fault reset. Opening a Uno USB port can reset the board; verify boot behavior with motor power disconnected first.
* Read sensors and perform independent emergency protection on the Uno even if Python freezes or USB disconnects. Do not disable safety checks to make the dashboard run.
* Provide a firmware communication timeout policy that opens the relay on host loss. Python cannot physically open a relay through a broken USB link. If using a host heartbeat, define and implement it at both ends before relying on it; this adapter currently sends operator commands only and must not be assumed to provide a heartbeat.
* Verify calibration, relay polarity, safe thresholds, boot OFF, fault OFF and reset-to-OFF with motor power disconnected before attempting powered motor operation. Preserve independent fuse/current limiting as appropriate for the actual circuit.

No firmware replacement is included because a correct sketch and LCD wiring are unavailable. Real-hardware mode is a prepared Python interface, not a claim of tested physical protection.
