"""Commerce Cart - API Views."""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Cart
from .serializers import (
    CartSerializer, CartSummarySerializer, CartItemSerializer, SavedForLaterSerializer,
    AddItemSerializer, UpdateItemSerializer, ApplyCouponSerializer,
    CouponResultSerializer, ValidationResultSerializer, CartStatisticsSerializer
)
from .services import CartService, CartStatisticsService


def get_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


class CartView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: CartSerializer}, tags=['Cart'])
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        try:
            cart = CartService.get_or_create_cart(user, session_key)
            return Response(CartSerializer(cart).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)

    @extend_schema(tags=['Cart'])
    def delete(self, request):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        count = CartService.clear_cart(user, session_key)
        return Response({'cleared': count})


class CartSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: CartSummarySerializer}, tags=['Cart'])
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        try:
            cart = CartService.get_or_create_cart(user, session_key)
            return Response(CartSummarySerializer(cart).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class AddItemView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=AddItemSerializer, responses={201: CartItemSerializer}, tags=['Cart'])
    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        try:
            item = CartService.add_item(user, data['product_id'], data['quantity'], session_key)
            return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class UpdateItemView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=UpdateItemSerializer, responses={200: CartItemSerializer}, tags=['Cart'])
    def put(self, request, item_id):
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        item = CartService.update_item(user, item_id, data['quantity'], session_key)
        if item:
            return Response(CartItemSerializer(item).data)
        return Response({'removed': True})

    @extend_schema(tags=['Cart'])
    def delete(self, request, item_id):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        result = CartService.remove_item(user, item_id, session_key)
        return Response({'removed': result})


class SaveForLaterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: SavedForLaterSerializer}, tags=['Cart'])
    def post(self, request, item_id):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        saved = CartService.save_for_later(user, item_id, session_key)
        if saved:
            return Response(SavedForLaterSerializer(saved).data)
        return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


class MoveToCartView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: CartItemSerializer}, tags=['Cart'])
    def post(self, request, saved_id):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        item = CartService.move_to_cart(user, saved_id, session_key)
        if item:
            return Response(CartItemSerializer(item).data)
        return Response({'error': 'Saved item not found'}, status=status.HTTP_404_NOT_FOUND)


class RemoveSavedView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Cart'])
    def delete(self, request, saved_id):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        result = CartService.remove_saved(user, saved_id, session_key)
        return Response({'removed': result})


class ApplyCouponView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=ApplyCouponSerializer, responses={200: CouponResultSerializer}, tags=['Cart'])
    def post(self, request):
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        result = CartService.apply_coupon(user, data['coupon_code'], session_key)
        return Response(result)

    @extend_schema(tags=['Cart'])
    def delete(self, request):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        CartService.remove_coupon(user, session_key)
        return Response({'removed': True})


class ValidateCartView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: ValidationResultSerializer}, tags=['Cart'])
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        session_key = get_session_key(request)
        result = CartService.validate_cart(user, session_key)
        return Response(result)


class AdminStatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('days', int)], responses={200: CartStatisticsSerializer}, tags=['Cart - Admin'])
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        stats = CartStatisticsService.get_statistics(days)
        return Response(stats)
