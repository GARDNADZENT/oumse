"""Backward-compatible safety exports for the original no-login app."""

from servicecore.safety import (
    DANGEROUS_PARTITIONS,
    PARTITION_NAME_RE,
    is_dangerous_partition,
    normalize_partition_names,
    validate_erase_targets,
    validate_partition_name,
)

__all__ = [
    "DANGEROUS_PARTITIONS",
    "PARTITION_NAME_RE",
    "is_dangerous_partition",
    "normalize_partition_names",
    "validate_erase_targets",
    "validate_partition_name",
]
