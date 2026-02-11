import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.http import JsonResponse
import plotly.io as pio
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from django.db.models.fields.json import JSONField
from django.conf import settings
from django.contrib import messages
from plot_visualisation.figure1_part2 import generate_umap

# or for a class-based DRF view
from rest_framework.authentication import SessionAuthentication
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
import pandas as pd
import numpy as np

class CsrfExemptSessionAuth(SessionAuthentication):
    def enforce_csrf(self, request):  # disable check
        return

def index(request):
    return render(request, 'index.html')

def generate_plotly_bar_chart(data):
    # Extract data
    disease_categories = data['Disease Category']
    case_counts = data['Case Count']
    diagnosed_cases = data['Diagnosed Cases']

    # Calculate diagnostic yield
    diagnostic_yield = [d / c for d, c in zip(diagnosed_cases, case_counts)]

    # Create the Plotly bar chart
    fig = go.Figure()

    # Add the bar chart data
    fig.add_trace(go.Bar(
        x=disease_categories,
        y=diagnostic_yield,
        name='Diagnostic Yield',
        marker_color='skyblue'
    ))

    # Set titles and labels
    fig.update_layout(
        title='Diagnostic Yield by Disease Category',
        xaxis_title='Disease Category',
        yaxis_title='Diagnostic Yield',
        template='plotly_white'
    )

    # Return the plot as a JSON object
    return fig.to_dict()

# Validation function to check required fields
def validate_json_data(data):
#    required_fields = ['id', 'age_group', 'gender', 'hpo_terms', 'novel_gene', 'is_solved', 'autozygosity']
    required_fields = ['solved', 'disease_category']

    errors = []

    for idx, entry in enumerate(data):
        missing_fields = [field for field in required_fields if field not in entry]

        if missing_fields:
            errors.append(f"Missing fields {missing_fields} in entry {idx + 1}")

        # Additional checks for specific fields can be added here
        # if 'id' in entry and not isinstance(entry['id'], int):
        #     errors.append(f"Field 'id' must be an integer in entry {idx + 1}")

        # if 'age_group' in entry and not isinstance(entry['age_group'], str):
        #     errors.append(f"Field 'age_group' must be a string in entry {idx + 1}")

        # if 'gender' in entry and not isinstance(entry['gender'], str):
        #     errors.append(f"Field 'gender' must be a string in entry {idx + 1}")

        # if 'hpo_terms' in entry and not isinstance(entry['hpo_terms'], str):
        #     errors.append(f"Field 'hpo_terms' must be a string in entry {idx + 1}")

        # if 'novel_gene' in entry and not isinstance(entry['novel_gene'], bool):
        #     errors.append(f"Field 'novel_gene' must be a boolean in entry {idx + 1}")

        if 'solved' in entry and not isinstance(entry['solved'], str):
            errors.append(f"Field 'is_solved' must be a string in entry {idx + 1}")

        if 'disease_category' in entry and not isinstance(entry['disease_category'], str):
            errors.append(f"Field 'disease_category' must be a string in entry {idx + 1}")

    return errors

@csrf_exempt
@api_view(["POST"])
def plot_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        # Load the JSON data from the request
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    # Convert API data to DataFrame (accept either list or {"data": [...]})
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        all_cases = pd.DataFrame(data["data"])
    else:
        all_cases = pd.DataFrame(data)

    # Basic validation
    required_cols = {"disease_category", "solved"}
    missing = [c for c in required_cols if c not in all_cases.columns]
    if missing:
        return JsonResponse({'error': 'Missing required fields', 'details': missing}, status=400)

    # Fill missing values in plotting columns
    all_cases['solved'] = all_cases['solved'].fillna('unsolved')
    all_cases['disease_category'] = all_cases['disease_category'].fillna('unknown')

    # Optional rename for clarity (aligns with your example’s naming)
    all_cases = all_cases.rename(columns={
        'solved': 'solved_candidate'
    })

    # Filter rows that still have valid values
    filtered = all_cases[
        all_cases['solved_candidate'].notna() & all_cases['disease_category'].notna()
    ].copy()

    if filtered.empty:
        return JsonResponse({'error': 'No valid rows to plot'}, status=400)

    # Group by disease_category and solved_candidate: absolute counts
    counts = (
        filtered.groupby(['disease_category', 'solved_candidate'])
        .size()
        .reset_index(name='count')
    )

    # Total per disease_category (for percentages and ordering)
    totals = (
        filtered.groupby('disease_category')
        .size()
        .reset_index(name='total_count')
    )

    # Merge totals, compute proportion
    df = counts.merge(totals, on='disease_category', how='left')
    df['solved_proportion_v'] = df['count'] / df['total_count'].where(df['total_count'] != 0, 1)

    # Sort categories by total count desc for nicer x-axis order
    ordered_cats = (
        totals.sort_values('total_count', ascending=False)['disease_category'].tolist()
    )

    # Build Plotly figure: show ABSOLUTE counts, include percentage in hover
    fig = go.Figure()
    for name, group_df in df.groupby("solved_candidate"):
        # Preserve category order
        group_df = group_df.set_index('disease_category').reindex(ordered_cats).reset_index()

        fig.add_trace(go.Bar(
            x=group_df["disease_category"],
            y=group_df["count"].tolist(),                 # absolute count on y-axis
            name=name,
            customdata=group_df[["solved_proportion_v"]].values.tolist(),
            hovertemplate="%{x}<br>%{y} cases<br>%{customdata[0]:.2%} yield<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        title="Diagnostic Yield by Disease Category",
        xaxis_title="Disease Category",
        yaxis_title="Number of Cases",
        xaxis=dict(categoryorder="array", categoryarray=ordered_cats),
        height=600,
        width=900,
    )

    graph_json = pio.to_json(fig)
    return JsonResponse(graph_json, safe=False)

@csrf_exempt
@api_view(["POST"])
def plot_age_bar(request):
    if request.method == 'POST':
        try:
            # Load the JSON data from the request
            data = json.loads(request.body)

            # Convert API data to DataFrame
            all_cases = pd.DataFrame(data)

            # Fill missing values
            all_cases['solved'] = all_cases['solved'].fillna('unsolved')
            all_cases['age_group'] = all_cases['age_group'].fillna('unknown')

            # Rename columns for clarity
            all_cases = all_cases.rename(columns={
                'age_group': 'adult_child',
                'solved': 'solved_candidate'
            })

            # Filter cases with 'solved_candidate' not null
            filtered_cases = all_cases[all_cases['solved_candidate'].notna()]

            # Group by 'adult_child' and 'solved_candidate' and count occurrences
            solved_proportions_ac = (
                filtered_cases.groupby(['adult_child', 'solved_candidate'])
                .size()
                .reset_index(name='count')
            )

            # Calculate total counts per 'adult_child'
            total_counts_ac = (
                filtered_cases.groupby('adult_child')
                .size()
                .reset_index(name='total_count')
            )

            # Merge total counts back into grouped data
            solved_proportions_ac = pd.merge(
                solved_proportions_ac,
                total_counts_ac,
                on='adult_child'
            )

            # Calculate percentages
            solved_proportions_ac['solved_proportion_v'] = (
                solved_proportions_ac['count'] / solved_proportions_ac['total_count']
            )

            # Build plotly figure manually to embed both count and percentage
            fig = go.Figure()
            for name, group_df in solved_proportions_ac.groupby("solved_candidate"):
                fig.add_trace(go.Bar(
                    x=group_df["adult_child"],
                    y=group_df["count"].tolist(),  # absolute count shown by default
                    name=name,
                    customdata=group_df[["solved_proportion_v"]].values.tolist(),
                    hovertemplate="%{x}<br>%{y} cases<br>%{customdata[0]:.2%} yield<extra></extra>",
                ))

            fig.update_layout(
                barmode="stack",
                title="Diagnostic Yield by Adult-Child Status",
                xaxis_title="Adult-Child Status",
                yaxis_title="Number of Cases",
            )

            # Convert the Plotly figure to JSON
            graph_json = pio.to_json(fig)
            return JsonResponse(graph_json, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@api_view(["POST"])
def plot_umap(request):

    if request.method == 'POST':
        try:
            # Load the JSON data from the request
            dataInput = json.loads(request.body)

            # Validate the incoming data
            #validation_errors = validate_json_data(data)
            #if validation_errors:
            #    return JsonResponse({'error': 'Validation Error', 'details': validation_errors}, status=400)
  
            all_cases = pd.DataFrame(dataInput['cases'])
            lab = dataInput['lab']
            redo = dataInput['redo']
            selected_case_id = dataInput['selected']
            print(redo)

            # Ensure required columns exist and handle missing data
            # all_cases['mutation'] = all_cases['mutation'].fillna('unknown')
            all_cases['HPO_Term_IDs'] = all_cases['HPO_Term_IDs'].fillna('unknown')

            # Rename columns for clarity
            #all_cases = all_cases.rename(columns={'age_group': 'adult_child', 'solved': 'solved_candidate'})

            fig = generate_umap(all_cases, lab, selected_case_id, redo)

            # Convert the Plotly figure to JSON
            graph_json = pio.to_json(fig)  # Convert the figure to JSON
            return JsonResponse(graph_json, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@api_view(["POST"])
def plot_view(request):
    all_cases_file = "all_cases_wHighEvNovel.tsv"
    all_cases = pd.read_csv(all_cases_file, delimiter='\t').drop_duplicates(subset='case_ID_paper')

    solved_proportions = (all_cases[all_cases['solved'].notna()]
                          .groupby(['disease_category'])
                          .apply(lambda x: x.groupby('solved').size() / x.shape[0])
                          .reset_index(name='solved_proportion_v')
                          )



    # Create a Plotly bar chart
    fig = px.bar(solved_proportions,
                 x='disease_category',
                 y='solved_proportion_v',
                 color='solved',
                 pattern_shape='solved',
                 #pattern_shape_map={'solved TRUE': '/', 'solved FALSE': ''},
                 title="Diagnostic yield by Disease Category",
                 labels={'solved_proportion_v': 'Solved Proportion', 'disease_category': 'Disease Category'},
                 barmode='stack')

    fig.update_layout(xaxis={'categoryorder': 'total descending'}, height=600, width=800)

    graph_json = pio.to_json(fig)  # Convert the figure to JSON
    return JsonResponse(graph_json, safe=False)

###Meghna: Uncomment to render in the view
    # Pass the JSON object to the template
    #return render(request, 'plot.html', {'plot': graph_json})

@csrf_exempt
@api_view(["POST"])
def plot_trend(request):

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    # ---------- Parse body ----------
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    rows = payload.get('cases', [])
    resolution = payload.get('resolution', 'quarter')  # 'quarter' | 'month'

    if not rows:
        fig = px.line(title="Diagnostic Yield Trend (no data)")
        return JsonResponse(json.loads(pio.to_json(fig)), safe=False)

    # ---------- DataFrame & validation ----------
    df = pd.DataFrame(rows)
    required = {'solved', 'year'} | ({'quarter'} if resolution == 'quarter' else {'month'})
    missing = [c for c in required if c not in df.columns]
    if missing:
        return JsonResponse({'error': f"Missing required fields: {', '.join(missing)}"}, status=400)

    df = df.dropna(subset=list(required)).copy()
    if df.empty:
        fig = px.line(title="Diagnostic Yield Trend (no rows after filtering)")
        return JsonResponse(json.loads(pio.to_json(fig)), safe=False)

    df['year'] = df['year'].astype(int)
    df['solved'] = df['solved'].astype(str)

    if resolution == 'quarter':
        df['quarter'] = df['quarter'].astype(int)
        df['period'] = pd.PeriodIndex.from_fields(year=df['year'], quarter=df['quarter'], freq='Q')
    else:
        df['month'] = df['month'].astype(int)
        df['period'] = pd.PeriodIndex.from_fields(year=df['year'], month=df['month'], freq='M')

    counts_wide = df.groupby(['period', 'solved']).size().unstack(fill_value=0)
    if counts_wide.empty or (counts_wide.sum(axis=1) == 0).all():
        fig = px.line(title="Diagnostic Yield Trend (no counts in groups)")
        return JsonResponse(json.loads(pio.to_json(fig)), safe=False)

    # proportions per period (avoid div-by-zero)
    denom = counts_wide.sum(axis=1).replace(0, 1)
    props_wide = counts_wide.div(denom, axis=0)

    counts = counts_wide.reset_index().melt(id_vars='period', var_name='solved', value_name='count')
    props  = props_wide.reset_index().melt(id_vars='period', var_name='solved', value_name='proportion')
    out    = counts.merge(props, on=['period', 'solved']).sort_values('period')

    out['period_label'] = out['period'].astype(str)
    category_order = list(out['period_label'].unique())

    # ---------- Plot: ABSOLUTE counts on Y; also carry proportions for toggling ----------
    fig = go.Figure()
    for name, group_df in out.groupby("solved", sort=False):
        # Preserve chronological order on x
        gd = group_df.set_index('period_label').reindex(category_order).reset_index()

        counts_list = gd["count"].astype(float).where(gd["count"].notna(), None).tolist()
        props_list  = gd["proportion"].astype(float).where(gd["proportion"].notna(), None).tolist()

        fig.add_trace(go.Scatter(
            x=gd["period_label"],
            y=counts_list,  # default: absolute counts on Y
            name=name,
            mode="lines+markers",
            customdata=np.column_stack([props_list]).tolist(),  # [proportion]
            hovertemplate=(
                "Period: %{x}<br>"
                "Count: %{y}<br>"
                "Yield: %{customdata[1]:.2%}<extra></extra>"
            ),
            connectgaps=False,
        ))

    fig.update_layout(
        title=f"Diagnostic Yield Trend ({'Quarterly' if resolution=='quarter' else 'Monthly'})",
        xaxis_title="Period",
        yaxis_title="Number of Cases",
        xaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': category_order},
        height=600
    )


    # ---------- Ensure JSON-serializability ----------
    for trace in fig.data:
        if isinstance(trace.x, np.ndarray):
            trace.x = trace.x.tolist()
        if isinstance(trace.y, np.ndarray):
            trace.y = trace.y.tolist()
        if hasattr(trace, "customdata") and isinstance(trace.customdata, np.ndarray):
            trace.customdata = trace.customdata.tolist()

    if isinstance(fig.layout.xaxis.categoryarray, np.ndarray):
        fig.layout.xaxis.categoryarray = fig.layout.xaxis.categoryarray.tolist()

    fig_json = pio.to_json(fig, pretty=False)
    fig_obj = json.loads(fig_json)

    return JsonResponse(fig_obj, safe=False)


class FaceSenderView(APIView):

    authentication_classes = [CsrfExemptSessionAuth]

    def get(self, request, *args, **kwargs):
        return render(request, 'index.html')

    res = JSONField(default=dict)

    def post(self, request, *args, **kwargs):
        '''
        Send the image as a request to Gestalt Matcher web service
        '''

        if request.method == "POST":
            messages.success(request, 'Data submitted successfully! ')

            all_cases_file = "all_cases_wHighEvNovel.tsv"
            all_cases = pd.read_csv(all_cases_file, delimiter='\t').drop_duplicates(subset='case_ID_paper')

            solved_proportions = (all_cases[all_cases['solved'].notna()]
                                  .groupby(['disease_category'])
                                  .apply(lambda x: x.groupby('solved').size() / x.shape[0])
                                  .reset_index(name='solved_proportion_v')
                                  )

            # Create a Plotly bar chart
            fig = px.bar(solved_proportions,
                         x='disease_category',
                         y='solved_proportion_v',
                         color='solved',
                         pattern_shape='solved',
                         #pattern_shape_map={'solved': '/', 'unsolved': ''},
                         title="Diagnostic yield by Disease Category",
                         labels={'solved_proportion_v': 'Diagnostic Yield', 'disease_category': 'Disease Category'},
                         barmode='stack')

            fig.update_layout(xaxis={'categoryorder': 'total descending'}, height=600, width=800)

            fig.write_html("diagnostic_yield.html")

            graph_json = pio.to_json(fig)  # Convert the figure to JSON
            #return JsonResponse(graph_json, safe=False)

            # Pass the JSON object to the template
            return render(request, 'plot.html', {'plot': graph_json})