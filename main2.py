"""Standalone virtual motor. No Arduino, USB cable or physical motor needed."""
import argparse
from server import Simulation, run_application


def main():
    parser = argparse.ArgumentParser(description='VoltGuard standalone virtual motor simulation')
    parser.add_argument('--http-port', type=int, default=5000)
    args = parser.parse_args()
    print('STANDALONE SIMULATION MODE: virtual motor and virtual relay; no USB connection')
    run_application(Simulation(), args.http_port)


if __name__ == '__main__':
    main()
