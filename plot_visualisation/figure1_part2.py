# Required for ontology parsing and similarity measures
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import numpy as np 

from rpy2.robjects import conversion, default_converter

    
# R Script for Data Preparation
r_script = """
library(ontologyIndex)
library(Rcpp)
library(ontologySimilarity)
library(tidyverse)
library(umap)
library(ggrepel)
library(flexclust)
library(proxy)
library(Matrix)
library(Matrix)
library(irlba)
library(RcppAnnoy)
library(igraph)

prepare_data <- function(TNAMSE_data, gene_to_pheno_path, hpo_obo, lab, redo) {

  hpo<-get_ontology(hpo_obo)
  blacklist_hpos = c("HP:0000006", "HP:0000007", "HP:0001417", "HP:0001419", "HP:0001423", "HP:0001428", "HP:0001450", "HP:0040284", "HP:0040283")
  only_phenotypes_hpo = get_descendants(hpo, "HP:0000118", exclude_roots = FALSE)
  hpos_to_keep =only_phenotypes_hpo[!only_phenotypes_hpo %in% blacklist_hpos]


   
  # format the HPO terms that we can use them as input; remove duplicated HPO terms
  gene_to_pheno <- read.table(gene_to_pheno_path, sep="\t", quote="", stringsAsFactors=FALSE, header=TRUE)

  TNAMSE_data <- TNAMSE_data %>% filter(is.na(HPO_Term_IDs)==FALSE)

  # Filter non-missing HPO Term IDs
  #TNAMSE_data <- TNAMSE_data %>% filter(!is.na(HPO_Term_IDs))

  # Clean and process HPO Term IDs
  TNAMSE_data$HPO_Term_IDs <- TNAMSE_data$HPO_Term_IDs %>% 
    str_replace_all(";", "") %>% strsplit(split = " ") %>% 
    sapply(., function(x) unique(x))

  TNAMSE_data <- TNAMSE_data %>% unnest_longer(HPO_Term_IDs)
  TNAMSE_data <- TNAMSE_data[TNAMSE_data$HPO_Term_IDs %in% hpos_to_keep,]

  # Deduplicate and clean data
  TNAMSE_data_red <- TNAMSE_data %>%
  group_by(case_ID_paper) %>%
  summarise(
    across(-HPO_Term_IDs, first),
    HPO_term_IDs = list(unique(HPO_Term_IDs)),
    .groups = "drop"
  )

  # Process gene-to-phenotype data
  gene_to_pheno <- gene_to_pheno[gene_to_pheno$HPO_Term_ID %in% hpos_to_keep,]
  overall_disease <- unique(gene_to_pheno$disease_ID_for_link)

  list_of_phenotypes_HPO <- data.frame()
  for (disease in overall_disease) {
    gene_to_pheno_disease <- gene_to_pheno[gene_to_pheno$disease_ID_for_link == disease,]
    #print(list_of_phenotypes_HPO)
    #print(list((gene_to_pheno_disease$HPO_Term_ID)))
    list_of_phenotypes_HPO <- rbind(
      list_of_phenotypes_HPO,
      data.frame(
        case_ID_paper = disease,
        HPO_term_IDs = I(list((gene_to_pheno_disease$HPO_Term_ID))),
        disease_category = "HPO",
        sequencing_laboratory = substring(disease, 1, 4),
        Disease_gene = I(list(unique(gene_to_pheno_disease$entrez_gene_symbol)))
      )
    )
  }


  library(plyr)
  TNAMSE_and_HPO <- rbind.fill(TNAMSE_data_red, list_of_phenotypes_HPO)
  detach("package:plyr", unload = TRUE)

  # Generate similarity matrix and UMAP embedding
  information_content <- descendants_IC(hpo)
  
  print("Checking redo")
  print(redo)
if (redo == "redo") {

  # ----------------------------
  # A) Prepare case list (1 row per case) and term_sets list
  # ----------------------------
  TNAMSE_cases <- TNAMSE_and_HPO %>%
    dplyr::distinct(case_ID_paper, .keep_all = TRUE)

  case_ids <- TNAMSE_cases$case_ID_paper
  term_sets <- TNAMSE_cases$HPO_term_IDs
  
  # Precompute exact-signature + ancestor-expanded term sets (avoid repeated get_ancestors)
  sig <- vapply(term_sets, function(ts) paste(sort(unique(ts[!is.na(ts)])), collapse="|"), character(1))

  anc_sets <- lapply(term_sets, function(ts) {
  ts <- unique(ts[!is.na(ts)])
  if (length(ts) == 0) return(character(0))
  parents <- unique(unlist(hpo$parents[ts]))
  out <- unique(c(ts, parents))
  out[!is.na(out)]
  })
  names(term_sets) <- case_ids

  n <- length(case_ids)
  if (n < 3) stop("Too few cases for embedding: ", n)

  # ----------------------------
  # B) Build sparse case x HPO matrix for candidate neighbor search
  # ----------------------------
  case_terms <- TNAMSE_cases %>%
    tidyr::unnest(HPO_term_IDs) %>%
    dplyr::filter(!is.na(HPO_term_IDs)) %>%
    dplyr::distinct(case_ID_paper, HPO_term_IDs)

  # Ensure consistent ordering of rows = case_ids
  case_terms$case_ID_paper <- factor(case_terms$case_ID_paper, levels = case_ids)

  hpo_levels <- sort(unique(case_terms$HPO_term_IDs))
  case_terms$HPO_term_IDs <- factor(case_terms$HPO_term_IDs, levels = hpo_levels)

  X <- Matrix::sparseMatrix(
    i = as.integer(case_terms$case_ID_paper),
    j = as.integer(case_terms$HPO_term_IDs),
    x = 1,
    dims = c(length(case_ids), length(hpo_levels)),
    dimnames = list(case_ids, hpo_levels)
  )

  # Optional but highly recommended: drop ultra-rare and ultra-common terms
  df <- Matrix::colSums(X > 0)
  keep_cols <- (df >= 2) & (df <= 0.5 * nrow(X))
  X <- X[, keep_cols, drop = FALSE]
  rm(df, keep_cols, case_terms); gc()

  # ----------------------------
  # C) TF-IDF + LSA embedding for fast kNN candidates
  # ----------------------------
  df2 <- Matrix::colSums(X > 0)
  idf <- log1p(nrow(X) / pmax(df2, 1))
  X_tfidf <- X %*% Diagonal(x = as.numeric(idf))

  # L2 normalize rows (so Euclidean ~ cosine-ish in low-dim space)
  rs <- sqrt(Matrix::rowSums(X_tfidf^2))
  rs[rs == 0] <- 1
  # Row-normalize without touching @x/@p directly (keeps matrix sparse)
  X_tfidf <- Matrix::Diagonal(x = as.numeric(1 / rs)) %*% X_tfidf

  cat("X_tfidf dims:", dim(X_tfidf), "\n"); flush.console()

  # LSA/SVD (keep this modest)
  svd_dim <- min(100, n - 1)
  sv <- irlba::irlba(X_tfidf, nv = svd_dim)
  Z <- sv$u %*% diag(sv$d)   # dense n x svd_dim

  rm(X, X_tfidf, sv, rs, df2, idf); gc()

  # ----------------------------
  # D) Candidate neighbors via Annoy
  # ----------------------------
  k <- min(200, n - 1)      # practical default
  if (n > 20000) k <- min(150, n - 1)
  annoy_trees <- 100

  ann <- RcppAnnoy::AnnoyEuclidean$new(ncol(Z))
  for (i in seq_len(nrow(Z))) ann$addItem(i - 1, Z[i, ])
  ann$build(annoy_trees)

  # neighbor list (indices 1..n)
  neigh_idx <- vector("list", n)
  for (i in seq_len(n)) {
    nn <- ann$getNNsByItem(i - 1, k + 1)
    nn <- nn[nn != (i - 1)] + 1  # drop self, convert to 1-based
    neigh_idx[[i]] <- nn
  }
  rm(Z, ann); gc()

  # Ensure identical phenotype profiles are directly connected (without ancestor smearing)
dup_groups <- split(seq_along(sig), sig)
dup_groups <- dup_groups[sapply(dup_groups, length) > 1]

for (g in dup_groups) {
  # connect within group (bounded)
  m <- min(length(g), 50L)
  for (ii in seq_along(g)) {
    i <- g[ii]
    # add up to (m-1) other members as neighbors
    others <- g[g != i]
    if (length(others) > (m - 1L)) others <- others[seq_len(m - 1L)]
    neigh_idx[[i]] <- unique(c(neigh_idx[[i]], others))
  }
}
  if (FALSE) {
  # ----------------------------
# D2) Augment candidates: all cases sharing at least one HPO term
#      (fixes "identical single-term cases far apart")
# ----------------------------

# Build inverted index: term -> case indices
term2cases <- new.env(parent = emptyenv())

for (i in seq_len(n)) {
  ts <- anc_sets[[i]]
  ts <- ts[!is.na(ts)]
  if (length(ts) == 0) next
  for (t in unique(ts)) {
    key <- as.character(t)
    if (exists(key, envir = term2cases, inherits = FALSE)) {
      term2cases[[key]] <- c(term2cases[[key]], i)
    } else {
      term2cases[[key]] <- i
    }
  }
}

# Add shared-term neighbors to each neigh list (cap to avoid explosion)
# precompute term frequency over expanded ancestors
term_freq <- new.env(parent=emptyenv())
for (i in seq_len(n)) {
  ts <- anc_sets[[i]]
  for (t in ts) {
    key <- as.character(t)
    term_freq[[key]] <- (if (exists(key, term_freq, inherits=FALSE)) term_freq[[key]] else 0L) + 1L
  }
}

cap_for_term <- function(t) {
  f <- term_freq[[as.character(t)]]
  if (is.null(f) || is.na(f)) return(50L)
  as.integer(max(50, min(800, round(2000 / sqrt(as.numeric(f))))))
}

for (i in seq_len(n)) {
  ts <- anc_sets[[i]]
  ts <- ts[!is.na(ts)]
  if (length(ts) == 0) next

  cand <- integer(0)

for (t in unique(ts)) {
  key <- as.character(t)

  if (!exists(key, envir = term2cases, inherits = FALSE)) next

  tmp <- term2cases[[key]]
  tmp <- tmp[tmp != i]
  tmp <- unique(tmp)

  cap <- cap_for_term(key)          # ✅ call per term
  if (length(tmp) > cap) tmp <- tmp[seq_len(cap)]  # ✅ cap per term

  cand <- c(cand, tmp)
}

cand <- unique(cand)
max_aug <- 500L
if (length(cand) > max_aug) {
  set.seed(i)
  cand <- sample(cand, max_aug)
}
neigh_idx[[i]] <- unique(c(neigh_idx[[i]], cand))
max_total <- 600L
if (length(neigh_idx[[i]]) > max_total) {
  set.seed(i)
  neigh_idx[[i]] <- sample(neigh_idx[[i]], max_total)
}

}
rm(term2cases); gc()
}
  # ----------------------------
  # E) Compute Resnik similarity ONLY for candidate pairs -> sparse matrix
  # ----------------------------
  information_content <- descendants_IC(hpo)

  ii <- integer(0)
  jj <- integer(0)
  vv <- numeric(0)

  # helper: Resnik avg similarity between two term sets (returns scalar)
    # helper: Resnik avg similarity between two term sets (returns scalar), with caching by phenotype signature
  resnik_cache <- new.env(parent = emptyenv(), hash = TRUE)

  resnik_avg_pair <- function(ts1, ts2, s1 = NULL, s2 = NULL) {
    if (is.null(s1)) s1 <- paste(sort(unique(ts1[!is.na(ts1)])), collapse="|")
    if (is.null(s2)) s2 <- paste(sort(unique(ts2[!is.na(ts2)])), collapse="|")

    key <- if (s1 <= s2) paste0(s1, "||", s2) else paste0(s2, "||", s1)

    if (exists(key, envir = resnik_cache, inherits = FALSE)) {
      return(resnik_cache[[key]])
    }

    ts1 <- unique(ts1); ts2 <- unique(ts2)
    ts1 <- ts1[!is.na(ts1)]; ts2 <- ts2[!is.na(ts2)]
    if (length(ts1) == 0 || length(ts2) == 0) {
      resnik_cache[[key]] <- NA_real_
      return(NA_real_)
    }

    g <- get_sim_grid(
      ontology = hpo,
      information_content = information_content,
      term_sets = list(ts1, ts2),
      term_sim_method = "resnik",
      combine = "average"
    )

    val <- as.numeric(g[1, 2])
    resnik_cache[[key]] <- val
    val
  }

  cat("Sparse Resnik: start at", format(Sys.time()), "\n"); flush.console()

  for (i in seq_len(n)) {
    js <- neigh_idx[[i]]
    
    
    if (length(js) == 0) next
    tsi <- term_sets[[i]]
    added_any <- FALSE
    for (j in js) {
      if (j <= i) next  # upper triangle only (symmetry)
      sim <- resnik_avg_pair(tsi, term_sets[[j]], sig[i], sig[j])
      if (!is.na(sim) && is.finite(sim)) {
        added_any <- TRUE
        ii <- c(ii, i)
        jj <- c(jj, j)
        vv <- c(vv, sim)
      }
    }
    
    if (!added_any && length(js) > 0) {
      # add a tiny edge to the closest candidate to avoid isolated nodes
      j0 <- js[1]
      ii <- c(ii, i)
      jj <- c(jj, j0)
      vv <- c(vv, 1e-6)
    }
    if (i %% 100 == 0) {
      cat("  computed pairs for i =", i, " / ", n, " at ", format(Sys.time()), "\n")
      flush.console()
    }
  }

  cat("Sparse Resnik: done at", format(Sys.time()), "\n"); flush.console()

  # Build symmetric sparse similarity matrix
  master_sim_mat <- Matrix::sparseMatrix(i = ii, j = jj, x = vv, dims = c(n, n), dimnames = list(case_ids, case_ids))
  master_sim_mat <- pmax(master_sim_mat, Matrix::t(master_sim_mat))
  Matrix::diag(master_sim_mat) <- 1

  # ----------------------------
# F) Enforce graph connectivity by adding a few "bridge" edges
# ----------------------------
if (requireNamespace("igraph", quietly = TRUE)) {

  # adjacency for components (ignore weights, just connectivity)
  A <- master_sim_mat
  A@x[A@x != 0] <- 1

  g <- igraph::graph_from_adjacency_matrix(A, mode = "undirected", diag = FALSE)
  comps <- igraph::components(g)$membership
  ncomp <- max(comps)

  cat("Graph components:", ncomp, "\n"); flush.console()

  if (ncomp > 1) {
    # main component = largest
    comp_sizes <- tabulate(comps, nbins = ncomp)
    main_comp <- which.max(comp_sizes)
    main_nodes <- which(comps == main_comp)

    # helper: pick a bridge target in main comp from candidate list
    pick_bridge_target <- function(i) {
      cand <- neigh_idx[[i]]
      cand <- cand[cand %in% main_nodes]
      if (length(cand) > 0) return(cand[1])
      # fallback: just pick a deterministic node from main comp
      main_nodes[1]
    }

    # Add one bridge per non-main component (very few edges)
    for (c in setdiff(seq_len(ncomp), main_comp)) {
      nodes_c <- which(comps == c)
      i <- nodes_c[1]
      j <- pick_bridge_target(i)

      # compute a real Resnik similarity for this bridge
      sim <- resnik_avg_pair(term_sets[[i]], term_sets[[j]], sig[i], sig[j])
      if (!is.na(sim) && is.finite(sim)) {
        master_sim_mat[i, j] <- sim
        master_sim_mat[j, i] <- sim
      } else {
        # if sim fails, still add a tiny weight so the graph is connected
        master_sim_mat[i, j] <- 1e-6
        master_sim_mat[j, i] <- 1e-6
      }
    }

    Matrix::diag(master_sim_mat) <- 1
  }

} else {
  cat("igraph not available; skipping connectivity bridges\n"); flush.console()
}

x_all <- master_sim_mat@x

# exclude diagonal-like 1s and tiny bridge weights from scaling stats
x_use <- x_all[x_all < 0.999999]
x_use <- x_use[x_use > 1e-5]

if (length(x_use) > 0) {
  mn <- as.numeric(stats::quantile(x_use, 0.01))
  mx <- as.numeric(stats::quantile(x_use, 0.99))
  if (mx > mn) {
    x_clamped <- pmin(pmax(x_all, mn), mx)
    master_sim_mat@x <- (x_clamped - mn) / (mx - mn)
    master_sim_mat@x <- pmax(master_sim_mat@x, 1e-6)
  }
}

Matrix::diag(master_sim_mat) <- 1


  saveRDS(master_sim_mat, file = "master_sim_mat_sparse_resnik.rds")

} else {
  master_sim_mat <- readRDS(file = "master_sim_mat_sparse_resnik.rds")
}



# sanity: identical term sets should have similarity > 0
dup_groups <- split(seq_along(sig), sig)
dup_groups <- dup_groups[sapply(dup_groups, length) > 1]
print(length(dup_groups))  # how many duplicated profiles

set.seed(1)

library(uwot)

# Convert similarity -> distance (only on edges)
D <- master_sim_mat
max_sim <- max(D@x[D@x < 0.999999])
D@x <- (max_sim - D@x)^2
Matrix::diag(D) <- 0
D <- Matrix::drop0(D, tol = 1e-12)

n <- nrow(D)

# UMAP neighbors: must be <= degree of your sparse graph (k used when building it)
deg <- Matrix::rowSums(D != 0)
deg_pos <- deg[deg > 0]
if (length(deg_pos) == 0) stop("All nodes have zero degree in sparse graph (no edges).")

k_cap <- as.integer(stats::quantile(deg_pos, 0.10))  # 10th percentile degree
k_cap <- max(10L, min(k_cap, 50L))                   # keep reasonable bounds
umap_k <- min(k_cap, n - 1)

idx_mat  <- matrix(1L, nrow = n, ncol = umap_k)
dist_mat <- matrix(1,  nrow = n, ncol = umap_k)

cat("nz==0 count:", sum(Matrix::rowSums(D != 0) == 0), "\n"); flush.console()
for (i in seq_len(n)) {
  row_i <- D[i, , drop = FALSE]
  nz <- which(row_i != 0)

  # If no neighbors (should be rare), connect to a dummy neighbor
 if (length(nz) == 0) {
  pool <- setdiff(seq_len(n), i)
  if (length(pool) >= umap_k) {
    idx_mat[i, ]  <- sample(pool, umap_k)
    dist_mat[i, ] <- rep(1, umap_k)
  } else {
    idx_mat[i, ]  <- c(pool, sample(pool, umap_k - length(pool), replace = TRUE))
    dist_mat[i, ] <- rep(1, umap_k)
  }
  next
}

  vals <- as.numeric(row_i[1, nz])  # distances on existing edges
  o <- order(vals, nz)                  # smallest distance = closest

  take <- min(umap_k, length(nz))
  sel_idx  <- nz[o[seq_len(take)]]
  sel_dist <- vals[o[seq_len(take)]]

  # pad if fewer than umap_k
  if (take < umap_k) {
  need <- umap_k - take
  pool <- setdiff(seq_len(n), c(i, sel_idx))
  if (length(pool) > 0) {
    extra <- pool[seq_len(min(need, length(pool)))]
    # use a "far" distance so these are weak links
    far <- max(sel_dist, 1)
    sel_idx  <- c(sel_idx, extra)
    sel_dist <- c(sel_dist, rep(far, length(extra)))
  }
  # if still short, fill with random (but not duplicates)
  if (length(sel_idx) < umap_k) {
    pool2 <- setdiff(seq_len(n), c(i, sel_idx))
    if (length(pool2) > 0) {
      extra2 <- sample(pool2, umap_k - length(sel_idx))
      far <- max(sel_dist, 1)
      sel_idx  <- c(sel_idx, extra2)
      sel_dist <- c(sel_dist, rep(far, length(extra2)))
    }
  }
}

  idx_mat[i, ]  <- as.integer(sel_idx)
  dist_mat[i, ] <- sel_dist
}

set.seed(1)
res_layout <- uwot::umap(
  X = NULL,
  n_neighbors  = umap_k,
  n_components = 4,
  nn_method    = list(idx = idx_mat, dist = dist_mat),
  min_dist     = 0.05,
  spread       = 1.0,
  n_threads    = 1,
  verbose      = TRUE
)

# ---- Deterministic orientation for publication (rigid rotation only) ----
pc <- prcomp(res_layout, center = TRUE, scale. = FALSE)
res_layout <- scale(res_layout, center = pc$center, scale = FALSE) %*% pc$rotation
colnames(res_layout) <- paste0("dim", 1:4)

res_umap <- list(layout = res_layout)
rownames(res_umap$layout) <- case_ids
library(future.apply) 
print("before>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
  umap_df <- as.data.frame(res_umap$layout)
umap_df$case_ID_paper <- rownames(res_umap$layout)

TNAMSE_and_HPO <- dplyr::left_join(TNAMSE_and_HPO, umap_df, by = "case_ID_paper")

  
print("after>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")


ggplot(TNAMSE_and_HPO, aes(x=dim1, y=dim2, color=disease_category)) +
  geom_point(alpha=0.2)


 number_of_clusters = 80
 set.seed(1)
 only_HPO<-TNAMSE_and_HPO %>% filter(disease_category == "HPO")

 custom.settings <- umap.defaults
  custom.settings$input <- "dist"
  custom.settings$n_components <- 4
 clusters = kcca(only_HPO %>% dplyr::select(one_of(paste0("dim", 1:(custom.settings$n_components)))), k=number_of_clusters, kccaFamily("kmeans"))



 only_HPO$cluster<-predict(clusters)
 TNAMSE_and_HPO$cluster_pred<-predict(clusters, newdata=TNAMSE_and_HPO %>% dplyr::select(one_of(paste0("dim", 1:(custom.settings$n_components)))))

 most_frequent_hpos_per_cluster<-only_HPO %>% group_by(cluster) %>% 
   add_count(name="count_of_patients_in_cluster") %>%
   ungroup() %>%
   unnest_longer(col=HPO_term_IDs) %>% 
   distinct(HPO_term_IDs,case_ID_paper, .keep_all = TRUE) %>%
   group_by(cluster,HPO_term_IDs) %>%
   add_count(name="count_of_HPO_term_in_Cluster")%>%
   distinct(cluster,HPO_term_IDs,count_of_HPO_term_in_Cluster,count_of_patients_in_cluster) %>%
   arrange(cluster,-count_of_HPO_term_in_Cluster)%>%
   mutate(proportion_w_HPO=round(count_of_HPO_term_in_Cluster/count_of_patients_in_cluster, 2))%>%
   group_by(cluster)%>%
   slice_max(order_by = count_of_HPO_term_in_Cluster, n = 5, with_ties=FALSE)

 most_frequent_hpos_per_cluster$HPO_Description<-sapply(most_frequent_hpos_per_cluster$HPO_term_IDs, function(x) hpo$name[hpo$id==x])



cluster_descriptions<-most_frequent_hpos_per_cluster %>% 
  group_by(cluster, count_of_patients_in_cluster) %>%
  mutate(description=paste0(paste(proportion_w_HPO,HPO_Description), collapse = "\n")) %>%
  distinct(cluster,count_of_patients_in_cluster,description)

plot_interim<-ggplot()+ theme_minimal() + theme(legend.position="bottom",panel.grid.major = element_blank(), panel.grid.minor = element_blank()) +
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category=="HPO"),
             aes(x = dim1, y = dim2), alpha=0.5, color="lightgrey") +
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & !novel_disease_gene),
             aes(x = dim1, y = dim2, color = disease_category), size=3, shape=19) + 
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & novel_disease_gene),
             aes(x = dim1, y = dim2, color = disease_category), fill="black", shape=24, size=4.0, stroke=1.5)

plot_interim

ggsave("plot_wo_label.pdf", plot = plot_interim, width=25, height=25, units="cm", dpi=500, useDingbats=FALSE)


  print(head(TNAMSE_and_HPO))
  TNAMSE_and_HPO[is.null(TNAMSE_and_HPO)] <- NA
  
  library(jsonlite)

# Convert list columns to JSON strings
TNAMSE_and_HPO_flat <- TNAMSE_and_HPO
TNAMSE_and_HPO_flat[] <- lapply(TNAMSE_and_HPO_flat, function(col) {
  if (is.list(col)) {
    return(sapply(col, toJSON, auto_unbox = TRUE))
  } else {
    return(col)
  }
})

  # Save the primary data
  write.csv(TNAMSE_and_HPO_flat, paste(lab, "csv", sep="."), row.names = FALSE)

  return(as.data.frame(TNAMSE_and_HPO))
}
"""



# Define file paths and inputs
args = [
    "hpo.obo",
    "genes_to_phenotype.txt",
    "redo"
]

hpo_obo = f"{args[0]}"
gene_to_pheno_path = f"{args[1]}"
#redo = args[2]

def generate_umap(tnamse_data, lab, selected_case_id, redo):
    
    # Read the genes_to_phenotype file and create a mapping dictionary
    gene_to_pheno = pd.read_csv("genes_to_phenotype.txt", sep="\t", dtype=str)
    
    labFile = lab + ".csv"

    # Filter
    #tnamse_data = tnamse_data[(tnamse_data["disease_category"] != 'unspecified') & (tnamse_data["disease_category"] != 'other')]

    if redo == 'redo' or not os.path.isfile(labFile) : 

      # Activate automatic conversion
      pandas2ri.activate()

      # Set the conversion explicitly
      conversion.set_conversion(default_converter)

      # Execute R script
      robjects.r(r_script)

      # Reference the R function
      prepare_data = robjects.globalenv['prepare_data']

      
      # Load Data
      #tnamse_data = pd.read_csv(in_file, sep="\t", decimal=",").drop_duplicates(subset="case_ID_paper")
     
      # Filter and Format Data
      tnamse_data = tnamse_data[tnamse_data["HPO_Term_IDs"].notna()]

      # Normalize `Frequency_HPO` column to a single type
      #gene_to_pheno["Frequency_HPO"] = gene_to_pheno["Frequency_HPO"].infer_objects()


      with conversion.localconverter(pandas2ri.converter):
        tnamse_data_r = conversion.py2rpy(tnamse_data)  # Convert Pandas DataFrame to R DataFrame

      # Call R function
      r_result = prepare_data(tnamse_data_r, gene_to_pheno_path, hpo_obo, lab, redo)


      #print(r_result)


    #TNAMSE_and_HPO = r_result
    # Load the data
    TNAMSE_and_HPO = pd.read_csv(labFile)
    #cluster_descriptions = pd.read_csv("cluster_descriptions.csv")
    print("Loaded TNAMSE_and_HPO:", TNAMSE_and_HPO)

    # Create a dictionary mapping HPO Term ID to HPO Term Name
    hpo_mapping = dict(zip(gene_to_pheno["HPO_Term_ID"], gene_to_pheno["HPO_Term_Name"]))

    # Convert HPO_Term_IDs column from JSON-like string to actual lists
    TNAMSE_and_HPO["HPO_term_IDs"] = TNAMSE_and_HPO["HPO_term_IDs"].apply(json.loads)

    # Map HPO term IDs to their names
    TNAMSE_and_HPO["HPO_Names"] = TNAMSE_and_HPO["HPO_term_IDs"].apply(
      lambda hpo_list: ", ".join([hpo_mapping.get(hpo, hpo) for hpo in hpo_list])
      if isinstance(hpo_list, list)
      else hpo_mapping.get(hpo_list, hpo_list)
    )
    
    #non_hpo_data = TNAMSE_and_HPO[(TNAMSE_and_HPO['disease_category'] != 'HPO')]
    non_hpo_data = TNAMSE_and_HPO[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['case_ID_paper'].isin(tnamse_data['case_ID_paper']))]
    hpo_data = TNAMSE_and_HPO[TNAMSE_and_HPO['disease_category'] == 'HPO']
    #novel_gene_data = TNAMSE_and_HPO[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['novel_disease_gene'])]

    print("non_hpo_data...", non_hpo_data)
    # Assign unique colors to each disease category
    categories = TNAMSE_and_HPO['disease_category'].unique()

    color_map = {
        "cardiovascular": "rgb(237,125,49)",  # Orange-like color
        "endocrine, metabolic, mitochondrial nutritional": "rgb(255,215,0)",
        "endocrine": "rgb(255,215,0)",
        "metabolic": "rgb(255, 102, 204)",
        "mitochondrial nutritional": "rgb(255,215,0)",  # Gold
        "neurodevelopmental": "rgb(91,155,213)",  # Light blue
        "haematopoiesis and immune system": "rgb(112,173,71)",  # Green
        "haematopoiesis/immune system": "rgb(112,173,71)",
        "organ abnormality": "rgb(196,90,94)",  # Pinkish
        "neurological neuromuscular": "rgb(177,160,199)",
        "neurological/neuromuscular": "rgb(177,160,199)",   # Light lilac
        "unspecified": "rgb(153, 102, 51)",
        "other": "rgb(153, 0, 0)"
    }

    TNAMSE_and_HPO['color'] = TNAMSE_and_HPO['disease_category'].map(color_map)

    # Re-plot using the rotated dimensions
    fig = make_subplots()

    text = hpo_data["HPO_Names"].str.wrap(60).apply(lambda x: x.replace('\n', '<br>'))
    
    # Add HPO points
    fig.add_trace(go.Scatter(
        x=hpo_data['dim1'],
        y=hpo_data['dim2'],
        mode='markers',
        marker=dict(color='lightgrey', opacity=0.5),
        name='HPO',
        hovertext=text,  # Assign hover text
        hoverinfo="text"  # Ensure hover text is displayed
    ))

    # Add scatter points for each non-HPO disease category  
    for category in categories:
        if category == 'HPO':
            continue

        subset = non_hpo_data[non_hpo_data['disease_category'] == category].copy()
        if subset.empty:
            continue

        # Filter out non-finite coordinates so every remaining point can render & hover
        finite = np.isfinite(subset['dim1'].to_numpy()) & np.isfinite(subset['dim2'].to_numpy())
        if not finite.any():
            continue
        subset = subset.loc[finite]

        # Build per-point hover text from THIS subset (indexes/lengths align)
        hpos_subset = (
            subset["HPO_Names"]
            .fillna("")
            .astype(str)
            .str.wrap(60)
            .str.replace("\n", "<br>")
        )
        # If a case has no HPO names, show a placeholder so hover isn’t empty
        hpos_subset = hpos_subset.replace("", "–")

        text = (
            "Case ID: " + subset["case_ID_paper"].astype(str) +
            "<br>HPO Terms: " + hpos_subset
        )

        fig.add_trace(go.Scatter(
            x=subset['dim1'],
            y=subset['dim2'],
            mode='markers',
            marker=dict(size=10, color=color_map.get(category, 'gray')),
            name=category,
            hovertext=text,       # aligned 1:1 with x/y
            hoverinfo="text",     # show only the text we provided
            hovertemplate="%{hovertext}<extra></extra>",  # cleaner hover box
        ))

    # Add the selected case trace LAST to ensure it is on top
    if selected_case_id:
        selected = TNAMSE_and_HPO[TNAMSE_and_HPO['case_ID_paper'] == selected_case_id]
        if not selected.empty:
            selected_hpos = (
                selected["HPO_Names"]
                .fillna("")
                .astype(str)
                .str.wrap(60)
                .str.replace("\n", "<br>")
            )
            text = (
                "Case ID: " + selected["case_ID_paper"].astype(str) +
                "<br>HPO Terms: " + selected_hpos
            )
            fig.add_trace(go.Scatter(
                x=selected['dim1'],
                y=selected['dim2'],
                mode='markers',
                marker=dict(
                    color='red', 
                    size=10,  # Larger size for visibility
                    line=dict(color='black', width=3)  # Distinct border
                ),
                name='selected case',
                hovertext=text,       # aligned 1:1 with x/y
                hoverinfo="text",     # show only the text we provided
                hovertemplate="%{hovertext}<extra></extra>",  # cleaner hover box
                hoverlabel=dict(
                    font=dict(color='black'),  # text color
                    bgcolor='red',           # optional: background color for contrast
                    bordercolor='black'        # optional: border
                )
            ))

    # Turn off 'other' and 'unspecified' categories by default
    for trace in fig.data:
        if trace.name == 'other' or trace.name == 'unspecified':
            trace.visible = 'legendonly'

    # Add novel gene points
    # fig.add_trace(go.Scatter(
    #     x=TNAMSE_and_HPO.loc[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['novel_disease_gene']), 'dim1'],
    #     y=TNAMSE_and_HPO.loc[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['novel_disease_gene']), 'dim2'],
    #     mode='markers',
    #     marker=dict(color='rgba(255, 0, 0, 0.0)', symbol='triangle-up', line=dict(width=2, color='black'), size=12),
    #     name='Novel Disease Gene'
    # ))

    # Position the legend inside the plot (top right)
    fig.update_layout(
        legend=dict(
            x=0.75,       # Horizontal position (0–1, left to right)
            y=0.05,       # Vertical position (0–1, bottom to top)
            bgcolor='rgba(255,255,255,0.5)',  # Optional: semi-transparent background
            bordercolor='Grey',
            borderwidth=1
        ),
        margin=dict(t=30, r=30, l=30, b=30)
    )

    fig.update_layout(title="UMAP Visualization", xaxis_title="dim1", yaxis_title="dim2", autosize=True, width=800, height=600)
    return fig
