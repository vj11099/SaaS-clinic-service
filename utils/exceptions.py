from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        custom_response = {
            'success': False,
            'error': {
                'message': None,
                'details': None,
            }
        }

        if isinstance(exc, ValidationError):
            custom_response['error']['message'] = 'Validation error'
            custom_response['error']['details'] = response.data
        else:
            if isinstance(response.data, dict):
                if 'detail' in response.data:
                    custom_response['error']['message'] = response.data['detail']
                else:
                    custom_response['error']['message'] = str(response.data)
                    custom_response['error']['details'] = response.data
            else:
                custom_response['error']['message'] = str(response.data)

        response.data = custom_response

    return response


def success_response(data=None, message=None, status=200):
    response_data = {
        'success': True,
        'data': data,
    }

    if message:
        response_data['message'] = message

    return Response(response_data, status=status)
