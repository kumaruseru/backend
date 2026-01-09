"""Store Inventory - URL Configuration."""
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Warehouses
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse_list'),
    path('warehouses/<int:pk>/', views.WarehouseDetailView.as_view(), name='warehouse_detail'),

    # Stock
    path('stock/', views.StockListView.as_view(), name='stock_list'),
    path('stock/low/', views.LowStockView.as_view(), name='low_stock'),
    path('stock/out/', views.OutOfStockView.as_view(), name='out_of_stock'),
    path('stock/reorder/', views.ReorderView.as_view(), name='reorder'),
    path('stock/<uuid:product_id>/', views.StockDetailView.as_view(), name='stock_detail'),
    path('stock/<uuid:product_id>/add/', views.StockAddView.as_view(), name='stock_add'),
    path('stock/<uuid:product_id>/adjust/', views.StockAdjustView.as_view(), name='stock_adjust'),
    path('stock/transfer/', views.StockTransferView.as_view(), name='stock_transfer'),

    # Movements
    path('movements/', views.MovementListView.as_view(), name='movement_list'),
    path('movements/product/<uuid:product_id>/', views.ProductMovementView.as_view(), name='product_movements'),

    # Alerts
    path('alerts/', views.AlertListView.as_view(), name='alert_list'),
    path('alerts/<int:alert_id>/resolve/', views.AlertResolveView.as_view(), name='alert_resolve'),

    # Inventory Counts
    path('counts/', views.InventoryCountListView.as_view(), name='count_list'),
    path('counts/create/', views.InventoryCountCreateView.as_view(), name='count_create'),
    path('counts/<uuid:count_id>/', views.InventoryCountDetailView.as_view(), name='count_detail'),
    path('counts/<uuid:count_id>/start/', views.InventoryCountStartView.as_view(), name='count_start'),
    path('counts/<uuid:count_id>/complete/', views.InventoryCountCompleteView.as_view(), name='count_complete'),
    path('counts/items/<int:item_id>/update/', views.InventoryCountItemUpdateView.as_view(), name='count_item_update'),

    # Statistics
    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('statistics/movements/', views.MovementSummaryView.as_view(), name='movement_summary'),
]
