"""Tests for health monitoring and circuit breaker."""

from __future__ import annotations

from openquery.core.health import SourceHealthMonitor
from openquery.models.health import CircuitState


class TestCircuitBreakerStateMachine:
    """Test circuit breaker state transitions."""

    def test_starts_closed(self):
        monitor = SourceHealthMonitor(threshold=3, cooldown=1.0)
        assert monitor.is_available("co.simit") is True
        health = monitor.get_health("co.simit")
        assert health.status == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        monitor = SourceHealthMonitor(threshold=3, cooldown=60.0)
        monitor.record_failure("co.simit", "timeout")
        monitor.record_failure("co.simit", "timeout")
        assert monitor.is_available("co.simit") is True  # 2 < 3
        monitor.record_failure("co.simit", "timeout")
        assert monitor.is_available("co.simit") is False  # 3 >= 3 → OPEN

    def test_success_resets_consecutive_failures(self):
        monitor = SourceHealthMonitor(threshold=3, cooldown=60.0)
        monitor.record_failure("co.simit", "timeout")
        monitor.record_failure("co.simit", "timeout")
        monitor.record_success("co.simit", 100.0)
        monitor.record_failure("co.simit", "timeout")
        monitor.record_failure("co.simit", "timeout")
        assert monitor.is_available("co.simit") is True  # consecutive=2 < 3

    def test_half_open_to_closed_on_success(self):
        monitor = SourceHealthMonitor(threshold=1, cooldown=0.0)
        monitor.record_failure("co.simit", "timeout")  # → OPEN
        assert monitor.is_available("co.simit") is True  # cooldown=0 → HALF_OPEN
        health = monitor.get_health("co.simit")
        assert health.status == CircuitState.HALF_OPEN
        monitor.record_success("co.simit", 50.0)
        health = monitor.get_health("co.simit")
        assert health.status == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        monitor = SourceHealthMonitor(threshold=1, cooldown=0.0)
        monitor.record_failure("co.simit", "timeout")  # → OPEN
        monitor.is_available("co.simit")  # cooldown=0 → HALF_OPEN
        monitor.record_failure("co.simit", "still broken")  # → OPEN
        health = monitor.get_health("co.simit")
        assert health.status == CircuitState.OPEN

    def test_open_blocks_until_cooldown(self):
        monitor = SourceHealthMonitor(threshold=1, cooldown=9999.0)
        monitor.record_failure("co.simit", "timeout")  # → OPEN
        assert monitor.is_available("co.simit") is False  # cooldown not elapsed


class TestHealthTracking:
    """Test success/failure counting and metrics."""

    def test_counts_successes(self):
        monitor = SourceHealthMonitor()
        monitor.record_success("co.simit", 100.0)
        monitor.record_success("co.simit", 200.0)
        health = monitor.get_health("co.simit")
        assert health.success_count == 2
        assert health.avg_latency_ms == 150.0

    def test_counts_failures(self):
        monitor = SourceHealthMonitor()
        monitor.record_failure("co.simit", "error1")
        monitor.record_failure("co.simit", "error2")
        health = monitor.get_health("co.simit")
        assert health.failure_count == 2
        assert health.last_error == "error2"

    def test_error_rate(self):
        monitor = SourceHealthMonitor()
        monitor.record_success("co.simit", 100.0)
        monitor.record_failure("co.simit", "err")
        health = monitor.get_health("co.simit")
        assert health.error_rate == 0.5

    def test_independent_sources(self):
        monitor = SourceHealthMonitor(threshold=2)
        monitor.record_failure("co.simit", "err")
        monitor.record_failure("co.simit", "err")
        assert monitor.is_available("co.simit") is False
        assert monitor.is_available("co.runt") is True

    def test_zero_latency_when_no_success(self):
        monitor = SourceHealthMonitor()
        health = monitor.get_health("co.simit")
        assert health.avg_latency_ms == 0.0


class TestHealthModels:
    """Test pydantic model validation."""

    def test_circuit_state_values(self):
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_source_health_defaults(self):
        from openquery.models.health import SourceHealth

        health = SourceHealth(name="test")
        assert health.status == CircuitState.CLOSED
        assert health.success_count == 0

    def test_health_report_defaults(self):
        from openquery.models.health import HealthReport

        report = HealthReport()
        assert report.status == "ok"
        assert report.sources == []
