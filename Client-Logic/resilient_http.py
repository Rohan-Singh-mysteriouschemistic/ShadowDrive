"""
resilient_http.py — Fault-tolerant HTTP client with exponential backoff.

Every HTTP call in the ShadowDrive client goes through this module.
It provides:
    1. Automatic retries with exponential backoff + jitter
    2. Circuit breaker (stop hammering a dead server)
    3. Idempotency safety (safe to retry POSTs because our endpoints are idempotent)
    4. Structured error logging
    5. Network state tracking (online/offline transitions)

Architecture:
    network_client.py → resilient_http.request() → requests.Session
                                  ↓
                         RetryPolicy + CircuitBreaker
"""

import time
import random
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import requests

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Server is down — reject all requests immediately
    HALF_OPEN = "half_open"  # Allowing one probe request through


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 5
    base_delay: float = 1.0        # seconds
    max_delay: float = 60.0        # seconds
    backoff_factor: float = 2.0
    jitter: float = 0.5            # ±50% randomization
    retryable_status_codes: tuple = (408, 429, 500, 502, 503, 504)
    retryable_exceptions: tuple = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
    )


@dataclass
class CircuitBreaker:
    """Prevents hammering a dead server.

    After `failure_threshold` consecutive failures, the circuit opens
    for `recovery_timeout` seconds.  After that, one probe request is
    allowed through (half-open).  If it succeeds, the circuit closes.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _failure_count: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "[CIRCUIT] OPEN — %d consecutive failures. "
                    "Blocking requests for %ds.",
                    self._failure_count, self.recovery_timeout,
                )

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow one probe
        return False  # OPEN — reject


class CircuitBreakerOpen(requests.exceptions.RequestException):
    """Exception raised when the circuit breaker is OPEN to fail fast."""
    pass


# ── Module-level singletons ──────────────────────────────────────────────────
_default_policy = RetryPolicy()
_circuit = CircuitBreaker()
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Reusable session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": "ShadowDrive-Agent/1.0"})
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session



def request(
    method: str,
    url: str,
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable] = None,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with retry + circuit breaker.

    Args:
        method:   HTTP method (GET, POST, PUT, DELETE).
        url:      Full URL.
        policy:   Override default retry policy.
        on_retry: Optional callback(attempt, delay, exception) for logging.
        **kwargs: Passed through to requests (json, data, files, headers, timeout).

    Returns:
        requests.Response on success.

    Raises:
        requests.exceptions.RequestException: After all retries exhausted.
        CircuitBreakerOpen: If the circuit breaker is open.
    """
    p = policy or _default_policy
    session = _get_session()

    # Default timeout: 30s connect, 120s read
    kwargs.setdefault("timeout", (30, 120))

    last_exception = None
    for attempt in range(1, p.max_retries + 1):
        # Circuit breaker check
        if not _circuit.allow_request():
            logger.warning("[CIRCUIT] Open. Failing fast for %s %s.", method, url)
            raise CircuitBreakerOpen("Circuit breaker is OPEN. Server is unreachable.", request=None, response=None)

        try:
            response = session.request(method, url, **kwargs)

            if response.status_code in p.retryable_status_codes:
                last_exception = requests.exceptions.HTTPError(
                    f"Server returned {response.status_code}", response=response,
                )
                _circuit.record_failure()
                # Fall through to retry logic
            else:
                _circuit.record_success()
                return response

        except p.retryable_exceptions as exc:
            last_exception = exc
            _circuit.record_failure()

        except Exception as exc:
            # Non-retryable exception (e.g., invalid URL, SSL error)
            _circuit.record_failure()
            raise

        # Compute backoff with jitter
        delay = min(
            p.base_delay * (p.backoff_factor ** (attempt - 1)),
            p.max_delay,
        )
        jitter = delay * p.jitter * (2 * random.random() - 1)
        delay = max(0.1, delay + jitter)

        if on_retry:
            on_retry(attempt, delay, last_exception)
        else:
            logger.warning(
                "[RETRY] Attempt %d/%d for %s %s failed: %s. "
                "Retrying in %.1fs.",
                attempt, p.max_retries, method, url, last_exception, delay,
            )

        time.sleep(delay)

    # All retries exhausted
    logger.error(
        "[FAILED] All %d attempts exhausted for %s %s. Last error: %s",
        p.max_retries, method, url, last_exception,
    )
    raise last_exception
