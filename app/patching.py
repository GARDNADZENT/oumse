"""Backward-compatible patching exports for the original no-login app."""

from servicecore.patching import (
    MAX_FILE_SIZE,
    MAX_FILL_BYTES,
    MAX_PATCH_ENTRIES,
    FillPatch,
    PatchError,
    PatchPlan,
    PatchResult,
    SinglePatch,
    apply_plan,
    load_patch_document,
    parse_patch_document,
    patch_file,
    sha256_bytes,
    validate_plan,
)

__all__ = [
    "MAX_FILE_SIZE",
    "MAX_FILL_BYTES",
    "MAX_PATCH_ENTRIES",
    "FillPatch",
    "PatchError",
    "PatchPlan",
    "PatchResult",
    "SinglePatch",
    "apply_plan",
    "load_patch_document",
    "parse_patch_document",
    "patch_file",
    "sha256_bytes",
    "validate_plan",
]
