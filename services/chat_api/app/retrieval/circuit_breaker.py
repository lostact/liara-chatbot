import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_time_secs: float = 60.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_time_secs = recovery_time_secs
        self.name = name

        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # "CLOSED" | "OPEN" | "HALF_OPEN"

    def record_success(self):
        if self.state != "CLOSED":
            logger.info(f"CircuitBreaker '{self.name}' state reset to CLOSED.")
        self.state = "CLOSED"
        self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"CircuitBreaker '{self.name}' opened after {self.failure_count} consecutive failures."
            )

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_time_secs:
                self.state = "HALF_OPEN"
                logger.info(f"CircuitBreaker '{self.name}' entering HALF_OPEN state.")
                return True
            return False

        if self.state == "HALF_OPEN":
            return True

        return True
