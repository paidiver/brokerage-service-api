"""Code to call the JNCC and BODC annotations API and compile the results."""

from urllib.parse import urljoin

import requests as rq

from brokerage_service_api.models.search_model import Result, SearchResults
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest

JNCC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8019/api/annotations/search/"
BODC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"


def fetch_results_from_bodc_annotations_api(params: AnnotationSearchRequest) -> list[Result]:
    """Call the BODC annotations api and return a list of results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        list: A list of Result objects constructed from the JNCC results.
    """
    try:
        bodc_response = rq.get(urljoin(BODC_ANNOTATIONS_API_ENDPOINT, params.to_query_string()))
        bodc_response.raise_for_status()
    except Exception as exc:
        # Log any errors and return an empty list, so any JNCC results can still be used.
        print(f"Something went wrong calling the BODC annotations API {exc}.")
        return []

    bodc_results = bodc_response.json().get("results").get("annotations")
    return [Result.construct_instance_from_raw_response(result, source="BODC") for result in bodc_results]


def fetch_results_from_jncc_annotations_api(params: AnnotationSearchRequest) -> list[Result]:
    """Call the JNCC annotations api and return a list of results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        list: A list of Result objects constructed from the JNCC results.
    """
    try:
        jncc_response = rq.get(urljoin(JNCC_ANNOTATIONS_API_ENDPOINT, params.to_query_string()))
        jncc_response.raise_for_status()
    except Exception as exc:
        # Log any errors and return an empty list, so any BODC results can still be used.
        print(f"Something went wrong calling the JNCC annotations API {exc}.")
        return []

    jncc_results = jncc_response.json().get("results").get("annotations")
    return [Result.construct_instance_from_raw_response(result, source="JNCC") for result in jncc_results]


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """
    return SearchResults(
        results=fetch_results_from_bodc_annotations_api(params=params)
        + fetch_results_from_jncc_annotations_api(params=params)
    )
