"""Store Wishlist - API Views."""
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Wishlist, WishlistItem
from .serializers import (
    WishlistSerializer, WishlistListSerializer, WishlistItemSerializer,
    WishlistCreateSerializer, WishlistUpdateSerializer,
    WishlistItemAddSerializer, WishlistItemUpdateSerializer,
    BulkAddSerializer, BulkRemoveSerializer, ToggleSerializer
)
from .services import WishlistService


class WishlistListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistListSerializer

    def get_queryset(self):
        return WishlistService.get_user_wishlists(self.request.user)

    @extend_schema(tags=['Wishlist'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class WishlistDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: WishlistSerializer}, tags=['Wishlist'])
    def get(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            return Response(WishlistSerializer(wishlist).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=WishlistCreateSerializer, responses={201: WishlistSerializer}, tags=['Wishlist'])
    def post(self, request):
        serializer = WishlistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        wishlist = WishlistService.create_wishlist(user=request.user, name=data['name'], description=data.get('description', ''), is_public=data.get('is_public', False))
        return Response(WishlistSerializer(wishlist).data, status=status.HTTP_201_CREATED)


class WishlistUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=WishlistUpdateSerializer, responses={200: WishlistSerializer}, tags=['Wishlist'])
    def patch(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            serializer = WishlistUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            updated = WishlistService.update_wishlist(wishlist, **serializer.validated_data)
            return Response(WishlistSerializer(updated).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)

    @extend_schema(responses={204: None}, tags=['Wishlist'])
    def delete(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            WishlistService.delete_wishlist(wishlist)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistShareView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Wishlist'])
    def post(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            token = wishlist.generate_share_token()
            return Response({'share_token': token, 'share_url': wishlist.share_url})
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)

    @extend_schema(tags=['Wishlist'])
    def delete(self, request, wishlist_id):
        try:
            wishlist = WishlistService.get_wishlist(wishlist_id, request.user)
            wishlist.revoke_share()
            return Response({'message': 'Share revoked'})
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class SharedWishlistView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: WishlistSerializer}, tags=['Wishlist'])
    def get(self, request, share_token):
        try:
            wishlist = WishlistService.get_shared_wishlist(share_token)
            return Response(WishlistSerializer(wishlist).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistItemAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=WishlistItemAddSerializer, responses={201: WishlistItemSerializer}, tags=['Wishlist'])
    def post(self, request):
        serializer = WishlistItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = WishlistService.add_item(user=request.user, product_id=data['product_id'], wishlist_id=data.get('wishlist_id'), note=data.get('note', ''), priority=data.get('priority', 'medium'), notify_on_sale=data.get('notify_on_sale', True), target_price=data.get('target_price'))
            return Response(WishlistItemSerializer(item).data, status=status.HTTP_201_CREATED)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class WishlistItemUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=WishlistItemUpdateSerializer, responses={200: WishlistItemSerializer}, tags=['Wishlist'])
    def patch(self, request, item_id):
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=request.user)
            serializer = WishlistItemUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            updated = WishlistService.update_item(item, **serializer.validated_data)
            return Response(WishlistItemSerializer(updated).data)
        except WishlistItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(responses={204: None}, tags=['Wishlist'])
    def delete(self, request, item_id):
        deleted = WishlistService.remove_item(item_id, request.user)
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


class ToggleWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ToggleSerializer, tags=['Wishlist'])
    def post(self, request):
        serializer = ToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']
        if WishlistService.is_in_wishlist(request.user, product_id):
            WishlistService.remove_product_from_all(request.user, product_id)
            return Response({'in_wishlist': False})
        else:
            WishlistService.add_item(request.user, product_id)
            return Response({'in_wishlist': True})


class CheckWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(parameters=[OpenApiParameter('product_id', str)], tags=['Wishlist'])
    def get(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': 'product_id required'}, status=status.HTTP_400_BAD_REQUEST)
        in_wishlist = WishlistService.is_in_wishlist(request.user, product_id)
        return Response({'in_wishlist': in_wishlist})


class BulkAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=BulkAddSerializer, tags=['Wishlist'])
    def post(self, request):
        serializer = BulkAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count = WishlistService.bulk_add(request.user, data['product_ids'], data.get('wishlist_id'))
        return Response({'added': count})


class BulkRemoveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=BulkRemoveSerializer, tags=['Wishlist'])
    def post(self, request):
        serializer = BulkRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count = WishlistService.bulk_remove(request.user, data['item_ids'])
        return Response({'removed': count})
