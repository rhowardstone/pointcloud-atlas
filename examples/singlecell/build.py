"""Single-cell example for pointcloud-atlas: anndata -> generic packer.

Reuses the demo AnnData built by ../../sc_atlas/build_pbmc_demo.py (pbmc3k). Shows
how a domain wraps the generic packer: build Attributes (categorical + continuous)
and call pack_atlas. The continuous marker-gene attributes exercise color-by-gene.
"""
import sys
from pathlib import Path

import numpy as np
import scanpy as sc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packer"))
from pack import Attribute, pack_atlas  # noqa: E402

H5AD = ROOT.parent / "sc_atlas" / "demo_data" / "demo.h5ad"
OUT = Path(__file__).resolve().parent / "data"
MARKERS = ["CD3D", "MS4A1", "NKG7", "LYZ", "PPBP"]  # T, B, NK, mono, platelet


def main():
    a = sc.read_h5ad(H5AD)
    n = a.n_obs
    attrs = [
        Attribute("cluster", "cluster", "categorical", a.obs["cluster"].to_numpy()),
        Attribute("library", "library", "categorical", a.obs["library"].to_numpy()),
        Attribute("n_genes", "genes detected", "continuous",
                  a.obs["n_genes_by_counts"].to_numpy(), colormap="viridis"),
        Attribute("pct_mt", "% mito", "continuous",
                  a.obs["pct_counts_mt"].to_numpy(), colormap="magma"),
    ]
    # marker-gene expression (from .raw lognorm), as continuous color-by attrs
    raw = a.raw.to_adata() if a.raw is not None else a
    for g in MARKERS:
        if g in raw.var_names:
            x = raw[:, g].X
            x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
            attrs.append(Attribute(g, f"{g} expr", "continuous", x, colormap="inferno"))

    emb2 = {"umap": a.obsm["X_umap"], "tsne": a.obsm["X_tsne"]}
    emb3 = {"umap": a.obsm["X_umap_3d"], "tsne": a.obsm["X_tsne_3d"]}
    edges = None
    if "connectivities" in a.obsp:
        coo = a.obsp["connectivities"].tocoo()
        m = coo.row < coo.col
        edges = np.column_stack([coo.row[m], coo.col[m], np.zeros(m.sum(), int)])

    man = pack_atlas(
        OUT, ids=a.obs_names.tolist(),
        embeddings_2d=emb2, embeddings_3d=emb3, primary_2d="umap",
        attributes=attrs, edges=edges,
        title="PBMC 3k — single-cell atlas", node_label="cells", id_label="barcode",
        hover_fields=["cluster", "library", "n_genes"],
        view_labels={"umap": "UMAP", "tsne": "t-SNE"},
        extra_config={"modality": "RNA"},
    )
    print(f"packed {man['n_nodes']} cells, {man['n_edges']} edges -> {OUT}")
    print("color-by:", [c["key"] for c in man["config"]["color_by"]])


if __name__ == "__main__":
    main()
