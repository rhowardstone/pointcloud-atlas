# Data contract

All buffers are **little-endian** and in the **same node-row order** (row `i` is the
same point in every file). `engine/index.html` fetches these from `/data/`.

## Buffers

| File | Layout | Meaning |
|---|---|---|
| `manifest.json` | JSON | counts, struct formats, ranges, and the `config` block (below) |
| `positions.bin` | `<ffHHHBB>` (16 B/node) | x, y (f32) + 3 categorical codes `s0,s1,s2` (u16) + flags (u8) + pad |
| `positions_<view>.bin` | `<ff>` (8 B/node) | secondary 2D embedding (e.g. `positions_tsne.bin`) |
| `positions_3d.bin` | `<fff>` (12 B/node) | primary 3D embedding |
| `positions_<view>_3d.bin` | `<fff>` (12 B/node) | secondary 3D embeddings |
| `cat_<key>.bin` | u16/node | a categorical attribute not packed into the struct |
| `num_<key>.bin` | f32/node | a continuous attribute |
| `edges.bin` | `<IIB>` (9 B/edge) | src idx (u32), dst idx (u32), type (u8) — optional overlay |
| `index.txt.gz` | gzipped text | one node id per line, node-row order |

The 3 struct slots `s0/s1/s2` are a fast path for the first three categorical
attributes; additional categoricals spill to `cat_<key>.bin`. Continuous attributes
are always `num_<key>.bin`.

## manifest.json

```jsonc
{
  "n_nodes": 2700, "n_edges": 32656,
  "node_struct": "<ffHHHBB", "edge_struct": "<IIB",
  "node_struct_3d": "<fff", "has_3d": true,
  "x_range": [..], "y_range": [..], "z_range": [..],
  "config": { /* the engine renders its whole UI from this */ }
}
```

### config

```jsonc
{
  "title": "My atlas",
  "node_label": "items",          // "2,700 items · …" in the header
  "id_label": "id",               // hover card prefix
  "primary_2d": "umap",
  "views_2d": ["umap","tsne"],    // populates the View dropdown
  "views_3d": ["umap","tsne"],
  "view_labels": {"umap":"UMAP","tsne":"t-SNE"},
  "color_by": [                   // populates the Color dropdown + legend + getColor
    { "key":"group", "label":"group", "kind":"categorical",
      "source":"struct:s0", "vocab":["a","b"], "palette":[[31,119,180],[255,127,14]] },
    { "key":"score", "label":"score", "kind":"continuous",
      "source":"num:score", "colormap":"viridis", "range":[0.0, 5.1] }
  ],
  "filters": [ /* {key,label,kind,source} — generic filter rail (roadmap) */ ],
  "hover": ["group","score"],     // fields shown in the hover card
  "link_template": null,          // optional per-node link-out URL template
  "feature_endpoint": null        // optional: lazy continuous columns at scale
}
```

`source` is one of `struct:s0|s1|s2`, `cat:<key>`, or `num:<key>` — telling the engine
where to read each attribute's per-node value. Colormaps: `viridis`, `magma`,
`inferno`, `plasma`.
