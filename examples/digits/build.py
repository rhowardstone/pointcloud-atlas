"""Digits example: sklearn `load_digits` -> generic packer.

A non-biological, fully-offline demo (1,797 handwritten 8x8 digit images) that
shows the engine is domain-agnostic AND exercises the hover **thumbnail** feature:
each point links to a PNG of its actual digit image via `thumb_template`.

Attributes:
  digit          categorical (0–9) — 10 labeled classes for legend subsetting
  mean_intensity continuous — average pixel value (ink amount)
  pca1           continuous — first principal component
See README.md.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import umap

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packer"))
from pack import Attribute, pack_atlas  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"


def main():
    d = load_digits()
    X, y, imgs = d.data, d.target, d.images          # X:(n,64) y:(n,) imgs:(n,8,8)
    n = len(y)
    ids = [str(i) for i in range(n)]

    pca10 = PCA(n_components=10, random_state=0).fit_transform(X)
    u2 = umap.UMAP(n_components=2, random_state=0).fit_transform(X)
    u3 = umap.UMAP(n_components=3, random_state=0).fit_transform(X)
    t2 = TSNE(n_components=2, init="pca", random_state=0).fit_transform(pca10)
    t3 = TSNE(n_components=3, init="pca", random_state=0).fit_transform(pca10)

    # thumbnails: upscale each 8x8 image to 64x64 PNG -> data/thumbs/{id}.png
    tdir = OUT / "thumbs"; tdir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        arr = (255 - (imgs[i] / 16.0 * 255)).clip(0, 255).astype(np.uint8)  # dark ink on white
        Image.fromarray(arr, "L").resize((64, 64), Image.NEAREST).save(tdir / f"{i}.png")

    attrs = [
        Attribute("digit", "digit", "categorical", y.astype(str)),
        Attribute("mean_intensity", "mean intensity", "continuous", X.mean(axis=1), colormap="viridis"),
        Attribute("pca1", "PC 1", "continuous", pca10[:, 0], colormap="plasma"),
    ]
    man = pack_atlas(
        OUT, ids=ids,
        embeddings_2d={"umap": u2, "tsne": t2}, embeddings_3d={"umap": u3, "tsne": t3},
        primary_2d="umap", attributes=attrs,
        title="Handwritten digits (sklearn)", node_label="digits", id_label="sample",
        hover_fields=["digit", "mean_intensity"],
        thumb_template="/data/thumbs/{id}.png",
        view_labels={"umap": "UMAP", "tsne": "t-SNE"},
    )
    print(f"packed {man['n_nodes']} digits + {n} thumbnails -> {OUT}")


if __name__ == "__main__":
    main()
