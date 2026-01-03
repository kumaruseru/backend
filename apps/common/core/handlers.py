"""
Common Core - Exception Handler.

Custom DRF exception handler that converts domain exceptions
to proper API responses.
"""
import logging
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import (
    DomainException, ValidationError, NotFoundError,
    AuthenticationError, AuthorizationError, BusinessRuleViolation,
    ExternalServiceError, RateLimitError, ConflictError
)

logger = logging.getLogger('apps.core')


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    
    Converts DomainException and its subclasses to proper API responses.
    """
    # First, call DRF's default exception handler
    response = drf_exception_handler(exc, context)
    
    # If DRF handled it, enhance the response
    if response is not None:
        response.data['code'] = getattr(exc, 'default_code', 'ERROR')
        return response
    
    # Handle DomainException hierarchy
    if isinstance(exc, DomainException):
        return Response(
            exc.to_dict(),
            status=exc.http_status
        )
    
    # Handle Django's Http404
    if isinstance(exc, Http404):
        return Response(
            {
                'code': 'NOT_FOUND',
                'message': str(exc) or 'Không tìm thấy tài nguyên',
            },
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Handle Django's PermissionDenied
    if isinstance(exc, PermissionDenied):
        return Response(
            {
                'code': 'PERMISSION_DENIED',
                'message': str(exc) or 'Không có quyền truy cập',
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Log unhandled exceptions
    logger.exception(
        'Unhandled exception',
        extra={
            'view': context['view'].__class__.__name__,
            'request_path': context['request'].path,
        }
    )
    
    # Return generic error for unhandled exceptions
    return Response(
        {
            'code': 'INTERNAL_ERROR',
            'message': 'Đã xảy ra lỗi hệ thống',
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


class ServiceUnavailable(APIException):
    """API Exception for service unavailable."""
    status_code = 503
    default_detail = 'Dịch vụ tạm thời không khả dụng'
    default_code = 'service_unavailable'


class BadRequest(APIException):
    """API Exception for bad requests."""
    status_code = 400
    default_detail = 'Yêu cầu không hợp lệ'
    default_code = 'bad_request'


class Conflict(APIException):
    """API Exception for conflicts."""
    status_code = 409
    default_detail = 'Xung đột dữ liệu'
    default_code = 'conflict'
