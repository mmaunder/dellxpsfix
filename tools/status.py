#!/usr/bin/env python3
"""Check the running service and idle counters; emit no personal machine IDs."""
import argparse
import json
import subprocess

from idle_probe import measure, seconds_value

UNIT = 'dellfix-idle-guard.service'
PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'UnitFileState',
              'NRestarts', 'MainPID', 'ActiveEnterTimestampMonotonic')


def query_service():
    command = ['systemctl', 'show', UNIT]
    for prop in PROPERTIES:
        command += ['-p', prop]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ValueError('systemctl could not query the guard service')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def assess(before, after, measurement):
    def running(unit):
        return (unit.get('LoadState') == 'loaded' and unit.get('ActiveState') == 'active'
                and unit.get('SubState') == 'running'
                and unit.get('MainPID') not in (None, '', '0'))
    stable = (running(before) and running(after)
              and before['MainPID'] == after['MainPID']
              and before.get('ActiveEnterTimestampMonotonic') not in (None, '', '0')
              and before['ActiveEnterTimestampMonotonic'] == after.get('ActiveEnterTimestampMonotonic'))
    enabled = after.get('UnitFileState') == 'enabled'
    return {'service': {key: after.get(key, 'unknown') for key in
                        ('ActiveState', 'SubState', 'UnitFileState', 'NRestarts')},
            'service_stable_during_measurement': stable,
            'measurement': measurement,
            'verification_passed': bool(stable and enabled and measurement['guard_effect_observed']),
            'interpretation': 'Checks startup configuration and observed idle behavior; reset prevention is unproven.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=seconds_value, default=5)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        before = query_service()
        measurement = measure(args.seconds)
        result = assess(before, query_service(), measurement)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'verification_passed': False, 'error': str(error)}))
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for key, value in result['service'].items():
            print(f'{key}: {value}')
        for state, values in measurement['states'].items():
            print(f'{state}: {values["entries"]} entries during measurement')
        print('Verification:', 'PASS' if result['verification_passed'] else 'NOT CONFIRMED')
        print(result['interpretation'])
        print('Rollback: sudo systemctl disable --now ' + UNIT)
    return 0 if result['verification_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
