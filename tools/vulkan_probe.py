"""Optional: print Vulkan SDK path and whether Lavapipe ICD is visible (no downloads)."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from vulkan_env import lavapipe_icd_json, prepare_icd_env, sdk_root  # noqa: E402


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    sdk = sdk_root()
    print(f"VULKAN_SDK (resolved): {sdk or '(not set)'}")
    if sdk:
        icd = lavapipe_icd_json(sdk)
        print(f"Lavapipe ICD: {icd or '(not in SDK)'}")
        if prepare_icd_env():
            print("VK_ICD_FILENAMES set for Lavapipe/SwiftShader")
    return 0 if sdk else 1


if __name__ == "__main__":
    try:  # a redirected stdout is strict ANSI code page under -I; write '?' for what it cannot encode
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    sys.exit(main())