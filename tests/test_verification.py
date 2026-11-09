import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import idle_probe as probe
import status


def sample(shallow=10, deep=10, boot='test-boot', elapsed=0):
    return {'boot_id': boot, 'monotonic': 5.0 + elapsed, 'driver': 'intel_idle',
            'online_cpus': [0], 'states': {
                'cpu0/state1': {'name': 'C1E', 'latency': 10, 'usage': shallow, 'time': shallow * 3},
                'cpu0/state2': {'name': 'C10', 'latency': 370, 'usage': deep, 'time': deep * 3}}}


def active_service(**overrides):
    return {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
            'UnitFileState': 'enabled', 'NRestarts': '0', 'MainPID': '123',
            'ActiveEnterTimestampMonotonic': '1000000', **overrides}


class EvidenceTests(unittest.TestCase):
    def test_deep_entries_fail_observation(self):
        self.assertFalse(probe.compare(sample(), sample(20, 11, elapsed=5), 20)['guard_effect_observed'])

    def test_inactive_cpu_is_inconclusive(self):
        self.assertFalse(probe.compare(sample(), sample(elapsed=5), 20)['guard_effect_observed'])

    def test_shallow_activity_with_deep_exclusion(self):
        result = probe.compare(sample(), sample(20, 10, elapsed=5), 20)
        self.assertTrue(result['guard_effect_observed'])
        self.assertNotIn('test-boot', json.dumps(result))
        self.assertNotIn('boot_id', result)

    def test_boot_change_or_missing_id_rejected(self):
        for boot in ('new-test-boot', ''):
            with self.subTest(boot=boot), self.assertRaises(ValueError):
                probe.compare(sample(), sample(20, 10, boot, elapsed=5), 20)

    def test_counter_reset_rejected(self):
        for field in ('usage', 'time'):
            after = sample(elapsed=5)
            after['states']['cpu0/state2'][field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                probe.compare(sample(), after, 20)

    def test_missing_state_rejected(self):
        after = sample(elapsed=5)
        del after['states']['cpu0/state2']
        with self.assertRaises(ValueError):
            probe.compare(sample(), after, 20)

    def test_missing_cpu_in_both_snapshots_rejected(self):
        before, after = sample(), sample(20, 10, elapsed=5)
        before['online_cpus'] = after['online_cpus'] = [0, 1]
        with self.assertRaises(ValueError):
            probe.compare(before, after, 20)

    def test_hotplug_and_driver_changes_rejected(self):
        for key, value in [('online_cpus', [0, 1]), ('driver', 'acpi_idle')]:
            after = sample(elapsed=5)
            after[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.compare(sample(), after, 20)

    def test_latency_change_rejected(self):
        after = sample(elapsed=5)
        after['states']['cpu0/state2']['latency'] = 1
        with self.assertRaises(ValueError):
            probe.compare(sample(), after, 20)

    def test_no_deep_states_is_inconclusive(self):
        before, after = sample(), sample(20, 10, elapsed=5)
        for row in (before, after):
            del row['states']['cpu0/state2']
        self.assertFalse(probe.compare(before, after, 20)['guard_effect_observed'])

    def test_empty_or_instant_measurement_rejected(self):
        for before, after in [(sample(), sample()), (sample(), sample(elapsed=-1))]:
            with self.assertRaises(ValueError):
                probe.compare(before, after, 20)
        before, after = sample(), sample(elapsed=5)
        before['states'] = after['states'] = {}
        with self.assertRaises(ValueError):
            probe.compare(before, after, 20)

    def test_multiple_cpus_with_different_latencies_rejected(self):
        before, after = sample(), sample(20, 10, elapsed=5)
        for row in (before, after):
            row['online_cpus'] = [0, 1]
            for key, value in list(row['states'].items()):
                row['states'][key.replace('cpu0', 'cpu1')] = copy.deepcopy(value)
            row['states']['cpu1/state2']['latency'] = 1
        with self.assertRaises(ValueError):
            probe.compare(before, after, 20)

    def test_bad_durations_rejected_before_sampling(self):
        for value in ('0', '-1', 'nan', 'inf', '301'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                probe.seconds_value(value)

    def test_partial_sysfs_read_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'online').write_text('0')
            (root / 'boot').write_text('test-boot')
            (root / 'cpuidle').mkdir()
            (root / 'cpuidle/current_driver').write_text('intel_idle')
            state = root / 'cpu0/cpuidle/state0'
            state.mkdir(parents=True)
            for key, value in {'name': 'C1', 'latency': '1', 'usage': '10'}.items():
                (state / key).write_text(value)
            with patch.object(probe, 'CPU_ROOT', root), patch.object(probe, 'BOOT_ID', root / 'boot'):
                with self.assertRaises(OSError):
                    probe.snapshot()
                (state / 'time').write_text('30')
                self.assertEqual(len(probe.snapshot()['states']), 1)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.measurement = probe.compare(sample(), sample(20, 10, elapsed=5), 20)

    def test_active_enabled_stable_service_passes(self):
        result = status.assess(active_service(), active_service(), self.measurement)
        self.assertTrue(result['verification_passed'])

    def test_stopped_disabled_or_restarted_service_cannot_pass(self):
        for overrides in ({'ActiveState': 'inactive'}, {'SubState': 'failed'},
                          {'UnitFileState': 'disabled'}, {'MainPID': '456'},
                          {'ActiveEnterTimestampMonotonic': '2000000'}):
            with self.subTest(overrides=overrides):
                self.assertFalse(status.assess(active_service(), active_service(**overrides),
                                               self.measurement)['verification_passed'])

    def test_active_service_does_not_mask_deep_idle(self):
        self.measurement['guard_effect_observed'] = False
        self.assertFalse(status.assess(active_service(), active_service(),
                                      self.measurement)['verification_passed'])


class CommandTests(unittest.TestCase):
    def test_guard_rejects_bad_arguments_before_device_access(self):
        for value in ('0', '-1', '9', '51', '10junk', '', '99999999999999999999999'):
            result = subprocess.run([str(ROOT / 'build/dellfix-idle-guard'), value],
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2, value)

    def test_help_needs_no_hardware_or_privileges(self):
        result = subprocess.run([str(ROOT / 'build/dellfix-idle-guard'), '--help'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--check', result.stdout)


if __name__ == '__main__':
    unittest.main()
