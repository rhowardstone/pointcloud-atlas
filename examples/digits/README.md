# Example: Handwritten digits (sklearn)

**What it is:** 1,797 handwritten digit images (8×8 grayscale) from
`sklearn.datasets.load_digits`. Each **point is one image**; nearby points look
alike. A deliberately *non-biological* example to show the engine is domain-agnostic
— and to demonstrate the **hover thumbnail + link-to-source** feature: every point
carries a PNG of its actual digit, shown in the hover panel.

## Attributes

| Attribute | Type | Meaning |
|---|---|---|
| `digit` | categorical | the label 0–9 (10 classes → great for legend-chip subsetting) |
| `mean intensity` | continuous | average pixel value (how much ink) |
| `PC 1` | continuous | first principal component |

`thumb_template = /data/thumbs/{id}.png` → hovering/clicking a point shows that
digit's image. `id` = the sample index.

## What it demonstrates
- A **10-class** categorical (clearer multi-category filtering than a single label)
- **Hover thumbnails** (`thumb_template`) — the same mechanism links points to
  source documents/images in any dataset (`link_template` adds an "open source" button)
- Fully **offline** (sklearn ships the data); UMAP + t-SNE in 2D & 3D

## Run
```bash
python3 build.py                                  # builds data/ + data/thumbs/*.png
python3 ../../serve.py examples/digits 8771       # open http://127.0.0.1:8771/
```
Requires `scikit-learn pillow umap-learn`.
