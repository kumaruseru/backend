"""Store Reviews - Serializers."""
from rest_framework import serializers
from .models import Review, ReviewImage, ReviewReply, ReviewVote, ReviewReport, ReviewSummary


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ['id', 'image', 'caption', 'sort_order']


class ReviewImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ['image', 'caption']


class ReviewReplySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ReviewReply
        fields = ['id', 'user_name', 'content', 'is_official', 'created_at']

    def get_user_name(self, obj) -> str:
        return obj.user.get_full_name() or 'Admin'


class ReviewSerializer(serializers.ModelSerializer):
    user_display_name = serializers.ReadOnlyField()
    user_avatar = serializers.SerializerMethodField()
    images = ReviewImageSerializer(many=True, read_only=True)
    replies = ReviewReplySerializer(many=True, read_only=True)
    has_images = serializers.ReadOnlyField()
    helpfulness_percentage = serializers.ReadOnlyField()

    class Meta:
        model = Review
        fields = ['id', 'user_display_name', 'user_avatar', 'rating', 'title', 'comment', 'quality_rating', 'value_rating', 'delivery_rating', 'is_verified_purchase', 'is_featured', 'images', 'replies', 'helpful_count', 'not_helpful_count', 'helpfulness_percentage', 'has_images', 'created_at']

    def get_user_avatar(self, obj) -> str:
        if hasattr(obj.user, 'profile') and obj.user.profile.avatar:
            return obj.user.profile.avatar.url
        return ''


class ReviewListSerializer(serializers.ModelSerializer):
    user_display_name = serializers.ReadOnlyField()
    has_images = serializers.ReadOnlyField()
    images_count = serializers.SerializerMethodField()
    has_reply = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'user_display_name', 'rating', 'title', 'comment', 'is_verified_purchase', 'has_images', 'images_count', 'helpful_count', 'has_reply', 'created_at']

    def get_images_count(self, obj) -> int:
        return obj.images.count()

    def get_has_reply(self, obj) -> bool:
        return obj.replies.filter(is_official=True).exists()


class ReviewCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(child=serializers.ImageField(), max_length=5, required=False)

    class Meta:
        model = Review
        fields = ['product', 'order', 'rating', 'title', 'comment', 'quality_rating', 'value_rating', 'delivery_rating', 'images']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1-5')
        return value

    def validate(self, data):
        user = self.context['request'].user
        product = data.get('product')
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError('You have already reviewed this product')
        return data

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        review = Review.objects.create(**validated_data)
        for i, image in enumerate(images_data):
            ReviewImage.objects.create(review=review, image=image, sort_order=i)
        return review


class ReviewUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment', 'quality_rating', 'value_rating', 'delivery_rating']


class ReviewVoteSerializer(serializers.Serializer):
    is_helpful = serializers.BooleanField()


class ReviewReportSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ReviewReport
        fields = ['id', 'review', 'reason', 'reason_display', 'details', 'status', 'status_display', 'created_at']


class ReviewReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewReport
        fields = ['review', 'reason', 'details']


class ReviewSummarySerializer(serializers.ModelSerializer):
    rating_distribution = serializers.ReadOnlyField()

    class Meta:
        model = ReviewSummary
        fields = ['total_reviews', 'average_rating', 'rating_5', 'rating_4', 'rating_3', 'rating_2', 'rating_1', 'rating_distribution', 'avg_quality', 'avg_value', 'avg_delivery', 'verified_count', 'with_images_count']


class ReviewAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email')
    product_name = serializers.CharField(source='product.name')
    images = ReviewImageSerializer(many=True, read_only=True)
    reports_count = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'user_email', 'product_name', 'rating', 'title', 'comment', 'is_verified_purchase', 'is_approved', 'is_rejected', 'rejection_reason', 'helpful_count', 'not_helpful_count', 'images', 'reports_count', 'created_at', 'moderated_at']

    def get_reports_count(self, obj) -> int:
        return obj.reports.filter(status='pending').count()


class ReviewModerationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)


class ReviewStatisticsSerializer(serializers.Serializer):
    total_reviews = serializers.IntegerField()
    pending_reviews = serializers.IntegerField()
    approved_reviews = serializers.IntegerField()
    rejected_reviews = serializers.IntegerField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    reviews_today = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
