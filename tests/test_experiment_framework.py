import json
import tempfile
import unittest
from pathlib import Path

import make_experiments as experiments
from advanced_experiments import TRANSFORMS
from experiment_support import measure_font, sha256_file, validate_font


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shapeform.ttf"


class ExperimentFrameworkTests(unittest.TestCase):
    def test_seeded_transform_serializes_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = [Path(directory) / name for name in ("one.ttf", "two.ttf")]
            for output in outputs:
                font = experiments.load_font(SOURCE)
                experiments.apply_tectonic(font, 80, seed=17)
                self.assertTrue(experiments.save_font(font, output))
            self.assertEqual(sha256_file(outputs[0]), sha256_file(outputs[1]))

    def test_sequence_emits_reopenable_fonts_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            experiments.generate_sequence(
                SOURCE, out, "arch", experiments.apply_arch, (0.0, 1.0), 3
            )
            sidecars = sorted(out.glob("*.json"))
            self.assertEqual(len(sidecars), 3)
            record = json.loads(sidecars[-1].read_text(encoding="utf-8"))
            self.assertEqual(record["sequence_kind"], "independent_sweep")
            self.assertEqual(record["step"], 2)
            self.assertEqual(record["claim_scope"], "geometric")
            generated = experiments.load_font(sidecars[-1].with_suffix(".ttf"))
            self.assertEqual(validate_font(generated), [])

    def test_measurements_have_explicit_geometry_fields(self):
        font = experiments.load_font(SOURCE)
        measurements = measure_font(font)
        self.assertGreater(measurements["points"], 0)
        self.assertGreater(measurements["total_contour_length"], 0)
        self.assertIsNotNone(measurements["bounding_box"])

    def test_advanced_transforms_serialize(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, (operation, (_, maximum)) in TRANSFORMS.items():
                output = Path(directory) / f"{name}.ttf"
                font = experiments.load_font(SOURCE)
                operation(font, maximum)
                self.assertTrue(experiments.save_font(font, output), name)

    def test_transform_order_changes_geometry(self):
        first = experiments.load_font(SOURCE)
        experiments.apply_wave(first, 90, 1.7)
        experiments.apply_quantize(first, 36)
        second = experiments.load_font(SOURCE)
        experiments.apply_quantize(second, 36)
        experiments.apply_wave(second, 90, 1.7)
        first_coords = list(next(experiments.iter_simple_glyphs(first))[1].coordinates)
        second_coords = list(next(experiments.iter_simple_glyphs(second))[1].coordinates)
        self.assertNotEqual(first_coords, second_coords)


if __name__ == "__main__":
    unittest.main()
