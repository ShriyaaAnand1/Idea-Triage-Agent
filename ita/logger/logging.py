import json
import logging
import os
import sys

from logging.handlers import TimedRotatingFileHandler

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "application.json.log")

os.makedirs(LOG_DIR, exist_ok=True)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(
                record,
                datefmt="%Y-%m-%d %H:%M:%S"
            ),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        extra_fields = getattr(
            record,
            "extra_fields",
            {}
        )

        log_entry.update(extra_fields)
        return json.dumps(log_entry)

logger = logging.getLogger("idea_review")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    formatter = JsonFormatter()
    stdout_handler = logging.StreamHandler( sys.stdout)
    stdout_handler.setFormatter(formatter)

    # Rolling file
    file_handler = TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)