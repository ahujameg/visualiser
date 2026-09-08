import json
import os
import sys
import subprocess
import tempfile
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
from plot_visualisation.figure1_part2 import generate_umap, lab_csv_path, CACHE_DIR

# or for a class-based DRF view
from rest_framework.authentication import SessionAuthentication
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
import pandas as pd
import numpy as np

# Directory containing manage.py (two levels up from this file).
_APPS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _recompute_lock_path(lab):
    # On CACHE_DIR (a mounted volume in prod) so the lock/log survive a container
    # restart alongside the artifacts the recompute produces.
    return os.path.join(CACHE_DIR, f".recompute_{lab}.lock")


def _pid_is_running(pid):
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def start_umap_recompute(lab, cases):
    """Start the (up to ~46h) full UMAP redo as a detached OS process.

    Never call generate_umap(..., redo='redo') directly from a request
    handler: that runs the sparse-Resnik/uwot pipeline in-process, which
    would hold the gunicorn worker for the entire duration (or get killed by
    --timeout partway through). This spawns plot_visualisation's
    recompute_umap management command instead, detached via
    start_new_session=True so it outlives worker restarts/timeouts, and
    writes <lab>.csv when done for the normal (non-redo) path to read.

    Returns "started" or "already_running". The lock file is created with
    O_CREAT|O_EXCL, so two requests arriving at the same moment (e.g. the
    HGQN backend firing its startup hook and monthly cron together, across
    two gunicorn workers) cannot both win -- exactly one spawns the R job,
    the rest get "already_running". A stale lock (pid no longer alive) is
    cleared and retried.
    """
    lock_path = _recompute_lock_path(lab)

    for _attempt in range(3):
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                pid = int((open(lock_path).read().strip() or "0"))
            except (OSError, ValueError):
                pid = 0
            if pid == 0 or _pid_is_running(pid):
                # Held: either a live recompute, or a winner that created the
                # lock microseconds ago and hasn't written its pid yet.
                return "already_running"
            try:
                os.remove(lock_path)  # stale: pid is dead
            except FileNotFoundError:
                pass
            continue  # retry the atomic create

        # We hold the lock. Park our own pid in it until the child pid is known,
        # so a concurrent caller sees it as held rather than empty.
        os.write(lock_fd, str(os.getpid()).encode())
        os.close(lock_fd)
        try:
            fd, payload_path = tempfile.mkstemp(
                prefix="umap_recompute_", suffix=".json", dir=CACHE_DIR
            )
            with os.fdopen(fd, "w") as fh:
                json.dump({"lab": lab, "cases": cases}, fh)

            log_path = os.path.join(CACHE_DIR, "recompute_umap.log")
            with open(log_path, "ab") as log_fh:
                proc = subprocess.Popen(
                    [sys.executable, "manage.py", "recompute_umap",
                     "--payload", payload_path, "--lock", lock_path],
                    cwd=_APPS_DIR,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # detach from this gunicorn worker
                )
            with open(lock_path, "w") as fh:
                fh.write(str(proc.pid))
            return "started"
        except BaseException:
            try:
                os.remove(lock_path)
            except OSError:
                pass
            raise

    return "already_running"


def normalize_case_id(value):
    if value is None or pd.isna(value):
        return None

    case_id = str(value).strip()
    if case_id.endswith(".0"):
        numeric_part = case_id[:-2]
        if numeric_part.isdigit():
            return numeric_part

    return case_id

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
            
            if dataInput is None:
                return JsonResponse({'error': 'No JSON input in the request body'}, status=400)

            # Validate the incoming data
            #validation_errors = validate_json_data(data)
            #if validation_errors:
            #    return JsonResponse({'error': 'Validation Error', 'details': validation_errors}, status=400)
  
            lab = dataInput['lab']
            redo = dataInput['redo']
            selected_case_id = normalize_case_id(dataInput.get('selected'))
            cases_payload = dataInput.get('cases')

            # generate_umap() would otherwise run the full sparse-Resnik/uwot
            # rebuild in-process whenever redo == 'redo' OR <lab>.csv doesn't
            # exist yet (e.g. right after a fresh deploy, when the cache files
            # haven't been generated). That rebuild has taken up to ~46h on
            # the test server -- it must never run inside this request/worker.
            # Hand it off to a detached process instead and tell the caller
            # to retry once it's done.
            needs_redo = redo == 'redo' or not os.path.isfile(lab_csv_path(lab))
            if needs_redo:
                if not isinstance(cases_payload, list) or not cases_payload:
                    return JsonResponse(
                        {
                            'error': "UMAP data for this lab hasn't been generated yet, "
                                     "and 'cases' was not provided to start building it."
                        },
                        status=409,
                    )
                status = start_umap_recompute(lab, cases_payload)
                return JsonResponse(
                    {
                        'status': 'computing',
                        'detail': status,
                        'message': 'UMAP data is being generated in the background; retry shortly.',
                    },
                    status=202,
                )

            all_cases = pd.DataFrame(cases_payload) if isinstance(cases_payload, list) else pd.DataFrame()
            if not all_cases.empty and 'HPO_Term_IDs' in all_cases.columns:
                all_cases['HPO_Term_IDs'] = all_cases['HPO_Term_IDs'].fillna('unknown')

            if not all_cases.empty and 'case_ID_paper' in all_cases.columns:
                all_cases['case_ID_paper'] = all_cases['case_ID_paper'].map(normalize_case_id)

            # Ensure required columns exist and handle missing data
            # all_cases['mutation'] = all_cases['mutation'].fillna('unknown')

            # Rename columns for clarity
            #all_cases = all_cases.rename(columns={'age_group': 'adult_child', 'solved': 'solved_candidate'})

            # # --- ensure we have HPO_term_IDs ---
            # if "HPO_term_IDs" not in all_cases.columns:
            #     # common alternative field names (adjust to your actual payload)
            #     for alt in ["hpoTerms", "HPO_terms", "hpo_term_IDs", "hpo_term_ids"]:
            #         if alt in all_cases.columns:
            #             all_cases = all_cases.rename(columns={alt: "HPO_term_IDs"})
            #             break

            # if "HPO_term_IDs" not in all_cases.columns:
            #     return JsonResponse({
            #         "error": "Missing required column 'HPO_term_IDs'",
            #         "available_columns": list(all_cases.columns),
            #     }, status=400)

            # # IMPORTANT: keep missing as NA/NaN, NOT the string "unknown"
            # all_cases["HPO_term_IDs"] = all_cases["HPO_term_IDs"].replace({"unknown": np.nan, "": np.nan})

            fig = generate_umap(all_cases, lab, selected_case_id, redo)

            # Convert the Plotly figure to JSON
            graph_json = pio.to_json(fig)  # Convert the figure to JSON
            return JsonResponse(graph_json, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@api_view(["POST"])
def plot_umap_recompute(request):
    """Kick off a full UMAP redo (sparse Resnik + uwot) as a detached process
    and return immediately.

    This has taken up to ~46h on the test server, so it must never run inside
    a gunicorn worker: a worker's --timeout would kill it, and while it holds
    the worker no other request can be served. See start_umap_recompute()
    above -- the same helper backs plot_umap's needs_redo guard, so both the
    monthly HGQN cron call and an interactive request hitting a missing cache
    file go through one code path and share the same duplicate-run lock.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    lab = data.get('lab', 'allLabs')
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        return JsonResponse({'error': "Field 'cases' is required"}, status=400)

    status = start_umap_recompute(lab, cases)
    return JsonResponse({"status": "started", "detail": status, "lab": lab}, status=202)


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
        # Happens e.g. when the resolution toggle is switched before a year is
        # picked, so the rows were built for the other resolution (no quarter/
        # month column). Return an empty chart, not a 400 -- same as the other
        # degenerate cases above -- so the client shows a blank plot and the
        # visualiser log isn't spammed with "Bad Request: /api/plot/trend/".
        fig = px.line(title="Diagnostic Yield Trend (no data)")
        return JsonResponse(json.loads(pio.to_json(fig)), safe=False)

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
