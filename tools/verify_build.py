"""End-of-build verification for Leonida Legacy (loader smoke, Vulkan ICD, optional GPU draw).

Called from make_game.py after the runtime stage. Does not download dependencies.
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_BUILD = os.path.join(ROOT, "runtime", "build")
SCRIPTS = os.path.join(ROOT, "scripts")

sys.path.insert(0, os.path.dirname(__file__))
from vulkan_env import prepare_icd_env, sdk_root  # noqa: E402


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run_checked(args: list[str], what: str) -> None:
    r = subprocess.run([str(a) for a in args])
    if r.returncode != 0:
        fail(f"{what} failed (exit {r.returncode})")


def build_runtime() -> None:
    ps1 = os.path.join(SCRIPTS, "build_runtime.ps1")
    if not os.path.isfile(ps1):
        fail(f"missing {ps1}")
    run_checked(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
        "build_runtime.ps1",
    )


def exe(name: str) -> str:
    path = os.path.join(RUNTIME_BUILD, name)
    if not os.path.isfile(path):
        fail(f"missing {path} (build the runtime first)")
    return path


def exe_optional(name: str) -> str | None:
    path = os.path.join(RUNTIME_BUILD, name)
    return path if os.path.isfile(path) else None


def verify_pe_loader() -> None:
    gta6rt = exe("gta6rt.exe")
    probe = subprocess.run([gta6rt, "--self-test"], capture_output=True)
    if probe.returncode == 0:
        print("PE loader: gta6rt --self-test ok")
        return
    pe = exe_optional("pe_loader_test.exe")
    tiny_dll = exe_optional("tiny_dll.dll")
    tiny_exe = exe_optional("tiny_exe.exe")
    if pe and tiny_dll and tiny_exe:
        run_checked([pe, tiny_dll, tiny_exe], "pe_loader_test")
        print("PE loader: pe_loader_test ok")
        return
    run_checked([gta6rt], "gta6rt (usage)")
    print("PE loader: gta6rt.exe present (no dedicated self-test in this build)")


def verify_vulkan() -> None:
    sdk = sdk_root()
    if sdk:
        print(f"Vulkan SDK: {sdk}")
    else:
        print("Vulkan SDK: not on PATH (set VULKAN_SDK if headers/tools are installed)")
    prepare_icd_env()
    for tool, args in (
        ("vk_bootstrap_test.exe", []),
        ("vk_descriptor_bench.exe", ["--self-test"]),
        ("vk_texture_test.exe", ["--self-test-cube-alpha"]),
    ):
        path = exe_optional(tool)
        if not path:
            continue
        run_checked([path, *args], f"{tool} {' '.join(args)}".strip())
        print(f"Vulkan: {tool} ok")
        return
    fail("no Vulkan smoke binary in runtime/build (expected vk_descriptor_bench or similar)")


def find_shader_pair(spirv_dir: str) -> tuple[str, str]:
    def pick(patterns: list[str]) -> str:
        for pat in patterns:
            hits = sorted(glob.glob(os.path.join(spirv_dir, pat)))
            if hits:
                return hits[0]
        return ""

    vs = pick(["VS_Passthrough*.spv", "VS_*.spv"])
    ps = pick(["PS_Passthrough*.spv", "PS_PassthroughCopy*.spv", "PS_*.spv"])
    if not vs or not ps:
        n = len(glob.glob(os.path.join(spirv_dir, "*.spv")))
        fail(f"need a VS and PS .spv in {spirv_dir} ({n} files); finish the shaders stage first")
    return vs, ps


def verify_gpu_draw(work: str) -> None:
    spirv = os.path.join(work, "shaders", "spirv")
    if not os.path.isdir(spirv):
        fail(f"shader output missing: {spirv}")
    vs, ps = find_shader_pair(spirv)
    out = os.path.join(work, "verify", "gpu_smoke.raw")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    harness = exe("vk_harness.exe")
    run_checked([harness, vs, ps, out, "64", "64"], "vk_harness")
    with open(out, "rb") as f:
        data = f.read()
    if len(data) < 64 * 64 * 16:
        fail("GPU smoke: output too small")
    for off in range(0, min(len(data), 4096), 4):
        if struct.unpack("<f", data[off:off + 4])[0] != -1.0:
            print(f"GPU smoke: ok ({os.path.basename(vs)} + {os.path.basename(ps)})")
            return
    fail("GPU smoke: only clear pixels (shader pipeline did not run)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True, help="build work directory (contains shaders/spirv after shader stage)")
    ap.add_argument("--require-gpu", action="store_true", help="require vk_harness draw (full build with shaders)")
    ap.add_argument("--skip-build", action="store_true", help="assume runtime/build already exists")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if not a.skip_build:
        build_runtime()
    verify_pe_loader()
    verify_vulkan()
    if a.require_gpu:
        verify_gpu_draw(work)
    print("verify_build: ok")
    return 0


if __name__ == "__main__":
    try:  # a redirected stdout is strict ANSI code page under -I; write '?' for what it cannot encode
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    sys.exit(main())