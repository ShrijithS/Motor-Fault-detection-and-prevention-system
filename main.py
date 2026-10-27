"""Real motor connected to Arduino. Run main2.py for USB-free simulation."""
import argparse
from server import ArduinoMotorSystem, run_application


def main():
    parser = argparse.ArgumentParser(description='VoltGuard REAL MOTOR / Arduino mode')
    parser.add_argument('--port', default='COM11', help='Arduino serial port (default COM11)')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--http-port', type=int, default=5000)
    args = parser.parse_args()
    system = ArduinoMotorSystem(args.port, args.baud)
    system.arduino.connect()
    print('REAL MOTOR MODE: Arduino readings and relay authority; compatible firmware required')
    if system.arduino.error:
        print('Arduino connection: ' + system.arduino.error)
    run_application(system, args.http_port)


if __name__ == '__main__':
    main()
