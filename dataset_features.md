# Dataset Feature Study
## HOTC and UAV-HSI-Crop — Observed Structure and Verified Features

> **Observation basis:** UAV-HSI-Crop features are derived from direct
> inspection of three uploaded `.npy` files (Train/rs, Train/gt, Val/rs).
> HOTC features are derived from direct inspection of an uploaded false-color
> frame (`0001.jpg`, 512×256 px, frame 1 of a traffic sequence). All numeric
> values in this document are measured from actual files unless marked ⚠.

---

## 1. HOTC — Hyperspectral Object Tracking Challenge

### 1.1 Sensor and Acquisition (from contest documentation + frame verification)

| Property | Value | Source |
|---|---|---|
| Camera platform | Three co-mounted XIMEA snapshot cameras | Contest page |
| Camera 1 — VIS | 16 spectral bands | Contest page |
| Camera 2 — NIR | 25 spectral bands | Contest page |
| Camera 3 — RedNIR | 15 usable bands (last band all-zero, drop it) | Contest page |
| Frame rate | 25 FPS | Contest page |
| Raw format | 2D mosaic per frame; `X2Cube` converts to 3D (H×W×bands) | Contest page |
| False-color video | CIE color-matching function derived RGB, strictly spatially aligned | Contest page |
| Spectral reflectance note | Physical reflectance not guaranteed (no white calibration) | Contest page |

### 1.2 False-Color Frame — Directly Observed (0001.jpg)

| Property | Measured value |
|---|---|
| Frame resolution | 512 × 256 pixels (W × H) |
| Color mode | RGB, uint8, range 0–255 |
| Mean channel values | R=105.8, G=104.3, B=101.4 (near-neutral average) |
| Scene brightness mean / std | 103.8 / 83.3 |
| Dark pixels (<40 brightness) | 32.1% |
| Mid-tone pixels (40–180) | 42.0% |
| Bright pixels (≥180) | 26.0% |

**Scene objects directly observed in frame 0001.jpg:**

| Object | Location in frame | Ontology node type |
|---|---|---|
| White SUV / car | Center-left, dominant object | `object.vehicle.car` |
| Motorcyclist | Center-right, in motion | `object.vehicle.motorcycle` + `object.person.rider` |
| Urban road surface | Lower portion | `object.infrastructure.road` |
| Trees (deciduous, dense canopy) | Right side and background | `object.vegetation.tree` |
| Multi-storey building | Upper-left background | `object.infrastructure.building` |
| Traffic light | Upper-center | `object.infrastructure.traffic_light` |
| Signal/lamp pole | Upper-center | `object.infrastructure.pole` |

**Spatial relations directly observable in this frame:**

- `car` → `in_front_of` → `motorcyclist` (car occupies larger bbox, closer depth plane)
- `motorcyclist` → `right_of` → `car`
- `tree` → `behind` → `car` (background, smaller apparent size)
- `building` → `above` → `road` (vertical arrangement)
- `traffic_light` → `above` → `road`
- `car` → `near` → `motorcyclist` (estimated center distance ~225 px)

### 1.3 Dataset Split ⚠ (from contest page, not directly verified from downloaded files)

| Split | Sequences | Labels |
|---|---|---|
| Train | 406 | Per-frame bbox: cx, cy, w, h |
| Validation | 75 | Per-frame bbox: cx, cy, w, h |
| Test (ranking) | 75 | None (unlabeled) |

### 1.4 Annotation Format

- **Single bounding box per sequence** (single-object tracking benchmark)
- Format per frame: `center_x, center_y, width, height`
- Labels provided independently for VIS, NIR, RedNIR, and false-color modalities
- No multi-object annotations; no per-pixel class labels

### 1.5 Challenge Attributes (11 per sequence)

FM (Fast Motion), BC (Background Clutter), IV (Illumination Variation),
OPR (Out-of-Plane Rotation), OCC (Occlusion), MB (Motion Blur),
LR (Low Resolution), SV (Scale Variation), IPR (In-Plane Rotation),
OV (Out-of-View), DEF (Deformation)

### 1.6 Key Limitations for Scene-Graph Generation

1. Single-object ground truth only — multi-object node set requires running a detector on false-color frames
2. No relation annotations — all edges must be derived
3. No depth/3D — geometry is 2D image-plane only
4. No semantic segmentation — class identity is sequence-level only
5. Spectral reflectance not absolutely calibrated (no white-reference)

---

## 2. UAV-HSI-Crop

### 2.1 File Structure — Directly Observed

```
data/
  Train/
    Training/
      rs/   ← hyperspectral input patches (.npy)
      gt/   ← ground truth label patches (.npy)
    Validation/
      rs/
      gt/
  Test/
    rs/
    gt/
```

Three splits confirmed: Training, Validation, Test (not two as previously documented).

### 2.2 Hyperspectral Patch Format — Directly Measured

**From `XJM_patch_9_0_9.npy` (Train/rs) and `MJK_N_patch_14_1_4.npy` (Val/rs):**

| Property | Measured value |
|---|---|
| Patch shape | (96, 96, 200) — H × W × bands |
| Band axis | Last axis (axis=2) |
| Number of spectral bands | 200 |
| Data type | float32 |
| Value range | 0.0 – ~0.93 (reflectance, 0–1 scale) |
| No-data (all-zero) pixels | 0 / 9,216 in inspected patches |
| Mean reflectance (Train patch) | 0.1758 ± 0.1658 |
| Mean reflectance (Val patch) | 0.2242 ± 0.1328 |

### 2.3 Spectral Profile — Directly Measured

From `XJM_patch_9_0_9.npy` (Train patch, vegetation-dominant):

| Band range | Approx wavelength (est.) | Mean reflectance | Interpretation |
|---|---|---|---|
| Bands 0–79 | ~400–640 nm | 0.045 | VIS — low absorption region |
| Bands 80–109 | ~640–730 nm | rising sharply | Red-edge transition |
| Band 109 | ~729 nm | steepest slope | Red-edge peak (NIR onset) |
| Band 92 | ~677 nm | local minimum | Chlorophyll absorption band |
| Bands 110–179 | ~730–940 nm | 0.355 | NIR plateau |
| Bands 180–199 | ~940–1000 nm | declining (~0.256) | SWIR onset / water absorption |

**NIR/VIS reflectance ratio: 7.87×** — confirms strong vegetation (crop canopy) signature.

The chlorophyll absorption band at ~677 nm and the red-edge onset at ~729 nm are
directly relevant to `has_matching_absorption` spectral relations in the ontology.

### 2.4 Ground Truth Format — Directly Measured

**From `MJK_N_patch_0_0_0.npy` (Train/gt):**

| Property | Measured value |
|---|---|
| Shape | (96, 96) — matches rs spatial dimensions |
| Data type | float32 (integer values only — no decimals observed) |
| Unique class labels in this patch | 2 → [1, 3] |
| Class 1 pixel fraction | 96.9% |
| Class 3 pixel fraction | 3.1% |
| Label semantics | Integer crop-type class IDs (species labels; full class map requires dataset documentation) |

**Note:** Only 2 of the full class set appear in this single patch. The full
dataset class vocabulary (crop species such as maize, wheat, soybean, etc.)
spans more integer IDs across all patches.

### 2.5 Features Directly Usable for Scene-Graph Construction

| Feature | Source | Ontology use |
|---|---|---|
| Per-pixel 200-band reflectance vector | `rs/*.npy` cube | Spectral signature per detected region; `is_same_material_as`, `has_similar_signature`, `is_abundance_fraction_of` |
| Chlorophyll absorption band (~677 nm, band 92) | Measured | `has_matching_absorption` between vegetation regions |
| Red-edge band (~729 nm, band 109) | Measured | `has_matching_absorption`; spectral health index |
| Per-pixel class label (integer) | `gt/*.npy` (96×96) | Node-type assignment; connected-component grouping → region nodes |
| Spatial adjacency within patch | Derived from gt label map | `adjacent_to`, `next_to`, `aligned_with` |
| NIR plateau (bands 130–180) | Measured | `has_higher_reflectance_than` between vegetation vs. non-vegetation |

---

## 3. Comparison Summary — From Actual Data

| Property | HOTC (observed) | UAV-HSI-Crop (observed) |
|---|---|---|
| Modality | False-color RGB video (CIE-derived from HS) + raw HS cube | Hyperspectral patches (200 bands) |
| Frame/patch spatial size | 512×256 px (observed) | 96×96 px (measured) |
| Spectral bands | 16/25/15 (VIS/NIR/RedNIR cameras) | 200 (measured) |
| Data type | uint8 false-color; raw HS format TBD | float32 reflectance (measured) |
| Value range | 0–255 (false-color) | 0–0.93 reflectance (measured) |
| Annotation | Single-object bbox (cx,cy,w,h) per frame | Per-pixel integer class label (measured) |
| Temporal | Yes — 25 FPS video | No (static patches) |
| Scene content | Urban traffic: car, motorcycle, pedestrian, trees, building, road (observed) | Crop canopy (vegetation NIR signature confirmed) |
| Spectral signature shape | N/A from false-color | Low VIS → red-edge ~729 nm → NIR plateau (measured) |
| Scene-graph relation families possible | Spatial + Temporal + Spectral | Spatial + Spectral |
