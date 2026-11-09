# Dell XPS idle guard

An experimental Linux workaround for abrupt resets on the **Dell XPS 14 DA14260**.
It keeps the processor out of its deepest idle states through the standard Linux
CPU latency interface.

**This is not a confirmed fix. So far, the initial test laptop has been running
normally with the workaround enabled, including after a restart and a full
shutdown/startup. Observation is limited to one laptop and a short period of use.
The cause of the resets and long-term effectiveness remain unproven.**

Created by [Mark Maunder](https://github.com/mmaunder). This is an independent
community experiment, not an official Dell update.

## Why it might help

Owners have reported sudden resets followed by one amber and six white flashes
of the power button. Dell describes that code as an abnormal embedded-controller
execution condition. It is a broad error indication: it does **not** identify
CPU idle as the cause. See the [Dell diagnostic table][dell-lights] and
[owners' discussion][discussion].

Even during normal use, CPU cores briefly idle between tasks. Deeper idle states
save more power by shutting down more circuitry. Our hypothesis is that a
platform power-management fault could be exposed during entry to, or exit from,
those states. Excluding them removes one possible trigger. The CPU's power
controllers and the embedded controller are distinct; their involvement in
these resets has not been established. [Linux describes these states here][cpuidle].

Balanced mode still allowed deep idle during initial testing, so switching to
Balanced did not test this hypothesis. The workaround changes the permitted
idle states, rather than selecting another performance profile.

## What it does

A small C process opens `/dev/cpu_dma_latency`, requests a **20 microsecond** CPU
latency limit, and keeps that file descriptor open. Linux uses the request when
choosing idle states. The process sleeps while holding the request; it does not
keep the CPU busy. When it stops, Linux removes its request automatically.
Other applications' requests remain in effect. See the [Linux PM QoS interface][qos].

The initial test machine exposed these states:

| State | Reported exit latency | With the default request |
| --- | ---: | --- |
| C1 | 1 microsecond | Allowed |
| C1E | 10 microseconds | Allowed |
| C6S | 300 microseconds | Excluded |
| C10 | 370 microseconds | Excluded |

State tables depend on the hardware and kernel. Verify the actual result on your
machine. An exit-latency request is not a guarantee about application response
times or a universal ban on every hardware power-saving mechanism.

The service starts automatically at boot. It requires no kernel rebuild,
additional kernel module, bootloader change, or BIOS setting change. Secure Boot
can remain enabled. It makes no embedded-controller register writes.

## Current scope and tradeoffs

- **Currently restricted to XPS 14 DA14260 with the `intel_idle` driver.** The
  program and installer reject other models or drivers. XPS 16 and other Dell
  models have not been validated by this project.
- Requires Linux with systemd, `/dev/cpu_dma_latency`, readable CPU idle counters,
  a C compiler, make, and Python 3.10 or newer. Initial testing used Ubuntu.
- Preventing deep idle can increase power consumption, reduce battery life,
  and increase heat. No reliable battery-life measurement is available yet.
- The request applies while the service runs. It does not establish protection
  during system suspend, early boot before the service starts, or unrelated faults.

## Build and install

Clone this repository and enter its directory:

```sh
git clone https://github.com/mmaunder/dellxpsfix.git
cd dellxpsfix
```

On Ubuntu/Debian, the build tools can be installed with:

```sh
sudo apt install build-essential python3
```

Build and test as your normal user:

```sh
make check
./build/dellfix-idle-guard --check
```

`make check` runs offline tests and validates the service definition. It does not
start the workaround or require the target laptop. `--check` reads the actual
model, idle driver, and device availability without making a latency request.
Stop here if the compatibility check fails.

Install and start the service:

```sh
sudo sh tools/install.sh
python3 tools/status.py
```

The installer copies the executable to `/usr/local/libexec`, documentation to
`/usr/local/share/doc/dellfix-idle-guard`, and the service definition to
`/etc/systemd/system`. Installed files are owned by root. It enables the service
for future boots and starts it now. Reinstalling replaces these files and
restarts the service. No automatic reboot is performed.

## Verify it is working

```sh
python3 tools/status.py
```

The check samples all online CPUs for five seconds. A pass means the service
was running throughout the measurement, is enabled at boot, shallow idle was
observed, and states above the 20 microsecond limit recorded no new entries.
On the initial machine, those excluded states are C6S and C10.

**A pass verifies service configuration and observed idle behavior. It does not
prove that the workaround caused that behavior or that future resets are prevented.**
Other software can also constrain idle states. A busy CPU with no shallow idle
activity produces an inconclusive result instead of a false pass.

Repeat the check after a normal reboot. Counters may already be nonzero because
deep idle was used before the service started; the check measures changes during
its observation window. A kernel or firmware update can change the state table,
so check again after updates too.

For a longer measurement or a shareable aggregate report:

```sh
python3 tools/status.py --seconds 30 --json
mkdir -p reports
python3 tools/idle_probe.py --seconds 30 --expect-guard --output reports/idle-check.json
```

`status.py` also checks the service. `idle_probe.py` checks only the counters and
can be used before installation without `--expect-guard`. Both tools return
nonzero for a failed expected check or unreadable/inconsistent evidence. The
tools use a boot identifier internally to reject cross-boot comparisons but
emit aggregate results without it. They do not upload data.

If a check fails, inspect the service locally:

```sh
systemctl status dellfix-idle-guard.service
journalctl -b -u dellfix-idle-guard.service
```

Avoid posting raw journal output; it can contain your hostname and timestamps.

## Stop, re-enable, or remove

Stop the request immediately and disable it for future boots:

```sh
sudo systemctl disable --now dellfix-idle-guard.service
```

Re-enable an installed service:

```sh
sudo systemctl enable --now dellfix-idle-guard.service
```

Remove the installed service, executable, and documentation:

```sh
sudo sh tools/uninstall.sh
```

Stopping the process closes its file descriptor and releases only its own latency
request. Removing this repository by itself does not stop an installed service.

## What has actually been observed

- CPU idle counters stopped advancing for the excluded deep states while
  shallow idle continued. Separate hardware-counter checks during initial
  testing were consistent with the intended change.
- The service started automatically after both a restart and a full
  shutdown/startup; counter checks passed again afterward.
- No additional spontaneous reset was reported during the limited initial
  observation period. There is no controlled trial or long-term stability result.

The diagnostic light is separate from the workaround. An earlier flashing code
persisted through a restart and cleared after a full shutdown/startup. The same
behavior is described in the [owners' discussion][discussion]. Clearing the light
does not establish that the underlying reset problem is resolved, and this
service does not clear or suppress diagnostic indicators.

For a useful stability test, keep other settings consistent and use the laptop
normally. Record the observation duration, AC/battery use, and whether another
reset occurs. A reset while the guard is confirmed active would show that this
workaround is insufficient in that configuration. A short crash-free run is
encouraging but does not establish a fix.

## Contributing

Reports with both successful and unsuccessful outcomes are useful. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the small set of details to include.
The issue template asks for aggregate results and observation conditions, not
personal identifiers or raw logs.

Source code is provided under the [MIT license](LICENSE).

[cpuidle]: https://www.kernel.org/doc/html/latest/admin-guide/pm/cpuidle.html
[qos]: https://www.kernel.org/doc/html/latest/power/pm_qos_interface.html
[dell-lights]: https://www.dell.com/support/manuals/en-us/xps-da14260-laptop/xps-14-da14260-service-manual/system-diagnostic-lights?guid=guid-924845d7-957f-49d6-8494-0d7d6b10e34d&lang=en-us
[discussion]: https://www.dell.com/community/en/conversations/xps/xps-1416-2026-abrupt-crashshutdown-while-on-battery-da14260-da16260/6a41380230ba7b5c1c724a29
