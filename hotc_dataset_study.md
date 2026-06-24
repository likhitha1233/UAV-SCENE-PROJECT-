# WHISPERS / HOT Dataset Study
# Annotation Design, Objects, and Relations

Prepared from: direct file inspection, benchmark paper (Xiong et al. 2018),
contest documentation (hsitracking.com), and literature review across
HOT2020 through HOT2026 tracker papers.

---

## Critical Finding

The HOTC/HOT dataset contains NO pairwise object relations. It was designed
exclusively for single-object tracking. Every sequence tracks exactly one
object; the ground truth is a sequence of bounding boxes for that one object.
There is no second object, no pair, and therefore no relation annotations in
the dataset.

This is not a gap or oversight -- it is the design intent. The paper that
created the benchmark (Xiong, Zhou, and Qian, 2018) frames the problem as:
"detect the size and location of an object in video frames given a bounding
box in the first frame."

What the dataset annotates that is relation-relevant for scene graph work
are 19 challenge attributes -- binary flags per sequence describing how the
target interacts with its context (e.g. OCC = the target is occluded by
something, BC = background shares appearance with the target, OSC = another
object has a similar colour). These are indirect relational cues, not
explicit edge annotations.

---

## Section 1 -- Annotation Design

### 1.1 Ground Truth File Format

    groundtruth.txt  (one file per sequence)

    Fields per line:
      center_x  -- horizontal centre of bounding box (pixels)
      center_y  -- vertical centre of bounding box (pixels)
      width     -- width of bounding box (pixels)
      height    -- height of bounding box (pixels)

    Delimiter  : comma (original MHT paper); space also used in later
                 contest distributions -- verify on your local files
    Lines      : one per frame; line N corresponds to frame N
    Targets    : one per sequence (single-object tracking only)

First-frame convention: the bounding box on line 1 initialises the tracker.
All tracker evaluation is measured from frame 2 onwards.

### 1.2 Annotation Process

Source: Xiong, Zhou, and Qian (2018), Section II-B.

1. Three human volunteers independently drew bounding boxes frame by frame
   for each sequence.
2. One domain expert reviewed all boxes and adjusted them where necessary.
3. The hyperspectral video and the false-color video were labelled
   independently -- not by projecting HS boxes onto the RGB frames. Minor
   spatial offsets between the two label sets may exist.
4. Labels are provided per modality:
     vis-groundtruth.txt
     nir-groundtruth.txt
     rednir-groundtruth.txt
     color-groundtruth.txt

### 1.3 Sequence Naming Convention (HOT2026)

Based on four examples cited in the literature:
  FM-Bicycle-001, SV-Bus-001, POC-Person-006, SOB-Car-004

Pattern: {ATTRIBUTE}-{CATEGORY}-{INDEX}

The dominant challenge attribute is encoded as the sequence name prefix.
Abbreviations observed: FM = Fast Motion, SV = Scale Variation,
POC = Partial Occlusion, SOB = Small Object.

NOTE: This convention is inferred from four examples only. It may not apply
to all HOT2026 sequences. Verify against your local folder listing.

### 1.4 File Structure per Sequence

    {modality}-{category}-{index}/
      HSI/             -- raw 2D mosaic frames (.jpg or .png)
      falsecolor/      -- CIE-derived RGB frames (.jpg)
      groundtruth.txt
      attributes.txt   -- binary vector, one value per challenge attribute

### 1.5 Sensor and Modality Details

Three co-mounted XIMEA snapshot cameras:

    Camera      Bands   Wavelength range    Notes
    VIS         16      ~460-600 nm         Primary tracking modality
    NIR         25      ~665-960 nm
    RedNIR      16      ~600-850 nm         Drop the last band (all-zero)

Frame rate: 25 FPS
Spatial resolution: 512 x 256 pixels (confirmed from uploaded frame 0001.jpg)
Raw format: 2D mosaic per frame; X2Cube converts to 3D (H x W x bands)
False-color: CIE color-matching function derived RGB; strictly spatially
             aligned with the HS cube

Calibration note: Dark calibration (subtract dark frame) and spectral
correction (sensor-specific matrix) are applied. White calibration is NOT
performed, so spectral reflectance values do not correspond to absolute
physical surface reflectance.

---

## Section 2 -- Relations in the Dataset

### 2.1 Native Annotations -- No Pairwise Relations

The dataset has zero pairwise object-to-object relation labels. There are
no edge annotations, no triplets, and no spatial, spectral, or temporal
relations between objects. All such relations must be derived.

### 2.2 Challenge Attributes as Implicit Relational Cues

The 19 binary per-sequence flags describe how the target object relates to
its context. Each attribute implies a specific type of relation that a scene
graph should capture:

    Code  Full name                        Implied relation type
    ----  -------------------------------- ----------------------------------------
    IV    Illumination Variation           spectral_signature_correlates_with
                                           (scene-wide illumination shift)
    SV    Scale Variation                  in_front_of / behind changes over time
    OCC   Occlusion                        is_occluded_by (another object)
    DEF   Deformation                      stationary_relative_to breaks down
    MB    Motion Blur                      bounding box spatial uncertainty
    FM    Fast Motion                      is_accelerating_relative_to
    IPR   In-Plane Rotation                aligned_with direction changes
    OPR   Out-of-Plane Rotation            appearance change (3D rotation)
    OV    Out-of-View                      target exits frame boundary
    BC    Background Clutter               has_similar_signature (target vs bg)
    LR    Low Resolution                   unreliable spectral signature extraction
    CM    Camera Motion (HOT2023+)         spatial relations require ego-motion
                                           correction
    REF   Reflections (HOT2023+)           has_similar_signature (artifact,
                                           not material match)
    ST    Small Target (HOT2023+)          proximity relations hard to compute
    TRA   Transparency (HOT2023+)          is_abundance_fraction_of (mixed spectrum)
    LL    Low Light (HOT2023+)             low SNR spectral signatures
    LC    Low Contrast (HOT2023+)          is_spectrally_anomalous_relative_to
                                           near threshold
    OSC   Objects with Similar Color       has_similar_signature between objects
          (HOT2023+)
    RLV   Red-NIR Low Visibility           cross-modal is_same_material_as breaks
          (HOT2023+)
    TOL   Turned Off Lights (HOT2023+)     scene-wide spectral shift (lights off)

HOT2020 used attributes IV through LR (11 attributes).
HOT2022 added CM (12 total).
HOT2023 and HOT2026 use all 19 listed above.

---

## Section 3 -- Complete Set of Objects

Objects are defined at the sequence level -- one object per sequence, not
per frame. Categories are compiled from HOT2020 through HOT2026 literature.

### 3.1 Traffic and Vehicles (outdoor)

    Object           Observed in          Notes
    ---------------  -------------------  -----------------------------------
    Car              HOT2020, 2023, 2026  Most common; estimated ~50% of
                                          all sequences
    Bicycle          HOT2026              e.g. FM-Bicycle-001
    Bus              HOT2026              e.g. SV-Bus-001
    Motorcycle       HOT2023, 2026        Tracked with or without rider
    Rider            HOT2023 NIR          Person on motorcycle, tracked as
                                          one unit (nir-rider17)
    Airplane         HSSV, extended       Aviation surveillance scenario
    Boat / Ship      HSSV, extended       Navigation surveillance scenario
    Electric car     HSSV                 Urban traffic scenario

### 3.2 People

    Object           Observed in          Notes
    ---------------  -------------------  -----------------------------------
    Person /         HOT2020, 2023, 2026  Walking or standing; POC-Person-006
    Pedestrian
    Face             HOT2020              Close-range face tracking
    Hand             HOT2020              Close-range hand tracking
    Student          WHISPER2020          Campus / classroom setting
    Rider            HOT2023 NIR          Person riding motorcycle

### 3.3 Animals

    Object           Observed in          Notes
    ---------------  -------------------  -----------------------------------
    Kangaroo         HOT2020              Zoo or wildlife setting
    Bird             Extended literature  Not confirmed in contest sequences
    Dog              Referenced in        Not confirmed in HOT contest files
                     original prompt

### 3.4 Indoor and Generic Objects

    Object           Observed in
    ---------------  ---------------------------------
    Board            HOT2020, HOT2023 (vis-board)
    Toy              HOT2020, HOT2023 (vis-toy2)
    Playing card     HOT2020, HOT2023 (vis-card19)
    Dice             HOT2023 (vis-dice2, rednir-dice2)
    Ball / Mirror    HOT2023 (rednir-ball-mirror9)
    Basketball       HOT2020
    Coke (can)       HOT2020
    Soda can         WHISPER2020
    Coin             WHU-Hi-H3 dataset
    Bracelet         WHU-Hi-H3 dataset
    Bag              WHU-Hi-H3 dataset
    Fruit            WHISPER2020
    Paper            WHISPER2020
    Bottle / Cup     Extended literature

### 3.5 Background Scene Regions (not tracked; context only)

These objects appear in the scene but are NOT annotated in HOT. They would
become non-target nodes in a derived scene graph. Confirmed from direct
inspection of the uploaded HOTC false-color frame (0001.jpg):

    Region                  Confirmed
    ----------------------  ------------------------------------------
    Urban road surface      Confirmed (lower portion of frame)
    Trees (deciduous)       Confirmed (right side and background)
    Building (multi-storey) Confirmed (upper-left background)
    Traffic light           Confirmed (upper-centre)
    Lamp / signal pole      Confirmed (upper-centre)
    Sky                     Confirmed (top strip)

Additional background regions observed in literature but not in this frame:
    Parking area, sidewalk, lane markings, vegetation strips.

### 3.6 HOD3K Related Dataset (same XIMEA camera, same resolution)

The HOD3K dataset uses the same XIMEA VIS camera and annotates three
object classes across 3,242 hyperspectral images:

    Class       Count    Notes
    ----------  -------  ----------------------------------------
    People      12,144   Dominant class
    Bicycles     2,188
    Cars           817

This multi-object annotation style is what a scene graph layer built on top
of HOTC false-color frames would need to replicate.

---

## Section 4 -- Complete Set of Derivable Relations

Since HOTC has no built-in relation annotations, all relations must be
derived from the available data signals. The table maps each relation to
its source.

### 4.1 Spatial Relations (intra-frame, from bounding boxes)

    Relation                    Source signal
    --------------------------  ------------------------------------------
    near / far_from             Distance between bbox centres
    next_to                     Adjacent bboxes, minimal vertical offset
    above / below               Relative vertical position with horizontal
                                overlap between bboxes
    left_of / right_of          Relative horizontal position with vertical
                                overlap
    in_front_of / behind        Relative bbox area (larger = nearer camera
                                on a flat ground-plane scene)
    overlapping                 IoU > 0 between target and context object
    inside / contains           One bbox fully within another
    on_top_of / supports        Target bbox bottom touches another object's
                                top with horizontal overlap
    aligned_with                Centers approximately collinear (parking
                                row, lane alignment)
    adjacent_to                 Regions share a boundary (road/sidewalk,
                                field/path)

### 4.2 Temporal Relations (cross-frame, from target trajectory)

    Relation                    Source signal
    --------------------------  ------------------------------------------
    is_next_position_of         Consecutive frames, same track -- directly
                                given by groundtruth.txt
    is_previous_position_of     Reverse of above
    same_track_as               Same track_id bridging a detection gap
                                (OCC-flagged sequences)
    co_occurs_with              Two detected objects both visible over
                                overlapping frame range
    moves_toward                Decreasing centre-to-centre distance over
                                time
    moves_away_from             Increasing centre-to-centre distance over
                                time
    stationary_relative_to      Near-constant relative distance between
                                two objects
    is_accelerating_relative_to Rate of distance change increasing (FM
                                attribute sequences)
    is_decelerating_relative_to Rate of distance change decreasing
    is_occluded_by              OCC flag + overlapping bbox at gap start;
                                the OCC attribute implicitly annotates this
    occludes                    Inverse of is_occluded_by

### 4.3 Spectral Relations (from HS cube per frame)

    Relation                         Source signal
    -------------------------------  ----------------------------------------
    is_same_material_as              SAM angle below strict threshold between
                                     two objects' mean spectral signatures
    has_similar_signature            SAM angle in moderate range; BC and OSC
                                     attribute sequences indicate this
                                     is likely present
    is_endmember_of                  Object signature identified as a pure
                                     material via N-FINDR or VCA unmixing
    has_abundance_fraction_of        NNLS unmixing; TRA (transparency)
                                     sequences are particularly relevant
    has_matching_absorption          Shared local reflectance minima at the
                                     same band index (e.g. chlorophyll
                                     absorption in vegetation, water
                                     absorption features)
    has_higher_reflectance_than      Comparative band-mean reflectance
    has_lower_reflectance_than       Inverse of above
    is_spectrally_anomalous_         Large SAM angle versus scene average;
    relative_to                      flags camouflaged or unexpected targets
    spectral_signature_              Shared illumination drift over time;
    correlates_with                  IV-flagged sequences are candidates

### 4.4 Semantic and Domain Relations (from object class and motion state)

    Relation          Applicable when
    ----------------  --------------------------------------------------
    parked_near       Vehicle class + stationary_relative_to + spatially
                      near infrastructure
    waiting_at        Person or vehicle stationary near traffic light or
                      crossing region
    crossing          Pedestrian track crosses road region
    yields_to         Slower vehicle decelerating relative to faster
                      approaching vehicle
    belongs_to_lane   Vehicle bbox within annotated lane region
    carries           Small object bbox stationary on larger vehicle bbox
    controls          Traffic light region spatially above intersection

---

## Section 5 -- Observed Frame Statistics (from uploaded 0001.jpg)

    Property                   Value
    -------------------------  ------------------------------------------
    Frame resolution           512 x 256 pixels (W x H)
    Colour mode                RGB, uint8, range 0-255
    Mean channel values        R = 105.8, G = 104.3, B = 101.4
    Scene brightness mean/std  103.8 / 83.3
    Dark pixels (< 40)         32.1 percent
    Mid-tone pixels (40-180)   42.0 percent
    Bright pixels (>= 180)     26.0 percent

Objects identified in this frame with their ontology node types:

    Object                  Location in frame          Ontology type
    ----------------------  -------------------------  ---------------------------
    White SUV               Centre-left, dominant      object.vehicle.car
    Motorcyclist            Centre-right, in motion    object.vehicle.motorcycle
    Person on motorcycle    Centre-right               object.person.rider
    Road surface            Lower portion              object.infrastructure.road
    Trees (deciduous)       Right side and background  object.vegetation.tree
    Multi-storey building   Upper-left background      object.infrastructure.building
    Traffic light           Upper-centre               object.infrastructure.traffic_light
    Signal pole             Upper-centre               object.infrastructure.pole

Spatial relations directly observable in this single frame:

    car       in_front_of   motorcyclist   (car projects larger, closer plane)
    car       near          motorcyclist   (estimated centre distance ~225 px)
    rider     right_of      car
    tree      behind        car            (background, smaller apparent area)
    building  above         road           (vertical arrangement)
    traffic_light  above   road

---

## Section 6 -- Assumptions and Uncertain Observations

Items marked ASSUMED or UNRESOLVED should be verified against actual files
in your HOT2026 Google Drive folder before being used as ground truth.

    Item                                 Status    Basis
    -----------------------------------  --------  ---------------------------
    Sequence naming convention           ASSUMED   Inferred from 4 example
    (ATTR-CATEGORY-INDEX for HOT2026)              names in one paper only
    Complete category list for           PARTIAL   Compiled from HOT2020-2024
    HOT2026 specifically                           literature; HOT2026 full
                                                   sequence list not publicly
                                                   documented yet
    groundtruth.txt delimiter            MINOR     Original paper = comma;
    (comma vs. space)                              some distributions = space;
                                                   verify on your local file
    attributes.txt binary vector         ASSUMED   Order assumed to follow
    column order                                   paper Table I order; verify
                                                   against any readme.txt in
                                                   your HOT2026 folder
    Multi-object bboxes                  ABSENT    HOT provides only the single
                                                   tracked-object bbox; running
                                                   an object detector on the
                                                   false-color frames is required
                                                   to populate multi-object nodes
    UAV-HSI-Crop GT classes 1 and 3      PARTIAL   Only two classes appear in
    semantic species labels                        the sampled patch; full
                                                   class-to-species mapping
                                                   requires the dataset
                                                   label_map.txt or its
                                                   documentation file
    Wavelength range 400-1000 nm for     ESTIMATED Derived from standard
    UAV-HSI-Crop (200 bands)                       UAV-HSI literature; not
                                                   read from a metadata file

---

## Section 7 -- Key References

    Xiong, Zhou, Qian (2018)
    "Material Based Object Tracking in Hyperspectral Videos: Benchmark
    and Algorithms". IEEE TIP 2020 (arXiv 1812.04179).
    -- Defines the HOT benchmark format, annotation process, and the
       single-object bounding-box groundtruth structure.

    HOTC contest page
    https://www.hsitracking.com/contest/
    -- Official format description, sensor details, calibration procedure,
       and challenge attribute definitions.

    Deep Feature-Based HS Object Tracking Survey (2025)
    Remote Sensing 17(4):645.
    -- Comprehensive comparison of all HOT dataset versions; source for
       HOT2023 extended attributes.

    BihoT: Large-Scale Dataset for Hyperspectral Camouflaged Object
    Tracking (2024). arXiv 2408.12232.
    -- Table I summarises all existing HOT datasets and their main
       tracked object categories.

    HOD3K: Object Detection in Hyperspectral Image (2023).
    arXiv 2306.08370.
    -- Multi-object annotation (people, cars, bikes) on the same XIMEA
       VIS camera; relevant model for scene graph multi-object node
       population.


---

## Section 8 -- UAV-HSI-Crop: Detailed Annotation and Object Study

### 8.1 Acquisition Details (Confirmed from Official Repository)

    Property              Value
    --------------------  ----------------------------------------------------
    Sensor                Resonon Pika L hyperspectral imager
    Spectral range        385 nm to 1024 nm
    Number of bands       200
    Spatial resolution    0.1 m per pixel (100 m flight height)
    Platform              Electric hexacopter (UAV)
    Acquisition date      September 18, 2019
    Study area            Shenzhou City, Hebei Province, China
    Sub-regions           MJK_N, MJK_S (Majiakou Village plots)
                          XJM (Xijingmeng Village plots)
    Post-processing       Spectronon + ENVI:
                          radiometric calibration, geometric correction,
                          image stitching, atmospheric correction
    Patch size            96 x 96 x 200 pixels (H x W x bands) -- confirmed
    Data type             float32 numpy arrays -- confirmed
    Split ratio           Training: ~80%, Test: ~20%
    Additional splits     Validation split observed locally (Train/Validation/)
                          making it a three-way split in practice

Source: official GitHub repository (MrSuperNiu/UAV-HSI-Crop-Dataset) and
ScienceDB entry doi:10.57760/sciencedb.01898.

### 8.2 Annotation Format (UAV-HSI-Crop)

Ground truth files are 2D numpy arrays of shape (96, 96), dtype float32,
containing integer class label values with no decimals (confirmed from
direct file inspection of MJK_N_patch_0_0_0.npy).

    File pair per patch:
      {site}_patch_{row}_{col}_{idx}.npy   <- rs/ folder: (96, 96, 200) float32
      {site}_patch_{row}_{col}_{idx}.npy   <- gt/ folder: (96, 96) float32

    Annotation type: per-pixel semantic segmentation (every pixel = one
    integer class label)
    Label range: integer values (exact full range requires all gt files;
                 sampled patch shows classes 1 and 3)
    Annotation method: field survey ground truth mapped to pixel coordinates
                       (standard practice for UAV hyperspectral crop datasets)

### 8.3 Filename Convention

    Format: {SITE}_{VARIANT}_patch_{ROW}_{COL}_{INDEX}.npy

    Examples:
      XJM_patch_9_0_9.npy        -- site XJM, no variant, grid (9,0), idx 9
      MJK_N_patch_0_0_0.npy      -- site MJK, variant N (North), grid (0,0), idx 0
      MJK_N_patch_14_1_4.npy     -- site MJK, variant N (North), grid (14,1), idx 4

    Site codes:
      XJM  = Xijingmeng Village plots
      MJK  = Majiakou Village plots
      _N   = North sub-region of MJK
      _S   = South sub-region of MJK (inferred; MJK_S expected)

### 8.4 Spectral Profiles -- Directly Measured from Uploaded Files

Estimated wavelength scale: 385 nm (band 0) to 1024 nm (band 199),
approximately 3.2 nm per band. (Source: Pika L sensor specification.)

    XJM_patch_9_0_9 (Train/rs -- dense crop canopy):
      Band 26  (~530 nm, green peak):    0.0394  -- low (chlorophyll absorption)
      Band 92  (~682 nm, red absorb):    0.0329  -- minimum (chlorophyll red)
      Band 109 (~734 nm, red edge):      0.1665  -- steepest rise
      Band 145 (~848 nm, NIR plateau):   0.3692  -- high reflectance plateau
      Band 190 (~999 nm, SWIR onset):    0.2990  -- decreasing
      NDVI proxy:  0.670 -- dense, healthy green canopy
      Interpretation: corn (maize) canopy at grain-fill stage
        (Hebei September; matches published corn spectral library profiles)

    MJK_N_patch_14_1_4 (Validation/rs -- lower-density canopy):
      Band 26  (~530 nm):   0.1223  -- higher VIS than XJM
      Band 92  (~682 nm):   0.1532  -- less absorption (less chlorophyll)
      Band 109 (~734 nm):   0.2633  -- smaller red-edge step
      Band 145 (~848 nm):   0.3381  -- lower NIR than XJM
      NDVI proxy:  0.265 -- sparse canopy, bare soil between rows, or
                            a different crop with lower leaf area index
      Interpretation: cotton, peanut, or inter-row soil mixture
        (Hebei September cotton: open-boll stage, reduced green area)

### 8.5 Ground Truth Class Spatial Pattern

From MJK_N_patch_0_0_0.npy:

    Class 1: 8,929 pixels (96.9%)  -- fills the patch interior
                                      primary field crop
    Class 3:   287 pixels  (3.1%)  -- concentrated at patch bottom-right edge
                                      (rows 84-95, cols 52-95)
                                      76% of class-3 pixels within 5 px of border
                                      interpretation: field boundary, path, or
                                      adjacent plot of a different crop type

This spatial pattern (dominant crop + narrow edge class) is consistent with
how field boundaries appear when patches are extracted from an orthomosaic:
one class occupies the field interior, and a narrow strip at the patch border
captures the adjacent footpath, irrigation channel, or a different crop plot.

### 8.6 Crop Class Label Mapping (Partial -- Inferred)

The full class-to-species mapping is not explicitly stated in the paper's
abstract or the GitHub README. The table below combines direct spectral
evidence (above) with regional agronomy knowledge:

    Class  Spectral evidence          Regional context (Hebei, September)
    -----  -------------------------  -----------------------------------
    1      High NDVI (0.67), strong   Corn (maize) -- dominant autumn crop
           red-edge, NIR plateau      in Hebei; September = grain fill /
           matching corn library      near-harvest
    3      Edge/boundary location,    Field boundary, irrigation path,
           3.1% of sampled patch      road, or inter-crop gap (ASSUMED
                                      from spatial pattern only)

    Other classes (not in sampled patches -- expected in full dataset):
    ?      Lower NDVI, higher VIS     Cotton (open-boll, September)
    ?      Moderate NIR               Peanut, sweet potato, sorghum
    ?      Very low reflectance       Water body, irrigation channel
    ?      Flat low spectrum          Bare soil, road surface

ASSUMPTION: The full label map (all integer classes and their species names)
is contained in a documentation file in your local data directory or in the
original ScienceDB download package. The exact mapping requires checking:
  - any README or label_map.txt in your Train/ or Test/ folders
  - Supplementary material of the HSI-TransUNet paper (Niu et al. 2022,
    Computers and Electronics in Agriculture, doi:10.1016/j.compag.2022.106993)

### 8.7 Relations Derivable from UAV-HSI-Crop Annotations

Since this dataset has per-pixel semantic labels and no temporal dimension,
all derivable relations are spatial or spectral:

    SPATIAL RELATIONS (between region-level nodes, derived from gt label map):
      adjacent_to       -- regions of different class sharing a boundary pixel
      next_to           -- region centroids within a configurable distance
      contains          -- one region fully enclosed within another (rare in
                           open field patches)
      aligned_with      -- crop rows of the same class are collinear
                           (visible from 0.1m resolution orthomosaics)

    SPECTRAL RELATIONS (between region nodes, derived from rs cube):
      is_same_material_as          -- two patches of class 1 from different
                                      sites share near-identical SAM angle
      has_similar_signature        -- class 1 and an adjacent class with
                                      partial canopy overlap
      is_abundance_fraction_of     -- mixed boundary pixels combine two
                                      adjacent crop spectra (class-3 boundary
                                      pixels are a linear mixture of their
                                      two neighbouring classes)
      has_matching_absorption      -- chlorophyll band (~682nm) shared across
                                      all vegetation classes; water absorption
                                      at ~970nm shared by all moist soils
      has_higher_reflectance_than  -- bare soil/road > crop canopy in VIS
                                      crop canopy > road in NIR
      is_spectrally_anomalous_     -- stressed, diseased, or weed-invaded
      relative_to                    pixels deviate from the class-mean
                                      signature of their labelled class

    TEMPORAL RELATIONS: not applicable (single-date acquisition).
      Note: multi-date acquisition of the same field over the growing
      season would enable spectral_signature_correlates_with and
      is_accelerating_relative_to (canopy growth rate) relations.
