import json
import sys

from loguru import logger


def serialize(record):
    subset = {
        "name": record["name"],
        "module": record["module"],
        "message": record["message"],
        "line": record["line"],
        "exception": record["exception"],
        "level_name": record["level"].name,
        "file_path": record["file"].path,
        "time": str(record["time"]),
    }
    return json.dumps(subset)


def patching(record):
    record["extra"]["serialized"] = serialize(record)


# logger = logger.patch(patching)
# logger.add(sys.stdout, format="{extra[serialized]}")
