"""
Store Wishlist - Production-Ready API Views.
"""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Wishlist, WishlistItem
from .serializers import (
    WishlistSerializer, WishlistSimpleSerializer, WishlistCreateSerializer,
    WishlistItemSerializer, WishlistItemListSerializer,
    WishlistItemAddSerializer, WishlistItemUpdateSerializer, WishlistItemMoveSerializer,
    SharedWishlistSerializer,
    BulkAddSerializer, BulkRemoveSerializer, MoveToCartSerializer
)
from .services import WishlistService


# ==================== Wishlist Endpoints ====================

class WishlistListView(generics.ListAPIView):
    """List user's wishlists."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistSimpleSerializer
    pagination_class = None
    
    def get_queryset(self):
        return WishlistService.get_user_wishlists(self.request.user)
    
    @extend_schema(
        responses={200: WishlistSimpleSerializer(many=True)},
        tags=['Wishlist']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class WishlistCreateView(APIView):
    """Create a new wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=WishlistCreateSerializer,
        responses={201: WishlistSerializer},
        tags=['Wishlist']
    )
    def post(self, request):
        serializer = WishlistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        wishlist = WishlistService.create_wishlist(
            user=request.user,
            **serializer.validated_data
        )
        
        return Response(
            WishlistSerializer(wishlist).data,
            status=status.HTTP_201_CREATED
        )


class WishlistDetailView(APIView):
    """Get/Update/Delete wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: WishlistSerializer},
        tags=['Wishlist']
    )
    def get(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            return Response(WishlistSerializer(wishlist).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)
    
    @extend_schema(
        request=WishlistCreateSerializer,
        responses={200: WishlistSerializer},
        tags=['Wishlist']
    )
    def patch(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            updated = WishlistService.update_wishlist(wishlist, **request.data)
            return Response(WishlistSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)
    
    @extend_schema(
        responses={204: None},
        tags=['Wishlist']
    )
    def delete(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            WishlistService.delete_wishlist(wishlist)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistItemsView(APIView):
    """Get items in a wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        responses={200: WishlistItemSerializer(many=True)},
        tags=['Wishlist']
    )
    def get(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            items = WishlistService.get_wishlist_items(wishlist)
            return Response(WishlistItemSerializer(items, many=True).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistShareView(APIView):
    """Generate/revoke share link."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Wishlist'])
    def post(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            token = wishlist.generate_share_token()
            return Response({
                'share_token': token,
                'share_url': wishlist.share_url
            })
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)
    
    @extend_schema(tags=['Wishlist'])
    def delete(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            wishlist.revoke_share()
            return Response({'success': True})
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class SharedWishlistView(APIView):
    """View shared wishlist."""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        responses={200: SharedWishlistSerializer},
        tags=['Wishlist']
    )
    def get(self, request, share_token):
        try:
            wishlist = WishlistService.get_shared_wishlist(share_token)
            return Response(SharedWishlistSerializer(wishlist).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


# ==================== Item Endpoints ====================

class AddItemView(APIView):
    """Add item to wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=WishlistItemAddSerializer,
        responses={201: WishlistItemSerializer},
        tags=['Wishlist - Items']
    )
    def post(self, request):
        serializer = WishlistItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        item = WishlistService.add_item(
            user=request.user,
            **serializer.validated_data
        )
        
        return Response(
            WishlistItemSerializer(item).data,
            status=status.HTTP_201_CREATED
        )


class ItemDetailView(APIView):
    """Update/Remove wishlist item."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=WishlistItemUpdateSerializer,
        responses={200: WishlistItemSerializer},
        tags=['Wishlist - Items']
    )
    def patch(self, request, item_id):
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=request.user)
            serializer = WishlistItemUpdateSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated = WishlistService.update_item(item, **serializer.validated_data)
            return Response(WishlistItemSerializer(updated).data)
        except WishlistItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        responses={204: None},
        tags=['Wishlist - Items']
    )
    def delete(self, request, item_id):
        removed = WishlistService.remove_item(item_id, request.user)
        if removed:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


class MoveItemView(APIView):
    """Move item to another wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=WishlistItemMoveSerializer,
        responses={200: WishlistItemSerializer},
        tags=['Wishlist - Items']
    )
    def post(self, request, item_id):
        serializer = WishlistItemMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=request.user)
            target = WishlistService.get_wishlist(
                serializer.validated_data['target_wishlist_id'],
                request.user
            )
            
            moved = WishlistService.move_item(item, target)
            return Response(WishlistItemSerializer(moved).data)
        except WishlistItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


# ==================== Quick Actions ====================

class ToggleWishlistView(APIView):
    """Toggle product in default wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Wishlist - Items'])
    def post(self, request, product_id):
        is_in_wishlist = WishlistService.is_in_wishlist(request.user, product_id)
        
        if is_in_wishlist:
            # FIX: Use Service instead of direct ORM delete
            # This ensures consistent behavior (logging, signals, counters)
            WishlistService.remove_product_from_all(request.user, product_id)
            return Response({'in_wishlist': False})
        else:
            # Add to default
            WishlistService.add_item(request.user, product_id)
            return Response({'in_wishlist': True})


class CheckWishlistView(APIView):
    """Check if product is in wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(tags=['Wishlist - Items'])
    def get(self, request, product_id):
        is_in_wishlist = WishlistService.is_in_wishlist(request.user, product_id)
        wishlists = WishlistService.get_wishlists_containing(request.user, product_id)
        
        return Response({
            'in_wishlist': is_in_wishlist,
            'wishlists': WishlistSimpleSerializer(wishlists, many=True).data
        })


# ==================== Bulk Operations ====================

class BulkAddView(APIView):
    """Bulk add products to wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=BulkAddSerializer,
        tags=['Wishlist - Bulk']
    )
    def post(self, request):
        serializer = BulkAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        count = WishlistService.bulk_add(
            user=request.user,
            product_ids=serializer.validated_data['product_ids'],
            wishlist_id=serializer.validated_data.get('wishlist_id')
        )
        
        return Response({'added': count})


class BulkRemoveView(APIView):
    """Bulk remove items."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=BulkRemoveSerializer,
        tags=['Wishlist - Bulk']
    )
    def post(self, request):
        serializer = BulkRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        count = WishlistService.bulk_remove(
            user=request.user,
            item_ids=serializer.validated_data['item_ids']
        )
        
        return Response({'removed': count})


class MoveToCartView(APIView):
    """Move wishlist items to cart."""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=MoveToCartSerializer,
        tags=['Wishlist - Bulk']
    )
    def post(self, request):
        serializer = MoveToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        count = WishlistService.move_to_cart(
            user=request.user,
            item_ids=serializer.validated_data.get('item_ids'),
            all_items=serializer.validated_data.get('all_items', False)
        )
        
        return Response({'moved_to_cart': count})
