from degradation_curve import intensity_for_position, positions_for_n_pages, CURVES

failures = 0

def check(cond, msg):
    global failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures += 1
    print("{:5s} {}".format(status, msg))


# --- every curve must start at (or very near) 0 and end at (or very near) 1 ---
for name in CURVES:
    start = intensity_for_position(0.0, name)
    end = intensity_for_position(1.0, name)
    check(abs(start - 0.0) < 1e-9, "{}: intensity at position 0 is 0.0 (got {})".format(name, start))
    check(abs(end - 1.0) < 1e-9, "{}: intensity at position 1 is 1.0 (got {})".format(name, end))

# --- every curve must be monotonically non-decreasing (degradation never
#     un-degrades as the document progresses) ---
for name in CURVES:
    samples = [intensity_for_position(i / 100, name) for i in range(101)]
    is_monotonic = all(samples[i] <= samples[i + 1] + 1e-9 for i in range(len(samples) - 1))
    check(is_monotonic, "{}: monotonically non-decreasing across [0,1]".format(name))

# --- ease_in should be BELOW linear for most of the range (backloaded:
#     stays more readable for longer, then catches up by the end) ---
mid_linear = intensity_for_position(0.5, "linear")
mid_ease_in = intensity_for_position(0.5, "ease_in")
check(mid_ease_in < mid_linear, "ease_in is backloaded relative to linear at the midpoint ({} < {})".format(mid_ease_in, mid_linear))

mid_cubic = intensity_for_position(0.5, "ease_in_cubic")
check(mid_cubic < mid_ease_in, "ease_in_cubic is more backloaded than ease_in at the midpoint ({} < {})".format(mid_cubic, mid_ease_in))

# --- cliff should stay near-floor before cliff_at, then rise sharply ---
before_cliff = intensity_for_position(0.5, "cliff", cliff_at=0.7, floor=0.15)
after_cliff = intensity_for_position(0.85, "cliff", cliff_at=0.7, floor=0.15)
check(before_cliff <= 0.15 + 1e-9, "cliff: stays at/below floor before cliff_at (got {})".format(before_cliff))
check(after_cliff > 0.5, "cliff: rises substantially past the cliff point (got {})".format(after_cliff))

# --- out-of-range positions must raise ---
try:
    intensity_for_position(1.5, "linear")
    check(False, "position > 1 should raise ValueError")
except ValueError:
    check(True, "position > 1 raises ValueError")

try:
    intensity_for_position(0.5, "not_a_real_curve")
    check(False, "unknown curve name should raise ValueError")
except ValueError:
    check(True, "unknown curve name raises ValueError")

# --- positions_for_n_pages ---
check(positions_for_n_pages(1) == [0.0], "positions_for_n_pages(1) == [0.0]")
p5 = positions_for_n_pages(5)
check(p5[0] == 0.0 and p5[-1] == 1.0, "positions_for_n_pages(5) starts at 0.0 and ends at 1.0")
check(len(p5) == 5, "positions_for_n_pages(5) returns 5 values")
check(all(p5[i] < p5[i+1] for i in range(4)), "positions_for_n_pages returns strictly increasing values")

try:
    positions_for_n_pages(0)
    check(False, "positions_for_n_pages(0) should raise ValueError")
except ValueError:
    check(True, "positions_for_n_pages(0) raises ValueError")

print()
if failures:
    print("{} FAILURES".format(failures))
    raise SystemExit(1)
print("All degradation curve tests passed.")
