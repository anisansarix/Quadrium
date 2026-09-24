from typing import Any, Callable
import time
from app.core.logging import get_logger
from app.config import settings

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logger = get_logger(__name__)

class MT5CircuitBreaker:
    def __init__(self):
        self.failures = 0
        self.last_failure_time = 0.0

    def check(self):
        if self.failures >= settings.mt5.circuit_breaker_threshold:
            elapsed = time.time() - self.last_failure_time
            if elapsed < settings.mt5.circuit_breaker_recovery_seconds:
                raise RuntimeError("MT5 Circuit Breaker is open")
            else:
                self.failures = 0  # Reset after recovery

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()

    def record_success(self):
        self.failures = 0

_cb = MT5CircuitBreaker()

def with_resilience(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        _cb.check()
        attempts = settings.mt5.retry_attempts
        delay = settings.mt5.retry_delay_seconds
        
        for i in range(attempts):
            try:
                res = func(*args, **kwargs)
                if res is False or res is None:
                    raise RuntimeError(f"MT5 call returned {res}")
                _cb.record_success()
                return res
            except Exception as e:
                logger.warning(f"MT5 call failed, attempt {i+1}/{attempts}: {e}")
                if i == attempts - 1:
                    _cb.record_failure()
                    raise
                time.sleep(delay)
    return wrapper


class MT5Service:
    @staticmethod
    @with_resilience
    def connect(login: int | None = None, password: str | None = None, server: str | None = None) -> bool:
        if mt5 is None:
            logger.error("mt5_not_available")
            return False

        if not mt5.initialize():
            logger.error("mt5_initialize_failed", error_code=mt5.last_error())
            return False

        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                logger.error("mt5_login_failed", login=login, error_code=mt5.last_error())
                return False
        return True

    @staticmethod
    def disconnect() -> None:
        if mt5 is not None:
            mt5.shutdown()

    @staticmethod
    @with_resilience
    def get_account_info() -> dict[str, Any] | None:
        if mt5 is None:
            raise RuntimeError("mt5_not_available")
        account_info = mt5.account_info()
        if account_info is None:
            raise RuntimeError("account_info is None")
        return account_info._asdict()
