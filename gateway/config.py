"""Central configuration loading and runtime validation."""
from dataclasses import asdict, dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class BatchConfig:
    target_parts: int = 20
    queue_capacity: int = 4
    production_ms: int = 500
    inspection_ms: int = 1200
    reject_modulus: int = 5
    reject_offset: int = 0

    def __post_init__(self):
        limits = {
            "target_parts": (1, 10000), "queue_capacity": (1, 1024),
            "production_ms": (1, 60000), "inspection_ms": (1, 60000),
            "reject_modulus": (1, 1000000), "reject_offset": (0, 1000000),
        }
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} must be an integer between {low} and {high}")

    def as_dict(self):
        return asdict(self)


def load_config(path: str | Path) -> dict:
    with open(path, "rb") as stream:
        config = tomllib.load(stream)
    BatchConfig(**config["production"])
    link = config["communication"]
    for key in ("ack_timeout_s", "completion_grace_s", "heartbeat_timeout_s", "reconnect_s"):
        if not 0.1 <= link[key] <= 30:
            raise ValueError(f"{key} must be between 0.1 and 30 seconds")
    if not 1 <= link["max_attempts"] <= 10:
        raise ValueError("max_attempts must be between 1 and 10")
    return config
