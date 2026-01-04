"""
Local implementation of InventoryGateway.
Directly calls the Inventory Service (Monolith style).
"""
from uuid import UUID
from apps.commerce.orders.interfaces import InventoryGateway
from apps.store.inventory.services import InventoryService

class LocalInventoryGateway(InventoryGateway):
    def check_availability(self, product_id: UUID, quantity: int) -> bool:
        return InventoryService.check_stock_availability(product_id, quantity)

    def reserve_stock(self, product_id: UUID, quantity: int, reference: str, user=None) -> None:
        InventoryService.reserve_stock(
            product_id=product_id,
            quantity=quantity,
            reference=reference,
            user=user
        )
