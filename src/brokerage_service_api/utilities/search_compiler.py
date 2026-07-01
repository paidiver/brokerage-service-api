"""Code to call the upstream annotations API's and compile the results."""

import os
import re
from itertools import batched
from urllib.parse import parse_qs

import requests as rq
from fastapi import Request

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


def construct_prev_and_next_response_fields(request_url: str, maximum_allowed_page: int) -> tuple[str | None]:
    """Use the incoming URL to construct the 'prev' and 'next' fields in the response.

    'prev' will stay as None if any the following conditions are met:
        - page is 1
        - An error is raised whilst parsing for the page value

    'prev' will change if the current page is > 1.

    -----------------
    'next_' will stay as None if the following conditions are met:
        - An error is raised whilst parsing for the page value

    'next_' will stay as the current value if it is the maximum allowed value. For example if the
    user is on page 2, and this is the last page, then 2 will be returned.

    'next_' will update by +1 if allowable. For example is there are 4 batches of results, and the user is on
    page 3, then 3 will be returned.

    """
    # Define the 'prev' and 'next' as None, unless further logic dictates they need to be changed.
    prev, next_ = None, None
    request_fields = parse_qs(request_url)
    minimum_page_value = 2

    try:
        current_page_value = int(request_fields["page"][0])
    except KeyError:
        # If no page is set in the query, assume page 1.
        current_page_value = 1
    except Exception:
        return prev, next_

    if current_page_value >= minimum_page_value:
        prev = str(current_page_value - 1)
    elif current_page_value == 1:
        prev = None

    # If the current page is the maximum allowable page, then set to that.
    if current_page_value == maximum_allowed_page:
        next_ = str(current_page_value)

    # If the current page is less than the maxium allowable, increment by 1.
    elif current_page_value < maximum_allowed_page:
        next_ = str(current_page_value + 1)

    return prev, next_


def construct_previous_and_next_urls(
    incoming_url: str, previous_value: str | None, next_value: str | None
) -> str | None:
    """Use the incoming URL, and the potential previous/next values to form the new URLS.

    Args:
        incoming_url: the incoming URL.
        previous_value: If a string, make a new url with the value.
        next_value: If a string, make a new url with the value

    Returns:
    Either a url, or None.
    """
    previous_url = re.sub("&page=\\d+", f"&page={previous_value}", incoming_url) if previous_value is not None else None

    if next_value is not None:
        if "&page=" in incoming_url:
            next_url = re.sub(r"&page=\d+", f"&page={next_value}", incoming_url)
        else:
            next_url = incoming_url + f"&page={next_value}"
    else:
        next_url = None

    return previous_url, next_url


def results_with_pagination_applied(
    count: int, all_results: Results, page_size: int, page_number: int | None, request: Request
) -> Results:
    """Apply pagination to the results and return a subset.

    Args:
        count: The total count of all results.
        all_results: All the upstream results, to perform the pagination upon.
        page_size: The number of results on one page.
        page_number: The page number to return.
        request: The raw request object.

    Returns:
    A SearchResults object with a subset of the results, and the prev|next fields populated.
    """
    # Batch the annotations into the required size (100 is the default).
    batched_annotations = list(batched(all_results.annotations, n=page_size))

    # Fetch the values needed for the previous and next URL's.
    prev_field, next_field = construct_prev_and_next_response_fields(
        request_url=str(request.url), maximum_allowed_page=len(batched_annotations)
    )

    # Use the values from the previous function calls to now build the previous and next URL's.
    previous_url, next_url = construct_previous_and_next_urls(
        incoming_url=str(request.url), previous_value=prev_field, next_value=next_field
    )

    # If no page number is passed, then just return the first page of results.
    # This is the default path, so the user will just see 100 results or less.
    if page_number is None:
        return SearchResults(
            previous=previous_url,
            next=next_url,
            count=count,  #
            results=Results(summary=all_results.summary, annotations=batched_annotations[0]),
        )

    # If the user passes a page number, return that specific batch or raise an error if not applicable.
    try:
        specified_annotation_batch = batched_annotations[page_number - 1]
    except IndexError:
        raise InvalidPageNumberError from None

    paginated_results = Results(summary=all_results.summary, annotations=specified_annotation_batch)
    return SearchResults(previous=previous_url, next=next_url, count=count, results=paginated_results)


def fetch_combined_results_from_annotation_apis(params: AnnotationSearchRequest, request: Request) -> SearchResults:
    """Call both annotations apis and return the combined results.

    Args:
        params: A model with all the required params to send upstream to the BODC/JNCC API's.
        request: The raw request object.

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
        count=len(all_annotations),
        all_results=all_results,
        page_size=params.page_size,
        page_number=params.page,
        request=request,
    )
