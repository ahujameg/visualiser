# Category assignment, Venn diagram, and UMAP

This directory contains an HPO-based workflow for assigning disease categories
to input cases and visualising the result as a Venn diagram or UMAP.

Run all commands below from the repository root (`visualiser/`).

## Use the category-assignment implementation

The application normally imports `plot_visualisation/views.py`, and that module
normally imports `plot_visualisation/figure1_part2.py`. Before running this
workflow, replace both files with their `_assign_category` counterparts:

```bash
cp plot_visualisation/views.py plot_visualisation/views.py.bak
cp plot_visualisation/figure1_part2.py plot_visualisation/figure1_part2.py.bak
cp plot_visualisation/views_assign_category.py plot_visualisation/views.py
cp plot_visualisation/figure1_part2_assign_category.py plot_visualisation/figure1_part2.py
```

The backup commands preserve the original implementations. To restore them:

```bash
mv plot_visualisation/views.py.bak plot_visualisation/views.py
mv plot_visualisation/figure1_part2.py.bak plot_visualisation/figure1_part2.py
```

## Input data

The current workflow reads the tab-separated file.


To use another set of cases, either replace that file or change `file_path` in:

- `plot_visualisation/views.py` for UMAP generation
- `plot_visualisation/venn_diagram.py` for Venn generation

The input must contain these columns:

| Column | Meaning |
| --- | --- |
| `patient_id` | Unique case identifier |
| `gene` | Gene/variant value displayed with the case |
| `hpo_terms` | Semicolon-separated HPO IDs, for example `HP:0001250;HP:0001263` |

`image_id` is listed by the loader but is not currently used. Missing or empty
`hpo_terms` values are accepted and become `unspecified`.

The following reference files must exist in the repository root:

- `hpo.obo`
- `genes_to_phenotype.txt`

The Python and R dependencies must also be installed as described in the
repository-level `README.md`. The UMAP code additionally uses the R packages
listed near the top of `figure1_part2.py`, including `ontologyIndex`,
`ontologySimilarity`, `tidyverse`, `umap`, `flexclust`, `proxy`, and `Matrix`.

## How a category is assigned

1. Each case's `hpo_terms` string is split on semicolons.
2. Obsolete HPO terms are replaced using their `replaced_by` or `consider`
   entry from `hpo.obo`.
3. For every term, the ontology is traversed through its `is_a` parents until
   one or more roots in `HPO_CATEGORY_MAP` are reached.
4. The UMAP loader reduces the resulting categories to the three classes used
   by this analysis:
   - both `neurodevelopmental` and `immune system` -> `overlap`
   - `neurodevelopmental` only -> `neurodevelopmental`
   - `immune system` only -> `immune system`
5. Cases with no mapped category become `unspecified`. Cases mapping only to
   another category are currently skipped by the UMAP loader.

The Venn workflow keeps all categories found during ontology traversal, then
tests each case for membership in `neurodevelopmental`, `immune system`, or
both.

The category roots and labels are defined in `HPO_CATEGORY_MAP` in both
`views.py` and `venn_diagram.py`. Keep the two maps synchronized if the mapping
is changed.

## Generate the Venn diagram

After setting the desired input path at the bottom of
`plot_visualisation/venn_diagram.py`, run:

```bash
pipenv run python plot_visualisation/venn_diagram.py
```

The script calls `generate_proportional_venn()` and produces:

- `/tmp/proportional_venn_diagram.html` — interactive Plotly output
- `venn.svg` — Plotly SVG output
- `venn_matplotlib.svg` — Matplotlib SVG output

The diagram compares the `neurodevelopmental` and `immune system` case sets.
Open the HTML file in a browser to inspect the interactive result.

## Generate the UMAP

Confirm that `file_path` in the `plot_umap()` function in
`plot_visualisation/views.py` points to the desired TSV. Then start Django:

```bash
pipenv run python manage.py runserver 7000
```

In another terminal, request UMAP generation:

```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{}' \
  http://127.0.0.1:7000/api/plot/umap/
```

The request body is currently ignored; the view uses these fixed values:

```text
lab = allLabs
redo = no
selected_case_id = null
```

The generated files are:

- `/tmp/umap_IEI.html` — interactive Plotly output
- `umap_IEI.svg` — SVG output
- `allLabs.csv` — cached embedding data

UMAP also uses `master_sim_mat.RDS` as the cached HPO similarity matrix. To
fully recompute the embedding for changed input cases, set `redo = 'redo'` in
`plot_umap()` before making the request. With `redo = 'no'`, existing
`allLabs.csv` data is reused; if that CSV does not exist, the R workflow runs
and expects a compatible `master_sim_mat.RDS` cache.

## Common issues

- Run commands from the repository root because several paths are relative.
- The code currently contains absolute paths to `hpo.obo` and the example TSV.
  Update them when the repository is checked out elsewhere.
- Static image export (`.svg`) requires Plotly's Kaleido/Chrome support.
- A changed HPO ontology, gene-to-phenotype file, or input cohort requires
  regeneration of the cached similarity matrix and embedding.
