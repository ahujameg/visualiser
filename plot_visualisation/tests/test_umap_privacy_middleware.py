import json
from types import SimpleNamespace

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from plot_visualisation.middleware import (
    UmapPrivacyMiddleware,
    extract_selected_case_id,
    redact_case_ids_from_figure,
)


class SelectedCaseExtractionTests(SimpleTestCase):
    def test_prefers_hidden_case_id_over_deidentified_label(self):
        payload = {
            "selected": "Not available",
            "selected_case_id": 123.0,
        }
        self.assertEqual(extract_selected_case_id(payload), "123")

    def test_extracts_case_id_from_selected_row(self):
        payload = {
            "selected": "Not available",
            "selectedRow": {"case_ID_paper": "CASE-42"},
        }
        self.assertEqual(extract_selected_case_id(payload), "CASE-42")

    def test_extracts_case_id_from_selected_index(self):
        payload = {
            "selected": "Not available",
            "selectedIndex": 1,
            "cases": [
                {"case_ID_paper": "CASE-1"},
                {"case_ID_paper": "CASE-2"},
            ],
        }
        self.assertEqual(extract_selected_case_id(payload), "CASE-2")


class UmapRedactionTests(SimpleTestCase):
    def test_removes_case_id_but_keeps_hpo_hover_text(self):
        figure = {
            "data": [
                {
                    "hovertext": [
                        "Case ID: CASE-42<br>HPO Terms: Seizure",
                        "HPO term only",
                    ]
                }
            ]
        }
        redact_case_ids_from_figure(figure)
        self.assertEqual(
            figure["data"][0]["hovertext"],
            ["HPO Terms: Seizure", "HPO term only"],
        )

    def test_middleware_injects_hidden_id_and_redacts_legacy_response(self):
        captured = {}
        figure = {
            "data": [
                {"hovertext": ["Case ID: CASE-42<br>HPO Terms: Seizure"]}
            ]
        }

        def get_response(request):
            captured["payload"] = json.loads(request.body)
            return JsonResponse(json.dumps(figure), safe=False)

        request = RequestFactory().post(
            "/api/plot/umap/",
            data=json.dumps(
                {
                    "selected": "Not available",
                    "selected_case": {"case_ID_paper": "CASE-42"},
                }
            ),
            content_type="application/json",
        )
        response = UmapPrivacyMiddleware(get_response)(request)

        self.assertEqual(captured["payload"]["selected"], "CASE-42")
        returned_figure = json.loads(json.loads(response.content))
        self.assertEqual(
            returned_figure["data"][0]["hovertext"],
            ["HPO Terms: Seizure"],
        )

    @override_settings(HGQN_VISUALISER_ADMIN_TOKEN="server-side-secret")
    def test_trusted_admin_proxy_keeps_case_id(self):
        figure = {
            "data": [
                {"hovertext": ["Case ID: CASE-42<br>HPO Terms: Seizure"]}
            ]
        }
        request = RequestFactory().post(
            "/api/plot/umap/",
            data=json.dumps({"selected_case_id": "CASE-42"}),
            content_type="application/json",
            HTTP_X_HGQN_VISUALISER_ADMIN_TOKEN="server-side-secret",
        )
        request.user = SimpleNamespace(
            is_authenticated=False,
            is_staff=False,
            is_superuser=False,
        )

        response = UmapPrivacyMiddleware(
            lambda _request: JsonResponse(json.dumps(figure), safe=False)
        )(request)
        returned_figure = json.loads(json.loads(response.content))
        self.assertIn("Case ID: CASE-42", returned_figure["data"][0]["hovertext"][0])
