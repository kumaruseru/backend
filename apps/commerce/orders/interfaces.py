"""
Inventory Gateway Interface.
Defines the contract for inventory operations required by Commerce context.
"""
from abc import ABC, abstractmethod
from uuid import UUID

class InventoryGateway(ABC):
    @abstractmethod
    def check_availability(self, product_id: UUID, quantity: int) -> bool:
        """Check if stock is available."""
        pass

    @abstractmethod
    def reserve_stock(self, product_id: UUID, quantity: int, reference: str, user=None) -> None:
        """Reserve stock for an order."""
        pass
