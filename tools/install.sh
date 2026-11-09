#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$(id -u)" != 0 ]; then
    echo 'Run this installer with sudo after building and running make check.' >&2
    exit 1
fi
if [ ! -x build/dellfix-idle-guard ]; then
    echo 'Build as your normal user with make check before installing.' >&2
    exit 1
fi
# Check compatibility before changing installed files or service settings.
./build/dellfix-idle-guard --check
command -v systemctl >/dev/null
test -d /run/systemd/system
install -d -o root -g root -m 0755 /usr/local/libexec /usr/local/share/doc/dellfix-idle-guard
install -o root -g root -m 0755 build/dellfix-idle-guard /usr/local/libexec/dellfix-idle-guard
install -o root -g root -m 0644 README.md LICENSE /usr/local/share/doc/dellfix-idle-guard/
install -o root -g root -m 0644 systemd/dellfix-idle-guard.service /etc/systemd/system/dellfix-idle-guard.service
systemctl daemon-reload
systemctl enable dellfix-idle-guard.service
systemctl restart dellfix-idle-guard.service
systemctl is-active --quiet dellfix-idle-guard.service
echo 'Installed and enabled. Verify counter behavior with: python3 tools/status.py'
echo 'Rollback: sudo systemctl disable --now dellfix-idle-guard.service'
