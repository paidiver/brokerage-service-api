"""Code to call the upstream annotations API's and compile the results."""

import os
from itertools import batched

import requests as rq

from brokerage_service_api.models.search_model import Result, Results, SearchResults, Summary
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest

JNCC_ANNOTATIONS_API_ENDPOINT = os.getenv("JNCC_SEARCH_ENDPOINT", "http://localhost:8018/api/annotations/search/")
BODC_ANNOTATIONS_API_ENDPOINT = os.getenv("BODC_SEARCH_ENDPOINT", "http://localhost:8019/api/annotations/search/")

ENDPOINTS = {"JNCC": JNCC_ANNOTATIONS_API_ENDPOINT, "BODC": BODC_ANNOTATIONS_API_ENDPOINT}


class UnknownFlavourError(Exception):
    """Raised when an unknown upstream is referenced."""

class InvalidPageNumberError(Exception):
    """Raised when a page number is requested that is too large."""


class AnnotationsAPIFetcher:
    """Methods to fetch from upstream API's and return data."""

    def __init__(self, flavour: str, params: AnnotationSearchRequest):
        """Initialise the class and make an attempt to call the upstream API."""
        self.flavour: str = flavour
        self.params: AnnotationSearchRequest = params
        self._results: list[Result] = []
        self._summary: Summary | None = None
        self._make_request()

    def order_results(self) -> None:
        """Perform an in-place sort of the internal _results list."""
        # If no order_by is passed, return with no action taken.
        if self.params.order_by is None:
            return

        # Retrieve the ordering key and check if it matches the available ordering.
        order_by_key = self.params.order_by

        if order_by_key == "label_aphia_id":
            self._results.sort(key=lambda result: result.label_aphia_id)
        if order_by_key == "annotation_creation_datetime":
            self._results.sort(key=lambda result: result.annotation_creation_datetime)
        if order_by_key == "label_name":
            self._results.sort(key=lambda result: result.label_name)

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
            # This is only called when we have a result set.
            self.order_results()

    @property
    def results(self) -> list[Result]:
        """Return the fetched results or an empty list."""
        return self._results

    @property
    def summary(self) -> Summary | None:
        """Return the fetched summary or None."""
        return self._summary


def results_with_pagination_applied(
    count: int, all_results: Results, page_size: int, page_number: int | None
) -> Results:
    """Apply pagination to the results and return a subset.

    Args:
        count: The total count of all results.
        all_results: All the upstream results, to perform the pagination upon.
        page_size: The number of results on one page.
        page_number: The page number to return.

    Returns:
    A SearchResults object with a subset of the results, and the prev|next fields populated.
    """
    # Batch the annotations into the required size (100 is the default).
    batched_annotations = list(batched(all_results.annotations, n=page_size))

    # If no page number is passed, then just return the first page of results.
    if page_number is None:
        return SearchResults(
            count=count, results=Results(summary=all_results.summary, annotations=batched_annotations[0])
        )

    try:
        specified_annotation_batch = batched_annotations[page_number - 1]
    except IndexError:
        raise InvalidPageNumberError from None
    
        
    paginated_results = Results(summary=all_results.summary, annotations=specified_annotation_batch)
    return SearchResults(count=count, results=paginated_results)


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.

    Returns:
        SearchResults: An instance with the results built from both the BODC and JNCC API's.
    """
    jncc, bodc = (
        AnnotationsAPIFetcher(flavour="JNCC", params=params),
        AnnotationsAPIFetcher(flavour="BODC", params=params),
    )

    all_annotations = jncc.results + bodc.results

    combined_summary = (jncc.summary + bodc.summary) if jncc.summary is not None and bodc.summary is not None else None
    all_results = Results(summary=combined_summary, annotations=all_annotations)

    # Perform any pagination that is required
    return results_with_pagination_applied(
        count=len(all_annotations), all_results=all_results, page_size=params.page_size, page_number=params.page
    )

    return SearchResults(count=len(all_annotations), results=all_results)
