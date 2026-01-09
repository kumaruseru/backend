"""Store Reviews - URL Configuration."""
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Public
    path('products/<uuid:product_id>/reviews/', views.ProductReviewListView.as_view(), name='product_reviews'),
    path('products/<uuid:product_id>/reviews/summary/', views.ProductReviewSummaryView.as_view(), name='product_summary'),
    path('reviews/<uuid:review_id>/', views.ReviewDetailView.as_view(), name='review_detail'),

    # User
    path('reviews/create/', views.ReviewCreateView.as_view(), name='create'),
    path('reviews/<uuid:review_id>/update/', views.ReviewUpdateView.as_view(), name='update'),
    path('reviews/<uuid:review_id>/vote/', views.ReviewVoteView.as_view(), name='vote'),
    path('reviews/report/', views.ReviewReportView.as_view(), name='report'),
    path('reviews/my/', views.MyReviewsView.as_view(), name='my_reviews'),
    path('reviews/reviewable/', views.ReviewableProductsView.as_view(), name='reviewable'),

    # Admin
    path('admin/reviews/', views.AdminReviewListView.as_view(), name='admin_list'),
    path('admin/reviews/<uuid:review_id>/moderate/', views.AdminReviewModerationView.as_view(), name='admin_moderate'),
    path('admin/reviews/<uuid:review_id>/reply/', views.AdminReplyView.as_view(), name='admin_reply'),
    path('admin/reviews/bulk-moderate/', views.AdminBulkModerationView.as_view(), name='admin_bulk'),
    path('admin/reports/', views.AdminReportListView.as_view(), name='admin_reports'),
    path('admin/statistics/', views.AdminStatisticsView.as_view(), name='admin_stats'),
]
