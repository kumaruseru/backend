"""Commerce Orders - Signals."""
import django.dispatch

order_created = django.dispatch.Signal()
order_confirmed = django.dispatch.Signal()
order_cancelled = django.dispatch.Signal()
order_shipped = django.dispatch.Signal()
order_delivered = django.dispatch.Signal()
order_completed = django.dispatch.Signal()
