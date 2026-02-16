from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def response_handler(func):
    """
    Decorator for handling standard API responses with error handling.

    Expected return format from decorated function:
        - (data, message, status_code) tuple
        - (data, message) tuple (defaults to HTTP_200_OK)

    Returns a Response with standardized format:
    Success:
    {
        "status": True,
        "message": message,
        "data": data
    }

    Error:
    {
        "status": False,
        "message": error_message,
        "errors": error_details (optional),
        "data": None
    }
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            # Handle tuple unpacking
            if isinstance(result, tuple):
                if len(result) == 3:
                    data, message, status_code = result
                elif len(result) == 2:
                    data, message = result
                    status_code = status.HTTP_200_OK
                else:
                    raise ValueError(
                        "Invalid return format. Expected (data, message) or (data, message, status_code)")
            else:
                raise ValueError("Decorated function must return a tuple")

            response_data = {
                "status": True,
                "message": message,
                "data": data
            }

            return Response(response_data, status=status_code)

        except Exception as e:
            response_data = {
                "status": False,
                "message": str(e),
                "data": None
            }

            if hasattr(e, 'detail'):
                response_data['errors'] = e.detail

            status_code = getattr(
                e, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(response_data, status=status_code)

    return wrapper


# def paginated_response_handler(func):
#     """
#     Decorator for handling paginated list responses with error handling.
#
#     Expected return format from decorated function:
#         - (queryset, page, serializer_data, message) tuple
#
#     The decorator will use the view's get_paginated_response method to format
#     the pagination metadata and merge it with the serialized data.
#
#     Returns a Response with format:
#     Success:
#     {
#         "status": True,
#         "message": message,
#         "total_page": total_pages,
#         "count": total_count,
#         "current_page": current_page,
#         "next": next_page_url,
#         "previous": previous_page_url,
#         "data": serializer_data
#     }
#
#     Error:
#     {
#         "status": False,
#         "message": error_message,
#         "errors": error_details (optional),
#         "data": None
#     }
#     """
#     @wraps(func)
#     def wrapper(self, request, *args, **kwargs):
#         try:
#             result = func(self, request, *args, **kwargs)
#
#             # Handle early return (e.g., empty queryset)
#             if isinstance(result, Response):
#                 return result
#
#             # Unpack the result
#             if not isinstance(result, tuple) or len(result) != 4:
#                 raise ValueError(
#                     "Decorated function must return (queryset, page, serializer_data, message)")
#
#             queryset, page, serializer_data, message = result
#
#             # If we have a page object, use the paginated response
#             if page is not None:
#                 paginated_response = self.get_paginated_response(
#                     serializer_data)
#                 pagination_data = paginated_response.data
#
#                 # Restructure to match expected format
#                 response_data = {
#                     "status": True,
#                     "message": message,
#                     "total_page": pagination_data.get('total_pages', 0),
#                     "count": pagination_data.get('count', 0),
#                     "current_page": pagination_data.get('current_page', int(request.GET.get('page', 1))),
#                     "next": pagination_data.get('next', None),
#                     "previous": pagination_data.get('previous', None),
#                     "data": pagination_data.get('results', serializer_data)
#                 }
#             else:
#                 # No pagination
#                 response_data = {
#                     "status": True,
#                     "message": message,
#                     "total_page": 1,
#                     "count": len(serializer_data) if serializer_data else 0,
#                     "current_page": 1,
#                     "next": None,
#                     "previous": None,
#                     "data": serializer_data
#                 }
#
#             return Response(response_data, status=status.HTTP_200_OK)
#
#         except Exception as e:
#             response_data = {
#                 "status": False,
#                 "message": str(e),
#                 "data": None
#             }
#
#             # Add detailed errors if available (e.g., ValidationError)
#             if hasattr(e, 'detail'):
#                 response_data['errors'] = e.detail
#
#             # Determine appropriate status code
#             status_code = getattr(
#                 e, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#             return Response(response_data, status=status_code)
#
#     return wrapper
