import logging

from app import config

_CONFIGURED = False


def setup(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s  %(name)-10s  %(message)s",
            datefmt="%H:%M:%S",
        )

        logging.getLogger("httpx").setLevel(logging.WARNING)
        _CONFIGURED = True
    return logging.getLogger(name)
