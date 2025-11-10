import time
import logging
from functools import wraps
from typing import Callable, Any
from rich.console import Console

console = Console()


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def log_step(step: str, message: str, style: str = "bold cyan") -> None:
    console.print(f"[{style}]{step}[/{style}]: {message}")


def log_info(message: str) -> None:
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def log_success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def log_warning(message: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def log_error(message: str) -> None:
    console.print(f"[bold red]✗[/bold red] {message}")


def timeit(func: Callable) -> Callable:
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        log_step(func.__name__, f"completed in {elapsed:.3f}s", "bold magenta")
        return result

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        log_step(func.__name__, f"completed in {elapsed:.3f}s", "bold magenta")
        return result

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class PerformanceMonitor:

    def __init__(self):
        self.metrics = {}

    def record(self, operation: str, duration_ms: float) -> None:
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration_ms)

    def get_stats(self, operation: str) -> dict:
        if operation not in self.metrics:
            return {}

        times = self.metrics[operation]
        return {
            "count": len(times),
            "avg_ms": sum(times) / len(times),
            "min_ms": min(times),
            "max_ms": max(times)
        }

    def reset(self) -> None:
        self.metrics.clear()


performance_monitor = PerformanceMonitor()
