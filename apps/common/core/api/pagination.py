"""Common Core - Pagination Utilities."""
from typing import Dict, Any
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """Standard pagination with configurable page size."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'results': data,
            'count': self.page.paginator.count,
            'page': self.page.number,
            'pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
        })


class SmallPagination(StandardPagination):
    """Small page size for lists."""
    page_size = 10
    max_page_size = 50


class LargePagination(StandardPagination):
    """Large page size for admin views."""
    page_size = 50
    max_page_size = 200


def paginate_queryset(queryset, page: int = 1, page_size: int = 20, max_page_size: int = 100) -> Dict[str, Any]:
    """Manual pagination helper."""
    page_size = min(page_size, max_page_size)
    page = max(page, 1)
    total = queryset.count()
    offset = (page - 1) * page_size
    items = list(queryset[offset:offset + page_size])
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        'items': items,
        'count': total,
        'page': page,
        'pages': total_pages,
        'page_size': page_size,
        'has_next': page < total_pages,
        'has_previous': page > 1,
    }
