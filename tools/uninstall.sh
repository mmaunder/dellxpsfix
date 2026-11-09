#!/bin/sh
set -eu
if [ "$(id -u)" != 0 ]; then
    echo 'Run this uninstaller with sudo.' >&2
    exit 1
fi
# Stop successfully before removing the executable or service definition.
systemctl disable --now dellfix-idle-guard.service
rm -f /etc/systemd/system/dellfix-idle-guard.service
rm -f /usr/local/libexec/dellfix-idle-guard
rm -f /usr/local/share/doc/dellfix-idle-guard/README.md
rm -f /usr/local/share/doc/dellfix-idle-guard/LICENSE
if [ -d /usr/local/share/doc/dellfix-idle-guard ]; then
    rmdir /usr/local/share/doc/dellfix-idle-guard 2>/dev/null || true
fi
systemctl daemon-reload
echo 'Removed the service and its installed files. Its CPU latency request has ended.'
