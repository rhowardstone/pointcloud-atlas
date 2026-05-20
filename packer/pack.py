"""pointcloud-atlas — generic buffer packer.

Turns plain arrays (coordinates + per-node attributes + ids) into the binary
"data contract" the pointcloud-atlas engine (`engine/index.html`) reads. Dataset-
agnostic: no domain assumptions. A domain emitter (e.g. single-cell anndata) just
builds `Attribute`s and calls `pack_atlas`.

Buffer layout (little-endian; every buffer in the same node-row order):
  positions.bin            16 B/node "<ffHHHBB": x, y, s0, s1, s2 (u16 cat codes), flags u8, pad
  positions_<view>.bin     8 B/node "<ff>"   (secondary 2D embeddings)
  positions_3d.bin         12 B/node "<fff>" (primary 3D embedding)
  positions_<view>_3d.bin  12 B/node "<fff>" (secondary 3D embeddings)
  cat_<key>.bin            u16/node  (categorical attribute not packed in the struct)
  num_<key>.bin            f32/node  (continuous attribute)
  edges.bin                9 B/edge "<IIB": src u32, dst u32, type u8
  index.txt.gz             gzipped, one node id per line

manifest.json carries a `config` block the engine renders its whole UI from:
  title, node_label, id_label, primary_2d, views_2d/3d, color_by[], filters[],
  hover[], link_template, feature_endpoint.
"""
from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

U16_MAX = 65535
POS_DTYPE = np.dtype([("x", "<f4"), ("y", "<f4"),
                      ("s0", "<u2"), ("s1", "<u2"), ("s2", "<u2"),
                      ("flags", "u1"), ("pad", "u1")])      # 16 B  "<ffHHHBB"
EDGE_DTYPE = np.dtype([("ai", "<u4"), ("bi", "<u4"), ("t", "u1")])  # 9 B "<IIB"
assert POS_DTYPE.itemsize == 16 and EDGE_DTYPE.itemsize == 9

# 20-color high-contrast categorical palette (tab20-ish), used when none supplied.
DEFAULT_PALETTE = [
    [31, 119, 180], [255, 127, 14], [44, 160, 44], [214, 39, 40], [148, 103, 189],
    [140, 86, 75], [227, 119, 194], [127, 127, 127], [188, 189, 34], [23, 190, 207],
    [174, 199, 232], [255, 187, 120], [152, 223, 138], [255, 152, 150], [197, 176, 213],
    [196, 156, 148], [247, 182, 210], [199, 199, 199], [219, 219, 141], [158, 218, 229],
]


@dataclass
class Attribute:
    """One per-node attribute the user can color by / filter on."""
    key: str
    label: str
    kind: str                      # 'categorical' | 'continuous'
    values: np.ndarray             # length n_nodes
    palette: list | None = None    # categorical: list of [r,g,b]; else auto
    colormap: str = "viridis"      # continuous: engine-side colormap name
    filter: bool = True            # expose a filter control
    legend: bool = True            # show in legend when active
    # filled by the packer:
    _slot: int | None = field(default=None, repr=False)
    _vocab: list | None = field(default=None, repr=False)


def _codes(values) -> tuple[np.ndarray, list[str]]:
    v = np.asarray(values).astype(str)
    vocab = sorted(set(v.tolist()))
    if len(vocab) > U16_MAX:
        raise ValueError(f"{len(vocab)} categories > uint16 limit")
    idx = {s: i for i, s in enumerate(vocab)}
    return np.fromiter((idx[s] for s in v), dtype="<u2", count=len(v)), vocab


def _edges(arr) -> np.ndarray:
    arr = np.asarray(arr)
    out = np.zeros(len(arr), dtype=EDGE_DTYPE)
    out["ai"] = arr[:, 0]
    out["bi"] = arr[:, 1]
    out["t"] = arr[:, 2] if arr.shape[1] > 2 else 0
    return out


def pack_atlas(
    outdir: str | Path,
    *,
    ids,
    embeddings_2d: dict[str, np.ndarray],
    embeddings_3d: dict[str, np.ndarray] | None = None,
    attributes: list[Attribute],
    primary_2d: str | None = None,
    edges: np.ndarray | None = None,
    title: str = "pointcloud-atlas",
    node_label: str = "nodes",
    id_label: str = "id",
    hover_fields: list[str] | None = None,
    link_template: str | None = None,
    thumb_template: str | None = None,
    feature_endpoint: str | None = None,
    view_labels: dict[str, str] | None = None,
    extra_config: dict | None = None,
) -> dict:
    """Write the full buffer set + config-rich manifest. Returns the manifest."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    n = len(ids)
    embeddings_3d = embeddings_3d or {}
    view_labels = view_labels or {}
    primary_2d = primary_2d or next(iter(embeddings_2d))
    if primary_2d not in embeddings_2d:
        raise ValueError(f"primary_2d {primary_2d!r} not in {list(embeddings_2d)}")
    for a in attributes:
        if len(a.values) != n:
            raise ValueError(f"attribute {a.key!r} length {len(a.values)} != n {n}")

    # assign the 3 categorical struct slots to the first categorical attrs (fast path);
    # the rest go to sidecars. continuous attrs always go to float32 sidecars.
    cats = [a for a in attributes if a.kind == "categorical"]
    for slot, a in enumerate(cats[:3]):
        a._slot = slot

    # ---- positions.bin (primary 2D + baked categorical slots + flags) ------
    xy = np.asarray(embeddings_2d[primary_2d], dtype="f4")
    rec = np.zeros(n, dtype=POS_DTYPE)
    rec["x"], rec["y"] = xy[:, 0], xy[:, 1]
    for a in cats:
        codes, vocab = _codes(a.values)
        a._vocab = vocab
        if a._slot is not None:
            rec[f"s{a._slot}"] = codes
        else:
            (outdir / f"cat_{a.key}.bin").write_bytes(codes.tobytes())
    (outdir / "positions.bin").write_bytes(rec.tobytes())

    # ---- continuous sidecars ----------------------------------------------
    for a in attributes:
        if a.kind == "continuous":
            vals = np.nan_to_num(np.asarray(a.values, dtype="f4"))
            (outdir / f"num_{a.key}.bin").write_bytes(np.ascontiguousarray(vals).tobytes())

    # ---- secondary 2D + all 3D embeddings ----------------------------------
    for name, emb in embeddings_2d.items():
        if name == primary_2d:
            continue
        a2 = np.ascontiguousarray(np.asarray(emb)[:, :2], dtype="<f4")
        (outdir / f"positions_{name}.bin").write_bytes(a2.tobytes())
    z_range = None
    if embeddings_3d:
        prim3 = primary_2d if primary_2d in embeddings_3d else next(iter(embeddings_3d))
        x3 = np.ascontiguousarray(np.asarray(embeddings_3d[prim3])[:, :3], dtype="<f4")
        (outdir / "positions_3d.bin").write_bytes(x3.tobytes())
        z_range = [float(x3[:, 2].min()), float(x3[:, 2].max())]
        for name, emb in embeddings_3d.items():
            if name == prim3:
                continue
            a3 = np.ascontiguousarray(np.asarray(emb)[:, :3], dtype="<f4")
            (outdir / f"positions_{name}_3d.bin").write_bytes(a3.tobytes())

    # ---- ids + edges -------------------------------------------------------
    (outdir / "index.txt.gz").write_bytes(
        gzip.compress("\n".join(map(str, ids)).encode("utf-8")))
    n_edges = 0
    if edges is not None and len(edges):
        (outdir / "edges.bin").write_bytes(_edges(edges).tobytes())
        n_edges = len(edges)

    # ---- config block (engine renders the whole UI from this) --------------
    color_by = []
    for a in attributes:
        if a._slot is not None:
            source = f"struct:s{a._slot}"
        elif a.kind == "categorical":
            source = f"cat:{a.key}"
        else:
            source = f"num:{a.key}"
        spec = {"key": a.key, "label": a.label, "kind": a.kind,
                "source": source, "legend": a.legend}
        if a.kind == "categorical":
            spec["vocab"] = a._vocab
            pal = a.palette or [DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]
                                for i in range(len(a._vocab))]
            spec["palette"] = pal
        else:
            spec["colormap"] = a.colormap
            vals = np.asarray(a.values, dtype="f4")
            spec["range"] = [float(np.nanmin(vals)), float(np.nanmax(vals))]
        color_by.append(spec)

    filters = [{"key": a.key, "label": a.label, "kind": a.kind,
                "source": color_by[i]["source"]}
               for i, a in enumerate(attributes) if a.filter]

    views_2d = sorted(embeddings_2d)
    views_3d = sorted(embeddings_3d)
    config = {
        "title": title, "node_label": node_label, "id_label": id_label,
        "primary_2d": primary_2d, "views_2d": views_2d, "views_3d": views_3d,
        "view_labels": view_labels,
        "color_by": color_by, "filters": filters,
        "hover": hover_fields or [a["key"] for a in color_by],
        "link_template": link_template, "thumb_template": thumb_template,
        "feature_endpoint": feature_endpoint,
    }
    if extra_config:
        config.update(extra_config)

    manifest = {
        "n_nodes": n, "n_edges": n_edges,
        "node_struct": "<ffHHHBB", "edge_struct": "<IIB",
        "node_struct_3d": "<fff", "xyz_bytes_per_node": 12,
        "has_3d": bool(embeddings_3d),
        "x_range": [float(xy[:, 0].min()), float(xy[:, 0].max())],
        "y_range": [float(xy[:, 1].min()), float(xy[:, 1].max())],
        "z_range": z_range,
        "built_at": int(time.time()),
        "config": config,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
