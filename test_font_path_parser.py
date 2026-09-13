from font_path_parser import parse_font_path

# Every path below is copied verbatim from the user's own directory
# listing - this is testing against ground truth, not invented examples.
CASES = [
    ("experiments/compound/Amiri-BoldItalic_dissolution_000.ttf",
     {"base_font": "Amiri-BoldItalic", "group": "dissolution"}),

    ("experiments/compound/Systada_wave_erosion_007.ttf",
     {"base_font": "Systada", "group": "wave_erosion"}),

    ("experiments/compound/Cheiro-Regular_full_decay_003.ttf",
     {"base_font": "Cheiro-Regular", "group": "full_decay"}),

    ("experiments/sequences/Amiri-BoldItalic_jitter_seq/Amiri-BoldItalic_jitter_000.ttf",
     {"base_font": "Amiri-BoldItalic", "group": "jitter"}),

    ("experiments/sequences/Cheiro-Regular_radial_seq/Cheiro-Regular_radial_004.ttf",
     {"base_font": "Cheiro-Regular", "group": "radial"}),

    ("experiments/sequences/Amiri-Bold_asc_evap_seq/Amiri-Bold_asc_evap_003.ttf",
     {"base_font": "Amiri-Bold", "group": "asc_evap"}),

    ("experiments/static/Amiri-BoldItalic_jitter_heavy.ttf",
     {"base_font": "Amiri-BoldItalic", "group": "jitter_heavy"}),

    ("experiments/static/Amiri-BoldItalic_condense_60.ttf",
     {"base_font": "Amiri-BoldItalic", "group": "condense"}),

    ("experiments-v01/Amiri-BoldItalic_jitter10.ttf",
     {"base_font": "Amiri-BoldItalic", "group": "jitter"}),

    ("experiments-v01/Systada_condense70.ttf",
     {"base_font": "Systada", "group": "condense"}),

    ("experiments-v01/dactyl_shear20.ttf",
     {"base_font": "dactyl", "group": "shear"}),

    ("experiments-v02/fields/melt/shapeform_melt_000.ttf",
     {"base_font": "shapeform", "group": "melt"}),

    ("experiments-v02/fields/contour_phase/shapeform_contour_phase_002.ttf",
     {"base_font": "shapeform", "group": "contour_phase"}),

    ("experiments-v02/order-effects/grid_then_wave/shapeform_grid_then_wave_000.ttf",
     {"base_font": "shapeform", "group": "grid_then_wave"}),

    ("experiments-v02/order-effects/wave_then_grid/shapeform_wave_then_grid_003.ttf",
     {"base_font": "shapeform", "group": "wave_then_grid"}),

    ("experiments-v02/recovery/shear_round_trip/shapeform_shear_round_trip_000.ttf",
     {"base_font": "shapeform", "group": "shear_round_trip"}),

    ("experiments-v02/ensembles/fracture_ensemble/shapeform_fracture_ensemble_004.ttf",
     {"base_font": "shapeform", "group": "fracture_ensemble"}),

    # Systada-Regular must not be mis-parsed as base "Systada" + leftover "-Regular"
    ("experiments/compound/Systada-Regular_dissolution_000.ttf",
     {"base_font": "Systada-Regular", "group": "dissolution"}),

    # A file whose base font isn't in the known list at all - with no
    # way to know where the font name ends and the effect begins, the
    # honest fallback keeps the whole unrecognized prefix in the group
    # rather than silently guessing.
    ("experiments/compound/SomeNewFont-Regular_jitter_000.ttf",
     {"base_font": "unknown", "group": "SomeNewFont-Regular_jitter"}),
]

failures = 0
for rel_path, expected in CASES:
    result = parse_font_path(rel_path)
    ok = all(result[k] == v for k, v in expected.items())
    status = "PASS" if ok else "FAIL"
    if not ok:
        failures += 1
    print("{:5s} {}".format(status, rel_path))
    if not ok:
        print("        expected: {}".format(expected))
        print("        got:      base_font={base_font!r} group={group!r}".format(**result))

print()
if failures:
    print("{} of {} cases FAILED".format(failures, len(CASES)))
    raise SystemExit(1)
else:
    print("All {} path-parsing cases passed.".format(len(CASES)))
