# Contributing

This is an experiment with limited evidence. Describe observations precisely:
an active service, an observed idle restriction, and an absence of resets over
a stated period are different results.

For an experience report, include:

- Laptop model, Linux distribution/kernel, and BIOS version.
- Whether the service is active and enabled and the aggregate result from
  `python3 tools/status.py --json`.
- Approximate observation duration and how often resets occurred before testing.
- Whether the laptop was on its charger or battery, the selected power profile,
  and whether sleep/resume was involved.
- Any new reset or diagnostic light, including whether it followed an intentional
  shutdown or restart. Distinguish an old flashing indication from a new one.

Keep service tags, serial numbers, usernames, hostnames, IP addresses, private
paths, and credentials out of reports. The provided counter summary omits these
fields; raw system logs and screenshots may not. Generated reports are ignored
by Git. There is no telemetry upload or automatic issue submission.

For code changes, run `make check`. Tests use fixtures and do not start a real
latency request. Hardware verification is a separate, explicit step. CI checks
compilation, counter validation, shell syntax, and the systemd unit; it cannot
establish laptop stability.

Keep the change limited to a reversible CPU latency request. Model support must
be based on verified driver/state information and clearly labeled observations.
An additional model's installer check passing is not evidence of crash prevention.
Preserve compatibility checks, request release on exit, and honest inconclusive
results when evidence is missing.
