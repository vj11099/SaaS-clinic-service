import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from apps.audit_logs.tasks import log_request_async
import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Tenant-aware DRF middleware for async request logging

    Logs all API requests except OPTIONS and HEAD methods
    Captures request/response data and logs asynchronously via Celery
    Logs are stored in each tenant's schema automatically
    """

    # Methods to exclude from logging
    EXCLUDED_METHODS = ['OPTIONS', 'HEAD']

    def process_request(self, request):
        """Start timer for request duration tracking"""
        request._start_time = time.time()
        return None

    def process_response(self, request, response):
        """
        Capture response data and trigger async logging
        """
        # Skip excluded methods
        if request.method in self.EXCLUDED_METHODS:
            return response

        # Skip if no start time (shouldn't happen, but safety check)
        if not hasattr(request, '_start_time'):
            return response

        # Calculate response time
        response_time_ms = (time.time() - request._start_time) * 1000

        try:
            # Get current tenant schema
            tenant_schema = connection.schema_name

            # if tenant_schema == 'public':
            #     return response

            # Prepare log data
            log_data = self._prepare_log_data(
                request, response, response_time_ms)

            # Trigger async logging task with tenant schema
            log_request_async.delay(tenant_schema, log_data)

        except Exception as e:
            # Never fail the request due to logging errors
            logger.error(f"Error preparing request log: {
                         str(e)}", exc_info=True)

        return response

    def _prepare_log_data(self, request, response, response_time_ms):
        """
        Prepare all data for logging

        Returns:
            dict: All log data ready for database insertion
        """
        status_code = response.status_code
        is_failed = status_code >= 400

        # Extract request data
        log_data = {
            # Request metadata
            'method': request.method,
            'path': request.path,

            # Request details
            'headers': self._get_headers(request),
            'query_params': dict(request.GET),
            'body': self._get_request_body(request),

            # User information
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip_address': self._get_client_ip(request),
            # Truncate
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],

            # Response data
            'status_code': status_code,
            'response_time_ms': round(response_time_ms, 2),
            'is_failed': is_failed,
        }

        # Only include response body for failed requests
        if is_failed:
            log_data['response_body'] = self._get_response_body(response)

        return log_data

    def _get_headers(self, request):
        """
        Extract HTTP headers from request
        Excludes certain sensitive headers
        """
        # Headers to exclude from logging
        excluded_headers = {
            'HTTP_COOKIE',
            # 'HTTP_AUTHORIZATION',  # Uncomment to exclude auth tokens
        }

        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_') and key not in excluded_headers:
                # Convert HTTP_CONTENT_TYPE to Content-Type format
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value

        return headers

    def _get_request_body(self, request):
        """
        Extract and parse request body
        Handles JSON and form data
        """
        try:
            # Check if body was already read
            if hasattr(request, '_body'):
                body = request._body
            else:
                body = request.body

            if not body:
                return {}

            # Try to parse as JSON
            try:
                return json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, try to get POST data
                if hasattr(request, 'POST') and request.POST:
                    return dict(request.POST)
                # If all else fails, return raw body as string (truncated)
                return {'raw_body': body.decode('utf-8', errors='ignore')[:1000]}

        except Exception as e:
            logger.warning(f"Error parsing request body: {str(e)}")
            return {}

    def _get_response_body(self, response):
        """
        Extract response body for failed requests
        Only called when status_code >= 400
        """
        try:
            # Check if response has content
            if hasattr(response, 'content'):
                content = response.content

                # Try to parse as JSON
                try:
                    return json.loads(content.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Return as string if not JSON (truncated)
                    return {'raw_response': content.decode('utf-8', errors='ignore')[:1000]}

            # For streaming or file responses
            return {'note': 'Response body not captured (streaming/file response)'}

        except Exception as e:
            logger.warning(f"Error parsing response body: {str(e)}")
            return {}

    def _get_client_ip(self, request):
        """
        Get client IP address from request
        Handles proxy headers
        """
        # Check for proxy headers first
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # X-Forwarded-For can contain multiple IPs, get the first one
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        return ip
