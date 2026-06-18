# Scene Graphs — Primer and Utility in Scene Understanding

---

## 1. What Is a Scene Graph?

A **scene graph** is a structured, graph-based representation of a visual scene in which:

- **Nodes** represent *entities* — objects, regions, or semantic concepts present in the scene (e.g., `car`, `tree`, `pedestrian`, `road`, `crop_field`).
- **Edges** represent *relations* between pairs of entities — directed, labeled predicates that describe how two nodes relate (e.g., `car --[parked_near]--> tree`, `bike --[on_top_of]--> car`, `pedestrian --[crossing]--> road`).

Each edge is a **triple**: `(subject, predicate, object)`, also written as `<subject, predicate, object>` in knowledge-graph notation. A scene graph is therefore a typed, labeled, directed multigraph — multiple distinct relations can exist between the same pair of nodes simultaneously (e.g., a car that is both `near` and `has_similar_signature` to another car).

This representation was first introduced at scale in the **Visual Genome** dataset (Krishna et al., 2017), which paired 108K images with densely annotated scene graphs (objects, attributes, and pairwise relations) derived from human annotations.

---

## 2. Static vs. Dynamic Scene Graphs

### Static scene graphs
Represent a **single image** (one moment in time). The graph captures spatial and semantic relations among visible objects in that frame. Visual Genome is the canonical example.

### Dynamic (video) scene graphs
Extend the representation to **video** by either:

**A. Frame-level formulation** — One scene graph per frame, with *cross-frame edges* linking the same physical object's node across consecutive frames (e.g., `car_frame_5 --[is_next_position_of]--> car_frame_4`). Relations can *change over time*: a car that is `far_from` a pedestrian at frame 1 may become `near` at frame 10. This formulation is used in the **Action Genome** dataset (Ji et al., 2020), which annotated video clips from the Charades dataset with per-frame subject–predicate–object triplets covering attention, spatial, and contact relations.

**B. Tracklet-level formulation** — Each physical object has a single node spanning its whole lifetime in the video; per-frame relations are replaced by temporally scoped edge attributes (`valid_frames: [5, 10]`). More compact but loses the frame-by-frame granularity of relation changes.

This repository uses the **frame-level formulation**, with `track_id` as the persistent identity field that links the same object's per-frame nodes into a continuous trajectory.

---

## 3. Relation Taxonomy

Relations in scene graphs are typically grouped into families:

| Family | What it describes | Examples |
|---|---|---|
| **Spatial** | Geometric position, containment, adjacency | `next_to`, `on_top_of`, `above`, `inside`, `left_of` |
| **Temporal** | Identity over time, motion, co-occurrence, occlusion | `is_next_position_of`, `co_occurs_with`, `is_occluded_by`, `moves_toward` |
| **Semantic / Functional** | Domain-specific roles and states | `parked_near`, `yields_to`, `controls`, `belongs_to_lane` |
| **Spectral** *(hyperspectral-specific)* | Material correspondence, unmixing relationships | `is_same_material_as`, `is_abundance_fraction_of`, `has_matching_absorption` |

The spectral family is a novel extension for hyperspectral data — it has no counterpart in standard RGB scene-graph datasets and is the primary contribution this taxonomy adds to the existing literature.

---

## 4. Utility in Scene Understanding

Scene graphs provide structured, queryable scene representations that enable higher-level reasoning beyond pixel-level predictions. Their main utilities are:

### 4.1 Bridging Perception and Reasoning
Raw detector/tracker output is an unstructured list of bounding boxes with class labels and confidence scores. A scene graph adds relational context: not just "there is a car and a pedestrian" but "the pedestrian is *crossing in front of* the car, which is *moving toward* the pedestrian." This relational context is what downstream reasoning (planning, anomaly detection, question answering) requires.

### 4.2 Structured Querying
Because the graph is a queryable data structure, analysts can ask questions that would require complex post-processing on raw video output:
- "Find all frames where a bicycle is on top of a car."
- "Which tracked objects are spectrally anomalous relative to the scene average?"
- "List all pedestrian trajectories that co-occur with an approaching vehicle within 50 frames."

### 4.3 Temporal/Dynamic Scene Understanding
Dynamic scene graphs make *how the scene changes over time* explicit and queryable. They support:
- **Event detection:** a `moves_toward` edge that transitions to `is_occluded_by` and then `same_track_as` describes an approach-occlusion-reappearance event.
- **Interaction recognition:** Action Genome shows that temporal evolution of relation triplets (e.g., `person --[holding]--> cup` followed by `person --[drinking_from]--> cup`) encodes action sequences.
- **Trajectory analysis:** tracking an object's outgoing spatial-relation edges across frames reveals its behavioral state (parked vs. in-motion, crossing vs. yielding).

### 4.4 Cross-Modal Scene Understanding (Hyperspectral-Specific)
In hyperspectral scenes, the same spatial layout can be observed across multiple spectral modalities (VIS, NIR, RedNIR in HOTC; all 200 bands in UAV-HSI-Crop). Scene graphs allow:
- **Material-based grouping:** Objects with `is_same_material_as` edges form spectral clusters that cross object-class boundaries (two cars of the same paint, two vegetation patches of the same species).
- **Unmixing structure:** `is_abundance_fraction_of` edges explicitly represent the linear mixture model — the graph *is* the unmixing result, in a queryable form.
- **Spectral anomaly routing:** an `is_spectrally_anomalous_relative_to` edge on a scene node immediately flags it for further inspection without re-processing the full cube.
- **Cross-modality correspondence:** the same physical object appears in VIS, NIR, and RedNIR sub-graphs; spectral edges link its signature across modalities.

### 4.5 Enabling Downstream Applications

| Application | How scene graphs help |
|---|---|
| **Traffic monitoring** | `yields_to`, `belongs_to_lane`, `moves_toward`, `waiting_at` relations directly encode traffic-state information for conflict/risk detection |
| **Collision prediction** | Temporal scene-graph classifiers (e.g., STTran, Cong et al. 2021) predict future relation states from current and past relation sequences |
| **Crop monitoring (UAV-HSI)** | `shows_stress_relative_to`, `has_matching_absorption`, `part_of_field` enable field-level health mapping from per-patch spectral scene graphs |
| **Object re-identification** | `is_same_material_as` and `spectral_signature_correlates_with` provide spectral identity cues to re-link a track after an occlusion gap |
| **Visual question answering** | A scene graph is a structured knowledge base; questions like "What is the object to the left of the car?" resolve to single graph queries |

---

## 5. Key Literature

| Reference | Contribution |
|---|---|
| Krishna et al. (2017) — *Visual Genome* | First large-scale image scene graph dataset; established the `<subject, predicate, object>` triple formulation |
| Ji et al. (2020) — *Action Genome* | Video extension of scene graphs; frame-level dynamic SGG; three-family relation taxonomy (attention / spatial / contact); 35 object classes and 25 relation predicates |
| Cong et al. (2021) — *STTran* | Spatial-temporal transformer for dynamic SGG from video; separates spatial and temporal relation prediction |
| Monninger et al. (2023) | Traffic scene graph construction for autonomous driving; road topology + actor–infrastructure relations |
| Xiong, Zhou & Qian (2020) — *Material-based object tracking* (IEEE TIP) | Foundation paper for the HOTC benchmark; HSI tracking via spectral material correspondence — underpins the spectral relation family here |
| Linear Spectral Mixture Model (standard) | Endmember / abundance fractions: `x = E·a + n`; basis for `is_endmember_of` and `is_abundance_fraction_of` relations |

---

## 6. How This Project Extends the Literature

Standard dynamic SGG (Action Genome, STTran) operates on RGB video and captures only spatial and contact/attention relations. This project extends the paradigm in two directions:

1. **Hyperspectral modality:** adding a fourth relation family (spectral) that has no counterpart in RGB-based SGG. Spectral relations encode material identity and unmixing structure — information that is invisible in RGB but intrinsic to hyperspectral data.

2. **Traffic + agriculture dual domains:** the node taxonomy covers both traffic-scene entities (vehicles, pedestrians, infrastructure) and agricultural entities (crop plants, soil patches, irrigation equipment), enabling the same graph framework and query API to serve both HOTC (traffic tracking) and UAV-HSI-Crop (crop monitoring) without schema changes.
