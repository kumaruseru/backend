"""Common Core - Exception Handler."""
import logging
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from apps.common.core.exceptions import DomainException

logger = logging.getLogger('apps.core')


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    response = drf_exception_handler(exc, context)

    if response is not None:
        response.data['code'] = getattr(exc, 'default_code', 'ERROR')
        return response

    if isinstance(exc, DomainException):
        return Response(exc.to_dict(), status=exc.http_status)

    if isinstance(exc, Http404):
        return Response({'code': 'NOT_FOUND', 'message': str(exc) or 'Không tìm thấy tài nguyên'}, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, PermissionDenied):
        return Response({'code': 'PERMISSION_DENIED', 'message': str(exc) or 'Không có quyền truy cập'}, status=status.HTTP_403_FORBIDDEN)

    logger.exception('Unhandled exception', extra={'view': context['view'].__class__.__name__, 'request_path': context['request'].path})
    return Response({'code': 'INTERNAL_ERROR', 'message': 'Đã xảy ra lỗi hệ thống'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
