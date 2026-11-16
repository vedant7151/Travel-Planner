import json
import logging

from app.core.config import LOG_LEVEL


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "agent": getattr(record, "agent", "system"),
            "trip_id": getattr(record, "trip_id", None),
            "message": record.getMessage(),
            "ts": self.formatTime(record),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("travel_planner")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    return logger


logger = setup_logging()
