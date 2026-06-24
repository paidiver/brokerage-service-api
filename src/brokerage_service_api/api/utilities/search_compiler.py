"""Code to call the JNCC and BODC annotations API and compile the results."""

JNCC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8019/api/annotations/search/"
BODC_ANNOTATIONS_API_ENDPOINT = "http://localhost:8018/api/annotations/search/"


from brokerage_service_api.models.search_model import SearchResults, Result


def fetch_results_from_bodc_annotations_api() -> list[Result]:
    """Call the BODC annotations api and return a list of results."""
    pass


def fetch_results_from_jncc_annotations_api() -> list[Result]:
    """Call the JNCC annotations api and return a list of results."""
    pass


def fetch_combined_results_from_annotation_apis() -> SearchResults:
    """Call both annotations apis and return the combined results."""
    pass