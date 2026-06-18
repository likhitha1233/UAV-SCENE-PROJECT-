"""
models.py
=========

Core data classes representing the dynamic hyperspectral scene graph.

Hierarchy
---------
VideoMeta
    Per-sequence metadata (sensor, bands, fps, etc.) -- one per HOTC video
    or UAV-HSI tile/sequence.

SceneGraphNode
    A single object instance observed in a single frame. Carries a
    persistent `track_id` so the same physical object can be linked across
    frames. May optionally carry a per-band spectral signature.

SceneGraphEdge
    A directed, typed, timestamped relation between two nodes. `category`
    mirrors ontology.RelationCategory and `relation` must be a key in
    ontology.RELATIONS.

FrameSceneGraph
    All nodes + intra-frame edges for one (video_id, frame_id).

DynamicSceneGraph
    A whole video: an ordered collection of FrameSceneGraphs plus
    cross-frame (temporal) edges. Provides trajectory extraction and
    conversion to a single NetworkX MultiDiGraph spanning all frames.

These classes are intentionally lightweight (dataclasses) -- the
queryable, persistent representation lives in storage.SceneGraphDB, which
nodes/edges get inserted into. The classes here are convenient containers
for building a graph in memory (e.g. while running a detector/tracker over
a video) before bulk-inserting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Iterable

import networkx as nx

from ontology import RELATIONS, RelationCategory, is_valid_relation, is_valid_node_type


# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------

@dataclass
class VideoMeta:
    video_id: str
    name: str
    source_dataset: str            # e.g. "HOTC2026-VIS", "UAV-HSI-Crop"
    num_frames: int
    fps: float = 25.0
    num_bands: int = 0
    band_wavelengths_nm: Optional[List[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    # Free-form extras, e.g. {"challenge_attributes": ["OCC", "SV"]}
    attributes: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass
class SceneGraphNode:
    node_id: str            # human-readable, unique within (video, frame)
    video_id: str
    frame_id: int
    node_type: str          # key into ontology.NODE_TYPES
    track_id: Optional[int] = None   # persistent identity across frames;
                                       # None for material/context nodes
    # Bounding box in (x, y, w, h) pixel coords. None for non-spatial
    # (e.g. material/endmember) nodes.
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0
    # Mean per-band reflectance/radiance for this object in this frame.
    spectral_signature: Optional[List[float]] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_valid_node_type(self.node_type):
            raise ValueError(f"Unknown node_type: {self.node_type!r}")

    @property
    def center(self) -> Optional[Tuple[float, float]]:
        if self.bbox is None:
            return None
        x, y, w, h = self.bbox
        return (x + w / 2.0, y + h / 2.0)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

@dataclass
class SceneGraphEdge:
    source_id: str          # SceneGraphNode.node_id
    target_id: str          # SceneGraphNode.node_id
    relation: str            # key into ontology.RELATIONS
    video_id: str
    # "Anchor" frame for the edge. For temporal edges that span two frames
    # (e.g. is_next_position_of), this is the frame of the *source* node;
    # the target node's frame is given in attributes['target_frame_id'].
    frame_id: int
    category: Optional[str] = None   # filled automatically if omitted
    confidence: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_valid_relation(self.relation):
            raise ValueError(f"Unknown relation: {self.relation!r}")
        if self.category is None:
            self.category = RELATIONS[self.relation].category.value

    def inverse(self) -> Optional["SceneGraphEdge"]:
        """Return the inverse edge (source/target swapped), if defined.

        NOTE: for the *motion-trend* temporal relations (moves_toward /
        moves_away_from / is_accelerating_relative_to /
        is_decelerating_relative_to) the `inverse` field in the ontology
        records the conceptually-opposite predicate, but blindly swapping
        source/target and applying it is usually NOT physically correct
        (e.g. if A drives toward B's parked position, B does not thereby
        "move away from" A -- B isn't moving at all). For these four
        relations, prefer computing each directed pair (A,B) and (B,A)
        independently (see temporal_relations.py) rather than calling
        .inverse(). This method remains correct/safe for symmetric
        relations and for genuinely directional pairs (e.g. on_top_of /
        supports, is_occluded_by / occludes, is_next_position_of /
        is_previous_position_of).
        """
        rel = RELATIONS[self.relation]
        inv_name = rel.name if rel.symmetric else rel.inverse
        if inv_name is None:
            return None
        return SceneGraphEdge(
            source_id=self.target_id,
            target_id=self.source_id,
            relation=inv_name,
            video_id=self.video_id,
            frame_id=self.frame_id,
            confidence=self.confidence,
            attributes=dict(self.attributes),
        )


# ---------------------------------------------------------------------------
# Frame-level scene graph
# ---------------------------------------------------------------------------

@dataclass
class FrameSceneGraph:
    video_id: str
    frame_id: int
    nodes: List[SceneGraphNode] = field(default_factory=list)
    edges: List[SceneGraphEdge] = field(default_factory=list)

    def add_node(self, node: SceneGraphNode) -> None:
        assert node.video_id == self.video_id and node.frame_id == self.frame_id
        self.nodes.append(node)

    def add_edge(self, edge: SceneGraphEdge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[SceneGraphNode]:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def to_networkx(self) -> "nx.MultiDiGraph":
        g = nx.MultiDiGraph()
        for n in self.nodes:
            g.add_node(n.node_id, **{
                "node_type": n.node_type,
                "track_id": n.track_id,
                "bbox": n.bbox,
                "frame_id": n.frame_id,
                **n.attributes,
            })
        for e in self.edges:
            g.add_edge(e.source_id, e.target_id, key=e.relation,
                       relation=e.relation, category=e.category,
                       confidence=e.confidence, **e.attributes)
        return g


# ---------------------------------------------------------------------------
# Dynamic (whole-video) scene graph
# ---------------------------------------------------------------------------

@dataclass
class DynamicSceneGraph:
    video: VideoMeta
    frames: Dict[int, FrameSceneGraph] = field(default_factory=dict)
    # Cross-frame edges (temporal category): is_next_position_of,
    # is_occluded_by spanning a range, co_occurs_with, etc.
    temporal_edges: List[SceneGraphEdge] = field(default_factory=list)

    def add_frame(self, frame: FrameSceneGraph) -> None:
        assert frame.video_id == self.video.video_id
        self.frames[frame.frame_id] = frame

    def add_temporal_edge(self, edge: SceneGraphEdge) -> None:
        """Append a *cross-frame* edge to the sequence-level edge list.

        Despite the name (kept for the common case), this list holds any
        edge whose source and target nodes may live in different frames --
        not only `category == "temporal"`. Two examples that are
        cross-frame but NOT temporal-category: `spectral_signature_
        correlates_with` (category=spectral, computed over a track's whole
        signature time series) and, in principle, `shows_stress_relative_to`
        if computed over a multi-date sequence. `SceneGraphEdge.__post_init__`
        already validates that `relation` is a known ontology entry, so no
        further category restriction is enforced here.
        """
        self.temporal_edges.append(edge)

    # Backwards/forwards-compatible alias with a more accurate name.
    add_cross_frame_edge = add_temporal_edge

    def all_nodes(self) -> Iterable[SceneGraphNode]:
        for fg in self.frames.values():
            yield from fg.nodes

    def all_intra_frame_edges(self) -> Iterable[SceneGraphEdge]:
        for fg in self.frames.values():
            yield from fg.edges

    def get_trajectory(self, track_id: int) -> List[SceneGraphNode]:
        """All nodes sharing `track_id`, ordered by frame_id."""
        nodes = [n for n in self.all_nodes() if n.track_id == track_id]
        return sorted(nodes, key=lambda n: n.frame_id)

    def to_networkx(self) -> "nx.MultiDiGraph":
        """A single graph spanning the whole video: intra-frame and
        temporal edges combined into one MultiDiGraph."""
        g = nx.MultiDiGraph()
        for fg in self.frames.values():
            sub = fg.to_networkx()
            g.add_nodes_from(sub.nodes(data=True))
            g.add_edges_from(sub.edges(data=True, keys=True))
        for e in self.temporal_edges:
            g.add_edge(e.source_id, e.target_id, key=e.relation,
                       relation=e.relation, category=e.category,
                       confidence=e.confidence, **e.attributes)
        return g

