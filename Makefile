CC ?= cc
CFLAGS := -std=c11 -O2 -Wall -Wextra -Werror -Wconversion -Wshadow -D_FORTIFY_SOURCE=2 -fstack-protector-strong
LDFLAGS := -Wl,-z,relro,-z,now

.PHONY: all check clean
all: build/dellfix-idle-guard

build/dellfix-idle-guard: src/idle_guard.c
	mkdir -p build
	$(CC) $(CFLAGS) $< $(LDFLAGS) -o $@

check: all
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
	sh -n tools/install.sh tools/uninstall.sh
	python3 tools/verify_unit.py

clean:
	rm -f build/dellfix-idle-guard
	rmdir build 2>/dev/null || test ! -d build
