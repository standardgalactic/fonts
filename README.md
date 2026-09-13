# Procedural Typography Laboratory

A collection of custom fonts, experimental font transformations, degradation sequences, visualization tools, and document-generation utilities built on FontTools.

The project explores the idea that typography can be treated as a dynamic process rather than a fixed object. Fonts become trajectories. Glyphs become evolving structures. Documents become experiments in legibility, decay, distortion, erosion, collapse, and transformation.

---

## Repository Overview

The repository contains:

* Original fonts
* Styled variants
* Experimental transformations
* Automated sequence generators
* Compound degradation models
* HTML preview tools
* LaTeX degradation-document generators
* Diagnostic and debugging utilities

---

# Installation

## Python Dependencies

```bash
pip install fonttools
```

Optional:

```bash
pip install brotli
pip install lxml
```

For LaTeX generation:

```bash
sudo apt install texlive-full
```

or at minimum:

```bash
sudo apt install texlive-luatex
```

---

# Repository Layout

## Original Fonts

Examples:

```text
Sga-Regular.ttf
Systada-Regular.ttf
NovaMonoStandardGalactic.ttf
Cheiro-Regular.ttf
Clypto-Regular.ttf
shapeform.ttf
dactyl.ttf
```

These serve as source material for transformations.

---

## Styled Fonts

```text
styled_fonts/
```

Contains manually generated style variants:

```text
bold
italic
expand
condense
outline
shadow
```

---

## Experimental Variants

```text
experiments/static/
```

Contains one-off transformed fonts.

Examples:

```text
jitter
wave
quantize
shear
collapse
droop
dropout
asc_evap
arch / bowl
twist / pinch / fisheye
scanlines / split
attractor / repulsor / vortex
vertical_wave / gravity
tectonic / memory
```

The newer families broaden the experiment beyond affine distortion and point
noise. `arch`, `twist`, `pinch`, `fisheye`, `attractor`, and `vortex` are
continuous deformation fields. `scanlines`, `split`, and `tectonic` introduce
discontinuities or faults. `memory` moves whole contours coherently rather than
perturbing unrelated points, while `gravity` models nonlinear vertical
compression.

---

## Transformation Sequences

```text
experiments/sequences/
```

Each directory contains a progressive transformation.

Example:

```text
Sga-Regular_jitter_seq/

    Sga-Regular_jitter_000.ttf
    Sga-Regular_jitter_001.ttf
    ...
    Sga-Regular_jitter_007.ttf
```

Sequence 000 is closest to the original.

Sequence 007 is the most transformed.

These are intended for animation, visualization, or document degradation experiments.

---

## Compound Transformations

```text
experiments/compound/
```

Contains multi-stage degradation models.

Examples:

```text
full_decay
dissolution
wave_erosion
geological
event_horizon
fault_memory
crt_failure
fossil_compression
signal_possession
```

These combine multiple transformations into a single progression.

---

# Generating Experimental Fonts

Main generator:

```bash
python make_experiments.py
```

This creates:

```text
experiments/static/
experiments/sequences/
experiments/compound/
```

depending on configuration.

Generated fonts are normalized before saving to prevent coordinate overflow.

## Advanced experiment suite

The v02 runner adds ten geometrically distinct operators: perspective,
envelope, fold, fracture, wind, polarization, melt, contour phase, staircase,
and suture. It also generates paired order-effect experiments, a shear
round-trip, and seeded fracture ensembles:

```bash
python make_advanced_experiments.py CursiveGalactic-Regular.ttf
python make-experiment-index.py
```

Outputs are written to `experiments-v02/`. The runner accepts multiple source
fonts and `--steps N`; generated fonts include validation, measurements, hashes,
and provenance sidecars.

Two focused viewers accompany the suite. `experiment-matrix-viewer.html`
compares every field transformation across aligned states.
`path-dependence-viewer.html` holds source and intensity constant while
comparing wave-then-grid with grid-then-wave. Serve the repository with
`python -m http.server` before opening either page.

---

# Checking Glyph Integrity

```bash
python check-glyphs.py
```

Used to verify:

* Missing glyphs
* Broken contours
* Coordinate issues
* Encoding problems

---

# Debugging Font Generation

Logs:

```text
errors.log
detailed-errors.log
```

Common failure:

```text
Value does not fit in format h
```

This means transformed coordinates exceeded the TrueType signed 16-bit range.

The generator should normalize coordinates before writing.

---

# Previewing Fonts

## Trajectory Analysis Viewer

Build the experiment index and serve the repository locally:

```bash
python make-experiment-index.py
python -m http.server
```

Then open `experiment-analysis-viewer.html`. It provides synchronized source
and result specimens, a sequence scrubber, an overlay, provenance, and geometric
measurements. New independent sweeps emit a JSON sidecar beside every generated
font. The metadata deliberately labels these measurements as geometric; they do
not establish perceptual legibility or semantic recognition.

The sequence API distinguishes `generate_sequence` (every state is transformed
from the original source) from `generate_cumulative_sequence` (each state is
transformed from its predecessor). Both record the sequence kind and parent in
their sidecars.

## HTML Preview

Generate a visual contact sheet:

```bash
python sample_sequence.py \
    --fonts experiments/sequences/Sga-Regular_jitter_seq \
    --out preview.html
```

Open:

```bash
firefox preview.html
```

or

```bash
python -m http.server
```

then visit:

```text
http://localhost:8000
```

---

# Creating Typographic Degradation Documents

The repository includes:

```text
make_degradation_doc.py
```

This converts a sequence of fonts into a progressively mutating document.

Example:

```bash
python make_degradation_doc.py \
    --fonts experiments/sequences/Sga-Regular_jitter_seq \
    --text source.txt \
    --granularity paragraph \
    --out output
```

---

## Granularity Modes

### Paragraph

Each paragraph receives a different font.

```bash
--granularity paragraph
```

---

### Sentence

Each sentence receives a different font.

```bash
--granularity sentence
```

---

### Word

Each word receives a different font.

```bash
--granularity word
```

This often creates striking degradation effects.

---

### Page

Fonts change every simulated page.

```bash
--granularity page
```

---

# Compiling Generated Documents

After generation:

```bash
cd output
lualatex main.tex
```

Output:

```text
main.pdf
```

The PDF gradually transitions through the font sequence.

---

# Example Experiments

## Information Decay

Use:

```text
full_decay
```

to simulate archival deterioration.

---

## Geological Drift

Use:

```text
geological
```

to create slow structural mutation.

---

## Signal Corruption

Use:

```text
dropout
```

or

```text
collapse
```

to model information loss.

---

## Wave Distortion

Use:

```text
wave
```

or

```text
wave_erosion
```

to simulate transmission instability.

---

# Research Directions

Potential applications include:

* Procedural typography
* Experimental publishing
* Visual cryptography
* Artificial writing systems
* Information decay studies
* Archival aesthetics
* Legibility experiments
* Computational paleography
* Dynamic manuscripts
* Generative art

---

# Typical Workflow

Generate transformations:

```bash
python make_experiments.py
```

Inspect sequences:

```bash
python sample_sequence.py \
    --fonts experiments/sequences/Sga-Regular_jitter_seq
```

Generate a document:

```bash
python make_degradation_doc.py \
    --fonts experiments/sequences/Sga-Regular_jitter_seq \
    --text source.txt
```

Compile:

```bash
cd output
lualatex main.tex
```

Study the resulting progression from stable typography to transformed typography.

---

# License

See:

```text
LICENSE
```

for licensing information.
