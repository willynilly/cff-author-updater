import logging


class LogCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs_by_level = {"INFO": [], "WARNING": [], "ERROR": []}

    def emit(self, record):
        level = record.levelname
        msg = self.format(record)
        if level in self.logs_by_level:
            self.logs_by_level[level].append(msg)

    def get_error_logs(self):
        return self.logs_by_level["ERROR"]

    def get_warning_logs(self):
        return self.logs_by_level["WARNING"]

    def get_info_logs(self):
        return self.logs_by_level["INFO"]


# Global log collector instance
_log_collector = LogCollector()


def setup_logging():
    # Set up root logger
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Add our log collector
    _log_collector.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(_log_collector)


def get_log_collector():
    return _log_collector
