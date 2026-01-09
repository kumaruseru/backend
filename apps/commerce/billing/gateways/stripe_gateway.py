"""Stripe Payment Gateway - Modernized with StripeClient.

Full integration with Stripe using the modern StripeClient pattern (v8+).
Features:
- StripeClient for all API calls
- Automatic retries with max_network_retries
- Async support with _async methods
- Webhook signature verification with proper error handling
- Checkout Sessions, PaymentIntents, Customers
- VND to USD currency conversion
- Full and partial refunds
- Subscription support
- Dispute handling
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List

from stripe import StripeClient
from stripe import Webhook, SignatureVerificationError
import stripe

from django.conf import settings

from .base import BasePaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing.stripe')


class StripeGateway(BasePaymentGateway):
    """Modern Stripe payment gateway using StripeClient pattern.
    
    Implements best practices from Stripe SDK v8+:
    - StripeClient for thread-safe, testable API calls
    - Automatic retries with configurable max_network_retries
    - Idempotency keys for safe retries
    - Proper webhook signature verification
    - Async support for high-throughput applications
    
    Note: VND amounts are converted to USD using configured exchange rate.
    """
    
    gateway_code = 'stripe'
    gateway_name = 'Stripe'
    supports_refund = True
    supports_webhook = True
    
    # Currency settings
    SUPPORTED_CURRENCY = 'usd'
    VND_TO_USD_RATE = Decimal('25000')
    USD_MIN_AMOUNT = 50  # Stripe minimum is $0.50 (50 cents)
    
    def __init__(self):
        self.secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.publishable_key = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '')
        self.webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        
        # Initialize StripeClient with best practices
        self._client: Optional[StripeClient] = None
        if self.secret_key:
            self._client = StripeClient(
                api_key=self.secret_key,
                max_network_retries=3,  # Automatic retry on transient failures
            )
            # Set app info for Stripe dashboard identification
            stripe.set_app_info(
                name="OWLS E-Commerce",
                version="1.0.0",
                url="https://owls.store"
            )
    
    @property
    def client(self) -> StripeClient:
        """Get StripeClient, raising error if not configured."""
        if not self._client:
            raise ValueError("Stripe is not configured. Check STRIPE_SECRET_KEY.")
        return self._client
    
    def _convert_vnd_to_usd(self, amount_vnd: Decimal) -> int:
        """Convert VND to USD cents.
        
        Stripe uses smallest currency unit (cents for USD).
        """
        rate = Decimal(getattr(settings, 'VND_TO_USD_RATE', self.VND_TO_USD_RATE))
        usd_amount = amount_vnd / rate
        cents = int(round(usd_amount, 2) * 100)
        return max(cents, self.USD_MIN_AMOUNT)
    
    def _usd_to_cents(self, usd: Decimal) -> int:
        """Convert USD to cents."""
        return int(round(usd, 2) * 100)
    
    def _get_or_create_customer(self, user, email: str = None) -> Optional[str]:
        """Get or create Stripe customer ID for user.
        
        Returns customer ID string, not the full object (more efficient).
        """
        try:
            if not user:
                return None
            
            # Check if user already has a Stripe customer ID
            customer_id = getattr(user, 'stripe_customer_id', None)
            
            if customer_id:
                try:
                    # Verify customer still exists
                    self.client.v1.customers.retrieve(customer_id)
                    return customer_id
                except stripe.error.InvalidRequestError:
                    pass  # Customer deleted, create new
            
            # Search for existing customer by email
            email = email or getattr(user, 'email', None)
            if email:
                customers = self.client.v1.customers.list(email=email, limit=1)
                if customers.data:
                    return customers.data[0].id
            
            # Create new customer
            customer = self.client.v1.customers.create(
                email=email,
                name=getattr(user, 'full_name', None) or getattr(user, 'get_full_name', lambda: None)(),
                metadata={
                    'user_id': str(getattr(user, 'id', '')),
                    'source': 'owls_ecommerce',
                }
            )
            
            # Store customer ID on user if possible
            if hasattr(user, 'stripe_customer_id'):
                user.stripe_customer_id = customer.id
                user.save(update_fields=['stripe_customer_id'])
            
            return customer.id
            
        except Exception as e:
            logger.warning(f"Failed to get/create Stripe customer: {e}")
            return None
    
    def create_payment(
        self,
        order,
        amount: Decimal,
        currency: str = 'VND',
        return_url: str = '',
        cancel_url: str = '',
        **kwargs
    ) -> PaymentResult:
        """Create Stripe Checkout Session.
        
        Converts VND to USD automatically. Creates hosted checkout page
        with all Stripe payment methods enabled.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            amount_cents = self._convert_vnd_to_usd(amount)
            usd_amount = Decimal(amount_cents) / 100
            
            customer_id = self._get_or_create_customer(order.user, order.email)
            
            # Build line items from order
            line_items = self._build_line_items(order)
            
            # Idempotency key for safe retries
            idempotency_key = f"checkout_{order.order_number}_{order.id}"
            
            # Checkout session parameters
            session_params = {
                'payment_method_types': ['card'],
                'mode': 'payment',
                'line_items': line_items,
                'success_url': f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
                'cancel_url': cancel_url or f"{return_url}?status=cancelled",
                'metadata': {
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'original_amount_vnd': str(amount),
                    'converted_amount_usd': str(usd_amount),
                    'exchange_rate': str(self.VND_TO_USD_RATE),
                },
                'payment_intent_data': {
                    'description': f'Order {order.order_number}',
                    'metadata': {
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                    },
                },
                'billing_address_collection': 'auto',
                'phone_number_collection': {'enabled': True},
                'expires_at': int((timezone.now() + timedelta(hours=24)).timestamp()),
                'locale': 'auto',
            }
            
            if customer_id:
                session_params['customer'] = customer_id
            else:
                session_params['customer_email'] = order.email or (order.user.email if order.user else None)
            
            if order.items.exists():
                session_params['shipping_address_collection'] = {
                    'allowed_countries': ['VN', 'US', 'SG', 'JP', 'KR', 'AU', 'GB', 'DE', 'FR']
                }
            
            # Create checkout session using StripeClient
            session = self.client.v1.checkout.sessions.create(
                params=session_params,
                options={'idempotency_key': idempotency_key}
            )
            
            logger.info(f"Stripe checkout created: {session.id} for order {order.order_number}")
            
            return PaymentResult(
                success=True,
                transaction_id=session.id,
                gateway_transaction_id=session.id,
                payment_url=session.url,
                raw_response={
                    'session_id': session.id,
                    'url': session.url,
                    'amount_usd': str(usd_amount),
                    'currency': self.SUPPORTED_CURRENCY,
                    'customer_id': customer_id,
                    'expires_at': session.expires_at,
                }
            )
            
        except stripe.error.CardError as e:
            logger.warning(f"Stripe card error: {e}")
            return PaymentResult(
                success=False,
                error_code=e.code or 'card_error',
                error_message=e.user_message or str(e),
                raw_response={'error': str(e)}
            )
        except stripe.error.RateLimitError as e:
            logger.error(f"Stripe rate limit: {e}")
            return PaymentResult(
                success=False,
                error_code='rate_limit',
                error_message='Too many requests. Please try again.',
                raw_response={'error': str(e)}
            )
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Stripe invalid request: {e}")
            return PaymentResult(
                success=False,
                error_code='invalid_request',
                error_message=str(e),
                raw_response={'error': str(e)}
            )
        except stripe.error.AuthenticationError as e:
            logger.critical(f"Stripe authentication error: {e}")
            return PaymentResult(
                success=False,
                error_code='authentication_error',
                error_message='Payment service configuration error.',
                raw_response={'error': str(e)}
            )
        except stripe.error.StripeError as e:
            logger.exception(f"Stripe error: {e}")
            return PaymentResult(
                success=False,
                error_code='stripe_error',
                error_message='Payment processing failed.',
                raw_response={'error': str(e)}
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return PaymentResult(
                success=False,
                error_code='unexpected_error',
                error_message='An unexpected error occurred.',
                raw_response={'error': str(e)}
            )
    
    def _build_line_items(self, order) -> List[Dict]:
        """Build line items from order for Checkout Session."""
        line_items = []
        
        for item in order.items.all():
            item_cents = self._convert_vnd_to_usd(item.unit_price)
            line_item = {
                'price_data': {
                    'currency': self.SUPPORTED_CURRENCY,
                    'product_data': {
                        'name': item.product_name[:100],  # Stripe limit
                        'metadata': {
                            'product_id': str(item.product_id) if item.product_id else '',
                            'original_price_vnd': str(item.unit_price),
                        }
                    },
                    'unit_amount': item_cents,
                },
                'quantity': item.quantity,
            }
            if item.product_sku:
                line_item['price_data']['product_data']['description'] = f'SKU: {item.product_sku}'
            line_items.append(line_item)
        
        # Add shipping fee
        if order.shipping_fee > 0:
            shipping_cents = self._convert_vnd_to_usd(order.shipping_fee)
            line_items.append({
                'price_data': {
                    'currency': self.SUPPORTED_CURRENCY,
                    'product_data': {'name': 'Shipping & Handling'},
                    'unit_amount': shipping_cents,
                },
                'quantity': 1,
            })
        
        # Add tax
        if order.tax > 0:
            tax_cents = self._convert_vnd_to_usd(order.tax)
            line_items.append({
                'price_data': {
                    'currency': self.SUPPORTED_CURRENCY,
                    'product_data': {'name': 'Tax'},
                    'unit_amount': tax_cents,
                },
                'quantity': 1,
            })
        
        return line_items
    
    def create_payment_intent(
        self,
        order,
        amount: Decimal,
        **kwargs
    ) -> PaymentResult:
        """Create PaymentIntent for custom payment flows.
        
        Use this for embedded payment forms or mobile apps.
        """
        try:
            amount_cents = self._convert_vnd_to_usd(amount)
            customer_id = self._get_or_create_customer(order.user, order.email)
            
            intent_params = {
                'amount': amount_cents,
                'currency': self.SUPPORTED_CURRENCY,
                'description': f'Order {order.order_number}',
                'metadata': {
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'original_amount_vnd': str(amount),
                },
                'automatic_payment_methods': {'enabled': True},
            }
            
            if customer_id:
                intent_params['customer'] = customer_id
            
            intent = self.client.v1.payment_intents.create(params=intent_params)
            
            return PaymentResult(
                success=True,
                transaction_id=intent.id,
                gateway_transaction_id=intent.id,
                raw_response={
                    'payment_intent_id': intent.id,
                    'client_secret': intent.client_secret,
                    'amount_usd': amount_cents / 100,
                    'status': intent.status,
                }
            )
            
        except stripe.error.StripeError as e:
            logger.exception(f"PaymentIntent creation error: {e}")
            return PaymentResult(
                success=False,
                error_code='stripe_error',
                error_message=str(e)
            )
    
    def verify_payment(
        self,
        transaction_id: str,
        gateway_data: Dict[str, Any]
    ) -> PaymentResult:
        """Verify payment from Stripe return URL."""
        try:
            session_id = gateway_data.get('session_id') or transaction_id
            
            session = self.client.v1.checkout.sessions.retrieve(
                session_id,
                params={'expand': ['payment_intent', 'customer']}
            )
            
            if session.payment_status == 'paid':
                payment_intent = session.payment_intent
                
                return PaymentResult(
                    success=True,
                    transaction_id=transaction_id,
                    gateway_transaction_id=payment_intent.id if hasattr(payment_intent, 'id') else str(payment_intent),
                    raw_response={
                        'session_id': session.id,
                        'payment_intent': payment_intent.id if hasattr(payment_intent, 'id') else str(payment_intent),
                        'payment_status': session.payment_status,
                        'amount_total': session.amount_total,
                        'currency': session.currency,
                        'customer_email': session.customer_details.email if session.customer_details else None,
                    }
                )
            else:
                return PaymentResult(
                    success=False,
                    transaction_id=transaction_id,
                    error_code='payment_incomplete',
                    error_message=f'Payment status: {session.payment_status}',
                    raw_response={'session_id': session.id, 'status': session.payment_status}
                )
                
        except stripe.error.InvalidRequestError as e:
            logger.warning(f"Invalid session: {e}")
            return PaymentResult(
                success=False,
                error_code='invalid_session',
                error_message='Payment session not found or expired.',
                raw_response={'error': str(e)}
            )
        except stripe.error.StripeError as e:
            logger.exception(f"Stripe verification error: {e}")
            return PaymentResult(
                success=False,
                error_code='verification_error',
                error_message=str(e),
                raw_response=gateway_data
            )
    
    def process_webhook(
        self,
        payload: bytes,
        headers: Dict[str, str] = None
    ) -> PaymentResult:
        """Process Stripe webhook events with proper signature verification.
        
        Uses Webhook.construct_event for secure signature verification.
        Handles both v1 snapshot events and v2 event notifications.
        """
        try:
            sig_header = headers.get('Stripe-Signature', '') if headers else ''
            
            if not self.webhook_secret:
                logger.warning("Stripe webhook secret not configured")
                return PaymentResult(
                    success=False,
                    error_code='not_configured',
                    error_message='Webhook secret not configured'
                )
            
            # Verify webhook signature using Stripe's official method
            try:
                event = Webhook.construct_event(
                    payload=payload.decode('utf-8') if isinstance(payload, bytes) else payload,
                    sig_header=sig_header,
                    secret=self.webhook_secret
                )
            except ValueError as e:
                logger.warning(f"Invalid webhook payload: {e}")
                return PaymentResult(
                    success=False,
                    error_code='invalid_payload',
                    error_message='Invalid webhook payload'
                )
            except SignatureVerificationError as e:
                logger.warning(f"Webhook signature verification failed: {e}")
                return PaymentResult(
                    success=False,
                    error_code='invalid_signature',
                    error_message='Webhook signature verification failed'
                )
            
            event_type = event.type
            event_object = event.data.object
            
            logger.info(f"Processing Stripe webhook: {event_type} (id: {event.id})")
            
            # Handle different event types
            handlers = {
                'checkout.session.completed': self._handle_checkout_completed,
                'checkout.session.expired': self._handle_checkout_expired,
                'payment_intent.succeeded': self._handle_payment_succeeded,
                'payment_intent.payment_failed': self._handle_payment_failed,
                'payment_intent.canceled': self._handle_payment_canceled,
                'charge.refunded': self._handle_charge_refunded,
                'charge.dispute.created': self._handle_dispute_created,
                'charge.dispute.closed': self._handle_dispute_closed,
                'customer.subscription.created': self._handle_subscription_created,
                'customer.subscription.updated': self._handle_subscription_updated,
                'customer.subscription.deleted': self._handle_subscription_deleted,
            }
            
            handler = handlers.get(event_type)
            if handler:
                return handler(event_object, event)
            else:
                logger.info(f"Unhandled webhook event: {event_type}")
                return PaymentResult(
                    success=True,
                    error_code='unhandled_event',
                    error_message=f'Event type {event_type} not handled.'
                )
                
        except Exception as e:
            logger.exception(f"Webhook processing error: {e}")
            return PaymentResult(
                success=False,
                error_code='webhook_error',
                error_message=str(e)
            )
    
    def _handle_checkout_completed(self, session, event) -> PaymentResult:
        """Handle checkout.session.completed event."""
        if session.payment_status == 'paid':
            return PaymentResult(
                success=True,
                transaction_id=session.id,
                gateway_transaction_id=session.payment_intent,
                raw_response={
                    'event_id': event.id,
                    'session_id': session.id,
                    'payment_intent': session.payment_intent,
                    'customer': session.customer,
                    'metadata': dict(session.metadata) if session.metadata else {},
                }
            )
        return PaymentResult(
            success=False,
            transaction_id=session.id,
            error_code='unpaid',
            error_message='Checkout completed but not paid.'
        )
    
    def _handle_checkout_expired(self, session, event) -> PaymentResult:
        """Handle checkout.session.expired event."""
        return PaymentResult(
            success=False,
            transaction_id=session.id,
            error_code='session_expired',
            error_message='Checkout session expired.',
            raw_response={'event_id': event.id, 'session_id': session.id}
        )
    
    def _handle_payment_succeeded(self, payment_intent, event) -> PaymentResult:
        """Handle payment_intent.succeeded event."""
        return PaymentResult(
            success=True,
            transaction_id=payment_intent.id,
            gateway_transaction_id=payment_intent.id,
            raw_response={
                'event_id': event.id,
                'payment_intent': payment_intent.id,
                'amount': payment_intent.amount,
                'currency': payment_intent.currency,
                'metadata': dict(payment_intent.metadata) if payment_intent.metadata else {},
            }
        )
    
    def _handle_payment_failed(self, payment_intent, event) -> PaymentResult:
        """Handle payment_intent.payment_failed event."""
        last_error = payment_intent.last_payment_error
        return PaymentResult(
            success=False,
            transaction_id=payment_intent.id,
            error_code=last_error.code if last_error else 'payment_failed',
            error_message=last_error.message if last_error else 'Payment failed.',
            raw_response={
                'event_id': event.id,
                'payment_intent': payment_intent.id,
                'error': dict(last_error) if last_error else None,
            }
        )
    
    def _handle_payment_canceled(self, payment_intent, event) -> PaymentResult:
        """Handle payment_intent.canceled event."""
        return PaymentResult(
            success=False,
            transaction_id=payment_intent.id,
            error_code='payment_canceled',
            error_message='Payment was canceled.',
            raw_response={'event_id': event.id, 'payment_intent': payment_intent.id}
        )
    
    def _handle_charge_refunded(self, charge, event) -> PaymentResult:
        """Handle charge.refunded event."""
        return PaymentResult(
            success=True,
            transaction_id=charge.payment_intent,
            gateway_transaction_id=charge.id,
            raw_response={
                'event_id': event.id,
                'charge_id': charge.id,
                'amount_refunded': charge.amount_refunded,
                'refunded': charge.refunded,
            }
        )
    
    def _handle_dispute_created(self, dispute, event) -> PaymentResult:
        """Handle charge.dispute.created event (chargeback)."""
        logger.warning(f"Dispute/chargeback created: {dispute.id}")
        return PaymentResult(
            success=False,
            transaction_id=dispute.payment_intent,
            error_code='dispute_created',
            error_message=f'Dispute created: {dispute.reason}',
            raw_response={
                'event_id': event.id,
                'dispute_id': dispute.id,
                'reason': dispute.reason,
                'amount': dispute.amount,
                'status': dispute.status,
            }
        )
    
    def _handle_dispute_closed(self, dispute, event) -> PaymentResult:
        """Handle charge.dispute.closed event."""
        logger.info(f"Dispute closed: {dispute.id} - status: {dispute.status}")
        return PaymentResult(
            success=dispute.status == 'won',
            transaction_id=dispute.payment_intent,
            error_code=f'dispute_{dispute.status}',
            error_message=f'Dispute {dispute.status}',
            raw_response={
                'event_id': event.id,
                'dispute_id': dispute.id,
                'status': dispute.status,
            }
        )
    
    def _handle_subscription_created(self, subscription, event) -> PaymentResult:
        """Handle customer.subscription.created event."""
        logger.info(f"Subscription created: {subscription.id}")
        return PaymentResult(
            success=True,
            transaction_id=subscription.id,
            gateway_transaction_id=subscription.id,
            raw_response={
                'event_id': event.id,
                'subscription_id': subscription.id,
                'customer': subscription.customer,
                'status': subscription.status,
            }
        )
    
    def _handle_subscription_updated(self, subscription, event) -> PaymentResult:
        """Handle customer.subscription.updated event."""
        logger.info(f"Subscription updated: {subscription.id} - status: {subscription.status}")
        return PaymentResult(
            success=True,
            transaction_id=subscription.id,
            gateway_transaction_id=subscription.id,
            raw_response={
                'event_id': event.id,
                'subscription_id': subscription.id,
                'status': subscription.status,
            }
        )
    
    def _handle_subscription_deleted(self, subscription, event) -> PaymentResult:
        """Handle customer.subscription.deleted event."""
        logger.info(f"Subscription deleted: {subscription.id}")
        return PaymentResult(
            success=True,
            transaction_id=subscription.id,
            error_code='subscription_canceled',
            raw_response={
                'event_id': event.id,
                'subscription_id': subscription.id,
            }
        )
    
    def _process_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Process Stripe refund using StripeClient."""
        try:
            payment_intent_id = transaction.gateway_transaction_id
            
            # If we have a session ID, retrieve the payment intent
            if payment_intent_id.startswith('cs_'):
                session = self.client.v1.checkout.sessions.retrieve(payment_intent_id)
                payment_intent_id = session.payment_intent
            
            amount_cents = self._convert_vnd_to_usd(amount)
            
            stripe_reasons = {
                'customer_request': 'requested_by_customer',
                'duplicate': 'duplicate',
                'fraudulent': 'fraudulent',
            }
            stripe_reason = stripe_reasons.get(reason, 'requested_by_customer')
            
            refund = self.client.v1.refunds.create(
                params={
                    'payment_intent': payment_intent_id,
                    'amount': amount_cents,
                    'reason': stripe_reason,
                    'metadata': {
                        'reason_detail': reason,
                        'original_amount_vnd': str(amount),
                    }
                }
            )
            
            if refund.status in ['succeeded', 'pending']:
                return RefundResult(
                    success=True,
                    refund_id=refund.id,
                    gateway_refund_id=refund.id,
                    raw_response={
                        'refund_id': refund.id,
                        'status': refund.status,
                        'amount': refund.amount,
                        'currency': refund.currency,
                    }
                )
            else:
                return RefundResult(
                    success=False,
                    error_code=refund.status,
                    error_message=f'Refund status: {refund.status}',
                    raw_response={'refund_id': refund.id, 'status': refund.status}
                )
                
        except stripe.error.InvalidRequestError as e:
            logger.warning(f"Refund invalid request: {e}")
            return RefundResult(
                success=False,
                error_code='invalid_request',
                error_message=str(e)
            )
        except stripe.error.StripeError as e:
            logger.exception(f"Stripe refund error: {e}")
            return RefundResult(
                success=False,
                error_code='refund_error',
                error_message=str(e)
            )
    
    # ==================== Modern Helper Methods ====================
    
    def get_payment_methods(self, customer_id: str) -> List[Dict]:
        """Get saved payment methods for a customer."""
        try:
            payment_methods = self.client.v1.payment_methods.list(
                params={'customer': customer_id, 'type': 'card'}
            )
            return [
                {
                    'id': pm.id,
                    'brand': pm.card.brand,
                    'last4': pm.card.last4,
                    'exp_month': pm.card.exp_month,
                    'exp_year': pm.card.exp_year,
                }
                for pm in payment_methods.data
            ]
        except stripe.error.StripeError as e:
            logger.warning(f"Failed to get payment methods: {e}")
            return []
    
    def create_setup_intent(self, customer_id: str) -> Dict[str, Any]:
        """Create SetupIntent for saving card without charging."""
        try:
            setup_intent = self.client.v1.setup_intents.create(
                params={
                    'customer': customer_id,
                    'payment_method_types': ['card'],
                }
            )
            return {
                'setup_intent_id': setup_intent.id,
                'client_secret': setup_intent.client_secret,
            }
        except stripe.error.StripeError as e:
            logger.exception(f"SetupIntent creation error: {e}")
            return {'error': str(e)}
    
    def attach_payment_method(self, payment_method_id: str, customer_id: str) -> Dict[str, Any]:
        """Attach a payment method to a customer."""
        try:
            pm = self.client.v1.payment_methods.attach(
                payment_method_id,
                params={'customer': customer_id}
            )
            return {
                'id': pm.id,
                'brand': pm.card.brand,
                'last4': pm.card.last4,
            }
        except stripe.error.StripeError as e:
            logger.warning(f"Failed to attach payment method: {e}")
            return {'error': str(e)}
    
    def detach_payment_method(self, payment_method_id: str) -> bool:
        """Detach a payment method from customer."""
        try:
            self.client.v1.payment_methods.detach(payment_method_id)
            return True
        except stripe.error.StripeError as e:
            logger.warning(f"Failed to detach payment method: {e}")
            return False
    
    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        payment_method_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'expand': ['latest_invoice.payment_intent'],
            }
            
            if payment_method_id:
                params['default_payment_method'] = payment_method_id
            
            params.update(kwargs)
            
            subscription = self.client.v1.subscriptions.create(params=params)
            
            return {
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start,
                'current_period_end': subscription.current_period_end,
                'latest_invoice': subscription.latest_invoice,
            }
        except stripe.error.StripeError as e:
            logger.exception(f"Subscription creation error: {e}")
            return {'error': str(e)}
    
    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            if at_period_end:
                subscription = self.client.v1.subscriptions.update(
                    subscription_id,
                    params={'cancel_at_period_end': True}
                )
            else:
                subscription = self.client.v1.subscriptions.cancel(subscription_id)
            
            return {
                'subscription_id': subscription.id,
                'status': subscription.status,
                'cancel_at_period_end': subscription.cancel_at_period_end,
            }
        except stripe.error.StripeError as e:
            logger.exception(f"Subscription cancellation error: {e}")
            return {'error': str(e)}
    
    def get_balance(self) -> Dict[str, Any]:
        """Get Stripe account balance."""
        try:
            balance = self.client.v1.balance.retrieve()
            return {
                'available': [
                    {'amount': b.amount, 'currency': b.currency}
                    for b in balance.available
                ],
                'pending': [
                    {'amount': b.amount, 'currency': b.currency}
                    for b in balance.pending
                ],
            }
        except stripe.error.StripeError as e:
            logger.exception(f"Balance retrieval error: {e}")
            return {'error': str(e)}
