options(repos = c(CRAN = Sys.getenv("CRAN_REPO", "https://cloud.r-project.org")))

required_packages <- c(
  "ontologyIndex",
  "Rcpp",
  "ontologySimilarity",
  "umap",
  "proxy",
  "Matrix",
  "irlba",
  "RcppAnnoy",
  "igraph",
  "dplyr",
  "tidyr",
  "stringr",
  "ggplot2",
  "plyr",
  "reticulate"
)

installed <- rownames(installed.packages())
missing <- setdiff(required_packages, installed)

if (length(missing) > 0) {
  cores <- max(1L, parallel::detectCores(logical = FALSE) - 1L)
  install.packages(
    missing,
    dependencies = c("Depends", "Imports", "LinkingTo"),
    Ncpus = cores
  )
}

remaining <- setdiff(required_packages, rownames(installed.packages()))
if (length(remaining) > 0) {
  stop("Missing required R packages after installation: ", paste(remaining, collapse = ", "))
}

for (package in required_packages) {
  suppressPackageStartupMessages(
    library(package, character.only = TRUE)
  )
}

message("Verified R packages: ", paste(required_packages, collapse = ", "))
