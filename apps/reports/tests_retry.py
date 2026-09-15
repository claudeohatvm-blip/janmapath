"""Retry behaviour for transient provider failures."""

from __future__ import annotations

import pytest
from google.genai import errors as gerr

from apps.reports.providers.base import is_retryable, status_code, with_retry


def api_error(code: int, status: str = "ERROR"):
    return gerr.APIError(code, {"error": {"message": "x", "status": status}})


class TestStatusDetection:
    @pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
    def test_transient_statuses_retry(self, code):
        assert is_retryable(api_error(code)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404])
    def test_configuration_errors_do_not_retry(self, code):
        # A bad key or a retired model fails identically forever; retrying it
        # only makes the person watching the progress screen wait longer.
        assert is_retryable(api_error(code)) is False

    def test_status_read_from_message_when_no_attribute(self):
        assert status_code(RuntimeError("503 UNAVAILABLE. {...}")) == 503

    def test_connection_failures_retry(self):
        assert is_retryable(ConnectionError("reset")) is True
        assert is_retryable(TimeoutError("timed out")) is True

    def test_unknown_errors_do_not_retry(self):
        assert is_retryable(ValueError("bad json")) is False


class TestWithRetry:
    def test_returns_first_success_without_sleeping(self):
        assert with_retry(lambda: "ok", base_delay=0) == "ok"

    def test_recovers_after_a_transient_failure(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise api_error(503, "UNAVAILABLE")
            return "recovered"

        assert with_retry(flaky, attempts=3, base_delay=0) == "recovered"
        assert len(calls) == 3

    def test_gives_up_after_the_attempt_limit(self):
        calls = []

        def always_busy():
            calls.append(1)
            raise api_error(503, "UNAVAILABLE")

        with pytest.raises(gerr.APIError):
            with_retry(always_busy, attempts=3, base_delay=0)
        assert len(calls) == 3

    def test_configuration_error_fails_on_the_first_attempt(self):
        calls = []

        def bad_key():
            calls.append(1)
            raise api_error(401, "UNAUTHENTICATED")

        with pytest.raises(gerr.APIError):
            with_retry(bad_key, attempts=3, base_delay=0)
        assert len(calls) == 1, "must not retry a credential failure"

    def test_backoff_grows_and_stays_bounded(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("apps.reports.providers.base.time.sleep", slept.append)

        with pytest.raises(gerr.APIError):
            with_retry(
                lambda: (_ for _ in ()).throw(api_error(503)),
                attempts=3,
                base_delay=1.0,
            )

        assert len(slept) == 2, "sleeps between attempts, not after the last"
        assert slept[1] > slept[0], "delay must grow"
        # A person is watching a progress screen; the ceiling stays seconds.
        assert sum(slept) < 6.0
