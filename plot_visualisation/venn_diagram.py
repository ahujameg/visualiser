from matplotlib_venn import venn2
import matplotlib.pyplot as plt
import plotly.io as pio
import plotly.tools as mpl_to_plotly
import os
import obonet

pio.get_chrome()

# Optional: example priority for tie-breaking
CATEGORY_PRIORITY = [ 
  'neurological',
  'neurodevelopmental',
  'metabolism/homeostasis',
  'cardiovascular',
  'immune system',
  'endocrine',
  'hematopoietic',
  'musculoskeletal',
  'genitourinary',
  'digestive system',
  'respiratory',
  'head or neck',
  'eye',
  'ear',
  'integument',
  'prenatal development or birth',
  'limbs',
  'breast',
  'thoracic cavity',
  'voice'
]

# Example mapping (simplified)
HPO_CATEGORY_MAP = {
  'HP:0001871': 'hematopoietic',
  'HP:0000152': 'head or neck',
  'HP:0040064': 'limbs',
  'HP:0001939': 'metabolism/homeostasis',
  'HP:0001197': 'prenatal development or birth',
  'HP:0000769': 'breast',
  'HP:0001626': 'cardiovascular',
  'HP:0025031': 'digestive system',
  'HP:0000598': 'ear',
  'HP:0000818': 'endocrine',
  'HP:0000478': 'eye',
  'HP:0000119': 'genitourinary',
  'HP:0002715': 'immune system',
  'HP:0001574': 'integument',
  'HP:0033127': 'musculoskeletal',
  'HP:0000707': 'neurological',
  'HP:0012759': 'neurodevelopmental',
  'HP:0002086': 'respiratory',
  'HP:0045027': 'thoracic cavity',
  'HP:0001608': 'voice',
}

def load_hpo_graph(obo_file_path):
    """
    Load the HPO graph from the .obo file and handle obsolete terms.
    """
    graph = obonet.read_obo(obo_file_path, ignore_obsolete=False)
    print(f"Graph loaded successfully with {len(graph.nodes)} nodes.")

    return graph

def replace_obsolete_terms(graph, hpo_terms):
    # Handle obsolete terms
    replaced_terms = []
    for hpo_term in hpo_terms:
        if hpo_term in graph.nodes:
            data = graph.nodes[hpo_term]
            if data.get("is_obsolete") == "true":
                print(f"Obsolete term found: {hpo_term}")
                if "replaced_by" in data or "consider" in data:
                    # Ensure replaced_by is a string (or handle lists)
                    if "replaced_by" in data:
                        replacement = data["replaced_by"]
                    else:
                        replacement = data["consider"] 

                    if isinstance(replacement, list):
                        replaced_terms.extend(replacement)  # Add all replacements if it's a list
                    else:
                        replaced_terms.append(replacement)  # Add single replacement
                    print(f"Term {hpo_term} is replaced by {replacement}")
                else:
                    print(f"Term {hpo_term} is obsolete but has no replacement.")
            else:
                replaced_terms.append(hpo_term)
        else:
            # If the term is not in the graph, keep it as is
            replaced_terms.append(hpo_term)
    
    return replaced_terms

def flatten(nested_data):
    for x in nested_data:
        # Check if it is a list but NOT a string
        if isinstance(x, (list, tuple)) and not isinstance(x, str):
            yield from flatten(x)
        else:
            yield x

import itertools
def walk_to_category(hpo_id, graph, visited=None):
    if visited is None:
        visited = set()
    if hpo_id in visited:
        return None
    visited.add(hpo_id)
    if hpo_id in HPO_CATEGORY_MAP:
        return HPO_CATEGORY_MAP[hpo_id]
    if hpo_id in graph.nodes:
        parents = graph.nodes[hpo_id].get('is_a', [])
    else:
        print(f"Warning: HPO ID {hpo_id} not found in graph.")
        return []
    categories = []
    for parent_id in parents:
        if parent_id in graph:
            cat = walk_to_category(parent_id, graph, visited)
            if cat:
                if isinstance(cat, list):
                    # flat_list = [item for sublist in cat for item in sublist]
                    categories.extend(list(flatten(cat)))
                else:
                    categories.append(cat)

    return list(flatten(categories))


def assign_multiple_category_from_obo(hpo_list, graph):
    categories = []
    for hpo_id in hpo_list:
        category = walk_to_category(hpo_id.strip(), graph)
        if category:
            categories.extend(category)

    if not categories:
        return "unspecified"

    return categories

import pandas as pd
def load_dataInput_fr_IEI(file_path):
    df = pd.read_csv(file_path, sep='\t')

    transformed = []
    graph = load_hpo_graph("/home/meghna/Documents/git-repo/TNAMSE/HGQN-Middleware/visualiser/hpo.obo")

    for _, row in df.iterrows():
        if pd.isna(row['hpo_terms']) or not isinstance(row['hpo_terms'], str):
            hpo_term_list = []
        else:
            hpo_term_list = [term.strip() for term in row['hpo_terms'].split(';') if term.strip()]
        
        # Check if any of hpo_term_list are obsolete and replace them by their replacements
        hpo_term_list = replace_obsolete_terms(graph, hpo_term_list)
        categories = assign_multiple_category_from_obo(hpo_term_list,graph)
        if (str(row["patient_id"])=="14321"):
            print(f"Assigned categories for patient {row['patient_id']}: {categories}")
        case = {
            "case_ID_paper": str(row["patient_id"]),
            "HPO_Term_IDs": "; ".join(hpo_term_list),
            "disease_categories": categories,
        }
        transformed.append(case)

    return pd.DataFrame(transformed)

def generate_venn_for_categories(file_path, output_dir="/tmp", output_filename="venn_diagram.html"):
    """
    Generate a Venn diagram for the overlap between 'neurodevelopmental' and 'immune system',
    and save it as an HTML file that can be accessed via a URL.
    """
    # Load the data
    all_cases = load_dataInput_fr_IEI(file_path)

    # Filter cases for the two categories
    neuro_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'neurodevelopmental' in x)]['case_ID_paper'])
    immune_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'immune system' in x)]['case_ID_paper'])

    # Calculate the overlap
    only_neuro = len(neuro_cases - immune_cases)
    only_immune = len(immune_cases - neuro_cases)
    overlap = len(neuro_cases & immune_cases)

    # Create the Venn diagram using matplotlib_venn
    plt.figure(figsize=(8, 8))
    venn = venn2(subsets=(only_neuro, only_immune, overlap), set_labels=('Neurodevelopmental', 'Immune System'))
    plt.title("Overlap Between Neurodevelopmental and Immune System Categories")

    # Convert the matplotlib figure to a Plotly figure
    plotly_fig = mpl_to_plotly.mpl_to_plotly(plt.gcf())
    plt.close()

    # Save the Plotly figure as an HTML file
    output_path = os.path.join(output_dir, output_filename)
    pio.write_html(plotly_fig, file=output_path, auto_open=False)

    # Return the URL to the saved HTML file
    return f"file://{output_path}"

import plotly.graph_objects as go
import os

def generate_interactive_venn(file_path, output_dir="/tmp", output_filename="interactive_venn_diagram.html"):
    """
    Generate an interactive Venn diagram for the overlap between 'neurodevelopmental' and 'immune system',
    and save it as an HTML file that can be accessed via a URL.
    """
    # Load the data
    all_cases = load_dataInput_fr_IEI(file_path)

    # Filter cases for the two categories
    neuro_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'neurodevelopmental' in x)]['case_ID_paper'])
    immune_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'immune system' in x)]['case_ID_paper'])

    # Calculate the overlap
    only_neuro = neuro_cases - immune_cases
    only_immune = immune_cases - neuro_cases
    overlap = neuro_cases & immune_cases

    # Sizes for the Venn diagram
    size_only_neuro = len(only_neuro)
    size_only_immune = len(only_immune)
    size_overlap = len(overlap)

    # Create the Venn diagram using Plotly
    fig = go.Figure()

    # Pre-compute circle geometry (centers and label offsets)
    left_center = (1.0, 1.0)
    right_center = (2.0, 1.0)
    label_offset = 0.45  # small offset keeps text inside exclusive regions

    # Add the first circle (Neurodevelopmental)
    fig.add_shape(
        type="circle",
        xref="x",
        yref="y",
        x0=left_center[0] - 1,
        y0=left_center[1] - 1,
        x1=left_center[0] + 1,
        y1=left_center[1] + 1,
        line_color="blue",
        opacity=0.5,
        fillcolor="blue",
    )
    fig.add_trace(go.Scatter(
        x=[left_center[0] - label_offset],
        y=[left_center[1]],
        text=[f"neurodevelopmental<br>only: {size_only_neuro}"],
        mode="text",
        textfont=dict(size=14, color="blue"),
        showlegend=False
    ))

    # Add the second circle (Immune System)
    fig.add_shape(
        type="circle",
        xref="x",
        yref="y",
        x0=right_center[0] - 1,
        y0=right_center[1] - 1,
        x1=right_center[0] + 1,
        y1=right_center[1] + 1,
        line_color="green",
        opacity=0.5,
        fillcolor="green",  
    )
    fig.add_trace(go.Scatter(
        x=[right_center[0] + label_offset],
        y=[right_center[1]],
        text=[f"immune system<br>only: {size_only_immune}"],
        mode="text",
        textfont=dict(size=14, color="green"),
        showlegend=False
    ))

    # Add the overlap text (midpoint between both centers)
    overlap_center_x = (left_center[0] + right_center[0]) / 2
    fig.add_trace(go.Scatter(
        x=[overlap_center_x],
        y=[left_center[1]],
        text=[f"Overlap: {size_overlap}"],
        mode="text",
        textfont=dict(size=14, color="purple"),
        showlegend=False
    ))

    # Update layout
    fig.update_layout(
        title="Venn Diagram: neurodevelopmental vs immune system",
        xaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-0.5, 3.5]),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            visible=False,
            scaleanchor="x",
            scaleratio=1,
            range=[-0.5, 2.5],
        ),
        width=800,
        height=600,
    )

    # Save the Plotly figure as an HTML file
    output_path = os.path.join(output_dir, output_filename)
    fig.write_html(output_path, auto_open=False)

    # Return the URL to the saved HTML file
    return f"file://{output_path}"

import math
import plotly.graph_objects as go
import os

def calculate_overlap_area(r1, r2, d):
    """
    Calculate the area of overlap between two circles.
    """
    if d >= r1 + r2:
        return 0  # No overlap
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2  # One circle is completely inside the other

    part1 = r1**2 * math.acos((d**2 + r1**2 - r2**2) / (2 * d * r1))
    part2 = r2**2 * math.acos((d**2 + r2**2 - r1**2) / (2 * d * r2))
    part3 = 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
    return part1 + part2 - part3

def generate_proportional_venn(file_path, output_dir="/tmp", output_filename="proportional_venn_diagram.html"):
    """
    Generate a proportional Venn diagram for the overlap between 'neurodevelopmental' and 'immune system',
    and save it as an HTML file that can be accessed via a URL.
    """
    # Load the data
    all_cases = load_dataInput_fr_IEI(file_path)

    # Filter cases for the two categories
    neuro_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'neurodevelopmental' in x)]['case_ID_paper'])
    immune_cases = set(all_cases[all_cases['disease_categories'].apply(lambda x: 'immune system' in x)]['case_ID_paper'])

    # Calculate the overlap
    only_neuro = neuro_cases - immune_cases
    only_immune = immune_cases - neuro_cases
    overlap = neuro_cases & immune_cases

    # Sizes for the Venn diagram
    size_only_neuro = len(only_neuro)
    size_only_immune = len(only_immune)
    size_overlap = len(overlap)

    # Calculate radii of the circles
    r_neuro = math.sqrt(size_only_neuro + size_overlap)  # Radius of Neurodevelopmental circle
    r_immune = math.sqrt(size_only_immune + size_overlap)  # Radius of Immune System circle

    # Find the distance between the centers of the circles
    d_min, d_max = 0, r_neuro + r_immune
    d = d_max
    for _ in range(100):  # Iterative adjustment
        d_mid = (d_min + d_max) / 2
        overlap_area = calculate_overlap_area(r_neuro, r_immune, d_mid)
        if overlap_area < size_overlap:
            d_max = d_mid
        else:
            d_min = d_mid
        d = d_mid

    # Create the Venn diagram using Plotly
    fig = go.Figure()

    # Circle centers (aligned along the x-axis for easier label placement)
    left_center = (r_neuro, 0.0)
    right_center = (d + r_immune, 0.0)
    overlap_center_x = (left_center[0] + right_center[0]) / 2 if (size_overlap > 0) else left_center[0]

    # Add the first circle (Neurodevelopmental)
    fig.add_shape(
        type="circle",
        xref="x",
        yref="y",
        x0=left_center[0] - r_neuro,
        y0=-r_neuro,
        x1=left_center[0] + r_neuro,
        y1=r_neuro,
        line_color="blue",
        opacity=0.5,
        fillcolor="rgb(0,0,255)",
    )
    left_offset = r_neuro * 0.5 if r_neuro else 0
    fig.add_trace(go.Scatter(
        x=[left_center[0] - left_offset],
        y=[left_center[1]],
        text=[f"neurodevelopmental<br>only: {size_only_neuro}"],
        mode="text",
        textfont=dict(size=14, color="blue"),
        showlegend=False
    ))

    # Add the second circle (Immune System)
    fig.add_shape(
        type="circle",
        xref="x",
        yref="y",
        x0=right_center[0] - r_immune,
        y0=-r_immune,
        x1=right_center[0] + r_immune,
        y1=r_immune,
        line_color="rgb(255,165,0)",
        opacity=0.5,
        fillcolor="rgb(255,165,0)",
    )
    right_offset = r_immune * 0.5 if r_immune else 0
    fig.add_trace(go.Scatter(
        x=[right_center[0] + right_offset],
        y=[right_center[1]],
        text=[f"immune system<br>only: {size_only_immune}"],
        mode="text",
        textfont=dict(size=14, color="green"),
        showlegend=False
    ))

    # Add the overlap text (only if overlap exists)
    overlap_text = f"overlap: {size_overlap}" if size_overlap else "no overlap"
    fig.add_trace(go.Scatter(
        x=[overlap_center_x + 0.4],
        y=[0],
        text=[overlap_text],
        mode="text",
        textfont=dict(size=14, color="purple"),
        showlegend=False
    ))

    # Update layout
    fig.update_layout(
        title="Venn Diagram: neurodevelopmental vs immune system",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            visible=False,
            range=[-0.2 * max(1, r_neuro), d + 2 * r_immune + 0.2 * max(1, r_immune)]
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            visible=False,
            scaleanchor="x",
            scaleratio=1,
            range=[-max(r_neuro, r_immune) - 0.5, max(r_neuro, r_immune) + 0.5],
        ),
        width=800,
        height=600,
    )

    # Save the Plotly figure as an HTML file
    output_path = os.path.join(output_dir, output_filename)
    fig.write_html(output_path, auto_open=False)
    fig.write_image("venn.svg")

    # Create the Venn diagram with matplotlib_venn.
    # IMPORTANT: matplotlib_venn.venn2 expects numeric subset sizes
    # in the order (only_set1, only_set2, intersection), not Python sets.
    plt.figure(figsize=(6, 6))
    venn2(
        subsets=(size_only_neuro, size_only_immune, size_overlap),
        set_labels=('Neurodevelopmental', 'Immune System'),
        set_colors=("blue", "orange"),
        alpha=0.6,
    )

    plt.title("Venn Diagram: neurodevelopmental vs immune system")
    plt.tight_layout()
    plt.savefig("venn_matplotlib.svg")

    # Return the URL to the saved HTML file
    return f"file://{output_path}"

file_path = "/home/meghna/Documents/git-repo/TNAMSE/HGQN-Middleware/visualiser/plot_visualisation/IEI_patients_with_hpo_and_category.tsv"
output_url = generate_proportional_venn(file_path)
print(f"Venn diagram saved at: {output_url}")
