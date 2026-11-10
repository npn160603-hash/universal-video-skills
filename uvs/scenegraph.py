"""Hierarchical visual scene graph (Phase 1.2).

Coordinate system: pixels, origin at the top-left of the parent's space, y grows downward.
Rotation is in degrees; a positive angle turns clockwise on screen (because y points down).

Each node's transform is relative to its parent. A node's local matrix maps its own space to
the parent's space:

    local = T(x, y) . R(rotation) . S(scale_x, scale_y) . T(-anchor_x, -anchor_y)

The world matrix of a node is the product of local matrices from the root down to the node.
Column vectors are used: p' = M . p with p = (x, y, 1).

Draw order is depth-first. Children are drawn in list order, so later children sit on top.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

KINDS = ("video", "image", "text", "shape", "group", "mask", "camera",
         "chart", "map", "particle", "overlay")

Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class SceneGraphError(ValueError):
    """Raised for malformed graphs or non-invertible transforms."""


@dataclass
class Transform:
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0          # degrees, clockwise on screen
    scale_x: float = 1.0
    scale_y: float = 1.0
    anchor_x: float = 0.0          # pivot point inside the node's own space
    anchor_y: float = 0.0
    opacity: float = 1.0           # 0..1, multiplied down the hierarchy


@dataclass
class Crop:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0


@dataclass
class Node:
    id: str
    kind: str = "group"
    transform: Transform = field(default_factory=Transform)
    crop: Crop | None = None
    width: float = 0.0             # intrinsic size of the node's own space
    height: float = 0.0
    payload: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)


@dataclass
class SceneGraph:
    root: Node


# ---------------------------------------------------------------------------
# Matrix helpers
# ---------------------------------------------------------------------------

def _mul(a: Matrix, b: Matrix) -> Matrix:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def _translate(x: float, y: float) -> Matrix:
    return ((1.0, 0.0, x), (0.0, 1.0, y), (0.0, 0.0, 1.0))


def _scale(sx: float, sy: float) -> Matrix:
    return ((sx, 0.0, 0.0), (0.0, sy, 0.0), (0.0, 0.0, 1.0))


def _rotate(deg: float) -> Matrix:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    # y is down, so this matrix turns clockwise on screen for positive angles.
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def local_matrix(t: Transform) -> Matrix:
    return _mul(_mul(_mul(_translate(t.x, t.y), _rotate(t.rotation)),
                     _scale(t.scale_x, t.scale_y)),
                _translate(-t.anchor_x, -t.anchor_y))


def invert(m: Matrix) -> Matrix:
    a, b, c = m[0]
    d, e, f = m[1]
    det = a * e - b * d
    if abs(det) < 1e-12:
        raise SceneGraphError("transform is not invertible (zero scale?)")
    ia, ib = e / det, -b / det
    id_, ie = -d / det, a / det
    ic = -(ia * c + ib * f)
    if_ = -(id_ * c + ie * f)
    return ((ia, ib, ic), (id_, ie, if_), (0.0, 0.0, 1.0))


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return (m[0][0] * x + m[0][1] * y + m[0][2], m[1][0] * x + m[1][1] * y + m[1][2])


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

def walk(graph: SceneGraph):
    """Yield (node, parent_id, depth) depth-first, in draw order.

    Raises SceneGraphError if the same node object is reached twice (a cycle or a shared child),
    so traversal always terminates.
    """
    stack = [(graph.root, None, 0)]
    seen: set[int] = set()
    while stack:
        node, parent, depth = stack.pop()
        if id(node) in seen:
            raise SceneGraphError(f"node {node.id!r} appears more than once (shared child or cycle)")
        seen.add(id(node))
        yield node, parent, depth
        for child in reversed(node.children):
            stack.append((child, node.id, depth + 1))


def index(graph: SceneGraph) -> dict[str, tuple[Node, str | None]]:
    """Map id -> (node, parent_id). Raises on duplicate ids or shared/cyclic children."""
    out: dict[str, tuple[Node, str | None]] = {}
    seen_objects: set[int] = set()
    for node, parent, _ in walk(graph):
        if id(node) in seen_objects:
            raise SceneGraphError(f"node {node.id!r} appears more than once (shared child or cycle)")
        seen_objects.add(id(node))
        if node.id in out:
            raise SceneGraphError(f"duplicate node id {node.id!r}")
        out[node.id] = (node, parent)
    return out


def find(graph: SceneGraph, node_id: str) -> Node:
    idx = index(graph)
    if node_id not in idx:
        raise SceneGraphError(f"no node with id {node_id!r}")
    return idx[node_id][0]


def ancestry(graph: SceneGraph, node_id: str) -> list[Node]:
    """Nodes from the root down to node_id, inclusive."""
    idx = index(graph)
    if node_id not in idx:
        raise SceneGraphError(f"no node with id {node_id!r}")
    chain: list[Node] = []
    current: str | None = node_id
    while current is not None:
        node, parent = idx[current]
        chain.append(node)
        current = parent
    return list(reversed(chain))


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def world_matrix(graph: SceneGraph, node_id: str) -> Matrix:
    m = IDENTITY
    for node in ancestry(graph, node_id):
        m = _mul(m, local_matrix(node.transform))
    return m


def to_world(graph: SceneGraph, node_id: str, x: float, y: float) -> tuple[float, float]:
    return apply(world_matrix(graph, node_id), x, y)


def to_local(graph: SceneGraph, node_id: str, x: float, y: float) -> tuple[float, float]:
    return apply(invert(world_matrix(graph, node_id)), x, y)


def world_opacity(graph: SceneGraph, node_id: str) -> float:
    o = 1.0
    for node in ancestry(graph, node_id):
        o *= node.transform.opacity
    return o


def world_rect(graph: SceneGraph, node_id: str) -> list[tuple[float, float]]:
    """Corners of the node's visible rectangle (after crop) in root space, clockwise from top-left."""
    node = find(graph, node_id)
    c = node.crop or Crop()
    x0, y0 = c.left, c.top
    x1, y1 = node.width - c.right, node.height - c.bottom
    m = world_matrix(graph, node_id)
    return [apply(m, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


# ---------------------------------------------------------------------------
# Validation and editing
# ---------------------------------------------------------------------------

def validate(graph: SceneGraph) -> list[str]:
    """Return human-readable problems. An empty list means the graph is usable."""
    problems: list[str] = []
    try:
        idx = index(graph)
    except SceneGraphError as exc:
        return [str(exc)]
    for node_id, (node, _) in idx.items():
        if node.kind not in KINDS:
            problems.append(f"node {node_id!r} has unknown kind {node.kind!r}; expected one of {', '.join(KINDS)}")
        t = node.transform
        if not 0.0 <= t.opacity <= 1.0:
            problems.append(f"node {node_id!r} opacity {t.opacity} is outside 0..1")
        if t.scale_x == 0 or t.scale_y == 0:
            problems.append(f"node {node_id!r} has a zero scale and cannot be inverted")
        if node.width < 0 or node.height < 0:
            problems.append(f"node {node_id!r} has a negative size")
        if node.crop is not None:
            c = node.crop
            if min(c.left, c.top, c.right, c.bottom) < 0:
                problems.append(f"node {node_id!r} has a negative crop")
            if c.left + c.right >= node.width or c.top + c.bottom >= node.height:
                problems.append(f"node {node_id!r} crop removes the whole node")
    return problems


def reorder_child(graph: SceneGraph, parent_id: str, child_id: str, new_index: int) -> SceneGraph:
    """Return a new graph with child moved to new_index among its siblings (layer order)."""
    g = copy.deepcopy(graph)
    parent = find(g, parent_id)
    names = [c.id for c in parent.children]
    if child_id not in names:
        raise SceneGraphError(f"{child_id!r} is not a child of {parent_id!r}")
    if not 0 <= new_index < len(names):
        raise SceneGraphError(f"index {new_index} is out of range for {len(names)} children")
    child = parent.children.pop(names.index(child_id))
    parent.children.insert(new_index, child)
    return g


def draw_order(graph: SceneGraph) -> list[str]:
    """Ids of all nodes in the order they are composited (first = bottom)."""
    return [node.id for node, _, _ in walk(graph)]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _node_to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "kind": node.kind,
        "transform": {k: getattr(node.transform, k) for k in (
            "x", "y", "rotation", "scale_x", "scale_y", "anchor_x", "anchor_y", "opacity")},
        "crop": None if node.crop is None else {k: getattr(node.crop, k) for k in
                                                ("left", "top", "right", "bottom")},
        "width": node.width,
        "height": node.height,
        "payload": node.payload,
        "children": [_node_to_dict(c) for c in node.children],
    }


def _node_from_dict(d: dict) -> Node:
    try:
        crop = None if d.get("crop") is None else Crop(**d["crop"])
        return Node(
            id=str(d["id"]),
            kind=str(d.get("kind", "group")),
            transform=Transform(**d.get("transform", {})),
            crop=crop,
            width=float(d.get("width", 0.0)),
            height=float(d.get("height", 0.0)),
            payload=dict(d.get("payload", {})),
            children=[_node_from_dict(c) for c in d.get("children", [])],
        )
    except (KeyError, TypeError) as exc:
        raise SceneGraphError(f"bad node definition {d.get('id', '?')!r}: {exc}") from exc


def to_dict(graph: SceneGraph) -> dict:
    return {"format": "uvs-scenegraph", "version": 1, "root": _node_to_dict(graph.root)}


def from_dict(data: dict) -> SceneGraph:
    if data.get("format") != "uvs-scenegraph":
        raise SceneGraphError("not a uvs-scenegraph document")
    return SceneGraph(root=_node_from_dict(data["root"]))
