"""
ontology.py
===========

Single source of truth for the *dynamic hyperspectral scene graph* node and
relation vocabulary used across this repository.

Design rationale
-----------------
Static scene graphs represent a frame as a set of object nodes connected by
pairwise predicate edges (Visual Genome / Action Genome style: <subject,
predicate, object>). Dynamic / video scene graphs extend this by either (a)
producing one scene graph per frame and linking corresponding object nodes
across frames (frame-level formulation), or (b) representing each object as
a single tracklet node spanning the whole sequence (tracklet-level
formulation). Action Genome groups its ~25 predicates into three families --
attention, spatial, and contact -- and allows multiple simultaneous spatial
or contact labels per object pair. Dynamic SGG surveys frame this evolution
as a temporal knowledge graph of <subject, relation, object, timestamp>
quadruples.

This module follows the **frame-level** formulation (finer-grained, matches
how HOTC/UAV-HSI data is naturally indexed by frame), but every node carries
a persistent ``track_id`` so a full tracklet can be reconstructed by
querying across frames (see storage.get_trajectory).

Because this is hyperspectral (not RGB) video, we add a fourth relation
family on top of Action-Genome-style spatial/contact relations: **spectral**
relations, grounded in the linear spectral mixture model (LMM) from
hyperspectral unmixing -- endmembers, abundance fractions, spectral angle /
cosine similarity, and absorption-feature matching. A fifth lightweight
family, **semantic/functional**, captures domain-specific relations needed
for traffic analysis (parked, yielding, lane membership, right-of-way) and
agricultural scenes (irrigation, field membership, crop stress), following
the entity/relation patterns used in traffic scene graph work.

NOTE on novelty: the spatial/temporal categories below are adapted from
established video scene graph literature (Action Genome; STTran; traffic
scene graph surveys). The *spectral* category is a proposed extension --
there is no single canonical "spectral scene graph" benchmark to copy from,
so these definitions are derived directly from the hyperspectral unmixing
literature (linear mixture model, endmember extraction, spectral angle
mapper) and should be treated as a starting taxonomy to refine with your
domain experts, not a fixed standard.

Everything here is plain data (dataclasses + dicts) so it can be consumed
from Python directly, or dumped to JSON via `export_ontology_json()` for use
by annotation tools, documentation generators, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
import json


# ---------------------------------------------------------------------------
# Relation categories
# ---------------------------------------------------------------------------

class RelationCategory(str, Enum):
    """The four (+1) families of edges in the dynamic scene graph."""

    SPATIAL = "spatial"      # relative position / containment / proximity
    TEMPORAL = "temporal"    # identity-over-time, motion, occlusion-in-time
    SPECTRAL = "spectral"    # material / unmixing / spectral-signature based
    SEMANTIC = "semantic"    # domain/functional relations (traffic, agri)


@dataclass(frozen=True)
class RelationDef:
    """Definition of a single relation (predicate) type."""

    name: str
    category: RelationCategory
    description: str
    # If the relation is directional, `inverse` names the predicate that
    # holds for (target, source) when (source, target, name) holds.
    # If symmetric, inverse == name (or None and symmetric=True).
    inverse: Optional[str] = None
    symmetric: bool = False
    # Loose guidance on which node "kinds" this typically connects.
    # Not enforced -- documentation / sanity-checking only.
    applies_between: str = "object-object"
    # Free-text pointer to the literature this is grounded in.
    reference: str = ""
    # Optional notes on expected edge attributes (e.g. {"fraction": float})
    expected_attributes: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# SPATIAL relations
# ---------------------------------------------------------------------------
# Grounded in Action Genome's "spatial" predicate family (in front of, on,
# beneath, behind, etc.) and traffic scene graph directional/proximity
# predicates (near, very_near, Front_Left, isIn lane, etc.)

_SPATIAL: List[RelationDef] = [
    RelationDef(
        "next_to", RelationCategory.SPATIAL,
        "Objects are immediately adjacent in image/world space, with no "
        "other object between them.",
        symmetric=True,
        reference="Action Genome spatial predicates (Ji et al., 2020).",
    ),
    RelationDef(
        "near", RelationCategory.SPATIAL,
        "Objects are within a configurable distance threshold of each "
        "other, but not necessarily touching/adjacent.",
        symmetric=True,
        reference="Proximity predicates in traffic scene graphs "
                   "(e.g. near/very_near in collision-risk SGs).",
        expected_attributes=["distance"],
    ),
    RelationDef(
        "far_from", RelationCategory.SPATIAL,
        "Objects are beyond a configurable distance threshold of each "
        "other (complement of `near`).",
        symmetric=True,
        reference="Complement of proximity predicates.",
        expected_attributes=["distance"],
    ),
    RelationDef(
        "on_top_of", RelationCategory.SPATIAL,
        "Source object is physically resting on / supported by target "
        "object (e.g. bike on_top_of car roof-rack).",
        inverse="supports",
        reference="Action Genome contact predicate 'on' generalised to "
                   "non-human subjects.",
    ),
    RelationDef(
        "supports", RelationCategory.SPATIAL,
        "Target object is physically resting on / supported by source "
        "object. Inverse of on_top_of.",
        inverse="on_top_of",
        reference="Inverse of on_top_of.",
    ),
    RelationDef(
        "above", RelationCategory.SPATIAL,
        "Source object is positioned higher than target in the vertical "
        "(image-y or world-z) axis, without necessarily touching it.",
        inverse="below",
        reference="Action Genome spatial predicate 'above'.",
    ),
    RelationDef(
        "below", RelationCategory.SPATIAL,
        "Source object is positioned lower than target in the vertical "
        "axis. Inverse of above.",
        inverse="above",
        reference="Action Genome spatial predicate 'beneath'.",
    ),
    RelationDef(
        "in_front_of", RelationCategory.SPATIAL,
        "Source object is closer to the camera / occupies a nearer depth "
        "plane than target.",
        inverse="behind",
        reference="Action Genome spatial predicate 'in front of'.",
    ),
    RelationDef(
        "behind", RelationCategory.SPATIAL,
        "Source object occupies a farther depth plane than target. "
        "Inverse of in_front_of.",
        inverse="in_front_of",
        reference="Action Genome spatial predicate 'behind'.",
    ),
    RelationDef(
        "left_of", RelationCategory.SPATIAL,
        "Source object is to the left of target in the image/scene frame.",
        inverse="right_of",
        reference="Directional predicates in AV scene graphs "
                   "(e.g. Front_Left / Rear_Right in collision-risk SGs).",
    ),
    RelationDef(
        "right_of", RelationCategory.SPATIAL,
        "Source object is to the right of target. Inverse of left_of.",
        inverse="left_of",
        reference="Directional predicates in AV scene graphs.",
    ),
    RelationDef(
        "inside", RelationCategory.SPATIAL,
        "Source object's extent is fully contained within target's "
        "extent (e.g. driver inside car).",
        inverse="contains",
        reference="Standard containment predicate, generalised from "
                   "Visual Genome / Action Genome.",
    ),
    RelationDef(
        "contains", RelationCategory.SPATIAL,
        "Target object's extent is fully contained within source's "
        "extent. Inverse of inside.",
        inverse="inside",
        reference="Inverse of inside.",
    ),
    RelationDef(
        "overlapping", RelationCategory.SPATIAL,
        "Bounding regions of the two objects overlap (IoU > 0) but "
        "neither fully contains the other.",
        symmetric=True,
        reference="Geometric overlap, common pre-relation feature in "
                   "VidSGG pipelines.",
        expected_attributes=["iou"],
    ),
    RelationDef(
        "adjacent_to", RelationCategory.SPATIAL,
        "Regions/areas (often infrastructure: lanes, fields, buildings) "
        "share a boundary or are directly side-by-side.",
        symmetric=True,
        applies_between="region-region",
        reference="Road connectivity / adjacency predicates in traffic "
                   "scene graphs (Monninger et al., 2023; Lv et al., 2024).",
    ),
    RelationDef(
        "aligned_with", RelationCategory.SPATIAL,
        "Objects share an orientation or are arranged collinearly "
        "(e.g. cars aligned_with a lane / parking row; crop rows "
        "aligned_with a field boundary).",
        symmetric=True,
        reference="Derived spatial-arrangement predicate, useful for "
                   "traffic lane discipline and crop row structure.",
    ),
]


# ---------------------------------------------------------------------------
# TEMPORAL relations
# ---------------------------------------------------------------------------
# Grounded in (a) the tracklet-linking that underlies all video SGG (each
# object's frame-level node is linked across time), (b) Action Genome's
# treatment of relationship evolution across frames, and (c) motion-based
# relations from AV collision-prediction scene graphs.

_TEMPORAL: List[RelationDef] = [
    RelationDef(
        "is_next_position_of", RelationCategory.TEMPORAL,
        "Source node (frame t+1) is the next-frame position of the same "
        "tracked object as target node (frame t). The core identity-link "
        "used to assemble a tracklet from per-frame nodes.",
        inverse="is_previous_position_of",
        applies_between="same-track, consecutive frames",
        reference="Tracklet linking in dynamic SGG (Action Genome; "
                   "STTran, Cong et al. 2021).",
        expected_attributes=["dt"],
    ),
    RelationDef(
        "is_previous_position_of", RelationCategory.TEMPORAL,
        "Source node (frame t) is the previous-frame position of the same "
        "tracked object as target node (frame t+1). Inverse of "
        "is_next_position_of.",
        inverse="is_next_position_of",
        applies_between="same-track, consecutive frames",
        reference="Inverse of is_next_position_of.",
        expected_attributes=["dt"],
    ),
    RelationDef(
        "same_track_as", RelationCategory.TEMPORAL,
        "Both nodes are instances (possibly non-adjacent frames, e.g. "
        "either side of an occlusion gap) of the same tracked object "
        "identity.",
        symmetric=True,
        applies_between="same-track, any frames",
        reference="Re-identification / track continuity, common in MOT "
                   "and used to bridge occlusion gaps.",
    ),
    RelationDef(
        "co_occurs_with", RelationCategory.TEMPORAL,
        "Two distinct objects are both present (visible or inferred) "
        "during an overlapping time interval.",
        symmetric=True,
        reference="Temporal co-occurrence, used for event/interaction "
                   "mining in temporal knowledge graphs of scenes.",
        expected_attributes=["frame_start", "frame_end"],
    ),
    RelationDef(
        "moves_toward", RelationCategory.TEMPORAL,
        "Source object's relative position with respect to target is "
        "decreasing in distance over the observed window (closing in).",
        inverse="moves_away_from",
        reference="Motion-based relation for risk/interaction analysis "
                   "(cf. proximity-trend features in AV collision-risk "
                   "scene graphs).",
        expected_attributes=["relative_speed"],
    ),
    RelationDef(
        "moves_away_from", RelationCategory.TEMPORAL,
        "Source object's relative position with respect to target is "
        "increasing in distance over the observed window. Inverse of "
        "moves_toward.",
        inverse="moves_toward",
        reference="Inverse of moves_toward.",
        expected_attributes=["relative_speed"],
    ),
    RelationDef(
        "is_accelerating_relative_to", RelationCategory.TEMPORAL,
        "Source object's velocity relative to target is increasing in "
        "magnitude over the observed window (closing speed growing, or "
        "own speed growing relative to target's frame of reference).",
        inverse="is_decelerating_relative_to",
        reference="Relative kinematics used in trajectory-prediction "
                   "traffic scene graphs (Schoenauer et al. 2022-style "
                   "relation-based motion prediction).",
        expected_attributes=["relative_acceleration"],
    ),
    RelationDef(
        "is_decelerating_relative_to", RelationCategory.TEMPORAL,
        "Source object's velocity relative to target is decreasing in "
        "magnitude over the observed window. Inverse of "
        "is_accelerating_relative_to.",
        inverse="is_accelerating_relative_to",
        reference="Inverse of is_accelerating_relative_to.",
        expected_attributes=["relative_acceleration"],
    ),
    RelationDef(
        "stationary_relative_to", RelationCategory.TEMPORAL,
        "The relative displacement between the two objects is "
        "approximately zero over the observed window (they move "
        "together, e.g. a rigidly-attached load and its vehicle, or "
        "two parked vehicles).",
        symmetric=True,
        reference="Special case of relative-motion relations; useful to "
                   "distinguish 'parked near' from 'driving alongside'.",
    ),
    RelationDef(
        "is_occluded_by", RelationCategory.TEMPORAL,
        "Source object's visibility is reduced/lost because target "
        "object spatially overlaps it from the camera viewpoint during "
        "this frame range.",
        inverse="occludes",
        reference="Occlusion (OCC) is one of the 11 standard challenge "
                   "attributes in HOT/HOTC benchmarks; modelled here as a "
                   "spatio-temporal relation per dynamic-SGG practice.",
        expected_attributes=["frame_start", "frame_end", "fraction_occluded"],
    ),
    RelationDef(
        "occludes", RelationCategory.TEMPORAL,
        "Source object spatially overlaps and visually hides target "
        "object from the camera viewpoint during this frame range. "
        "Inverse of is_occluded_by.",
        inverse="is_occluded_by",
        reference="Inverse of is_occluded_by.",
        expected_attributes=["frame_start", "frame_end", "fraction_occluded"],
    ),
]


# ---------------------------------------------------------------------------
# SPECTRAL relations
# ---------------------------------------------------------------------------
# Grounded in the linear spectral mixture model: x_i = E a_i + n_i, where E
# is the endmember matrix (pure-material signatures) and a_i the per-pixel
# abundance vector (non-negative, sums to 1). Endmembers are typically
# extracted via N-FINDR / VCA and matched to spectral libraries via
# Euclidean distance or spectral angle.

_SPECTRAL: List[RelationDef] = [
    RelationDef(
        "is_same_material_as", RelationCategory.SPECTRAL,
        "The two objects/regions are classified as composed of the same "
        "physical material, based on spectral signature matching (e.g. "
        "spectral angle below a strict threshold, or identical material "
        "class label).",
        symmetric=True,
        reference="Material-based correspondence; cf. 'Material based "
                   "object tracking in hyperspectral videos' "
                   "(Xiong, Zhou & Qian, IEEE TIP 2020), the paper "
                   "underlying the HOTC benchmark.",
        expected_attributes=["spectral_angle", "material_label"],
    ),
    RelationDef(
        "has_similar_signature", RelationCategory.SPECTRAL,
        "The two objects/regions have spectrally similar reflectance "
        "curves (e.g. cosine similarity / spectral angle within a "
        "moderate threshold) without necessarily being the same material "
        "-- a weaker relation than is_same_material_as, useful for "
        "candidate matching or anomaly screening.",
        symmetric=True,
        reference="Spectral similarity metrics (SAM, cosine similarity, "
                   "Euclidean distance) used for endmember-to-library "
                   "matching.",
        expected_attributes=["similarity_score", "metric"],
    ),
    RelationDef(
        "is_endmember_of", RelationCategory.SPECTRAL,
        "Source node's spectral signature serves as (one of) the pure "
        "endmember signatures for the material class represented by "
        "target node.",
        inverse="has_endmember",
        applies_between="object/pixel-region -> material node",
        reference="Endmember extraction (N-FINDR, VCA) in linear "
                   "spectral unmixing.",
    ),
    RelationDef(
        "has_endmember", RelationCategory.SPECTRAL,
        "Target node's spectral signature serves as a pure endmember for "
        "the material class represented by source node. Inverse of "
        "is_endmember_of.",
        inverse="is_endmember_of",
        applies_between="material node -> object/pixel-region",
        reference="Inverse of is_endmember_of.",
    ),
    RelationDef(
        "is_abundance_fraction_of", RelationCategory.SPECTRAL,
        "Source object's/region's spectrum is partially explained by "
        "target endmember node, with the proportion given in the edge "
        "attribute `fraction` (per the linear mixture model, fractions "
        "across all of a node's is_abundance_fraction_of edges should be "
        "non-negative and sum to ~1).",
        inverse="has_abundance_fraction",
        applies_between="object/pixel-region -> material/endmember node",
        reference="Abundance estimation in linear spectral unmixing "
                   "(non-negativity + sum-to-one constraints).",
        expected_attributes=["fraction"],
    ),
    RelationDef(
        "has_abundance_fraction", RelationCategory.SPECTRAL,
        "Target object's/region's spectrum is partially explained by "
        "source endmember node, with proportion `fraction`. Inverse of "
        "is_abundance_fraction_of.",
        inverse="is_abundance_fraction_of",
        applies_between="material/endmember node -> object/pixel-region",
        reference="Inverse of is_abundance_fraction_of.",
        expected_attributes=["fraction"],
    ),
    RelationDef(
        "has_matching_absorption", RelationCategory.SPECTRAL,
        "The two objects/regions share a characteristic absorption "
        "feature at (approximately) the same wavelength band(s) -- e.g. "
        "the chlorophyll red-edge absorption (~680-700 nm) shared by two "
        "vegetation regions, or a water absorption feature.",
        symmetric=True,
        reference="Absorption-feature matching for material "
                   "identification in spectral library workflows.",
        expected_attributes=["wavelength_nm", "depth"],
    ),
    RelationDef(
        "has_higher_reflectance_than", RelationCategory.SPECTRAL,
        "Source object has higher reflectance than target in a specified "
        "band or band range (edge attribute `band_range`).",
        inverse="has_lower_reflectance_than",
        reference="Comparative spectral-reflectance relation, useful for "
                   "discriminating visually-similar materials.",
        expected_attributes=["band_range", "delta"],
    ),
    RelationDef(
        "has_lower_reflectance_than", RelationCategory.SPECTRAL,
        "Source object has lower reflectance than target in a specified "
        "band or band range. Inverse of has_higher_reflectance_than.",
        inverse="has_higher_reflectance_than",
        reference="Inverse of has_higher_reflectance_than.",
        expected_attributes=["band_range", "delta"],
    ),
    RelationDef(
        "is_spectrally_anomalous_relative_to", RelationCategory.SPECTRAL,
        "Source object's spectral signature deviates significantly from "
        "target (typically a local background / scene-average / "
        "expected-class reference node), beyond a configured threshold -- "
        "flags potential camouflage, novel materials, or sensor "
        "artefacts.",
        reference="Hyperspectral anomaly detection; relevant to "
                   "hyperspectral camouflaged object tracking (BihoT, "
                   "Liu et al. 2024).",
        expected_attributes=["anomaly_score"],
    ),
    RelationDef(
        "spectral_signature_correlates_with", RelationCategory.SPECTRAL,
        "The temporal evolution of the two objects'/regions' spectral "
        "signatures is correlated across the sequence (e.g. shared "
        "illumination drift, or two crop plots showing the same "
        "senescence trend).",
        symmetric=True,
        reference="Temporal-spectral relation for tracking shared "
                   "environmental effects or correlated material change "
                   "(e.g. crop health monitoring).",
        expected_attributes=["correlation", "band_range"],
    ),
]


# ---------------------------------------------------------------------------
# SEMANTIC / FUNCTIONAL relations (domain-specific: traffic + agriculture)
# ---------------------------------------------------------------------------
# Grounded in traffic scene graph node/edge vocabularies (vehicles,
# pedestrians, lanes, traffic infrastructure; relations such as controls,
# overlaps, road connectivity, lane membership, right-of-way) and extended
# with agriculture-domain relations for the UAV-HSI crop use case.

_SEMANTIC: List[RelationDef] = [
    RelationDef(
        "parked_near", RelationCategory.SEMANTIC,
        "A vehicle is stationary (see stationary_relative_to / low "
        "velocity over time) and spatially near the target object "
        "(e.g. car parked_near tree).",
        reference="Traffic scene graph entity-state relation, combines "
                   "spatial proximity with a motion-state attribute.",
    ),
    RelationDef(
        "waiting_at", RelationCategory.SEMANTIC,
        "A vehicle/pedestrian is stationary at a controlling "
        "infrastructure element (traffic light, junction, stop line, "
        "crossing).",
        applies_between="actor -> infrastructure",
        reference="Behavioural state relation common in traffic scene "
                   "graphs for AV planning.",
    ),
    RelationDef(
        "crossing", RelationCategory.SEMANTIC,
        "A pedestrian/cyclist is traversing a road, lane, or crosswalk "
        "region.",
        applies_between="actor -> region",
        reference="Pedestrian-crossing relation used in vehicle-"
                   "pedestrian interaction / collision-risk scene graphs.",
    ),
    RelationDef(
        "yields_to", RelationCategory.SEMANTIC,
        "Source actor has lower priority and is expected to give way to "
        "target actor under traffic rules / right-of-way norms.",
        inverse="has_right_of_way_over",
        reference="Priority/right-of-way relations in ego-centric "
                   "traffic scene graphs (e.g. GraphPilot-style relation "
                   "vocabularies).",
    ),
    RelationDef(
        "has_right_of_way_over", RelationCategory.SEMANTIC,
        "Source actor has higher traffic priority than target actor. "
        "Inverse of yields_to.",
        inverse="yields_to",
        reference="Inverse of yields_to.",
    ),
    RelationDef(
        "controls", RelationCategory.SEMANTIC,
        "Source infrastructure node regulates target node/region (e.g. "
        "traffic_light controls intersection, traffic_sign controls "
        "lane).",
        applies_between="infrastructure -> region/actor",
        reference="Infrastructure-control predicates in traffic scene "
                   "graphs (Monninger et al., 2023; Mlodzian et al., 2023; "
                   "Lv et al., 2024).",
    ),
    RelationDef(
        "connects_to", RelationCategory.SEMANTIC,
        "Source road/lane segment is topologically connected to target "
        "segment (road-network connectivity).",
        symmetric=False,
        applies_between="infrastructure-infrastructure",
        reference="Road connectivity / topology relations in traffic "
                   "scene graphs.",
    ),
    RelationDef(
        "belongs_to_lane", RelationCategory.SEMANTIC,
        "Source actor's position falls within target lane region.",
        applies_between="actor -> infrastructure(lane)",
        reference="'isIn left_lane'-style belonging relation from AV "
                   "collision-prediction scene graphs.",
    ),
    RelationDef(
        "carries", RelationCategory.SEMANTIC,
        "Source object transports target object as cargo/load (often "
        "co-occurs with on_top_of and stationary_relative_to spatial/"
        "temporal edges, e.g. car carries bike).",
        inverse="carried_by",
        reference="Functional refinement of on_top_of for cargo "
                   "relations relevant to traffic scenes.",
    ),
    RelationDef(
        "carried_by", RelationCategory.SEMANTIC,
        "Source object is transported as cargo/load by target object. "
        "Inverse of carries.",
        inverse="carries",
        reference="Inverse of carries.",
    ),
    RelationDef(
        "part_of_field", RelationCategory.SEMANTIC,
        "Source object/region (e.g. a crop plant, weed patch) belongs to "
        "target field/plot region.",
        applies_between="object/region -> region",
        reference="Agricultural field-membership relation for UAV-HSI "
                   "crop scenes.",
    ),
    RelationDef(
        "irrigated_by", RelationCategory.SEMANTIC,
        "Source field/crop region receives water from target irrigation "
        "infrastructure or water body.",
        applies_between="region -> infrastructure",
        reference="Agriculture-domain functional relation.",
    ),
    RelationDef(
        "shows_stress_relative_to", RelationCategory.SEMANTIC,
        "Source crop region exhibits vegetation-stress indicators "
        "(e.g. reduced red-edge / NDVI-type response derived from "
        "has_matching_absorption / reflectance comparisons) relative to "
        "a healthier reference region.",
        reference="Ties spectral vegetation-index relations to an "
                   "interpretable agronomic state; complements "
                   "has_lower_reflectance_than / has_matching_absorption.",
        expected_attributes=["index_name", "delta"],
    ),
]


# ---------------------------------------------------------------------------
# Assemble the full relation ontology
# ---------------------------------------------------------------------------

RELATIONS: Dict[str, RelationDef] = {
    r.name: r for r in (_SPATIAL + _TEMPORAL + _SPECTRAL + _SEMANTIC)
}


def relations_by_category(category: RelationCategory) -> List[str]:
    """Return relation names belonging to a given category."""
    return [name for name, r in RELATIONS.items() if r.category == category]


def get_inverse(relation_name: str) -> Optional[str]:
    """Return the inverse relation name, or the same name if symmetric."""
    r = RELATIONS[relation_name]
    if r.symmetric:
        return r.name
    return r.inverse


def is_valid_relation(name: str) -> bool:
    return name in RELATIONS


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

class NodeKind(str, Enum):
    """Top-level node kinds. `OBJECT` nodes are concrete scene entities;
    `MATERIAL` nodes are abstract spectral-domain entities (endmembers /
    spectral clusters) used to anchor spectral-category edges; `CONTEXT`
    nodes represent the scene/frame itself for global attributes."""

    OBJECT = "object"
    MATERIAL = "material"
    CONTEXT = "context"


@dataclass(frozen=True)
class NodeTypeDef:
    name: str               # dotted path, e.g. "object.vehicle.car"
    kind: NodeKind
    description: str
    domain: str = "general"  # "traffic", "agriculture", "general"
    spectral_relevant: bool = True  # whether storing a signature is expected


_NODE_TYPES_LIST: List[NodeTypeDef] = [
    # --- Vehicles -----------------------------------------------------
    NodeTypeDef("object.vehicle.car", NodeKind.OBJECT,
                 "Passenger car.", domain="traffic"),
    NodeTypeDef("object.vehicle.truck", NodeKind.OBJECT,
                 "Truck / lorry.", domain="traffic"),
    NodeTypeDef("object.vehicle.bus", NodeKind.OBJECT,
                 "Bus.", domain="traffic"),
    NodeTypeDef("object.vehicle.van", NodeKind.OBJECT,
                 "Van.", domain="traffic"),
    NodeTypeDef("object.vehicle.motorcycle", NodeKind.OBJECT,
                 "Motorcycle / scooter.", domain="traffic"),
    NodeTypeDef("object.vehicle.bicycle", NodeKind.OBJECT,
                 "Bicycle (unoccupied or as object).", domain="traffic"),
    NodeTypeDef("object.vehicle.aircraft", NodeKind.OBJECT,
                 "Aircraft (aviation surveillance scenes).",
                 domain="traffic"),
    NodeTypeDef("object.vehicle.watercraft", NodeKind.OBJECT,
                 "Boat / ship (navigation surveillance scenes).",
                 domain="traffic"),

    # --- People --------------------------------------------------------
    NodeTypeDef("object.person.pedestrian", NodeKind.OBJECT,
                 "Pedestrian.", domain="traffic"),
    NodeTypeDef("object.person.cyclist", NodeKind.OBJECT,
                 "Person riding a bicycle.", domain="traffic"),
    NodeTypeDef("object.person.rider", NodeKind.OBJECT,
                 "Person riding a motorcycle/scooter.", domain="traffic"),

    # --- Animals ---------------------------------------------------------
    NodeTypeDef("object.animal.dog", NodeKind.OBJECT, "Dog."),
    NodeTypeDef("object.animal.bird", NodeKind.OBJECT, "Bird."),
    NodeTypeDef("object.animal.generic", NodeKind.OBJECT,
                 "Animal not covered by a specific subtype."),

    # --- Vegetation / crop -------------------------------------------------
    NodeTypeDef("object.vegetation.tree", NodeKind.OBJECT, "Tree."),
    NodeTypeDef("object.vegetation.shrub", NodeKind.OBJECT, "Shrub / bush."),
    NodeTypeDef("object.vegetation.grass", NodeKind.OBJECT,
                 "Grass / turf area."),
    NodeTypeDef("object.vegetation.crop_plant", NodeKind.OBJECT,
                 "Individual crop plant or crop canopy patch; use the "
                 "`attributes['species']` field for crop type (e.g. "
                 "maize, wheat, soybean).",
                 domain="agriculture"),
    NodeTypeDef("object.vegetation.weed_patch", NodeKind.OBJECT,
                 "Weed patch within a crop field.", domain="agriculture"),

    # --- Traffic infrastructure --------------------------------------------
    NodeTypeDef("object.infrastructure.road", NodeKind.OBJECT,
                 "Road surface / driving lane region.", domain="traffic",
                 spectral_relevant=False),
    NodeTypeDef("object.infrastructure.sidewalk", NodeKind.OBJECT,
                 "Sidewalk / pavement region.", domain="traffic",
                 spectral_relevant=False),
    NodeTypeDef("object.infrastructure.lane_marking", NodeKind.OBJECT,
                 "Painted lane marking.", domain="traffic"),
    NodeTypeDef("object.infrastructure.traffic_light", NodeKind.OBJECT,
                 "Traffic signal.", domain="traffic"),
    NodeTypeDef("object.infrastructure.traffic_sign", NodeKind.OBJECT,
                 "Traffic sign.", domain="traffic"),
    NodeTypeDef("object.infrastructure.building", NodeKind.OBJECT,
                 "Building / structure.", domain="traffic"),
    NodeTypeDef("object.infrastructure.pole", NodeKind.OBJECT,
                 "Pole / post (lamp post, signal post, etc.).",
                 domain="traffic"),
    NodeTypeDef("object.infrastructure.parking_space", NodeKind.OBJECT,
                 "Parking space region.", domain="traffic",
                 spectral_relevant=False),
    NodeTypeDef("object.infrastructure.bridge", NodeKind.OBJECT,
                 "Bridge / overpass.", domain="traffic"),

    # --- Agricultural infrastructure ---------------------------------------
    NodeTypeDef("object.agriculture.soil_patch", NodeKind.OBJECT,
                 "Bare soil region.", domain="agriculture"),
    NodeTypeDef("object.agriculture.water_body", NodeKind.OBJECT,
                 "Standing water / irrigation channel.",
                 domain="agriculture"),
    NodeTypeDef("object.agriculture.irrigation_equipment", NodeKind.OBJECT,
                 "Irrigation equipment (sprinkler, pivot, drip line).",
                 domain="agriculture"),
    NodeTypeDef("object.agriculture.field_boundary", NodeKind.OBJECT,
                 "Field/plot boundary region.", domain="agriculture",
                 spectral_relevant=False),

    # --- Generic / fallback --------------------------------------------------
    NodeTypeDef("object.generic", NodeKind.OBJECT,
                 "Unclassified object -- use attributes['raw_label'] for "
                 "the original detector label if available."),

    # --- Material / spectral-domain nodes ------------------------------------
    NodeTypeDef("material.endmember", NodeKind.MATERIAL,
                 "Abstract node representing a pure-material spectral "
                 "endmember signature extracted via unmixing (e.g. "
                 "N-FINDR/VCA). Use attributes['material_label'] for the "
                 "human-readable material name (asphalt, metal, "
                 "vegetation_canopy, soil, water, glass, ...).",
                 spectral_relevant=True),
    NodeTypeDef("material.spectral_cluster", NodeKind.MATERIAL,
                 "Abstract node representing an unsupervised cluster of "
                 "similar spectral signatures, prior to semantic "
                 "labelling.",
                 spectral_relevant=True),

    # --- Context ---------------------------------------------------------
    NodeTypeDef("context.scene", NodeKind.CONTEXT,
                 "Root node for an entire frame/video, holding "
                 "frame-global attributes (illumination estimate, "
                 "weather proxy, frame index, etc.).",
                 spectral_relevant=False),
]

NODE_TYPES: Dict[str, NodeTypeDef] = {n.name: n for n in _NODE_TYPES_LIST}


def is_valid_node_type(name: str) -> bool:
    return name in NODE_TYPES


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_ontology_json(path: str) -> None:
    """Dump the full ontology to a JSON file (for non-Python tools)."""
    data: Dict[str, Any] = {
        "node_types": {
            name: {**asdict(nt), "kind": nt.kind.value}
            for name, nt in NODE_TYPES.items()
        },
        "relations": {
            name: {**asdict(r), "category": r.category.value}
            for name, r in RELATIONS.items()
        },
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    # Quick sanity report when run directly.
    for cat in RelationCategory:
        names = relations_by_category(cat)
        print(f"{cat.value:>9s}: {len(names):2d} relations -> {names}")
    print(f"\n{len(NODE_TYPES)} node types defined.")
    export_ontology_json("ontology.json")
    print("Wrote ontology.json")
