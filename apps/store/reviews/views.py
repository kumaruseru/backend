"""Store Reviews - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Review, ReviewReport
from .serializers import (
    ReviewSerializer, ReviewListSerializer, ReviewCreateSerializer, ReviewUpdateSerializer,
    ReviewVoteSerializer, ReviewReportCreateSerializer, ReviewReportSerializer,
    ReviewSummarySerializer, ReviewAdminSerializer, ReviewModerationSerializer,
    ReviewStatisticsSerializer
)
from .services import ReviewService


class ProductReviewListView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[OpenApiParameter('rating', int, enum=[1, 2, 3, 4, 5]), OpenApiParameter('verified_only', bool), OpenApiParameter('with_images', bool), OpenApiParameter('sort', str, enum=['recent', 'helpful', 'rating_high', 'rating_low']), OpenApiParameter('limit', int), OpenApiParameter('offset', int)], responses={200: ReviewListSerializer(many=True)}, tags=['Reviews'])
    def get(self, request, product_id):
        result = ReviewService.get_product_reviews(product_id=product_id, rating=request.query_params.get('rating'), verified_only=request.query_params.get('verified_only') == 'true', with_images=request.query_params.get('with_images') == 'true', sort=request.query_params.get('sort', 'recent'), limit=int(request.query_params.get('limit', 20)), offset=int(request.query_params.get('offset', 0)))
        return Response({'reviews': ReviewListSerializer(result['reviews'], many=True).data, 'total': result['total'], 'has_more': result['has_more']})


class ProductReviewSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ReviewSummarySerializer}, tags=['Reviews'])
    def get(self, request, product_id):
        summary = ReviewService.get_review_summary(product_id)
        return Response(ReviewSummarySerializer(summary).data)


class ReviewDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ReviewSerializer}, tags=['Reviews'])
    def get(self, request, review_id):
        try:
            review = Review.objects.prefetch_related('images', 'replies').get(id=review_id, is_approved=True)
            return Response(ReviewSerializer(review).data)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)


class ReviewCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ReviewCreateSerializer, responses={201: ReviewSerializer}, tags=['Reviews'])
    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            review = ReviewService.create_review(user=request.user, **serializer.validated_data)
            return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class ReviewUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ReviewUpdateSerializer, responses={200: ReviewSerializer}, tags=['Reviews'])
    def patch(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id, user=request.user)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReviewUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = ReviewService.update_review(review, **serializer.validated_data)
        return Response(ReviewSerializer(updated).data)

    @extend_schema(responses={204: None}, tags=['Reviews'])
    def delete(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id, user=request.user)
            ReviewService.delete_review(review)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)


class MyReviewsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReviewListSerializer
    pagination_class = None

    def get_queryset(self):
        return ReviewService.get_user_reviews(self.request.user)

    @extend_schema(tags=['Reviews'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ReviewableProductsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Reviews'])
    def get(self, request):
        from apps.store.catalog.serializers import ProductCardSerializer
        products = ReviewService.get_reviewable_products(request.user)
        return Response(ProductCardSerializer(products, many=True).data)


class ReviewVoteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ReviewVoteSerializer, tags=['Reviews'])
    def post(self, request, review_id):
        serializer = ReviewVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = Review.objects.get(id=review_id, is_approved=True)
            ReviewService.vote_review(review=review, user=request.user, is_helpful=serializer.validated_data['is_helpful'])
            return Response({'helpful_count': review.helpful_count, 'not_helpful_count': review.not_helpful_count})
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class ReviewReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ReviewReportCreateSerializer, responses={201: ReviewReportSerializer}, tags=['Reviews'])
    def post(self, request):
        serializer = ReviewReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = Review.objects.get(id=serializer.validated_data['review'].id)
            report = ReviewService.report_review(review=review, reporter=request.user, reason=serializer.validated_data['reason'], details=serializer.validated_data.get('details', ''))
            return Response(ReviewReportSerializer(report).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AdminReviewListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ReviewAdminSerializer

    def get_queryset(self):
        queryset = Review.objects.select_related('user', 'product').prefetch_related('images', 'reports')
        status_filter = self.request.query_params.get('status')
        if status_filter == 'pending':
            queryset = queryset.filter(is_approved=False, is_rejected=False)
        elif status_filter == 'approved':
            queryset = queryset.filter(is_approved=True)
        elif status_filter == 'rejected':
            queryset = queryset.filter(is_rejected=True)
        return queryset.order_by('-created_at')

    @extend_schema(parameters=[OpenApiParameter('status', str, enum=['pending', 'approved', 'rejected'])], tags=['Reviews - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminReviewModerationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=ReviewModerationSerializer, responses={200: ReviewAdminSerializer}, tags=['Reviews - Admin'])
    def post(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReviewModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        if action == 'approve':
            ReviewService.approve_review(review, request.user)
        elif action == 'reject':
            ReviewService.reject_review(review, reason, request.user)
        return Response(ReviewAdminSerializer(review).data)


class AdminBulkModerationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(tags=['Reviews - Admin'])
    def post(self, request):
        review_ids = request.data.get('review_ids', [])
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        count = ReviewService.bulk_moderate(review_ids, action, request.user, reason)
        return Response({'moderated': count})


class AdminReplyView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(tags=['Reviews - Admin'])
    def post(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found'}, status=status.HTTP_404_NOT_FOUND)
        content = request.data.get('content', '')
        if not content:
            return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)
        reply = ReviewService.add_reply(review, request.user, content, is_official=True)
        return Response({'id': reply.id, 'content': reply.content})


class AdminReportListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = ReviewReportSerializer
    pagination_class = None

    def get_queryset(self):
        return ReviewService.get_pending_reports()

    @extend_schema(tags=['Reviews - Admin'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: ReviewStatisticsSerializer}, tags=['Reviews - Admin'])
    def get(self, request):
        stats = ReviewService.get_statistics()
        return Response(stats)
