"""Настройка логирования приложения из внешнего JSON-конфига."""

import json
import warnings
import logging
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timedelta, timezone


DEFAULT_LOGGING_OPTIONS = {
    "log_level": "INFO",
    "debug_log_level": "DEBUG",
    "django_log_level": "INFO",
    "sql_log_level": "DEBUG",
    "utc_offset_hours": 3,
    "enable_console": True,
    "enable_file": True,
    "log_file": "logs/platform.log",
    "max_bytes": 5 * 1024 * 1024,
    "backup_count": 3,
    "log_request_body_in_debug": False,
    "request_log_max_chars": 1000,
}


class UTCFormatter:
    """Форматтер с настраиваемым UTC-смещением (по умолчанию UTC+3)."""

    def __init__(self, fmt=None, datefmt=None, style="%", utc_offset_hours=3):
        self._formatter = logging.Formatter(
            fmt=fmt, datefmt=datefmt, style=style)
        self._tz = timezone(timedelta(hours=float(utc_offset_hours)))

    def formatTime(self, record, datefmt=None):
        """Форматирование времени записи с заданным смещением."""

        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

    def format(self, record):
        """Форматирование записи лога."""

        original_format_time = self._formatter.formatTime
        self._formatter.formatTime = self.formatTime
        try:
            return self._formatter.format(record)
        finally:
            self._formatter.formatTime = original_format_time


def _load_json_options(config_paths):
    for config_path in config_paths:
        if not config_path.exists():
            continue

        try:
            with config_path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
                if not isinstance(payload, dict):
                    warnings.warn(
                        f"Лог-конфиг {config_path} должен быть JSON-объектом. "
                        "Будут использованы значения по умолчанию.",
                        RuntimeWarning,
                    )
                    return {}
                return payload
        except json.JSONDecodeError as exc:
            warnings.warn(
                f"Не удалось прочитать {config_path}: {exc}. "
                "Будут использованы значения по умолчанию.",
                RuntimeWarning,
            )
            return {}

    return {}


def load_logging_options(base_dir):
    """Загружает параметры логирования из log_conf.json."""

    config_paths = [
        Path(base_dir) / "log_conf.json",
    ]

    options = deepcopy(DEFAULT_LOGGING_OPTIONS)
    options.update(_load_json_options(config_paths))
    return options


def build_logging_config(base_dir, debug):
    """Формирует Django LOGGING-конфигурацию."""

    options = load_logging_options(base_dir)
    project_root = Path(base_dir)

    log_file = project_root / options["log_file"]
    log_file.parent.mkdir(parents=True, exist_ok=True)

    default_level = options["debug_log_level"] if debug else options["log_level"]

    handlers = {}
    root_handlers = []

    if options["enable_console"]:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "verbose" if debug else "standard",
            "level": default_level,
        }
        root_handlers.append("console")

    if options["enable_file"]:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_file),
            "maxBytes": int(options["max_bytes"]),
            "backupCount": int(options["backup_count"]),
            "encoding": "utf-8",
            "formatter": "verbose",
            "level": default_level,
        }
        root_handlers.append("file")

    if not root_handlers:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": default_level,
        }
        root_handlers.append("console")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": "platform_project.logging_setup.UTCFormatter",
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "utc_offset_hours": options["utc_offset_hours"],
            },
            "verbose": {
                "()": "platform_project.logging_setup.UTCFormatter",
                "format": (
                    "%(asctime)s %(levelname)s [%(name)s] "
                    "%(module)s.%(funcName)s:%(lineno)d | %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "utc_offset_hours": options["utc_offset_hours"],
            },
        },
        "handlers": handlers,
        "root": {
            "handlers": root_handlers,
            "level": default_level,
        },
        "loggers": {
            "django": {
                "handlers": root_handlers,
                "level": options["django_log_level"],
                "propagate": False,
            },
            "django.request": {
                "handlers": root_handlers,
                "level": "WARNING",
                "propagate": False,
            },
            "django.server": {
                "handlers": root_handlers,
                "level": options["django_log_level"],
                "propagate": False,
            },
            "django.db.backends": {
                "handlers": root_handlers,
                "level": options["sql_log_level"] if debug else "WARNING",
                "propagate": False,
            },
            "platform_app": {
                "handlers": root_handlers,
                "level": default_level,
                "propagate": False,
            },
            "platform_project": {
                "handlers": root_handlers,
                "level": default_level,
                "propagate": False,
            },
        },
    }
