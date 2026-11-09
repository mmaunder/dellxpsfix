#!/usr/bin/env python3
"""Validate the service without installing it or starting a CPU latency request."""
from pathlib import Path
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    binary = str(root / 'build/dellfix-idle-guard')
    if any(c in binary for c in '\r\n'):
        raise SystemExit('Build path must not contain newlines')
    binary = binary.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    source = (root / 'systemd/dellfix-idle-guard.service').read_text()
    source = source.replace('ExecStart=/usr/local/libexec/dellfix-idle-guard 20',
                            f'ExecStart="{binary}" 20')
    with tempfile.TemporaryDirectory(prefix='idle-guard-unit-') as directory:
        unit = Path(directory) / 'dellfix-idle-guard.service'
        unit.write_text(source)
        subprocess.run(['systemd-analyze', 'verify', str(unit)], check=True)


if __name__ == '__main__':
    main()
