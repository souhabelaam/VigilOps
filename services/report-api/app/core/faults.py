import os
import threading
import time

LEAK_CHUNK_BYTES = 1024 * 1024  # 1 MB per step
LEAK_INTERVAL_SECONDS = 0.5
LEAK_MAX_MB = 200  # safety cap so a leak cannot exhaust the laptop


def faults_enabled() -> bool:
    """Fault hooks are dangerous, so they are off unless explicitly enabled."""
    return os.environ.get("FAULTS_ENABLED", "").lower() == "true"


class FaultState:
    """Holds the currently active faults and how to start or stop each one."""

    def __init__(self) -> None:
        self.latency_seconds = 0.0
        self._cpu_stop: threading.Event | None = None
        self._memory_stop: threading.Event | None = None
        self._leaked: list[bytearray] = []

    # ---- CPU burn: a thread that never stops computing ----
    def start_cpu(self) -> None:
        if self._cpu_stop is not None:
            return
        stop = threading.Event()
        self._cpu_stop = stop

        def burn() -> None:
            while not stop.is_set():
                sum(i * i for i in range(10_000))

        threading.Thread(target=burn, daemon=True).start()

    def stop_cpu(self) -> None:
        if self._cpu_stop is not None:
            self._cpu_stop.set()
            self._cpu_stop = None

    # ---- Memory leak: keep allocating, never free ----
    def start_memory(self) -> None:
        if self._memory_stop is not None:
            return
        stop = threading.Event()
        self._memory_stop = stop

        def leak() -> None:
            while not stop.is_set() and len(self._leaked) < LEAK_MAX_MB:
                # Multiplying a filled bytearray writes every byte, so the
                # memory is really used (a zeroed one may stay untouched).
                self._leaked.append(bytearray(b"x") * LEAK_CHUNK_BYTES)
                time.sleep(LEAK_INTERVAL_SECONDS)

        threading.Thread(target=leak, daemon=True).start()

    def stop_memory(self) -> None:
        if self._memory_stop is not None:
            self._memory_stop.set()
            self._memory_stop = None
        self._leaked = []  # dropping the references frees the memory

    # ---- Slow responses: extra delay on every business request ----
    def start_latency(self, delay_ms: int) -> None:
        self.latency_seconds = delay_ms / 1000

    def stop_latency(self) -> None:
        self.latency_seconds = 0.0

    # ---- Crash: exit shortly after the response is sent ----
    def crash(self) -> None:
        threading.Timer(0.2, lambda: os._exit(1)).start()

    def status(self) -> dict:
        return {
            "cpu": self._cpu_stop is not None,
            "memory": self._memory_stop is not None,
            "memory_leaked_mb": len(self._leaked),
            "latency_ms": int(self.latency_seconds * 1000),
        }


faults = FaultState()
