from celery import shared_task
from django_tenants.utils import schema_context
import logging
import json

# Create a dedicated logger for request logging
request_logger = logging.getLogger('request_logger')
logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True, max_retries=3)
def log_request_async(self, tenant_schema, log_data):
    """
    Async task to log API requests to database and console
    Runs in the correct tenant schema context

    Args:
        tenant_schema (str): The tenant schema name
        log_data (dict): Dictionary containing all request/response data
    """
    try:
        # Switch to the correct tenant schema
        with schema_context(tenant_schema):
            from .models import RequestLog

            # Create the log entry in the tenant's schema
            RequestLog.objects.create(**log_data)

            # Log to console/TUI for live monitoring
            _log_to_console_structured(tenant_schema, log_data)

    except Exception as exc:
        # Log the error but don't fail the request
        logger.error(
            f"Failed to log request in schema {tenant_schema}: {str(exc)}",
            exc_info=True
        )

        # Retry the task (max 3 times with exponential backoff)
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for logging request in schema {
                    tenant_schema}"
            )


def _log_to_console_structured(tenant_schema, log_data):
    """
    Log request using Python's logging module with structured data

    Args:
        tenant_schema (str): The tenant schema name
        log_data (dict): Dictionary containing all request/response data
    """
    # Determine log level based on status code
    status_code = log_data['status_code']
    if status_code >= 500:
        log_level = logging.ERROR
    elif status_code >= 400:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    # Format user info
    user_info = f"user_id={log_data.get('user_id', 'anonymous')}"

    # Create structured log message
    log_message = (
        f"[{tenant_schema}] {log_data['method']} {log_data['path']} - "
        f"Status: {status_code} - "
        f"Time: {log_data['response_time_ms']:.2f}ms - "
        f"{user_info} - "
        f"IP: {log_data.get('ip_address', 'N/A')}"
    )

    # Create extra context for structured logging
    extra_context = {
        'tenant_schema': tenant_schema,
        'method': log_data['method'],
        'path': log_data['path'],
        'status_code': status_code,
        'response_time_ms': log_data['response_time_ms'],
        'user_id': log_data.get('user_id'),
        'ip_address': log_data.get('ip_address'),
        'is_failed': log_data.get('is_failed', False),
    }

    # Log the request
    request_logger.log(log_level, log_message, extra=extra_context)

    # If failed, log additional details
    if log_data.get('is_failed'):
        request_logger.error(
            f"[{tenant_schema}] Failed request details"
        )
        request_logger.error(
            f"Response Body: {json.dumps(
                log_data.get('response_body', {}), indent=2)}"
        )
        request_logger.error(
            f"Request Body: {json.dumps(log_data.get('body', {}), indent=2)}"
        )
