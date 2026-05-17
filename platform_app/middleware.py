"""Middleware для подробного логирования запросов и ответов."""

import logging
import time

from django.conf import settings


logger = logging.getLogger("platform_app.request")


class RequestLoggingMiddleware:
    """Логирует входящие запросы и исходящие ответы."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_ts = time.perf_counter()

        user_repr = request.user.username if request.user.is_authenticated else "anonymous"
        logger.info("Request started: %s %s user=%s",
                    request.method, request.path, user_repr)

        if settings.DEBUG:
            get_keys = sorted(request.GET.keys())
            post_keys = sorted(request.POST.keys())
            logger.debug(
                "Request debug info: query_keys=%s post_keys=%s remote_addr=%s user_agent=%s",
                get_keys,
                post_keys,
                request.META.get("REMOTE_ADDR", "-"),
                request.META.get("HTTP_USER_AGENT", "-")[:200],
            )

            if settings.APP_LOGGING_OPTIONS.get("log_request_body_in_debug", False):
                max_chars = int(settings.APP_LOGGING_OPTIONS.get(
                    "request_log_max_chars", 1000))
                body = request.body.decode("utf-8", errors="replace")
                logger.debug("Request body (truncated): %s", body[:max_chars])

        try:
            response = self.get_response(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start_ts) * 1000
            logger.exception(
                "Request failed with exception: %s %s duration_ms=%.2f",
                request.method,
                request.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start_ts) * 1000
        logger.info(
            "Request finished: %s %s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )

        if settings.DEBUG:
            logger.debug(
                "Response debug info: content_type=%s headers=%s",
                response.get("Content-Type", "-"),
                sorted(response.headers.keys()),
            )

        return response
