import logging
import os


class LogCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs_by_level = {"INFO": [], "WARNING": [], "ERROR": [], "DEBUG": [], "CRITICAL": []}

    def emit(self, record):
        level = record.levelname
        msg = self.format(record)
        if level in self.logs_by_level:
            self.logs_by_level[level].append(msg)

    def get_error_logs(self, is_unique: bool = False):
        return self._get_logs(level="ERROR", is_unique=is_unique)


    def get_warning_logs(self, is_unique: bool = False):
        return self._get_logs(level="WARNING", is_unique=is_unique)


    def get_info_logs(self, is_unique: bool = False):
        return self._get_logs(level="INFO", is_unique=is_unique)
    
    def get_debug_logs(self, is_unique: bool = False):
        return self._get_logs(level="DEBUG", is_unique=is_unique)
    
    def get_critical_logs(self, is_unique: bool = False):
        return self._get_logs(level="CRITICAL", is_unique=is_unique)

    def _get_logs(self, level: str, is_unique: bool = False):
        logs = self.logs_by_level[level]
        if is_unique:
            return list(dict.fromkeys(logs))
        else:
            return logs


# Global log collector instance
_log_collector = LogCollector()


def setup_logging():
    # change the debug level based on the environment variable
    # ACTIONS_STEP_DEBUG is set to true in GitHub Actions to enable debug logging
    if os.getenv("ACTIONS_STEP_DEBUG") == "true":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    # Set up root logger
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Add our log collector
    _log_collector.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(_log_collector)


def get_log_collector():
    return _log_collector
