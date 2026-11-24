"""Predict make_game.py shader flags from vk_subgroup_info JSON (read-only, no game data)."""
from __future__ import annotations

import json

# make_game.VK_DRIVER_ID_INTEL_PROPRIETARY_WINDOWS — Intel igvk64.dll.
INTEL_WIN_VULKAN_DRIVER = 5


def parse_vk_subgroup_stdout(stdout: str) -> dict:
    """Last JSON line from tools/vk_subgroup_info.py (same rule as make_game.runtime_gpu_info)."""
    lines = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    if not lines:
        return {}
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _mesh_compute_enabled(info: dict) -> bool:
    return (
        info.get("driver_id") == INTEL_WIN_VULKAN_DRIVER
        and bool(info.get("mesh_in_supported_stages"))
    )


def _wave64_emulate_auto(info: dict, *, mesh_compute: bool) -> bool:
    """Whether make_game wave64_settings('auto') would turn emulation on (best effort, no vulkaninfo)."""
    rdna1 = bool(info.get("rdna1_amd_windows"))
    mesh_supported = info.get("mesh_in_supported_stages")
    compute_only = mesh_compute or (rdna1 and mesh_supported is False)
    if compute_only:
        native = info.get("native64_compute", info.get("native64"))
    else:
        native = info.get("native64")
    if native and (rdna1 or info.get("rdna2_amd_windows")):
        return False
    if native:
        return False
    # Probe could not confirm native wave64, or subgroup path is not 64-wide — same safe default as make_game.
    return True


def automatic_translator_flags(info: dict) -> list[str]:
    """Flags make_game.py turns on automatically for the shader stage (subset of FALLBACK_FLAGS)."""
    if info.get("error"):
        return []
    flags: list[str] = []
    mesh_compute = _mesh_compute_enabled(info)
    if mesh_compute:
        flags.append("--mesh-compute")
    if _wave64_emulate_auto(info, mesh_compute=mesh_compute):
        flags.append("--wave64-emulate")
    if info.get("per_vertex_inputs") is False:
        flags.append("--f16-interp-fallback")
    if info.get("barycentric_fallback") is True:
        flags.append("--bary-fallback")
    need_pc = 152 if mesh_compute else 144
    max_pc = info.get("max_push_constants_size")
    if isinstance(max_pc, int) and max_pc < need_pc:
        flags.append("--pc-tail-ubo")
    return flags


def other_eligible_device_names(info: dict, *, limit: int = 4) -> list[str]:
    """Other Vulkan devices that passed the runtime filter (multi-GPU laptops)."""
    chosen = info.get("device")
    names = info.get("eligible_devices") or []
    out: list[str] = []
    for entry in names:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name or name == chosen:
            continue
        out.append(name)
        if len(out) >= limit:
            break
    return out