# Example: PBMC 3k (single-cell RNA-seq)

**What it is:** 2,700 peripheral-blood mononuclear cells from the classic 10x
Genomics PBMC 3k dataset — the standard scanpy tutorial dataset. Each **point is a
cell**; nearby cells have similar gene-expression profiles. Processed with the
standard scanpy pipeline (QC → normalize → HVG → PCA → neighbors → Leiden clusters
→ UMAP & t-SNE in 2D and 3D). Clusters are named by canonical marker genes.

## Attributes (what you can color / filter / search by)

| Attribute | Type | Meaning |
|---|---|---|
| `cell type` | categorical | cluster named by markers: T cells, B cells, NK cells, CD14 / FCGR3A Monocytes, Dendritic, Megakaryocytes |
| `cluster` | categorical | raw unsupervised Leiden cluster id |
| `genes detected` | continuous | number of genes with non-zero counts in the cell (a QC metric) |
| `% mitochondrial` | continuous | fraction of counts from mito genes (a QC / stress metric) |
| `CD3D / MS4A1 / NKG7 / LYZ / FCGR3A / PPBP` | continuous | expression of marker genes (T / B / NK / mono / FCGR3A-mono / platelet) |

Hover id = the cell **barcode**. Edges = the kNN cell graph (toggle in Display).

## What it demonstrates
- **Categorical** color + legend-chip subsetting (cell type, cluster)
- **Continuous** color + numeric-range filtering (genes, %mito, marker expression)
- **Search** by barcode or cell-type name; **size-by** any continuous attribute

## Run
```bash
python3 ../../serve.py examples/singlecell        # data/ is committed — just serve it
# open http://127.0.0.1:8770/
python3 build.py                                  # (optional) regenerate data/ from scratch
```
`build.py` is self-contained (downloads PBMC 3k via scanpy); requires
`scanpy anndata umap-learn scikit-learn`.
