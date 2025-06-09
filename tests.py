from django.test import TestCase
from django.urls import reverse
from pprint import pprint
import json
import pandas as pd
import csv

# class PlotApiTestCase(TestCase):
#     def setUp(self):
#         self.url = reverse('plot_api')  
#     def read_tsv_file(self, file_path):
#         data = {
#             "Disease Category": [],  # Updated field name
#             "Case Count": [],
#             "Diagnosed Cases": []
#         }
#
#         with open(file_path, 'r') as tsvfile:
#             reader = csv.DictReader(tsvfile, delimiter='\t')
#             for row in reader:
#                 # Collect the data from the TSV
#                 data["Disease Category"].append(row["disease_category"])
#
#                 # Assuming you want to derive Case Count and Diagnosed Cases
#                 # Here, you'll need to decide how to calculate these values based on the data in your TSV.
#                 # For demonstration, let's assume 'solved' indicates if a case is diagnosed.
#
#                 # Increment count based on the 'solved' field
#                 case_count = 1  # Every row represents one case
#                 diagnosed_case = 1 if row["solved"] == 'solved' else 0
#
#                 data["Case Count"].append(case_count)
#                 data["Diagnosed Cases"].append(diagnosed_case)
#
#         return data
#
#     def test_plot_api_with_real_data(self):
#         # Read data from the TSV file
#         tsv_file_path = 'all_cases_wHighEvNovel.tsv'  # Update the path
#         test_data = self.read_tsv_file(tsv_file_path)
#
#         # Send a POST request to the API with real data from the TSV
#         response = self.client.post(self.url, json.dumps(test_data), content_type='application/json')
#
#         # Check that the response is successful
#         self.assertEqual(response.status_code, 200)
#
#         # Check that the response contains the expected keys
#         response_data = response.json()
#
#         # Print the response data for debugging
#         # print("Response Data from the API:", response_data)
#         print("Response Data (First 10 Rows):")
#         pprint(response_data['data'][:1])  # Adjust as necessary for the actual structure of response_data
#
#         self.assertIn('data', response_data)
#         self.assertIn('layout', response_data)
#
#         # Optional: Check if the diagnostic yield is calculated correctly
#         diagnostic_yield = [d / c for d, c in zip(test_data['Diagnosed Cases'], test_data['Case Count'])]
#         self.assertEqual(response_data['data'][0]['y'], diagnostic_yield)
#
#     def test_plot_api_invalid_data(self):
#         # Send invalid data (missing required fields)
#         invalid_data = {
#             "Case Count": [50, 30, 20]
#         }
#         response = self.client.post(self.url, json.dumps(invalid_data), content_type='application/json')
#
#         # Check that the response indicates an error
#         self.assertEqual(response.status_code, 400)
#         self.assertIn('error', response.json())
#
#     def test_plot_api_invalid_json(self):
#         # Send an invalid JSON format
#         response = self.client.post(self.url, 'invalid json', content_type='application/json')
#
#         # Check that the response indicates an error
#         self.assertEqual(response.status_code, 400)
#         self.assertIn('error', response.json())
#
#     def test_plot_api_valid_data(self):
#         # Sample data to send in the POST request
#         test_data = {
#             "Disease Category": ["Category A", "Category B", "Category C"],
#             "Case Count": [50, 30, 20],
#             "Diagnosed Cases": [40, 15, 10]
#         }
#
#         # Send a POST request to the API
#         response = self.client.post(self.url, json.dumps(test_data), content_type='application/json')
#
#         # Check that the response is successful
#         self.assertEqual(response.status_code, 200)
#
#         # Check that the response contains the expected keys
#         response_data = response.json()
#         self.assertIn('data', response_data)
#         self.assertIn('layout', response_data)
#
#         # Optional: Check if the diagnostic yield is calculated correctly
#         diagnostic_yield = [d / c for d, c in zip(test_data['Diagnosed Cases'], test_data['Case Count'])]
#         # Assuming the first bar represents the first disease category
#         self.assertEqual(response_data['data'][0]['y'], diagnostic_yield)

class PlotApiTestCase(TestCase):
    def setUp(self):
        self.url = reverse('plot_api')  # Update with the actual URL name

    def test_plot_api_with_real_data(self):
        # Define the input JSON data
        input_data = [
            {
                "id": 319,
                "age_group": "child",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "child",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": 0.0
            }
        ]

        # Send a POST request to the API with the JSON data
        response = self.client.post(self.url, json.dumps(input_data), content_type='application/json')

        # Check that the response is successful
        self.assertEqual(response.status_code, 200)

        # Check that the response contains the expected keys
        response_data = response.json()

        # Print the first 10 entries in response data for debugging
        print("Response Data (First 10 Rows):")
        pprint(response_data['data'][:10])

        self.assertIn('data', response_data)
        self.assertIn('layout', response_data)

        # Optional: Check if the diagnostic yield is correctly calculated
        # Expected diagnostic yield would be 2 solved cases out of 2 total cases = 100% = 1.0
        diagnostic_yield = [1.0]  # As all cases in input_data are solved
        self.assertEqual(response_data['data'][0]['y'], diagnostic_yield)

    def test_plot_api_invalid_data(self):
        # Send invalid data (missing required fields)
        print('Testing invalid data now §§§§§§§§§§§§§')
        invalid_data = [
            {
                "age": "child",
                "sex": "female"
            }
        ]
        response = self.client.post(self.url, json.dumps(invalid_data), content_type='application/json')
        print(f'Response = ', response)
        # Check that the response indicates an error
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_plot_api_invalid_json(self):
        # Send an invalid JSON format
        response = self.client.post(self.url, 'invalid json', content_type='application/json')

        # Check that the response indicates an error
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

class PlotAgeApiTestCase(TestCase):
    def setUp(self):
        self.url = reverse('plot_age_bar')  # Update with the actual URL name

    def test_plot_api_with_real_data(self):
        # Define the input JSON data
        input_data = [
            {
                "id": 319,
                "age_group": "child",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "adult",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": 0.0
            },
            {
                "id": 319,
                "age_group": "child",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "adult",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": 0.0
            },
            {
                "id": 319,
                "age_group": "child",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "adult",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": 0.0
            },
            {
                "id": 319,
                "age_group": "adult",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene":False,
                "is_solved": "unclear",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "adult",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "unclear",
                "autozygosity": 0.0
            },
            {
                "id": 319,
                "age_group": "child",
                "gender": "female",
                "hpo_terms": "HP:0000252; HP:0000286; HP:0000369; HP:0005709",
                "novel_gene": False,
                "is_solved": "unclear",
                "autozygosity": None
            },
            {
                "id": 321,
                "age_group": "adult",
                "gender": "male",
                "hpo_terms": "HP:0004322; HP:0001263",
                "novel_gene": True,
                "is_solved": "solved",
                "autozygosity": 0.0
            }
        ]

        # Load data
        all_cases_file = "all_cases_wHighEvNovel.tsv"
        all_cases = pd.read_csv(all_cases_file, delimiter='\t').drop_duplicates(subset='case_ID_paper')

 #       input_data = all_cases.to_dict(orient="records")
        # Send a POST request to the API with the JSON data
        response = self.client.post(self.url, json.dumps(input_data), content_type='application/json')

        # Check that the response is successful
        self.assertEqual(response.status_code, 200)

        # Check that the response contains the expected keys
        response_data = response.json()

        # Print the first 10 entries in response data for debugging
        print("Response Data (First 10 Rows):")
        pprint(response_data['data'][:10])

        self.assertIn('data', response_data)
        self.assertIn('layout', response_data)

