"""Code to call the JNCC and BODC annotations API and compile the results."""
import requests as rq
from brokerage_service_api.models.search_model import Result, SearchResults

JNCC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8019/api/annotations/search/"
BODC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"


def fetch_results_from_bodc_annotations_api() -> list[Result]:
    """Call the BODC annotations api and return a list of results."""

    try:
        bodc_response = rq.get(BODC_ANNOTATIONS_API_ENDPOINT)
        bodc_response.raise_for_status()
    except Exception as exc: # TODO: Catch specific exceptions and log properly.
        print(f"Something went wrong calling the BODC annotations API {exc}.")
        return []
    
    # TODO: Implement class method within the Result class to parse properly.
    bodc_response_data = bodc_response.json().get("results")

   

def fetch_results_from_jncc_annotations_api() -> list[Result]:
    """Call the JNCC annotations api and return a list of results."""
    try:
        jncc_response = rq.get(JNCC_ANNOTATIONS_API_ENDPOINT)
        jncc_response.raise_for_status()
    except Exception as exc: # TODO: Catch specific exceptions and log properly.
        print(f"Something went wrong calling the JNCC annotations API {exc}.")
        return []
    
    # TODO: Implement class method within the Result class to parse properly.
    jncc_response_data = jncc_response.json().get("results")

def fetch_combined_results_from_annotation_apis() -> SearchResults:
    """Call both annotations apis and return the combined results."""

    bodc_results = fetch_results_from_bodc_annotations_api()
    jncc_results = fetch_results_from_jncc_annotations_api()

    return bodc_results + jncc_results

