"""
storage.py
==========

SQLite-backed persistent, queryable storage for one or more
`DynamicSceneGraph`s. This is the "structured repository" referenced in
Task 5: every node and edge (spatial, temporal, spectral, semantic) is a
row, indexed for the query patterns scene-graph consumers actually need
(by video, by frame, by track, by relation name/category, by node type).

Why SQLite?
-----------
- Single-file, zero-server database -- fits "store on our server" without
  needing a DB service; the .db file can be copied/shared/version-controlled
  (with care for size).
- Native Python support (sqlite3 stdlib) with full SQL querying, so analysts
  can drop into raw SQL for ad-hoc questions (see `SceneGraphDB.execute`)
  while still having a typed Python API for the common operations below.
- Scales comfortably to the node/edge counts implied by HOTC-scale videos
  (hundreds of frames x tens of objects x tens of relations per video); if
  you outgrow it, the schema maps cleanly onto Postgres.

Schema
------
videos(video_id PK, name, source_dataset, num_frames, fps, num_bands,
       band_wavelengths_nm JSON, width, height, attributes JSON)

nodes(pk, video_id, node_id, frame_id, node_type, track_id,
      bbox_x, bbox_y, bbox_w, bbox_h, confidence,
      spectral_signature JSON, attributes JSON)
      UNIQUE(video_id, node_id)

edges(pk, video_id, frame_id, source_id, target_id, relation, category,
      confidence, attributes JSON)

`node_id` is unique per video by construction (see builders.make_node_id:
`{type_leaf}_{track}_{frame}`), so cross-frame edges can reference a target
node in a different frame than `edges.frame_id` (the edge's *anchor* frame,
e.g. the source node's frame for `is_next_position_of`) and still be
resolved with a simple (video_id, node_id) lookup -- no integer foreign
keys needed.

Quick start
-----------
    from storage import SceneGraphDB
    db = SceneGraphDB("scene_graphs.sqlite")
    db.insert_dynamic_scene_graph(dsg)

    # All "parked_near" relations in this video
    for src, edge, tgt in db.find_relation_triples("parked_near", video_id="seq001"):
        print(src.node_type, src.track_id, "->", edge.relation, "->", tgt.node_type, tgt.track_id)

    # Full trajectory of track 5
    traj = db.get_trajectory("seq001", track_id=5)

    # Whole-video graph as a NetworkX MultiDiGraph
    g = db.to_networkx("seq001")
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx

from models import DynamicSceneGraph, FrameSceneGraph, SceneGraphEdge, SceneGraphNode, VideoMeta


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    video_id            TEXT PRIMARY KEY,
    name                TEXT,
    source_dataset      TEXT,
    num_frames          INTEGER,
    fps                 REAL,
    num_bands           INTEGER,
    band_wavelengths_nm TEXT,
    width               INTEGER,
    height              INTEGER,
    attributes          TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    pk                  INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id            TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    frame_id            INTEGER NOT NULL,
    node_type           TEXT NOT NULL,
    track_id            INTEGER,
    bbox_x              REAL,
    bbox_y              REAL,
    bbox_w              REAL,
    bbox_h              REAL,
    confidence          REAL,
    spectral_signature  TEXT,
    attributes          TEXT,
    UNIQUE(video_id, node_id),
    FOREIGN KEY(video_id) REFERENCES videos(video_id)
);
CREATE INDEX IF NOT EXISTS idx_nodes_video_frame ON nodes(video_id, frame_id);
CREATE INDEX IF NOT EXISTS idx_nodes_video_track ON nodes(video_id, track_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);

CREATE TABLE IF NOT EXISTS edges (
    pk          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT NOT NULL,
    frame_id    INTEGER NOT NULL,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    relation    TEXT NOT NULL,
    category    TEXT NOT NULL,
    confidence  REAL,
    attributes  TEXT,
    FOREIGN KEY(video_id) REFERENCES videos(video_id)
);
CREATE INDEX IF NOT EXISTS idx_edges_video_frame ON edges(video_id, frame_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
CREATE INDEX IF NOT EXISTS idx_edges_category ON edges(category);
CREATE INDEX IF NOT EXISTS idx_edges_video_source ON edges(video_id, source_id);
CREATE INDEX IF NOT EXISTS idx_edges_video_target ON edges(video_id, target_id);
"""


class SceneGraphDB:

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SceneGraphDB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insert_video(self, meta: VideoMeta) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO videos "
            "(video_id, name, source_dataset, num_frames, fps, num_bands, "
            " band_wavelengths_nm, width, height, attributes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                meta.video_id, meta.name, meta.source_dataset, meta.num_frames,
                meta.fps, meta.num_bands,
                json.dumps(meta.band_wavelengths_nm) if meta.band_wavelengths_nm else None,
                meta.width, meta.height, json.dumps(meta.attributes),
            ),
        )

    def insert_node(self, node: SceneGraphNode) -> None:
        bbox = node.bbox if node.bbox is not None else (None, None, None, None)
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes "
            "(video_id, node_id, frame_id, node_type, track_id, "
            " bbox_x, bbox_y, bbox_w, bbox_h, confidence, "
            " spectral_signature, attributes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                node.video_id, node.node_id, node.frame_id, node.node_type,
                node.track_id, *bbox, node.confidence,
                json.dumps(node.spectral_signature) if node.spectral_signature is not None else None,
                json.dumps(node.attributes),
            ),
        )

    def insert_nodes(self, nodes: Iterable[SceneGraphNode]) -> None:
        for n in nodes:
            self.insert_node(n)

    def insert_edge(self, edge: SceneGraphEdge) -> None:
        self.conn.execute(
            "INSERT INTO edges "
            "(video_id, frame_id, source_id, target_id, relation, category, "
            " confidence, attributes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                edge.video_id, edge.frame_id, edge.source_id, edge.target_id,
                edge.relation, edge.category, edge.confidence,
                json.dumps(edge.attributes),
            ),
        )

    def insert_edges(self, edges: Iterable[SceneGraphEdge]) -> None:
        for e in edges:
            self.insert_edge(e)

    def insert_dynamic_scene_graph(self, dsg: DynamicSceneGraph, commit: bool = True) -> None:
        """Persist an entire DynamicSceneGraph: video metadata, every
        frame's nodes and intra-frame edges, and all cross-frame
        (temporal / spectral-correlation) edges."""
        self.insert_video(dsg.video)
        for fg in dsg.frames.values():
            self.insert_nodes(fg.nodes)
            self.insert_edges(fg.edges)
        self.insert_edges(dsg.temporal_edges)
        if commit:
            self.conn.commit()

    # ------------------------------------------------------------------
    # Row <-> dataclass conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_video(row: sqlite3.Row) -> VideoMeta:
        return VideoMeta(
            video_id=row["video_id"], name=row["name"],
            source_dataset=row["source_dataset"], num_frames=row["num_frames"],
            fps=row["fps"], num_bands=row["num_bands"],
            band_wavelengths_nm=json.loads(row["band_wavelengths_nm"]) if row["band_wavelengths_nm"] else None,
            width=row["width"], height=row["height"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
        )

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> SceneGraphNode:
        bbox = None
        if row["bbox_x"] is not None:
            bbox = (row["bbox_x"], row["bbox_y"], row["bbox_w"], row["bbox_h"])
        return SceneGraphNode(
            node_id=row["node_id"], video_id=row["video_id"], frame_id=row["frame_id"],
            node_type=row["node_type"], track_id=row["track_id"], bbox=bbox,
            confidence=row["confidence"],
            spectral_signature=json.loads(row["spectral_signature"]) if row["spectral_signature"] else None,
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> SceneGraphEdge:
        return SceneGraphEdge(
            source_id=row["source_id"], target_id=row["target_id"], relation=row["relation"],
            video_id=row["video_id"], frame_id=row["frame_id"], category=row["category"],
            confidence=row["confidence"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
        )

    # ------------------------------------------------------------------
    # Simple lookups
    # ------------------------------------------------------------------

    def get_video(self, video_id: str) -> Optional[VideoMeta]:
        row = self.conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
        return self._row_to_video(row) if row else None

    def list_videos(self) -> List[VideoMeta]:
        rows = self.conn.execute("SELECT * FROM videos ORDER BY video_id").fetchall()
        return [self._row_to_video(r) for r in rows]

    def get_node(self, video_id: str, node_id: str) -> Optional[SceneGraphNode]:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE video_id = ? AND node_id = ?",
            (video_id, node_id),
        ).fetchone()
        return self._row_to_node(row) if row else None

    def get_frame_graph(self, video_id: str, frame_id: int) -> FrameSceneGraph:
        """Nodes physically in `frame_id`, plus all edges *anchored* at
        `frame_id` (edges.frame_id == frame_id). For cross-frame edges, the
        target node may belong to a different frame -- its id is still
        available via `edge.target_id` / `edge.attributes['target_frame_id']`,
        but it won't appear in `.nodes` here. Use `get_node` to resolve it."""
        node_rows = self.conn.execute(
            "SELECT * FROM nodes WHERE video_id = ? AND frame_id = ?",
            (video_id, frame_id),
        ).fetchall()
        edge_rows = self.conn.execute(
            "SELECT * FROM edges WHERE video_id = ? AND frame_id = ?",
            (video_id, frame_id),
        ).fetchall()
        fg = FrameSceneGraph(video_id=video_id, frame_id=frame_id)
        for r in node_rows:
            fg.add_node(self._row_to_node(r))
        for r in edge_rows:
            fg.add_edge(self._row_to_edge(r))
        return fg

    def get_trajectory(self, video_id: str, track_id: int) -> List[SceneGraphNode]:
        """All nodes for `track_id` in `video_id`, ordered by frame_id."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE video_id = ? AND track_id = ? "
            "ORDER BY frame_id ASC",
            (video_id, track_id),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    # ------------------------------------------------------------------
    # Flexible queries
    # ------------------------------------------------------------------

    def query_nodes(
        self,
        video_id: Optional[str] = None,
        node_type: Optional[str] = None,
        node_type_prefix: Optional[str] = None,
        frame_id: Optional[int] = None,
        frame_range: Optional[Tuple[int, int]] = None,
        track_id: Optional[int] = None,
    ) -> List[SceneGraphNode]:
        """Filtered node query. `node_type_prefix` matches dotted-prefix
        (e.g. "object.vehicle" matches "object.vehicle.car" and
        "object.vehicle.truck"); `frame_range=(lo, hi)` is inclusive."""
        clauses, params = [], []
        if video_id is not None:
            clauses.append("video_id = ?"); params.append(video_id)
        if node_type is not None:
            clauses.append("node_type = ?"); params.append(node_type)
        if node_type_prefix is not None:
            clauses.append("(node_type = ? OR node_type LIKE ?)")
            params.append(node_type_prefix)
            params.append(node_type_prefix + ".%")
        if frame_id is not None:
            clauses.append("frame_id = ?"); params.append(frame_id)
        if frame_range is not None:
            clauses.append("frame_id BETWEEN ? AND ?")
            params.extend(frame_range)
        if track_id is not None:
            clauses.append("track_id = ?"); params.append(track_id)

        sql = "SELECT * FROM nodes"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY frame_id ASC, node_id ASC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def query_edges(
        self,
        video_id: Optional[str] = None,
        relation: Optional[str] = None,
        relations: Optional[Sequence[str]] = None,
        category: Optional[str] = None,
        frame_id: Optional[int] = None,
        frame_range: Optional[Tuple[int, int]] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        source_track_id: Optional[int] = None,
        target_track_id: Optional[int] = None,
        source_node_type: Optional[str] = None,
        target_node_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> List[SceneGraphEdge]:
        """Flexible edge query. `source_track_id` / `target_track_id` and
        `source_node_type` / `target_node_type` require a join against
        `nodes` and are slightly more expensive than the plain
        `edges`-only filters."""
        clauses, params = [], []
        joins = ""

        if video_id is not None:
            clauses.append("e.video_id = ?"); params.append(video_id)
        if relation is not None:
            clauses.append("e.relation = ?"); params.append(relation)
        if relations is not None:
            placeholders = ",".join("?" for _ in relations)
            clauses.append(f"e.relation IN ({placeholders})")
            params.extend(relations)
        if category is not None:
            clauses.append("e.category = ?"); params.append(category)
        if frame_id is not None:
            clauses.append("e.frame_id = ?"); params.append(frame_id)
        if frame_range is not None:
            clauses.append("e.frame_id BETWEEN ? AND ?")
            params.extend(frame_range)
        if source_id is not None:
            clauses.append("e.source_id = ?"); params.append(source_id)
        if target_id is not None:
            clauses.append("e.target_id = ?"); params.append(target_id)
        if min_confidence is not None:
            clauses.append("e.confidence >= ?"); params.append(min_confidence)

        if source_track_id is not None or source_node_type is not None:
            joins += (" JOIN nodes ns ON ns.video_id = e.video_id "
                      "AND ns.node_id = e.source_id")
            if source_track_id is not None:
                clauses.append("ns.track_id = ?"); params.append(source_track_id)
            if source_node_type is not None:
                clauses.append("ns.node_type = ?"); params.append(source_node_type)

        if target_track_id is not None or target_node_type is not None:
            joins += (" JOIN nodes nt ON nt.video_id = e.video_id "
                      "AND nt.node_id = e.target_id")
            if target_track_id is not None:
                clauses.append("nt.track_id = ?"); params.append(target_track_id)
            if target_node_type is not None:
                clauses.append("nt.node_type = ?"); params.append(target_node_type)

        sql = "SELECT e.* FROM edges e" + joins
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY e.frame_id ASC, e.pk ASC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def find_relation_triples(
        self,
        relation: str,
        video_id: Optional[str] = None,
        frame_range: Optional[Tuple[int, int]] = None,
    ) -> List[Tuple[SceneGraphNode, SceneGraphEdge, SceneGraphNode]]:
        """All `(source_node, edge, target_node)` triples for a given
        relation, with both endpoint nodes resolved. This is the most
        common query pattern: "show me every `parked_near` / `is_same_
        material_as` / `is_occluded_by` relation in this video"."""
        edges = self.query_edges(video_id=video_id, relation=relation, frame_range=frame_range)
        out = []
        for e in edges:
            src = self.get_node(e.video_id, e.source_id)
            tgt = self.get_node(e.video_id, e.target_id)
            if src is not None and tgt is not None:
                out.append((src, e, tgt))
        return out

    # ------------------------------------------------------------------
    # Aggregate / summary helpers
    # ------------------------------------------------------------------

    def relation_counts(self, video_id: Optional[str] = None) -> Dict[str, int]:
        sql = "SELECT relation, COUNT(*) AS n FROM edges"
        params: List[Any] = []
        if video_id is not None:
            sql += " WHERE video_id = ?"
            params.append(video_id)
        sql += " GROUP BY relation ORDER BY n DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return {r["relation"]: r["n"] for r in rows}

    def category_counts(self, video_id: Optional[str] = None) -> Dict[str, int]:
        sql = "SELECT category, COUNT(*) AS n FROM edges"
        params: List[Any] = []
        if video_id is not None:
            sql += " WHERE video_id = ?"
            params.append(video_id)
        sql += " GROUP BY category ORDER BY n DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return {r["category"]: r["n"] for r in rows}

    def node_type_counts(self, video_id: Optional[str] = None) -> Dict[str, int]:
        sql = "SELECT node_type, COUNT(*) AS n FROM nodes"
        params: List[Any] = []
        if video_id is not None:
            sql += " WHERE video_id = ?"
            params.append(video_id)
        sql += " GROUP BY node_type ORDER BY n DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return {r["node_type"]: r["n"] for r in rows}

    def list_tracks(self, video_id: str) -> List[Dict[str, Any]]:
        """One summary row per track_id: node_type, first/last frame, and
        number of observed frames."""
        rows = self.conn.execute(
            "SELECT track_id, node_type, MIN(frame_id) AS first_frame, "
            "MAX(frame_id) AS last_frame, COUNT(*) AS n_frames "
            "FROM nodes WHERE video_id = ? AND track_id IS NOT NULL "
            "GROUP BY track_id ORDER BY track_id",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_networkx(self, video_id: str) -> "nx.MultiDiGraph":
        """Whole-video graph (all frames, including the global frame_id=-1
        material/context nodes) as a single NetworkX MultiDiGraph."""
        g = nx.MultiDiGraph()
        for n in self.query_nodes(video_id=video_id):
            g.add_node(n.node_id, node_type=n.node_type, track_id=n.track_id,
                       frame_id=n.frame_id, bbox=n.bbox, **n.attributes)
        for e in self.query_edges(video_id=video_id):
            g.add_edge(e.source_id, e.target_id, key=e.relation,
                       relation=e.relation, category=e.category,
                       frame_id=e.frame_id, confidence=e.confidence,
                       **e.attributes)
        return g

    def export_video_json(self, video_id: str, path: str) -> None:
        """Dump a video's full graph (metadata + nodes + edges) to JSON."""
        video = self.get_video(video_id)
        data = {
            "video": asdict(video) if video else None,
            "nodes": [asdict(n) for n in self.query_nodes(video_id=video_id)],
            "edges": [asdict(e) for e in self.query_edges(video_id=video_id)],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Schema introspection / ad-hoc SQL
    # ------------------------------------------------------------------

    def execute(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        """Escape hatch for arbitrary read-only SQL, e.g.:

            db.execute(
                "SELECT relation, category, COUNT(*) FROM edges "
                "WHERE video_id=? GROUP BY relation, category",
                ("seq001",),
            )
        """
        return self.conn.execute(sql, params).fetchall()
