"""Vulkan SDK discovery and optional Lavapipe ICD for headless/software testing.

Uses only environment variables and tools already on PATH. Does not download anything.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable


def sdk_root() -> str:
    """Vulkan SDK install root, or '' if unknown."""
    env = os.environ.get("VULKAN_SDK", "").strip()
    if env and Path(env).is_dir():
        return env
    spirv = shutil.which("spirv-as")
    if not spirv:
        return ""
    root = Path(spirv).resolve().parent.parent
    for name in ("spirv-as", "spirv-as.exe"):
        if (root / "Bin" / name).is_file() or (root / "bin" / name).is_file():
            return str(root)
    return ""


def _icd_dirs(sdk: str) -> Iterable[Path]:
    root = Path(sdk)
    for sub in ("Share/vulkan/icd.d", "share/vulkan/icd.d"):
        d = root / sub
        if d.is_dir():
            yield d


def lavapipe_icd_json(sdk: str) -> str:
    """Path to a Lavapipe or SwiftShader ICD manifest inside the SDK, if present."""
    for d in _icd_dirs(sdk):
        for pattern in ("lvp_icd*.json", "vk_swiftshader_icd.json"):
            for p in sorted(d.glob(pattern)):
                return str(p)
    return ""


def prepare_icd_env() -> bool:
    """If Lavapipe is bundled with VULKAN_SDK, point the loader at it. Returns whether env was changed."""
    sdk = sdk_root()
    if not sdk:
        return False
    os.environ["VULKAN_SDK"] = sdk
    icd = lavapipe_icd_json(sdk)
    if not icd:
        return False
    os.environ["VK_ICD_FILENAMES"] = icd
    bin_dir = Path(sdk) / "Bin"
    if bin_dir.is_dir():
        path = os.environ.get("PATH", "")
        prefix = str(bin_dir)
        if prefix.lower() not in path.lower():
            os.environ["PATH"] = prefix + os.pathsep + path
    return True