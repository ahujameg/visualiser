import requests
import base64
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

def plot_api(request):
    if request.method == 'POST':
        # Get the dynamic data from the request (JSON format)
        try:
            request_data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        # Ensure the necessary fields are present
        if not all(key in request_data for key in ['Disease Category', 'Case Count', 'Diagnosed Cases']):
            return JsonResponse({'error': 'Missing required data fields'}, status=400)

        # Generate the Plotly chart JSON
        plotly_chart = generate_plotly_bar_chart(request_data)

        # Return the chart data as JSON
        return JsonResponse(plotly_chart)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

def plot_view(request):
    all_cases_file = "all_cases_wHighEvNovel.tsv"
    all_cases = pd.read_csv(all_cases_file, delimiter='\t').drop_duplicates(subset='case_ID_paper')

    solved_proportions = (all_cases[all_cases['solved'].notna()]
                          .groupby(['disease_category'])
                          .apply(lambda x: x.groupby('solved_candidate').size() / x.shape[0])
                          .reset_index(name='solved_proportion_v'))

    # Create a Plotly bar chart
    fig = px.bar(solved_proportions,
                 x='disease_category',
                 y='solved_proportion_v',
                 color='solved_candidate',
                 pattern_shape='solved_candidate',
                 pattern_shape_map={'solved TRUE': '/', 'solved FALSE': ''},
                 title="Solved Proportions by Disease Category",
                 labels={'solved_proportion_v': 'Solved Proportion', 'disease_category': 'Disease Category'},
                 barmode='stack')

    fig.update_layout(xaxis={'categoryorder': 'total descending'}, height=600, width=800)

    graph_json = pio.to_json(fig)  # Convert the figure to JSON
    # return JsonResponse(graph_json, safe=False)

    # Pass the JSON object to the template
    return render(request, 'plot.html', {'plot': graph_json})


class FaceSenderView(APIView):

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
                                  .apply(lambda x: x.groupby('solved_candidate').size() / x.shape[0])
                                  .reset_index(name='solved_proportion_v'))

            # Create a Plotly bar chart
            fig = px.bar(solved_proportions,
                         x='disease_category',
                         y='solved_proportion_v',
                         color='solved_candidate',
                         pattern_shape='solved_candidate',
                         pattern_shape_map={'solved TRUE': '/', 'solved FALSE': ''},
                         title="Solved Proportions by Disease Category",
                         labels={'solved_proportion_v': 'Solved Proportion', 'disease_category': 'Disease Category'},
                         barmode='stack')

            fig.update_layout(xaxis={'categoryorder': 'total descending'}, height=600, width=800)

            graph_json = pio.to_json(fig)  # Convert the figure to JSON
            #return JsonResponse(graph_json, safe=False)

            # Pass the JSON object to the template
            return render(request, 'plot.html', {'plot': graph_json})