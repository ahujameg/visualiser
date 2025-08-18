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

# def plot_api(request):
#     if request.method == 'POST':
#         # Get the dynamic data from the request (JSON format)
#         try:
#             request_data = json.loads(request.body)
#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON format'}, status=400)
#
#         # Ensure the necessary fields are present
#         if not all(key in request_data for key in ['Disease Category', 'Case Count', 'Diagnosed Cases']):
#             return JsonResponse({'error': 'Missing required data fields'}, status=400)
#
#         # Generate the Plotly chart JSON
#         plotly_chart = generate_plotly_bar_chart(request_data)
#
#         # Return the chart data as JSON
#         return JsonResponse(plotly_chart)
#
#     return JsonResponse({'error': 'Invalid request method'}, status=405)

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
    
    if request.method == 'POST':
        try:
            # Load the JSON data from the request
            data = json.loads(request.body)

            # Validate the incoming data
            validation_errors = validate_json_data(data)
            if validation_errors:
                return JsonResponse({'error': 'Validation Error', 'details': validation_errors}, status=400)

            # Parse JSON data from request body
            data = json.loads(request.body)
            all_cases = pd.DataFrame(data)

            # Ensure required columns exist
            # if 'solved' not in all_cases or 'disease_category' not in all_cases:
            #     return JsonResponse({'error': 'Missing required fields in input data'}, status=400)

            # Calculate solved proportions
            #if all_cases['solved'].isin('solved'):
            # ss = (
            #     all_cases[all_cases['solved'].notna()]
            #         .groupby(['disease_category'])
            #         .apply(lambda x: x.groupby('solved').size() / x.shape[0])
            #         )
            # print(ss)
            solved_proportions = (
                all_cases[all_cases['solved'].notna()]
                .groupby(['disease_category', 'solved'])
                .size()
                .unstack(fill_value=0)  # Ensure we get a DataFrame even if all cases are solved
            )

            # Normalize to get proportions
            solved_proportions = solved_proportions.div(solved_proportions.sum(axis=1), axis=0).reset_index()

            # Convert to long format for Plotly
            solved_proportions = solved_proportions.melt(id_vars=['disease_category'], 
                                             var_name='solved', 
                                             value_name='solved_proportion_v')

            # solved_proportions = (all_cases[all_cases['solved'].notna()]
            #               .groupby(['disease_category'])
            #               .apply(lambda x: x.groupby('solved').size() / x.shape[0])
            #               .reset_index(name='solved_proportion_v')
            #               )

            # Rename the count column properly
            #solved_proportions = solved_proportions.rename(columns={0: 'solved_proportion_v'})
            print(solved_proportions)
            # Create a Plotly bar chart
            fig = px.bar(
                solved_proportions,
                x='disease_category',
                y='solved_proportion_v',
                color='solved',
                pattern_shape='solved',
                title="Diagnostic yield by Disease Category",
                labels={'solved_proportion_v': 'Diagnostic Yield', 'disease_category': 'Disease Category'},
                barmode='stack'
            )

            fig.update_layout(xaxis={'categoryorder': 'total descending'}, height=600, width=800)
            # Save figure
            #fig.write_image("plot_diagnostic_yield_b.pdf")

            graph_json = pio.to_json(fig)  # Convert the figure to JSON
            return JsonResponse(graph_json, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@api_view(["POST"])
def plot_age_bar(request):
    #print(request.body)

    if request.method == 'POST':
        try:
            # Load the JSON data from the request
            data = json.loads(request.body)

            # Validate the incoming data
            #validation_errors = validate_json_data(data)
            #if validation_errors:
            #    return JsonResponse({'error': 'Validation Error', 'details': validation_errors}, status=400)

            # Convert API data to DataFrame
            all_cases = pd.DataFrame(data)

            # Ensure required columns exist and handle missing data
            all_cases['solved'] = all_cases['solved'].fillna('unsolved')
            all_cases['age_group'] = all_cases['age_group'].fillna('unknown')

            # Rename columns for clarity
            all_cases = all_cases.rename(columns={'age_group': 'adult_child', 'solved': 'solved_candidate'})

            # Filter cases with 'solved_candidate' not null
            filtered_cases = all_cases[all_cases['solved_candidate'].notna()]

            # Group by 'adult_child' and 'solved_candidate' and count occurrences
            solved_proportions_ac = filtered_cases.groupby(['adult_child', 'solved_candidate']).size().reset_index(
                name='count')

            # Calculate the total counts per 'adult_child'
            total_counts_ac = filtered_cases.groupby('adult_child').size().reset_index(name='total_count')

            # Merge the total counts back into the original DataFrame
            solved_proportions_ac = pd.merge(solved_proportions_ac, total_counts_ac, on='adult_child')

            # Calculate the solved proportion
            solved_proportions_ac['solved_proportion_v'] = solved_proportions_ac['count'] / solved_proportions_ac[
                'total_count']

            # Create interactive bar plot for adult-child status
            fig_ac = px.bar(
                solved_proportions_ac,
                x='adult_child',
                y='solved_proportion_v',
                color='solved_candidate',
                title="Diagnostic Yield by Adult-Child Status",
                labels={
                    'solved_proportion_v': 'Diagnostic Yield',
                    'adult_child': 'Adult-Child Status',
                    'solved_candidate': 'Solved'
                },
                barmode='stack'
            )

            # Save figure
            #fig_ac.write_image("plot_diagnostic_yield_all_info_adult_child.pdf")

            # Convert the Plotly figure to JSON
            graph_json = pio.to_json(fig_ac)  # Convert the figure to JSON
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
        
            # Convert API data to DataFrame
            
            #dataInput = pd.DataFrame(data)
            #print(dataInput)
            all_cases = pd.DataFrame(dataInput['cases'])
            print(all_cases)
            lab = dataInput['lab']
            print(lab)
            redo = dataInput['redo']
            print(redo)

            #print(all_cases)

            # Ensure required columns exist and handle missing data
            # all_cases['mutation'] = all_cases['mutation'].fillna('unknown')
            all_cases['HPO_Term_IDs'] = all_cases['HPO_Term_IDs'].fillna('unknown')

            # Rename columns for clarity
            #all_cases = all_cases.rename(columns={'age_group': 'adult_child', 'solved': 'solved_candidate'})

            fig = generate_umap(all_cases, lab, redo)

            # Save figure
            #fig.write_image("plot_umap.pdf")

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

    props_wide = counts_wide.div(counts_wide.sum(axis=1), axis=0)

    counts = counts_wide.reset_index().melt(id_vars='period', var_name='solved', value_name='count')
    props  = props_wide.reset_index().melt(id_vars='period', var_name='solved', value_name='proportion')
    out    = counts.merge(props, on=['period', 'solved']).sort_values('period')

    out['period_label'] = out['period'].astype(str)
    category_order = list(out['period_label'].unique())

    fig = px.line(
        out,
        x='period_label',
        y='proportion',
        color='solved',
        markers=True,
        custom_data=['count'],
        title=f"Diagnostic Yield Trend ({'Quarterly' if resolution=='quarter' else 'Monthly'})",
        labels={'proportion': 'Diagnostic Yield', 'period_label': 'Period', 'solved': 'Case Status'},
    )

    fig.update_traces(
        mode='lines+markers',
        hovertemplate=(
            "Period: %{x}<br>"
            #"Solved: %{legendgroup}<br>"
            "Yield: %{y:.1%}<br>"
            "Count: %{customdata[0]}<extra></extra>"
        )
    )
    fig.update_yaxes(tickformat='.0%')
    fig.update_layout(
        xaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': category_order},
        height=600
    )

    # ---------- Ensure JSON-serializability ----------
    for trace in fig.data:
        if isinstance(trace.x, np.ndarray):
            trace.x = trace.x.tolist()
        if isinstance(trace.y, np.ndarray):
            trace.y = trace.y.tolist()
        if isinstance(trace.customdata, np.ndarray):
            trace.customdata = trace.customdata.tolist()

    if isinstance(fig.layout.xaxis.categoryarray, np.ndarray):
        fig.layout.xaxis.categoryarray = fig.layout.xaxis.categoryarray.tolist()

    # ---------- Convert to dict ----------
    fig_json = pio.to_json(fig, pretty=False)
    fig_obj = json.loads(fig_json)

    print("Backend - Traces:", len(fig_obj["data"]))
    print("Sample y:", fig_obj["data"][0]["y"] if fig_obj["data"] else "None")

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