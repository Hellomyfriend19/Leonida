"""scripts/pc_readiness_gpu: automatic translator flags match make_game.py rules.

    python -I tests/test_pc_readiness_gpu.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

from pc_readiness_gpu import automatic_translator_flags, parse_vk_subgroup_stdout  # noqa: E402


class PcReadinessGpuTest(unittest.TestCase):
    def test_parse_last_json_line(self) -> None:
        raw = "noise\n{\"device\": \"GPU\", \"native64\": true}\n"
        self.assertEqual(parse_vk_subgroup_stdout(raw)["device"], "GPU")

    def test_intel_mesh_compute(self) -> None:
        info = {"driver_id": 5, "mesh_in_supported_stages": True, "native64": True,
                "per_vertex_inputs": True, "max_push_constants_size": 256}
        flags = automatic_translator_flags(info)
        self.assertIn("--mesh-compute", flags)
        self.assertNotIn("--pc-tail-ubo", flags)
        low = dict(info)
        low["max_push_constants_size"] = 128
        self.assertIn("--pc-tail-ubo", automatic_translator_flags(low))

    def test_rdna_like_clean(self) -> None:
        info = {"native64": True, "per_vertex_inputs": True, "barycentric_fallback": False,
                "max_push_constants_size": 256, "mesh_in_supported_stages": True, "driver_id": 1,
                "rdna2_amd_windows": True}
        self.assertEqual(automatic_translator_flags(info), [])

    def test_no_wave64_when_rdna_native(self) -> None:
        info = {"native64": True, "rdna2_amd_windows": True, "per_vertex_inputs": True,
                "barycentric_fallback": False, "max_push_constants_size": 256}
        self.assertNotIn("--wave64-emulate", automatic_translator_flags(info))


if __name__ == "__main__":
    unittest.main()