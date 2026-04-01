"""Tests for core.retry — exponential backoff retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.core.retry import retry


class TestRetry:
    """Tests for the retry() function."""

    def test_success_on_first_attempt(self):
        fn = MagicMock(return_value="ok")
        result = retry(fn, max_attempts=3)
        assert result == "ok"
        assert fn.call_count == 1

    @patch("openquery.core.retry.time.sleep")
    def test_retries_on_failure(self, mock_sleep):
        fn = MagicMock(side_effect=[ValueError("fail"), "ok"])
        result = retry(fn, max_attempts=3, base_delay=1.0)
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once()

    @patch("openquery.core.retry.time.sleep")
    def test_exhausts_max_attempts(self, mock_sleep):
        fn = MagicMock(side_effect=ValueError("always fails"))
        with pytest.raises(ValueError, match="always fails"):
            retry(fn, max_attempts=3, base_delay=0.01)
        assert fn.call_count == 3

    @patch("openquery.core.retry.time.sleep")
    def test_respects_exception_filter(self, mock_sleep):
        """Only retries specified exception types."""
        fn = MagicMock(side_effect=TypeError("wrong type"))
        with pytest.raises(TypeError):
            retry(fn, max_attempts=3, exceptions=(ValueError,), base_delay=0.01)
        # Should not retry since TypeError not in exceptions
        assert fn.call_count == 1

    @patch("openquery.core.retry.time.sleep")
    def test_on_retry_callback(self, mock_sleep):
        callback = MagicMock()
        fn = MagicMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])
        result = retry(fn, max_attempts=3, on_retry=callback, base_delay=0.01)
        assert result == "ok"
        assert callback.call_count == 2
        # First callback: attempt=1, error
        assert callback.call_args_list[0][0][0] == 1
        assert callback.call_args_list[1][0][0] == 2

    @patch("openquery.core.retry.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        fn = MagicMock(side_effect=[ValueError(), ValueError(), "ok"])
        retry(fn, max_attempts=3, base_delay=1.0, max_delay=30.0)
        # First retry: 1.0 * 2^0 = 1.0
        # Second retry: 1.0 * 2^1 = 2.0
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 2.0

    @patch("openquery.core.retry.time.sleep")
    def test_max_delay_cap(self, mock_sleep):
        fn = MagicMock(side_effect=[ValueError()] * 5 + ["ok"])
        retry(fn, max_attempts=6, base_delay=10.0, max_delay=15.0)
        # All delays should be capped at max_delay=15.0
        for call in mock_sleep.call_args_list:
            assert call[0][0] <= 15.0

    def test_single_attempt_no_retry(self):
        fn = MagicMock(side_effect=ValueError("no retry"))
        with pytest.raises(ValueError, match="no retry"):
            retry(fn, max_attempts=1)
        assert fn.call_count == 1

    @patch("openquery.core.retry.time.sleep")
    def test_preserves_last_exception(self, mock_sleep):
        """The last exception should be raised, not the first."""
        errors = [ValueError("first"), ValueError("second"), ValueError("third")]
        fn = MagicMock(side_effect=errors)
        with pytest.raises(ValueError, match="third"):
            retry(fn, max_attempts=3, base_delay=0.01)
