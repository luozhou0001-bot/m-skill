from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

SeverityName = Literal["blocker", "major", "minor"]
POLICY_FILE = "mskill.toml"
_ALLOWED_SEVERITIES: tuple[SeverityName, ...] = ("blocker", "major", "minor")
_ALLOWED_POLICY_KEYS = {"fail_on", "require_complete"}
_ALLOWED_TOP_LEVEL_KEYS = {"policy"}


class PolicyError(ValueError):
    """Raised when mskill.toml cannot be parsed or validated."""


@dataclass(frozen=True)
class Policy:
    fail_on: tuple[SeverityName, ...] = ("blocker",)
    require_complete: bool = False
    source: str = "defaults"

    def blocks(self, severity: object) -> bool:
        return severity in self.fail_on

    def summary(self) -> str:
        fail_on = ",".join(self.fail_on) if self.fail_on else "none"
        return f"source={self.source}; fail_on={fail_on}; require_complete={str(self.require_complete).lower()}"


def _normalize_fail_on(value: object) -> tuple[SeverityName, ...]:
    if not isinstance(value, list):
        raise PolicyError("policy.fail_on must be an array of severity strings")

    selected: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise PolicyError(f"policy.fail_on[{index}] must be a string")
        if item not in _ALLOWED_SEVERITIES:
            allowed = ", ".join(_ALLOWED_SEVERITIES)
            raise PolicyError(
                f"invalid policy.fail_on severity {item!r}; expected one of: {allowed}"
            )
        selected.add(item)

    return tuple(severity for severity in _ALLOWED_SEVERITIES if severity in selected)


def load_policy(root: Path) -> Policy:
    path = root / POLICY_FILE
    if not path.exists():
        return Policy()

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise PolicyError(f"invalid TOML in {POLICY_FILE}: {exc}") from exc
    except OSError as exc:
        raise PolicyError(f"cannot read {POLICY_FILE}: {exc}") from exc

    if not isinstance(data, dict):
        raise PolicyError(f"{POLICY_FILE} must contain a TOML table")

    unknown_top_level = sorted(set(data) - _ALLOWED_TOP_LEVEL_KEYS)
    if unknown_top_level:
        raise PolicyError(
            f"unknown top-level key(s) in {POLICY_FILE}: {', '.join(unknown_top_level)}"
        )

    raw_policy = data.get("policy", {})
    if not isinstance(raw_policy, dict):
        raise PolicyError("[policy] must be a TOML table")

    unknown_policy = sorted(set(raw_policy) - _ALLOWED_POLICY_KEYS)
    if unknown_policy:
        raise PolicyError(
            f"unknown policy key(s): {', '.join(unknown_policy)}"
        )

    fail_on: tuple[SeverityName, ...] = ("blocker",)
    if "fail_on" in raw_policy:
        fail_on = _normalize_fail_on(raw_policy["fail_on"])

    require_complete = raw_policy.get("require_complete", False)
    if not isinstance(require_complete, bool):
        raise PolicyError("policy.require_complete must be a boolean")

    return Policy(
        fail_on=fail_on,
        require_complete=require_complete,
        source=POLICY_FILE,
    )
