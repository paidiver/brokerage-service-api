"""Code to call the upstream annotations API's and compile the results."""

import os

import requests as rq

from brokerage_service_api.models.search_model import Result, Results, SearchResults, Summary
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest

JNCC_ANNOTATIONS_API_ENDPOINT = os.getenv("JNCC_SEARCH_ENDPOINT", "http://localhost:8018/api/annotations/search/")
BODC_ANNOTATIONS_API_ENDPOINT = os.getenv("BODC_SEARCH_ENDPOINT", "http://localhost:8019/api/annotations/search/")

ENDPOINTS = {"JNCC": JNCC_ANNOTATIONS_API_ENDPOINT, "BODC": BODC_ANNOTATIONS_API_ENDPOINT}


class UnknownFlavourError(Exception):
    """Raised when an unknown upstream is referenced."""


class AnnotationsAPIFetcher:
    """Methods to fetch from upstream API's and return data."""

    def __init__(self, flavour: str, params: AnnotationSearchRequest):
        """Initialise the class and make an attempt to call the upstream API."""
        self.flavour: str = flavour
        self.params: AnnotationSearchRequest = params
        self._results: list[Result] = []
        self._summary: Summary | None = None
        self._make_request()

    def order_results(self, ordering_key: str) -> None:
        """Perform an in-place sort of the internal _results list."""
        if ordering_key == "aphia_id":
            self._results.sort(key=lambda result: result.label_aphia_id)

    def _make_request(self) -> None:
        """Make request to the upstream API and store the results in the class if available."""
        endpoint = ENDPOINTS.get(self.flavour)
        if endpoint is None:
            raise UnknownFlavourError(f"{self.flavour} is not recognised.")

        try:
            response = rq.get(f"{endpoint}{self.params.to_query_string()}", timeout=30)
            response.raise_for_status()
        except rq.RequestException as exc:
            # Exit early if the request fails.
            print(f"Something went wrong calling the {self.flavour} annotations API {exc}.")
            return

        try:
            results = response.json().get("results")
        except ValueError:
            # Exit early if the JSON is malformed in the response.
            print(f"{self.flavour} returned invalid JSON.")
            return

        # Exit early if there is no 'results' object entry in the JSON.
        if results is None:
            return

        if (summary := results.get("summary")) is not None:
            self._summary = Summary(**summary)

        if (annotations := results.get("annotations")) is not None:
            self._results = [
                Result.construct_instance_from_raw_response(result, source=self.flavour) for result in annotations
            ]

    @property
    def results(self) -> list[Result]:
        """Return the fetched results or an empty list."""
        return self._results

    @property
    def summary(self) -> Summary | None:
        """Return the fetched summary or None."""
        return self._summary


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """
    jncc = AnnotationsAPIFetcher(flavour="JNCC", params=params)
    bodc = AnnotationsAPIFetcher(flavour="BODC", params=params)

    all_annotations = jncc.results + bodc.results

    combined_summary = (jncc.summary + bodc.summary) if jncc.summary is not None and bodc.summary is not None else None

    return SearchResults(
        count=len(all_annotations), results=Results(summary=combined_summary, annotations=all_annotations)
    )
