"""
Commerce Cart - Production-Ready API Views.

Comprehensive endpoints with:
- Cart CRUD
- Saved for later
- Coupon preview
- Stock validation
- Guest cart support
"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.common.core.exceptions import DomainException
from .models import Cart
from .serializers import (
    CartSerializer, CartSummarySerializer, CartItemSerializer,
    SavedForLaterSerializer,
    AddToCartSerializer, UpdateCartItemSerializer,
    ApplyCouponSerializer, BulkAddSerializer,
    CartValidationSerializer, RefreshPricesResponseSerializer
)
from .services import CartService


class AllowAnyOrAuthenticated(permissions.BasePermission):
    """Allow both authenticated and guest users."""
    def has_permission(self, request, view):
        return True


def get_session_key(request) -> str:
    """Get or create session key for guest carts."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


# ==================== CART ENDPOINTS ====================

class CartView(APIView):
    """Get current cart."""
    permission_classes = [AllowAnyOrAuthenticated]
    
    @extend_schema(
        responses={200: CartSerializer},
        tags=['Cart']
    )
    def get(self, request):
        """Get current user's or guest's cart."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            return Response(CartSerializer(cart).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        responses={200: {'type': 'object', 'properties': {'cleared': {'type': 'integer'}}}},
        tags=['Cart']
    )
    def delete(self, request):
        """Clear cart."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            count = CartService.clear_cart(cart)
            
            return Response({'cleared': count})
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class CartSummaryView(APIView):
    """Get cart summary (for header badge)."""
    permission_classes = [AllowAnyOrAuthenticated]
    
    @extend_schema(
        responses={200: CartSummarySerializer},
        tags=['Cart']
    )
    def get(self, request):
        """Get minimal cart info."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            return Response(CartSummarySerializer(cart).data)
        except DomainException as e:
            return Response({'total_items': 0, 'subtotal': 0})


class CartAddView(APIView):
    """Add item to cart."""
    permission_classes = [AllowAnyOrAuthenticated]
    throttle_scope = 'cart_modify'
    
    @extend_schema(
        request=AddToCartSerializer,
        responses={201: CartItemSerializer},
        tags=['Cart']
    )
    def post(self, request):
        """Add product to cart."""
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            item = CartService.add_item(
                cart,
                data['product_id'],
                data.get('quantity', 1),
                data.get('attributes')
            )
            
            return Response(
                CartItemSerializer(item).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class CartBulkAddView(APIView):
    """Add multiple items at once."""
    permission_classes = [AllowAnyOrAuthenticated]
    throttle_scope = 'cart_modify'
    
    @extend_schema(
        request=BulkAddSerializer,
        responses={201: CartSerializer},
        tags=['Cart']
    )
    def post(self, request):
        """Add multiple products to cart."""
        serializer = BulkAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            
            for item_data in serializer.validated_data['items']:
                CartService.add_item(
                    cart,
                    item_data['product_id'],
                    item_data.get('quantity', 1)
                )
            
            # Refresh cart
            cart.refresh_from_db()
            
            return Response(
                CartSerializer(cart).data,
                status=status.HTTP_201_CREATED
            )
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class CartItemView(APIView):
    """Update or remove cart item."""
    permission_classes = [AllowAnyOrAuthenticated]
    throttle_scope = 'cart_modify'
    
    @extend_schema(
        request=UpdateCartItemSerializer,
        responses={200: CartItemSerializer},
        tags=['Cart']
    )
    def patch(self, request, item_id):
        """Update item quantity."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            item = cart.items.filter(id=item_id).first()
            
            serializer = UpdateCartItemSerializer(
                data=request.data,
                context={'item': item}
            )
            serializer.is_valid(raise_exception=True)
            
            result = CartService.update_item(
                cart, item_id, serializer.validated_data['quantity']
            )
            
            if result:
                return Response(CartItemSerializer(result).data)
            else:
                return Response({'deleted': True})
                
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        responses={204: None},
        tags=['Cart']
    )
    def delete(self, request, item_id):
        """Remove item from cart."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            CartService.remove_item(cart, item_id)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== SAVED FOR LATER ====================

class SaveForLaterView(APIView):
    """Move item to saved for later."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: SavedForLaterSerializer},
        tags=['Cart - Saved']
    )
    def post(self, request, item_id):
        """Save item for later."""
        try:
            cart = CartService.get_cart(request.user)
            saved = CartService.save_for_later(cart, item_id)
            
            return Response(SavedForLaterSerializer(saved).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class MoveToCartView(APIView):
    """Move saved item back to cart."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: CartItemSerializer},
        tags=['Cart - Saved']
    )
    def post(self, request, saved_id):
        """Move saved item to cart."""
        try:
            cart = CartService.get_cart(request.user)
            item = CartService.move_to_cart(cart, saved_id)
            
            return Response(CartItemSerializer(item).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class RemoveSavedView(APIView):
    """Remove saved item."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={204: None},
        tags=['Cart - Saved']
    )
    def delete(self, request, saved_id):
        """Remove saved item."""
        try:
            cart = CartService.get_cart(request.user)
            CartService.remove_saved(cart, saved_id)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== COUPON ====================

class CartCouponView(APIView):
    """Apply or remove coupon."""
    permission_classes = [AllowAnyOrAuthenticated]
    
    @extend_schema(
        request=ApplyCouponSerializer,
        responses={200: {'type': 'object'}},
        tags=['Cart']
    )
    def post(self, request):
        """Apply coupon to cart."""
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            result = CartService.apply_coupon(
                cart,
                serializer.validated_data['coupon_code']
            )
            
            if result['success']:
                return Response(result)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        responses={204: None},
        tags=['Cart']
    )
    def delete(self, request):
        """Remove coupon from cart."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            CartService.remove_coupon(cart)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== VALIDATION ====================

class CartValidateView(APIView):
    """Validate cart for checkout."""
    permission_classes = [AllowAnyOrAuthenticated]
    
    @extend_schema(
        responses={200: CartValidationSerializer},
        tags=['Cart']
    )
    def get(self, request):
        """Validate cart stock and availability."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            result = CartService.validate_cart(cart)
            
            return Response(result)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


class CartRefreshPricesView(APIView):
    """Refresh cart item prices."""
    permission_classes = [AllowAnyOrAuthenticated]
    
    @extend_schema(
        responses={200: RefreshPricesResponseSerializer},
        tags=['Cart']
    )
    def post(self, request):
        """Update all prices to current."""
        try:
            user = request.user if request.user.is_authenticated else None
            session_key = get_session_key(request) if not user else None
            
            cart = CartService.get_or_create_cart(user, session_key)
            result = CartService.refresh_prices(cart)
            
            return Response(result)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)


# ==================== MERGE ====================

class CartMergeView(APIView):
    """Merge guest cart on login."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request={'type': 'object', 'properties': {'session_key': {'type': 'string'}}},
        responses={200: CartSerializer},
        tags=['Cart']
    )
    def post(self, request):
        """Merge guest cart into user cart."""
        session_key = request.data.get('session_key')
        
        if not session_key:
            session_key = get_session_key(request)
        
        cart = CartService.merge_guest_cart(request.user, session_key)
        
        if cart:
            return Response(CartSerializer(cart).data)
        else:
            # Return user's cart
            cart = CartService.get_or_create_cart(request.user)
            return Response(CartSerializer(cart).data)
