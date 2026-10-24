"""Small redaction-by-construction request log: no headers, bodies or query strings."""

import logging, json
from logging.handlers import RotatingFileHandler


def request_logger(data_dir):
    logger = logging.getLogger("zerowall.requests." + str(data_dir))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            data_dir / "requests.log",
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def log_request(logger, request_id, method, route, status, elapsed_ms):
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": method,
                "route": route,
                "status": status,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )
    )
