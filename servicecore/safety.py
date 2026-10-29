from __future__ import annotations

import re
from collections.abc import Iterable

PARTITION_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

# Partitions whose erasure or overwrite can permanently brick a device or destroy
# calibration data. FRP/metadata/userdata are intentionally not listed because they
# are supported service operations; the GUI still asks for typed confirmation.
DANGEROUS_PARTITIONS = frozenset(
    {
        "boot_para",
        "bootloader",
        "efuse",
        "expdb",
        "flashinfo",
        "gpt",
        "lk",
        "lk2",
        "nvdata",
        "nvram",
        "otp",
        "pgpt",
        "preloader",
        "protect1",
        "protect2",
        "rpmb",
        "seccfg",
        "uboot",
    }
)


def normalize_partition_names(names: str | Iterable[str]) -> list[str]:
    if isinstance(names, str):
        return [names.strip()]
    return [str(name).strip() for name in names]


def validate_partition_name(name: str) -> str | None:
    """Return an error message, or None when the partition name is acceptable."""
    candidate = name.strip()
    if not candidate:
        return "Partition name is empty."
    if not PARTITION_NAME_RE.fullmatch(candidate):
        return f"Unsafe partition name: {candidate!r}."
    return None


def is_dangerous_partition(name: str) -> bool:
    return name.strip().lower() in DANGEROUS_PARTITIONS


def validate_erase_targets(names: str | Iterable[str]) -> list[str]:
    """Validate a list of erase targets and return human-readable errors."""
    targets = normalize_partition_names(names)
    errors: list[str] = []
    if not targets or all(not name for name in targets):
        return ["No partitions selected."]

    for name in targets:
        error = validate_partition_name(name)
        if error:
            errors.append(error)

    dangerous = [name for name in targets if is_dangerous_partition(name)]
    if dangerous:
        errors.append(
            "Refusing to erase critical partition(s): " + ", ".join(sorted(set(dangerous))) + "."
        )
    return errors
