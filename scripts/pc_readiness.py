r"""Check whether this PC is ready to build Leonida from your own Xbox Series copy.

    python -I scripts/pc_readiness.py
    python -I scripts/pc_readiness.py --game "D:\path\to\package"
    python -I scripts/pc_readiness.py --lang de
    python -I scripts/pc_readiness.py --lang ru --json

UI text lives in scripts/i18n/pc_readiness/<lang>.json (English default). Does not download anything and does not
read game file contents beyond names and sizes (same as make_game.py --check).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(ROOT, "tools")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import make_game  # noqa: E402
from mc_command import mc_command, install_hint as mc_install_hint  # noqa: E402
from pc_readiness_gpu import (  # noqa: E402
    automatic_translator_flags,
    other_eligible_device_names,
    parse_vk_subgroup_stdout,
)
from pc_readiness_i18n import (  # noqa: E402
    Messages,
    available_languages,
    detect_language,
    load_messages,
    normalize_lang,
)

PASS, WARN, FAIL = "pass", "warn", "fail"
DEFAULT_STAGES = ["check", "shaders", "assets", "runtime"]


class Row:
    __slots__ = ("key", "status", "title", "detail")

    def __init__(self, key: str, status: str, title: str, detail: str = "") -> None:
        self.key = key
        self.status = status
        self.title = title
        self.detail = detail

    def to_dict(self) -> dict:
        return {"key": self.key, "status": self.status, "title": self.title, "detail": self.detail}


def mark_python(m: Messages) -> Row:
    v = sys.version_info
    title = m.t("label_python")
    if v >= (3, 12):
        return Row("python", PASS, title, f"{v.major}.{v.minor}.{v.micro}")
    return Row("python", FAIL, title, m.t("python_required"))


def mark_os(m: Messages) -> Row:
    uname = platform.uname()
    label = f"{uname.system} {uname.release} ({uname.machine})"
    title = m.t("label_operating_system")
    if os.name == "nt" and uname.machine.lower() in ("amd64", "x86_64"):
        return Row("os", PASS, title, label)
    if os.name == "nt":
        return Row("os", WARN, title, label + m.t("os_warn_not_x64"))
    return Row("os", WARN, title, label + m.t("os_warn_non_windows"))


def disk_target(work: str) -> str:
    if os.path.isdir(work):
        return work
    parent = os.path.dirname(work)
    if parent and os.path.isdir(parent):
        return parent
    drive, _ = os.path.splitdrive(work)
    if drive:
        return drive + os.sep
    return os.path.expanduser("~")


def mark_disk(work: str, stages: list[str], m: Messages) -> Row:
    need_gb = sum(make_game.MIN_FREE_GB.get(s, 0) for s in stages if s in ("shaders", "assets"))
    path = disk_target(work)
    title = m.t("label_free_disk")
    try:
        free_gb = shutil.disk_usage(path).free / 2**30
    except OSError as e:
        return Row("disk", FAIL, title, f"{path}: {e}")
    detail = m.t("disk_detail", free_gib=free_gb, path=path, need_gb=need_gb, stages=", ".join(stages))
    if need_gb <= 0 or free_gb >= need_gb:
        return Row("disk", PASS, title, detail)
    if free_gb >= need_gb - make_game.MIN_FREE_GB.get("assets", 0) and "assets" in stages:
        detail += m.t("disk_loader_only_hint")
        return Row("disk", WARN, title, detail)
    return Row("disk", FAIL, title, detail)


def mark_tool_missing(key: str, label: str, hint: str) -> Row:
    return Row(key, FAIL, label, hint)


def collect_build_tools(stages: list[str], wav: bool, m: Messages) -> list[Row]:
    rows: list[Row] = []
    if "shaders" in stages:
        mc = mc_command()[0]
        resolved = mc if os.path.isfile(mc) else (shutil.which(mc) or "")
        if resolved:
            rows.append(Row("llvm-mc", PASS, "llvm-mc", resolved))
        else:
            hint = mc_install_hint().replace("\n", " ") + make_game.appdata_hint(mc)
            rows.append(mark_tool_missing("llvm-mc", "llvm-mc", hint))
        for t in ("spirv-as", "spirv-val"):
            if shutil.which(t):
                rows.append(Row(t, PASS, t, shutil.which(t) or ""))
            else:
                rows.append(mark_tool_missing(t, t, make_game.spirv_tools_hint()))
        sdk = os.environ.get("VULKAN_SDK", "").strip()
        vs_title = m.t("label_vulkan_sdk")
        if sdk and os.path.isdir(sdk):
            rows.append(Row("vulkan-sdk", PASS, vs_title, sdk))
        elif shutil.which("spirv-as"):
            rows.append(Row("vulkan-sdk", WARN, vs_title, m.t("vulkan_sdk_unset")))
        else:
            rows.append(Row("vulkan-sdk", WARN, vs_title, make_game.spirv_tools_hint()))
    if "assets" in stages:
        if make_game.dotnet_sdk_ok():
            rows.append(Row("dotnet", PASS, ".NET SDK", shutil.which("dotnet") or ""))
        else:
            rows.append(mark_tool_missing(
                "dotnet", ".NET 8 SDK", "https://dotnet.microsoft.com/download/dotnet/8.0"))
    if os.name == "nt" and "runtime" in stages:
        if make_game.visual_cpp_tools_ok():
            rows.append(Row("vs-cpp", PASS, m.t("label_vs_cpp"), m.t("vs_cpp_ok")))
        else:
            rows.append(mark_tool_missing(
                "vs-cpp", m.t("vs_cpp_missing_title"), m.t("vs_cpp_missing_detail")))
    if wav and "assets" in stages:
        if shutil.which("ffmpeg"):
            rows.append(Row("ffmpeg", PASS, "ffmpeg", shutil.which("ffmpeg") or ""))
        else:
            rows.append(mark_tool_missing("ffmpeg", "ffmpeg", "https://ffmpeg.org/download.html"))
    return rows


def soft_game_check(game: str, m: Messages) -> Row:
    title = m.t("label_game_package")
    if not os.path.isdir(game):
        return Row("game", FAIL, title, m.t("game_folder_missing", path=game))
    manifest = make_game.match_version(game)
    if not manifest:
        return Row("game", FAIL, title, m.t("game_unsupported"))
    bad = 0
    for rel, info in manifest["files"].items():
        p = os.path.join(game, rel)
        if not os.path.isfile(p) or os.path.getsize(p) != info["size"]:
            bad += 1
    exe = os.path.join(game, manifest["expected_exe"])
    if bad:
        return Row("game", FAIL, title, m.t(
            "game_bad_files", title=manifest["title"], version=manifest["version"], count=bad))
    note = m.t("game_all_ok")
    if not os.path.isfile(exe):
        note += m.t("game_exe_missing", exe=manifest["expected_exe"])
        return Row("game", WARN, title, f"{game} — {note}")
    return Row("game", PASS, title, f"{game} — {note}")


def scan_games(m: Messages) -> list[Row]:
    containers: list = []
    found = make_game.find_dumps(containers)
    rows: list[Row] = []
    if not found and not containers:
        rows.append(Row("game-scan", WARN, m.t("label_game_search"), m.t("game_scan_none")))
        return rows
    if found:
        lines = [f"{d} ({v['title']} {v['version']})" for d, v in found[:5]]
        extra = len(found) - len(lines)
        detail = "; ".join(lines)
        if extra > 0:
            detail += m.t("game_scan_extra", count=extra)
        status = PASS if len(found) == 1 else WARN
        rows.append(Row("game-scan", status, m.t("label_game_search"),
                        m.t("game_scan_found", count=len(found), detail=detail)))
    for p, h in containers[:3]:
        rows.append(Row("game-container", WARN, m.t("label_container"),
                        m.t("game_container_bad", path=p, kind=h["kind"], version=h["version"])))
    return rows


def mark_gpu(m: Messages) -> Row:
    title = m.t("label_gpu_vulkan")
    script = os.path.join(TOOLS, "vk_subgroup_info.py")
    try:
        r = subprocess.run([sys.executable, "-I", script], capture_output=True, text=True,
                           errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return Row("gpu", WARN, title, m.t("gpu_query_failed", error=e))
    data = parse_vk_subgroup_stdout(r.stdout or "")
    if not data:
        err = (r.stderr or "").strip().splitlines()
        tail = err[-1] if err else f"exit {r.returncode}"
        return Row("gpu", WARN, title, m.t("gpu_query_failed", error=tail))
    if data.get("error"):
        return Row("gpu", WARN, title, data["error"])
    name = data.get("device", "?")
    parts: list[str] = [name]
    sg_default = data.get("subgroup_size")
    sg_max = data.get("max_subgroup_size")
    if isinstance(sg_default, int) and isinstance(sg_max, int):
        parts.append(m.t("gpu_subgroup_detail", default=sg_default, max=sg_max))
    vk_filter = os.environ.get("LEONIDA_VK_DEVICE", "").strip()
    if vk_filter:
        parts.append(m.t("gpu_vk_device_filter", value=vk_filter))
    others = other_eligible_device_names(data)
    if others:
        parts.append(m.t("gpu_multi_other", names=", ".join(others)))
    auto_flags = automatic_translator_flags(data)
    if auto_flags:
        parts.append(m.t("gpu_build_auto_flags", flags=" ".join(auto_flags)))
    else:
        parts.append(m.t("gpu_build_auto_none"))
    # Human-readable notes aligned with the flags above (not a second source of truth).
    if "--mesh-compute" in auto_flags:
        parts.append(m.t("gpu_note_mesh_compute"))
    if "--wave64-emulate" in auto_flags:
        parts.append(m.t("gpu_note_wave64"))
    if "--bary-fallback" in auto_flags:
        parts.append(m.t("gpu_note_barycentric"))
    if "--f16-interp-fallback" in auto_flags:
        parts.append(m.t("gpu_note_f16_interp"))
    if "--pc-tail-ubo" in auto_flags:
        push = data.get("max_push_constants_size", 0)
        if isinstance(push, int):
            parts.append(m.t("gpu_note_push", bytes=push))
    status = WARN if auto_flags or others else PASS
    if not auto_flags and data.get("native64"):
        parts.append(m.t("gpu_good_match"))
    detail = "; ".join(parts) + m.t("gpu_boot_disclaimer")
    return Row("gpu", status, title, detail)


def overall(rows: list[Row], m: Messages) -> tuple[str, str]:
    if any(r.status == FAIL for r in rows):
        return FAIL, f"{m.t('overall_not_ready')} — {m.t('overall_not_ready_hint')}"
    if any(r.status == WARN for r in rows):
        return WARN, f"{m.t('overall_warn')} — {m.t('overall_warn_hint')}"
    return PASS, m.t("overall_pass")


def print_report(rows: list[Row], summary: str, m: Messages) -> None:
    icons = {PASS: "[OK]", WARN: "[!!]", FAIL: "[XX]"}
    print()
    print("=" * 60)
    print(m.t("report_title"))
    if m.resolved != "en":
        print(f"  (language: {m.resolved})")
    print("=" * 60)
    for r in rows:
        line = f"  {icons[r.status]}  {r.title}"
        if r.detail:
            line += f"\n       {r.detail}"
        print(line)
    print("-" * 60)
    print(f"  => {summary}")
    print()
    print(m.t("footer_legal"))
    print()


def main() -> int:
    if sys.version_info < (3, 12) and __name__ == "__main__":
        print("ERROR: Python 3.12+ required for this script.", file=sys.stderr)
        return 1
    langs = available_languages()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", metavar="DIR", help="check this package folder (names and sizes only)")
    ap.add_argument("--out", metavar="DIR", help=f"port output folder (default: {make_game.default_out()})")
    ap.add_argument("--work", metavar="DIR", help="work folder for disk check (default: <out>/work)")
    ap.add_argument("--stages", default=",".join(DEFAULT_STAGES),
                    help="stages for tool/disk checks (default: check,shaders,assets,runtime)")
    ap.add_argument("--wav", action="store_true", help="also require ffmpeg like make_game.py --wav")
    ap.add_argument(
        "--lang",
        default=None,
        metavar="CODE",
        help=f"UI language ({', '.join(langs)}; default: en, or LEONIDA_LANG)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    ap.add_argument("--skip-gpu", action="store_true", help="skip Vulkan GPU query")
    ap.add_argument("--skip-scan", action="store_true", help="do not search the PC for game copies")
    args = ap.parse_args()

    lang = args.lang if args.lang is not None else detect_language()
    if args.lang and normalize_lang(args.lang) is None:
        print(f"WARNING: unknown language {args.lang!r}; using English", file=sys.stderr)
        lang = "en"
    try:
        messages = load_messages(lang)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    for s in stages:
        if s not in make_game.STAGES:
            ap.error(f"unknown stage {s!r}")

    out = os.path.abspath(args.out or make_game.default_out())
    work = os.path.abspath(args.work or os.path.join(out, "work"))

    rows: list[Row] = [mark_os(messages), mark_python(messages)]
    rows.append(mark_disk(work, stages, messages))
    rows.extend(collect_build_tools(stages, args.wav, messages))
    if args.game:
        rows.append(soft_game_check(os.path.abspath(args.game), messages))
    elif not args.skip_scan:
        rows.extend(scan_games(messages))
    if not args.skip_gpu:
        rows.append(mark_gpu(messages))

    status, summary = overall(rows, messages)
    if args.json:
        payload = {
            "status": status,
            "summary": summary,
            "language": messages.resolved,
            "checks": [r.to_dict() for r in rows],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_report(rows, summary, messages)

    return 1 if status == FAIL else 0


if __name__ == "__main__":
    try:  # a redirected stdout is strict ANSI code page under -I; write '?' for what it cannot encode
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    sys.exit(main())