"""Single-cell example: 10x PBMC 3k -> generic packer (self-contained).

Runs the standard scanpy pipeline on the classic PBMC 3k dataset (downloaded by
scanpy on first run), names the clusters by canonical markers, and packs the
buffers the engine reads. The packed `data/` is committed, so you can just
`python3 ../../serve.py examples/singlecell` without running this. Re-run this
only to regenerate. See README.md for what every attribute means.

Requires: scanpy, anndata, umap-learn, scikit-learn.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import scanpy as sc

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packer"))
from pack import Attribute, pack_atlas  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"

TYPE_MARKERS = {
    "T cells": ["CD3D", "CD3E", "IL7R"], "B cells": ["MS4A1", "CD79A"],
    "NK cells": ["NKG7", "GNLY"], "CD14 Monocytes": ["CD14", "LYZ"],
    "FCGR3A Monocytes": ["FCGR3A", "MS4A7"], "Dendritic": ["FCER1A", "CST3"],
    "Megakaryocytes": ["PPBP"],
}
CONT_MARKERS = ["CD3D", "MS4A1", "NKG7", "LYZ", "FCGR3A", "PPBP"]


def dense(x):
    return np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()


def main():
    a = sc.datasets.pbmc3k()
    a.var_names_make_unique(); a.obs_names_make_unique()
    a.var["mt"] = a.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(a, qc_vars=["mt"], inplace=True, percent_top=None)
    sc.pp.filter_cells(a, min_genes=200); sc.pp.filter_genes(a, min_cells=3)
    sc.pp.normalize_total(a, target_sum=1e4); sc.pp.log1p(a)
    sc.pp.highly_variable_genes(a, n_top_genes=2000)
    a.raw = a
    h = a[:, a.var.highly_variable].copy()
    sc.pp.scale(h, max_value=10)
    sc.tl.pca(h, n_comps=50, svd_solver="arpack")
    sc.pp.neighbors(h, n_neighbors=15, n_pcs=40)
    try:
        sc.tl.leiden(h, key_added="cluster", flavor="igraph", n_iterations=2, directed=False)
    except Exception:
        sc.tl.louvain(h, key_added="cluster")
    sc.tl.umap(h, n_components=3); h.obsm["X_umap_3d"] = h.obsm["X_umap"].copy()
    sc.tl.umap(h, n_components=2)
    sc.tl.tsne(h, n_pcs=40)
    from sklearn.manifold import TSNE
    h.obsm["X_tsne_3d"] = TSNE(n_components=3, init="pca", random_state=0).fit_transform(h.obsm["X_pca"][:, :40])

    raw, have = a.raw.to_adata(), set(a.raw.var_names)
    scores = {t: np.mean([dense(raw[:, g].X) for g in gs if g in have], axis=0)
              for t, gs in TYPE_MARKERS.items() if any(g in have for g in gs)}
    types = list(scores); mat = np.vstack([scores[t] for t in types])
    cluster = h.obs["cluster"].astype(str).to_numpy()
    cell_type = np.empty(a.n_obs, dtype=object)
    for cl in np.unique(cluster):
        m = cluster == cl
        cell_type[m] = types[int(mat[:, m].mean(axis=1).argmax())]

    attrs = [
        Attribute("cell_type", "cell type", "categorical", cell_type),
        Attribute("cluster", "cluster", "categorical", cluster),
        Attribute("n_genes", "genes detected", "continuous", a.obs["n_genes_by_counts"].to_numpy(), colormap="viridis"),
        Attribute("pct_mt", "% mitochondrial", "continuous", a.obs["pct_counts_mt"].to_numpy(), colormap="magma"),
    ] + [Attribute(g, f"{g} expression", "continuous", dense(raw[:, g].X), colormap="inferno")
         for g in CONT_MARKERS if g in have]

    coo = h.obsp["connectivities"].tocoo(); mk = coo.row < coo.col
    edges = np.column_stack([coo.row[mk], coo.col[mk], np.zeros(int(mk.sum()), int)])

    man = pack_atlas(
        OUT, ids=a.obs_names.tolist(),
        embeddings_2d={"umap": h.obsm["X_umap"], "tsne": h.obsm["X_tsne"]},
        embeddings_3d={"umap": h.obsm["X_umap_3d"], "tsne": h.obsm["X_tsne_3d"]},
        primary_2d="umap", attributes=attrs, edges=edges,
        title="PBMC 3k — single-cell RNA-seq", node_label="cells", id_label="barcode",
        hover_fields=["cell_type", "cluster", "n_genes", "pct_mt"],
        view_labels={"umap": "UMAP", "tsne": "t-SNE"}, extra_config={"modality": "RNA"},
    )
    print(f"packed {man['n_nodes']} cells -> {OUT}; cell types: {sorted(set(cell_type))}")


if __name__ == "__main__":
    main()
