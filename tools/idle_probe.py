#!/usr/bin/env python3
"""Read CPU idle counters without changing power settings; report aggregate deltas."""
import argparse
import json
import math
from pathlib import Path
import time

CPU_ROOT = Path('/sys/devices/system/cpu')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
EXPLANATION = ('Idle counters describe this measurement window. They do not establish '
               'the cause of resets, attribute the result to this service alone, '
               'or prove lasting stability.')


def read_required(path):
    value = path.read_text().strip()
    if not value:
        raise ValueError(f'Empty required counter or metadata: {path.name}')
    return value


def parse_cpus(value):
    cpus = set()
    for part in value.split(','):
        bounds = part.split('-')
        if len(bounds) == 1:
            low = high = int(bounds[0])
        elif len(bounds) == 2:
            low, high = map(int, bounds)
        else:
            raise ValueError('Invalid online CPU list')
        if low < 0 or high < low or high > 65535:
            raise ValueError('Invalid online CPU range')
        cpus.update(range(low, high + 1))
    if not cpus:
        raise ValueError('No online CPUs reported')
    return sorted(cpus)


def snapshot():
    # Boot ID is used only to reject cross-boot comparisons; it is never emitted.
    boot = read_required(BOOT_ID)
    online = parse_cpus(read_required(CPU_ROOT / 'online'))
    driver = read_required(CPU_ROOT / 'cpuidle/current_driver')
    states = {}
    for cpu in online:
        paths = sorted((CPU_ROOT / f'cpu{cpu}/cpuidle').glob('state[0-9]*'))
        if not paths:
            raise ValueError(f'Missing idle states for online CPU {cpu}')
        for path in paths:
            values = {'name': read_required(path / 'name')}
            for name in ('latency', 'usage', 'time'):
                values[name] = int(read_required(path / name))
                if values[name] < 0:
                    raise ValueError('Negative idle counter or latency')
            states[f'cpu{cpu}/{path.name}'] = values
    if online != parse_cpus(read_required(CPU_ROOT / 'online')):
        raise ValueError('Online CPUs changed while reading counters')
    if boot != read_required(BOOT_ID):
        raise ValueError('Boot changed while reading counters')
    return {'boot_id': boot, 'online_cpus': online, 'driver': driver,
            'monotonic': time.monotonic(), 'states': states}


def compare(before, after, limit):
    if not 10 <= limit <= 50:
        raise ValueError('Latency limit must be between 10 and 50 microseconds')
    if not before['boot_id'] or before['boot_id'] != after['boot_id']:
        raise ValueError('Boot changed or its identifier is unavailable')
    if before['online_cpus'] != after['online_cpus']:
        raise ValueError('Online CPUs changed during measurement')
    if before['driver'] != after['driver']:
        raise ValueError('Idle driver changed during measurement')
    if not before['states'] or before['states'].keys() != after['states'].keys():
        raise ValueError('Idle state inventory is missing or changed')
    expected_cpus = {f'cpu{cpu}' for cpu in before['online_cpus']}
    present_cpus = {key.split('/')[0] for key in before['states']}
    if not expected_cpus or expected_cpus != present_cpus:
        raise ValueError('Idle counters do not cover all online CPUs')
    elapsed = after['monotonic'] - before['monotonic']
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError('Invalid measurement duration')
    totals = {}
    restricted_cpus, shallow_cpus = set(), set()
    for key, first in before['states'].items():
        last = after['states'][key]
        if (first['name'], first['latency']) != (last['name'], last['latency']):
            raise ValueError('Idle state definition changed during measurement')
        count, duration = last['usage'] - first['usage'], last['time'] - first['time']
        if count < 0 or duration < 0:
            raise ValueError('Idle counter reset during measurement')
        group = totals.setdefault(first['name'], {'entries': 0, 'time_us': 0,
                                                  'latency_us': first['latency']})
        if group['latency_us'] != first['latency']:
            raise ValueError('Same-named idle states have different CPU latencies')
        group['entries'] += count
        group['time_us'] += duration
        if first['latency'] > limit:
            restricted_cpus.add(key.split('/')[0])
        elif first['latency'] > 0:
            shallow_cpus.add(key.split('/')[0])
    restricted = sum(v['entries'] for v in totals.values() if v['latency_us'] > limit)
    shallow = sum(v['entries'] for v in totals.values() if 0 < v['latency_us'] <= limit)
    observed = (restricted_cpus == expected_cpus and shallow_cpus == expected_cpus
                and restricted == 0 and shallow > 0)
    return {'duration_seconds': elapsed, 'online_cpu_count': len(expected_cpus),
            'driver': before['driver'], 'latency_limit_us': limit, 'states': totals,
            'restricted_entries': restricted, 'shallow_entries': shallow,
            'guard_effect_observed': observed, 'interpretation': EXPLANATION}


def seconds_value(value):
    seconds = float(value)
    if not math.isfinite(seconds) or not 1 <= seconds <= 300:
        raise argparse.ArgumentTypeError('Use a duration between 1 and 300 seconds')
    return seconds


def measure(seconds, limit=20):
    before = snapshot()
    time.sleep(seconds)
    return compare(before, snapshot(), limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=seconds_value, default=30)
    parser.add_argument('--limit-us', type=int, choices=range(10, 51), default=20)
    parser.add_argument('--expect-guard', action='store_true')
    parser.add_argument('--output', type=Path, help='Write aggregate results only')
    args = parser.parse_args()
    try:
        result = measure(args.seconds, args.limit_us)
        encoded = json.dumps(result, indent=2) + '\n'
        if args.output:
            args.output.write_text(encoded)
        print(encoded, end='')
    except (OSError, ValueError) as error:
        print(json.dumps({'error': str(error), 'guard_effect_observed': False}))
        return 2
    return int(args.expect_guard and not result['guard_effect_observed'])


if __name__ == '__main__':
    raise SystemExit(main())
