#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* One fd-scoped PM QoS request. No EC writes or permanent sysfs changes. */
static int check_text(const char *path, const char *expected)
{
    char buf[128];
    FILE *f = fopen(path, "r");
    if (f == NULL) {
        perror(path);
        return -1;
    }
    char *result = fgets(buf, sizeof(buf), f);
    fclose(f);
    if (result == NULL) return -1;
    buf[strcspn(buf, "\r\n")] = '\0';
    if (strcmp(buf, expected) != 0) {
        fprintf(stderr, "Unsupported %s: %s (expected %s)\n", path, buf, expected);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    int32_t latency = 20;
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        puts("Usage: dellfix-idle-guard [latency-us: 10..50; default 20]\n"
             "       dellfix-idle-guard --check\n"
             "XPS 14 DA14260 only. Hold a CPU PM QoS request until SIGTERM/SIGINT.\n"
             "--check validates the platform without making a latency request.\n"
             "Stopping the process removes its request automatically.");
        return 0;
    }
    if (argc > 2) return 2;
    int check_only = argc == 2 && strcmp(argv[1], "--check") == 0;
    if (argc == 2 && !check_only) {
        char *end = NULL;
        errno = 0;
        long value = strtol(argv[1], &end, 10);
        if (errno || end == argv[1] || *end || value < 10 || value > 50) {
            fputs("Latency must be an integer from 10 to 50 microseconds.\n", stderr);
            return 2;
        }
        latency = (int32_t)value;
    }
    if (check_text("/sys/class/dmi/id/product_name", "XPS 14 DA14260") ||
        check_text("/sys/devices/system/cpu/cpuidle/current_driver", "intel_idle"))
        return 1;
    if (check_only) {
        struct stat device;
        if (lstat("/dev/cpu_dma_latency", &device) || !S_ISCHR(device.st_mode)) {
            fputs("Expected /dev/cpu_dma_latency character device is unavailable.\n", stderr);
            return 1;
        }
        puts("Compatible model, idle driver, and PM QoS device detected.\n"
             "No latency request was made. Verify idle counters after installation.");
        return 0;
    }

    /* Blocking before opening also makes termination during startup safe. */
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGTERM);
    sigaddset(&signals, SIGINT);
    if (sigprocmask(SIG_BLOCK, &signals, NULL) != 0) {
        perror("sigprocmask");
        return 1;
    }
    int fd = open("/dev/cpu_dma_latency", O_RDWR | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        perror("open /dev/cpu_dma_latency");
        return 1;
    }
    struct stat st;
    if (fstat(fd, &st) || !S_ISCHR(st.st_mode)) {
        fputs("cpu_dma_latency must be a character device\n", stderr);
        close(fd);
        return 1;
    }
    /* The kernel ABI requires a native-endian signed 32-bit microsecond value. */
    if (write(fd, &latency, sizeof(latency)) != (ssize_t)sizeof(latency)) {
        perror("write PM QoS request");
        close(fd);
        return 1;
    }
    printf("Holding CPU idle latency <= %" PRId32 " us; experimental mitigation.\n", latency);
    fflush(stdout);
    int caught = 0;
    int error = sigwait(&signals, &caught);
    close(fd);
    if (error) {
        fprintf(stderr, "sigwait: %s\n", strerror(error));
        return 1;
    }
    printf("Released CPU latency request on signal %d.\n", caught);
    return 0;
}
