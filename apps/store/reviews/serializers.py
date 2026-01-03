"""
Store Reviews - Production-Ready Serializers.
"""
from rest_framework import serializers
from .models import Review, ReviewImage, ReviewReply, ReviewVote, ReviewReport, ReviewSummary


# ==================== Image Serializers ====================

class ReviewImageSerializer(serializers.ModelSerializer):
    """Review image output."""
    
    class Meta:
        model = ReviewImage
        fields = ['id', 'image', 'caption', 'sort_order']


class ReviewImageUploadSerializer(serializers.ModelSerializer):
    """For uploading review images."""
    
    class Meta:
        model = ReviewImage
        fields = ['image', 'caption']


# ==================== Reply Serializers ====================

class ReviewReplySerializer(serializers.ModelSerializer):
    """Review reply output."""
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewReply
        fields = ['id', 'user_name', 'content', 'is_official', 'created_at']
    
    def get_user_name(self, obj) -> str:
        return obj.user.get_full_name() or 'Admin'


# ==================== Review Serializers ====================

class ReviewSerializer(serializers.ModelSerializer):
    """Full review output DTO."""
    user_display_name = serializers.ReadOnlyField()
    user_avatar = serializers.SerializerMethodField()
    images = ReviewImageSerializer(many=True, read_only=True)
    replies = ReviewReplySerializer(many=True, read_only=True)
    
    has_images = serializers.ReadOnlyField()
    helpfulness_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_display_name', 'user_avatar',
            'rating', 'title', 'comment',
            'quality_rating', 'value_rating', 'delivery_rating',
            'is_verified_purchase', 'is_featured',
            'images', 'replies',
            'helpful_count', 'not_helpful_count', 'helpfulness_percentage',
            'has_images', 'created_at'
        ]
    
    def get_user_avatar(self, obj) -> str:
        if hasattr(obj.user, 'profile') and obj.user.profile.avatar:
            return obj.user.profile.avatar.url
        return ''


class ReviewListSerializer(serializers.ModelSerializer):
    """Simplified review for listings."""
    user_display_name = serializers.ReadOnlyField()
    has_images = serializers.ReadOnlyField()
    images_count = serializers.SerializerMethodField()
    has_reply = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_display_name',
            'rating', 'title', 'comment',
            'is_verified_purchase',
            'has_images', 'images_count',
            'helpful_count', 'has_reply',
            'created_at'
        ]
    
    def get_images_count(self, obj) -> int:
        return obj.images.count()
    
    def get_has_reply(self, obj) -> bool:
        return obj.replies.filter(is_official=True).exists()


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Create review input."""
    images = serializers.ListField(
        child=serializers.ImageField(),
        max_length=5,
        required=False
    )
    
    class Meta:
        model = Review
        fields = [
            'product', 'order',
            'rating', 'title', 'comment',
            'quality_rating', 'value_rating', 'delivery_rating',
            'images'
        ]
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Đánh giá phải từ 1-5 sao')
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        product = data.get('product')
        
        # Check if user already reviewed this product
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError('Bạn đã đánh giá sản phẩm này rồi')
        
        return data
    
    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        review = Review.objects.create(**validated_data)
        
        for i, image in enumerate(images_data):
            ReviewImage.objects.create(
                review=review,
                image=image,
                sort_order=i
            )
        
        return review


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """Update review input."""
    
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment', 'quality_rating', 'value_rating', 'delivery_rating']


# ==================== Vote Serializers ====================

class ReviewVoteSerializer(serializers.Serializer):
    """Vote on a review."""
    is_helpful = serializers.BooleanField()


# ==================== Report Serializers ====================

class ReviewReportSerializer(serializers.ModelSerializer):
    """Report output."""
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ReviewReport
        fields = [
            'id', 'review', 'reason', 'reason_display',
            'details', 'status', 'status_display',
            'created_at'
        ]


class ReviewReportCreateSerializer(serializers.ModelSerializer):
    """Create report input."""
    
    class Meta:
        model = ReviewReport
        fields = ['review', 'reason', 'details']


# ==================== Summary Serializers ====================

class ReviewSummarySerializer(serializers.ModelSerializer):
    """Review summary for product page."""
    rating_distribution = serializers.ReadOnlyField()
    
    class Meta:
        model = ReviewSummary
        fields = [
            'total_reviews', 'average_rating',
            'rating_5', 'rating_4', 'rating_3', 'rating_2', 'rating_1',
            'rating_distribution',
            'avg_quality', 'avg_value', 'avg_delivery',
            'verified_count', 'with_images_count'
        ]


# ==================== Admin Serializers ====================

class ReviewAdminSerializer(serializers.ModelSerializer):
    """Admin review output with moderation info."""
    user_email = serializers.CharField(source='user.email')
    product_name = serializers.CharField(source='product.name')
    images = ReviewImageSerializer(many=True, read_only=True)
    reports_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_email', 'product_name',
            'rating', 'title', 'comment',
            'is_verified_purchase', 'is_approved', 'is_rejected',
            'rejection_reason',
            'helpful_count', 'not_helpful_count',
            'images', 'reports_count',
            'created_at', 'moderated_at'
        ]
    
    def get_reports_count(self, obj) -> int:
        return obj.reports.filter(status='pending').count()


class ReviewModerationSerializer(serializers.Serializer):
    """Moderation action input."""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)


# ==================== Statistics ====================

class ReviewStatisticsSerializer(serializers.Serializer):
    """Review statistics output."""
    total_reviews = serializers.IntegerField()
    pending_reviews = serializers.IntegerField()
    approved_reviews = serializers.IntegerField()
    rejected_reviews = serializers.IntegerField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    reviews_today = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
