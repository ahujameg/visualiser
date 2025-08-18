# Required for ontology parsing and similarity measures
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os

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
    distinct(case_ID_paper, .keep_all = TRUE) %>% 
    select(-HPO_Term_IDs)

  for (x in 1:nrow(TNAMSE_data_red)) {
    TNAMSE_data_red$HPO_term_IDs[[x]] <- (TNAMSE_data[which(TNAMSE_data$case_ID_paper == TNAMSE_data_red[x,]$case_ID_paper), ]$HPO_Term_IDs)
  }

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

  

  # # Precompute unique HPO term sets
  # unique_hpo_sets <- unique(TNAMSE_data_red$HPO_term_IDs)
  # similarity_cache <- list()

  # compute_similarity <- function(term_set) {
  #   key <- paste(sort(term_set), collapse = "_")
  #   if (!key %in% names(similarity_cache)) {
  #     similarity_cache[[key]] <- get_sim_grid(ontology = hpo, 
  #                                             information_content = descendants_IC(hpo),
  #                                             term_sets = list(term_set),
  #                                             term_sim_method = "resnik", 
  #                                             combine = "average")
  #   }
  #   return(similarity_cache[[key]])
  # }

  # # Compute similarity matrix using cached values
  # sim_results <- lapply(TNAMSE_data_red$HPO_term_IDs, compute_similarity)
  # master_sim_mat <- do.call(rbind, sim_results)

  # # Convert to sparse matrix for efficiency
  # master_sim_mat <- Matrix(master_sim_mat, sparse = TRUE)

  # # Optimize distance matrix computation
  # set.seed(1)
  # custom.settings <- umap.defaults
  # custom.settings$input <- "dist"
  # custom.settings$n_components <- 4
  
  # dist_matrix <- proxy::dist(as.matrix(max(master_sim_mat) - master_sim_mat) ** 2, method = "euclidean")
  
  # res_umap <- umap(as.matrix(dist_matrix), config = custom.settings)
  # colnames(res_umap$layout) <- paste0("dim", 1:(custom.settings$n_components))
  
  # TNAMSE_data_red <- cbind(TNAMSE_data_red, res_umap$layout)




  library(plyr)
  TNAMSE_and_HPO <- rbind.fill(TNAMSE_data_red, list_of_phenotypes_HPO)
  detach("package:plyr", unload = TRUE)

  # Generate similarity matrix and UMAP embedding
  information_content <- descendants_IC(hpo)
  
  print("Checking redo")
  print(redo)
  if (redo == "redo") {
    print(redo)
    # plan(multisession, workers = parallel::detectCores() - 1)
    # master_sim_mat <- future_lapply(TNAMSE_and_HPO$HPO_term_IDs, function(x) {
    #   get_sim_grid(ontology = hpo, information_content = information_content, term_sets = x, term_sim_method = "resnik", combine = "average")
    # })
    # plan(sequential)  # Reset plan
    master_sim_mat <- get_sim_grid(ontology = hpo, information_content = information_content,
                                   term_sets = TNAMSE_and_HPO$HPO_term_IDs, 
                                   term_sim_method = "resnik", combine = "average")
    write_rds(x = master_sim_mat, file = "master_sim_mat.RDS")
  } else {
    print("redo is off")
    master_sim_mat <- readRDS(file = "master_sim_mat.RDS")
  }

  set.seed(1)
  custom.settings <- umap.defaults
  custom.settings$input <- "dist"
  custom.settings$n_components <- 4

  res_umap <- umap(as.matrix(max(master_sim_mat) - master_sim_mat) ** 2, config = custom.settings)
  colnames(res_umap$layout) <- paste0("dim", 1:(custom.settings$n_components))
 

library(future.apply) 
print("before>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
  TNAMSE_and_HPO <- cbind(TNAMSE_and_HPO, res_umap$layout)

  
print("after>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
TNAMSE_and_HPO<- TNAMSE_and_HPO%>%
  mutate(dim1=-dim1,
         dim2=-dim2)

ggplot(TNAMSE_and_HPO, aes(x=dim1, y=dim2, color=disease_category)) +
  geom_point(alpha=0.2)


 number_of_clusters = 80
 set.seed(1)
 only_HPO<-TNAMSE_and_HPO %>% filter(disease_category == "HPO")

 clusters = kcca(only_HPO %>% dplyr::select(one_of(paste0("dim", 1:(custom.settings$n_components)))), k=number_of_clusters, kccaFamily("kmeans"))
 #plot(result_only_disease[,1], result_only_disease[,2], col=rainbow(max(clusters$cluster))[clusters$cluster+1], pch=20)



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



# cluster_stats_TNAMSE_cohort<-TNAMSE_and_HPO %>% 
#   dplyr::filter(disease_category!="HPO" | is.na(disease_category)) %>%
#   group_by(cluster_pred)%>%
#   add_count(name="cluster_size")%>%
#   group_by(cluster_pred,cluster_size)%>%
#   mutate(is_solved=mean(solved=="solved", na.rm=TRUE)) %>%
#   distinct(is_solved,cluster_pred,cluster_size)

# cluster_descriptions<- cbind(as.data.frame(cluster_descriptions), clusters@centers)
# write_tsv(x=cluster_descriptions, "cluster_descriptions.tsv")

#clusters_for_diseases <- read.table("clusters_with_clinical_annotation.txt", sep="\t", header=T)
#cluster_descriptions$manually_annotated_category<-clusters_for_diseases$Category


# TNAMSE_and_HPO <-TNAMSE_and_HPO %>% 
#   left_join(only_HPO %>% dplyr::select(case_ID_paper, cluster),
#             by=c("case_ID_paper"="case_ID_paper"), )%>%
#   left_join(cluster_stats_TNAMSE_cohort,
#             by=c("cluster_pred"="cluster_pred"), )

# plot_interim<-ggplot()+ theme_minimal() + theme(legend.position="bottom",panel.grid.major = element_blank(), panel.grid.minor = element_blank()) +
#   geom_point(data = TNAMSE_and_HPO %>% filter(disease_category=="HPO"),
#              aes(x = dim1, y = dim2), alpha=0.5, color="lightgrey") +
#   geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & !novel_disease_gene),
#              aes(x = dim1, y = dim2, color = disease_category), size=3) + 
#   geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & novel_disease_gene),
#              aes(x = dim1, y = dim2, color = disease_category), shape=17, size=5) + 
#   geom_label_repel(data = cluster_descriptions, aes(x=dim1, y=dim2, label=description), size=2, color="black", show.legend = FALSE)

# ggsave("plot_w_label.pdf", plot = plot_interim, width=50, height=50, units="cm", dpi=500, useDingbats=FALSE)

plot_interim<-ggplot()+ theme_minimal() + theme(legend.position="bottom",panel.grid.major = element_blank(), panel.grid.minor = element_blank()) +
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category=="HPO"),
             aes(x = dim1, y = dim2), alpha=0.5, color="lightgrey") +
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & !novel_disease_gene),
             aes(x = dim1, y = dim2, color = disease_category), size=3, shape=19) + 
  geom_point(data = TNAMSE_and_HPO %>% filter(disease_category!="HPO" & novel_disease_gene),
             aes(x = dim1, y = dim2, color = disease_category), fill="black", shape=24, size=4.0, stroke=1.5)

plot_interim

ggsave("plot_wo_label.pdf", plot = plot_interim, width=25, height=25, units="cm", dpi=500, useDingbats=FALSE)

  #print(TNAMSE_and_HPO)
  #return(TNAMSE_and_HPO)
  #print(str(TNAMSE_and_HPO))
  print(head(TNAMSE_and_HPO))
  #write.csv(TNAMSE_and_HPO, "rtnamse.csv")
  #write.csv(as.data.frame(TNAMSE_and_HPO), "rtnamse_frame.csv")
  TNAMSE_and_HPO[is.null(TNAMSE_and_HPO)] <- NA
  #TNAMSE_and_HPO <- lapply(TNAMSE_and_HPO, function(x) if (is.null(x)) NA else x)
  #save(as.data.frame(TNAMSE_and_HPO),file="data.Rda")
  
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
  #write.csv(cluster_descriptions, "cluster_descriptions.csv", row.names = FALSE)

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

def generate_umap(tnamse_data, lab, redo):
    
    # Read the genes_to_phenotype file and create a mapping dictionary
    gene_to_pheno = pd.read_csv("genes_to_phenotype.txt", sep="\t", dtype=str)
    
    labFile = lab + ".csv"

    # Filter
    tnamse_data = tnamse_data[(tnamse_data["disease_category"] != 'unspecified') & (tnamse_data["disease_category"] != 'other')]
    
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
    
    # Add rotated HPO points
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
        if category != 'HPO':  # Exclude HPO category
            subset = non_hpo_data[non_hpo_data['disease_category'] == category]
            hpos = non_hpo_data["HPO_Names"].str.wrap(60).apply(lambda x: x.replace('\n', '<br>'))
            text = 'Case ID: ' + subset["case_ID_paper"] + '<br>HPO Terms: ' + hpos
            #.append(subset["HPO_Names"].str.wrap(30).apply(lambda x: x.replace('\n', '<br>')))
            fig.add_trace(go.Scatter(
                x=subset['dim1'],
                y=subset['dim2'],
                mode='markers',
                marker=dict(size=10, color=color_map[category]),
                name=category,  # Legend entry for the category
                hovertext=text,  # Assign hover text
                hoverinfo="text"  # Ensure hover text is displayed
            ))

    # Add novel gene points
    fig.add_trace(go.Scatter(
        x=TNAMSE_and_HPO.loc[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['novel_disease_gene']), 'dim1'],
        y=TNAMSE_and_HPO.loc[(TNAMSE_and_HPO['disease_category'] != 'HPO') & (TNAMSE_and_HPO['novel_disease_gene']), 'dim2'],
        mode='markers',
        marker=dict(color='rgba(255, 0, 0, 0.0)', symbol='triangle-up', line=dict(width=2, color='black'), size=12),
        name='Novel Disease Gene'
    ))

    fig.update_layout(title="UMAP Visualization", xaxis_title="dim1", yaxis_title="dim2", autosize=True, width=800, height=600)

    return fig


