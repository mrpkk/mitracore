"""Политика guard: сколько агенту можно тратить, кому и в каких сетях.

Файл политики — единственный источник правил. Всё, чего в нём нет, считается
запрещённым: пустой allowlist получателей означает «никому нельзя», а не
«любому можно». Неразобранная политика — отказ, а не тихое «разрешим».
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PolicyError(ValueError):
    """Политика не разобрана — вызывающий не запускает команду."""


def _num(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolicyError(f"{field} must be a number")
    if value < 0:
        raise PolicyError(f"{field} must be >= 0")
    return round(float(value), 6)


def _names(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise PolicyError(f"{field} must be a list of strings")
    return tuple(x.strip() for x in value if x.strip())


@dataclass(frozen=True)
class Policy:
    daily_budget_usd: float
    max_per_call_usd: float
    payees: tuple[str, ...]
    networks: tuple[str, ...]
    kill_switch: Path
    ledger: Path
    keys: Path
    agent_id: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        path = Path(path)
        try:
            data = json.loads(path.read_text("utf-8"))
        except OSError as exc:
            raise PolicyError(f"policy {path} not readable: {exc}") from exc
        except ValueError as exc:
            raise PolicyError(f"policy {path} is not JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PolicyError(f"policy {path} must be a JSON object")
        return cls.from_dict(data, path.parent)

    @classmethod
    def from_dict(cls, data: dict, base_dir: str | Path) -> "Policy":
        """Пути в политике относительны её каталогу — файл переносится целиком."""
        base = Path(base_dir)

        def path_of(key: str, default: str) -> Path:
            raw = data.get(key, default)
            if not isinstance(raw, str) or not raw.strip():
                raise PolicyError(f"{key} must be a non-empty path")
            value = Path(raw).expanduser()
            return value if value.is_absolute() else base / value

        for required in ("daily_budget_usd", "max_per_call_usd"):
            if required not in data:
                raise PolicyError(f"{required} is required")

        agent = data.get("agent_id")
        return cls(
            daily_budget_usd=_num(data["daily_budget_usd"], "daily_budget_usd"),
            max_per_call_usd=_num(data["max_per_call_usd"], "max_per_call_usd"),
            payees=_names(data.get("payees", []), "payees"),
            networks=_names(data.get("networks", []), "networks"),
            kill_switch=path_of("kill_switch", "KILL"),
            ledger=path_of("ledger", "ledger.jsonl"),
            keys=path_of("keys", "keys"),
            agent_id=str(agent) if agent else None,
        )

    def killed(self) -> bool:
        """Файл-флаг: пока файл на месте, агент стоит."""
        return self.kill_switch.exists()

    def allows_payee(self, payee: str) -> bool:
        allowed = {x.lower() for x in self.payees}
        return payee.strip().lower() in allowed
