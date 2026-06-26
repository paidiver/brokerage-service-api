"""Code to call the JNCC and BODC annotations API and compile the results."""

from urllib.parse import urljoin

import requests as rq

from brokerage_service_api.models.search_model import Result, Results, SearchResults
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest

JNCC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"
BODC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"


class BODCAnnotationsAPIFetcher:
    def __init__(self, params: AnnotationSearchRequest):
        """Initialise the class and make an attempt to call the BODC API."""
        self.params = params
        self._results = []
        self._summary = None
        self._make_request()

    def _make_request(self) -> None:
        """Make request to the BODC API and store the results in the class if available."""
        try:
            jncc_response = rq.get(urljoin(BODC_ANNOTATIONS_API_ENDPOINT, self.params.to_query_string()))
            jncc_response.raise_for_status()
        except Exception as exc:
            print(f"Something went wrong calling the BODC annotations API {exc}.")
            return
    
            
        bodc_results = jncc_response.json().get("results")
        
        # Exit early if there is no 'results' object entry in the JSON.
        if bodc_results is None:
            return
        
        if (bodc_summary := bodc_results.get("summary")) is not None:
            self._summary = bodc_summary

        if (bodc_annotations := bodc_results.get("annotations")) is not None:
            self._results = [Result.construct_instance_from_raw_response(result, source="BODC") for result in bodc_annotations]
        
    @property
    def bodc_results(self) -> list[Result]:
        """Return the fetched BODC results or an empty list."""
        return self._results
    
    @property
    def bodc_summary(self) -> dict | None:
        """"Return the fetched BODC summary or None."""
        return self._summary



class JNCCAnnotationsAPIFetcher:
    def __init__(self, params: AnnotationSearchRequest):
        """Initialise the class and make an attempt to call the JNCC API."""
        self.params = params
        self._results = []
        self._summary = None
        self._make_request()

    def _make_request(self) -> None:
        """Make request to the JNCC API and store the results in the class if available."""
        try:
            jncc_response = rq.get(urljoin(JNCC_ANNOTATIONS_API_ENDPOINT, self.params.to_query_string()))
            jncc_response.raise_for_status()
        except Exception as exc:
            print(f"Something went wrong calling the JNCC annotations API {exc}.")
            return
    
            
        jncc_results = jncc_response.json().get("results")
        
        # Exit early if there is no 'results' object entry in the JSON.
        if jncc_results is None:
            return
        
        if (jncc_summary := jncc_results.get("summary")) is not None:
            self._summary = jncc_summary

        if (jncc_annotations := jncc_results.get("annotations")) is not None:
            self._results = [Result.construct_instance_from_raw_response(result, source="JNCC") for result in jncc_annotations]
        
    @property
    def jncc_results(self) -> list[Result]:
        """Return the fetched JNCC results or an empty list."""
        return self._results
    
    @property
    def jncc_summary(self) -> dict | None:
        """"Return the fetched JNCC summary or None."""
        return self._summary


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """
    jncc = JNCCAnnotationsAPIFetcher(params=params)
    all_annotations = jncc.jncc_results

    return SearchResults(
        count=len(all_annotations),
        results=Results(annotations=all_annotations)
    )
