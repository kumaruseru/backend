"""Stripe Payment Gateway.

Full integration with Stripe using Checkout Sessions, PaymentIntents, Customers, 
and comprehensive payment features. USD only.
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

import stripe
from django.conf import settings

from .base import BasePaymentGateway, PaymentResult, RefundResult

logger = logging.getLogger('apps.billing.stripe')

# Configure Stripe API
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
stripe.api_version = '2024-12-18.acacia'  # Latest API version


class StripeGateway(BasePaymentGateway):
    """Stripe payment gateway with full feature integration.
    
    Features:
    - Checkout Sessions for secure hosted payments
    - PaymentIntents for custom payment flows
    - Customer management for repeat buyers
    - Automatic currency conversion (VND → USD)
    - Webhook signature verification
    - Full and partial refunds
    - Payment metadata tracking
    - Idempotency key support
    
    Note: Only USD is supported for Stripe payments.
    VND amounts are converted to USD using configured exchange rate.
    """
    
    gateway_code = 'stripe'
    gateway_name = 'Stripe'
    supports_refund = True
    supports_webhook = True
    
    # Currency settings
    SUPPORTED_CURRENCY = 'usd'
    VND_TO_USD_RATE = Decimal('25000')  # Approximate rate, should be dynamic
    
    def __init__(self):
        self.secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.publishable_key = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '')
        self.webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        
        # Ensure stripe is configured
        if self.secret_key:
            stripe.api_key = self.secret_key
    
    def _convert_vnd_to_usd(self, amount_vnd: Decimal) -> int:
        """Convert VND to USD cents.
        
        Stripe uses smallest currency unit (cents for USD).
        """
        rate = getattr(settings, 'VND_TO_USD_RATE', self.VND_TO_USD_RATE)
        usd_amount = amount_vnd / Decimal(rate)
        # Round to 2 decimal places and convert to cents
        cents = int(round(usd_amount, 2) * 100)
        return max(cents, 50)  # Stripe minimum is $0.50 (50 cents)
    
    def _get_or_create_customer(self, user, email: str = None) -> Optional[stripe.Customer]:
        """Get or create Stripe customer for user."""
        try:
            if not user:
                return None
            
            # Check if user already has a Stripe customer ID
            customer_id = getattr(user, 'stripe_customer_id', None)
            
            if customer_id:
                try:
                    return stripe.Customer.retrieve(customer_id)
                except stripe.error.InvalidRequestError:
                    pass  # Customer deleted, create new
            
            # Search for existing customer by email
            email = email or getattr(user, 'email', None)
            if email:
                customers = stripe.Customer.list(email=email, limit=1)
                if customers.data:
                    return customers.data[0]
            
            # Create new customer
            customer = stripe.Customer.create(
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
            
            return customer
            
        except stripe.error.StripeError as e:
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
        try:
            # Convert amount to USD cents
            amount_cents = self._convert_vnd_to_usd(amount)
            usd_amount = Decimal(amount_cents) / 100
            
            # Get or create customer
            customer = self._get_or_create_customer(order.user, order.email)
            
            # Build line items from order
            line_items = []
            
            for item in order.items.all():
                item_cents = self._convert_vnd_to_usd(item.unit_price)
                line_items.append({
                    'price_data': {
                        'currency': self.SUPPORTED_CURRENCY,
                        'product_data': {
                            'name': item.product_name[:100],  # Stripe limit
                            'description': f'SKU: {item.product_sku}' if item.product_sku else None,
                            'metadata': {
                                'product_id': str(item.product_id) if item.product_id else '',
                                'original_price_vnd': str(item.unit_price),
                            }
                        },
                        'unit_amount': item_cents,
                    },
                    'quantity': item.quantity,
                })
            
            # Add shipping fee if exists
            if order.shipping_fee > 0:
                shipping_cents = self._convert_vnd_to_usd(order.shipping_fee)
                line_items.append({
                    'price_data': {
                        'currency': self.SUPPORTED_CURRENCY,
                        'product_data': {
                            'name': 'Shipping & Handling',
                        },
                        'unit_amount': shipping_cents,
                    },
                    'quantity': 1,
                })
            
            # Add tax if exists
            if order.tax > 0:
                tax_cents = self._convert_vnd_to_usd(order.tax)
                line_items.append({
                    'price_data': {
                        'currency': self.SUPPORTED_CURRENCY,
                        'product_data': {
                            'name': 'Tax',
                        },
                        'unit_amount': tax_cents,
                    },
                    'quantity': 1,
                })
            
            # Create idempotency key for safe retries
            idempotency_key = f"checkout_{order.order_number}_{order.id}"
            
            # Checkout session parameters
            session_params = {
                'payment_method_types': ['card'],
                'mode': 'payment',
                'line_items': line_items,
                'success_url': return_url + '?session_id={CHECKOUT_SESSION_ID}&status=success',
                'cancel_url': cancel_url or return_url + '?status=cancelled',
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
                # Enhanced features
                'billing_address_collection': 'auto',
                'phone_number_collection': {'enabled': True},
                'expires_at': int((timezone.now() + timedelta(hours=24)).timestamp()),
                'locale': 'auto',
            }
            
            # Add customer if available
            if customer:
                session_params['customer'] = customer.id
            else:
                session_params['customer_email'] = order.email or (order.user.email if order.user else None)
            
            # Add shipping address collection for physical goods
            if order.items.exists():
                session_params['shipping_address_collection'] = {
                    'allowed_countries': ['VN', 'US', 'SG', 'JP', 'KR', 'AU', 'GB', 'DE', 'FR']
                }
            
            # Create checkout session with idempotency
            session = stripe.checkout.Session.create(
                **session_params,
                idempotency_key=idempotency_key
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
                    'customer_id': customer.id if customer else None,
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
            customer = self._get_or_create_customer(order.user, order.email)
            
            intent_params = {
                'amount': amount_cents,
                'currency': self.SUPPORTED_CURRENCY,
                'description': f'Order {order.order_number}',
                'metadata': {
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'original_amount_vnd': str(amount),
                },
                'automatic_payment_methods': {
                    'enabled': True,
                },
            }
            
            if customer:
                intent_params['customer'] = customer.id
            
            intent = stripe.PaymentIntent.create(**intent_params)
            
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
            
            # Retrieve session with expanded payment intent
            session = stripe.checkout.Session.retrieve(
                session_id,
                expand=['payment_intent', 'customer']
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
                    raw_response={
                        'session_id': session.id,
                        'status': session.payment_status,
                    }
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
        payload: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> PaymentResult:
        """Process Stripe webhook events with signature verification."""
        try:
            sig_header = headers.get('Stripe-Signature', '') if headers else ''
            
            # Verify webhook signature
            if self.webhook_secret and sig_header:
                try:
                    event = stripe.Webhook.construct_event(
                        payload=payload if isinstance(payload, (str, bytes)) else str(payload),
                        sig_header=sig_header,
                        secret=self.webhook_secret
                    )
                except stripe.error.SignatureVerificationError as e:
                    logger.warning(f"Webhook signature failed: {e}")
                    return PaymentResult(
                        success=False,
                        error_code='invalid_signature',
                        error_message='Webhook signature verification failed.'
                    )
            else:
                # Parse payload directly (less secure, dev only)
                import json
                event = stripe.Event.construct_from(
                    json.loads(payload) if isinstance(payload, str) else payload,
                    stripe.api_key
                )
            
            event_type = event.type
            event_object = event.data.object
            
            logger.info(f"Processing Stripe webhook: {event_type}")
            
            # Handle different event types
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(event_object)
            
            elif event_type == 'payment_intent.succeeded':
                return self._handle_payment_succeeded(event_object)
            
            elif event_type == 'payment_intent.payment_failed':
                return self._handle_payment_failed(event_object)
            
            elif event_type == 'charge.refunded':
                return self._handle_charge_refunded(event_object)
            
            elif event_type == 'charge.dispute.created':
                return self._handle_dispute_created(event_object)
            
            else:
                logger.info(f"Unhandled webhook event: {event_type}")
                return PaymentResult(
                    success=True,  # Acknowledge but don't process
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
    
    def _handle_checkout_completed(self, session) -> PaymentResult:
        """Handle checkout.session.completed event."""
        if session.payment_status == 'paid':
            return PaymentResult(
                success=True,
                transaction_id=session.id,
                gateway_transaction_id=session.payment_intent,
                raw_response={
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
    
    def _handle_payment_succeeded(self, payment_intent) -> PaymentResult:
        """Handle payment_intent.succeeded event."""
        return PaymentResult(
            success=True,
            transaction_id=payment_intent.id,
            gateway_transaction_id=payment_intent.id,
            raw_response={
                'payment_intent': payment_intent.id,
                'amount': payment_intent.amount,
                'currency': payment_intent.currency,
                'metadata': dict(payment_intent.metadata) if payment_intent.metadata else {},
            }
        )
    
    def _handle_payment_failed(self, payment_intent) -> PaymentResult:
        """Handle payment_intent.payment_failed event."""
        last_error = payment_intent.last_payment_error
        return PaymentResult(
            success=False,
            transaction_id=payment_intent.id,
            error_code=last_error.code if last_error else 'payment_failed',
            error_message=last_error.message if last_error else 'Payment failed.',
            raw_response={
                'payment_intent': payment_intent.id,
                'error': dict(last_error) if last_error else None,
            }
        )
    
    def _handle_charge_refunded(self, charge) -> PaymentResult:
        """Handle charge.refunded event."""
        return PaymentResult(
            success=True,
            transaction_id=charge.payment_intent,
            gateway_transaction_id=charge.id,
            raw_response={
                'charge_id': charge.id,
                'amount_refunded': charge.amount_refunded,
                'refunded': charge.refunded,
            }
        )
    
    def _handle_dispute_created(self, dispute) -> PaymentResult:
        """Handle charge.dispute.created event (chargeback)."""
        logger.warning(f"Dispute/chargeback created: {dispute.id}")
        return PaymentResult(
            success=False,
            transaction_id=dispute.payment_intent,
            error_code='dispute_created',
            error_message=f'Dispute created: {dispute.reason}',
            raw_response={
                'dispute_id': dispute.id,
                'reason': dispute.reason,
                'amount': dispute.amount,
            }
        )
    
    def _process_refund(
        self,
        transaction,
        amount: Decimal,
        reason: str
    ) -> RefundResult:
        """Process Stripe refund."""
        try:
            # Get the payment intent ID
            payment_intent_id = transaction.gateway_transaction_id
            
            # If we have a session ID, retrieve the payment intent
            if payment_intent_id.startswith('cs_'):
                session = stripe.checkout.Session.retrieve(payment_intent_id)
                payment_intent_id = session.payment_intent
            
            # Convert refund amount to USD cents
            amount_cents = self._convert_vnd_to_usd(amount)
            
            # Map reason to Stripe reason
            stripe_reasons = {
                'customer_request': 'requested_by_customer',
                'duplicate': 'duplicate',
                'fraudulent': 'fraudulent',
            }
            stripe_reason = stripe_reasons.get(reason, 'requested_by_customer')
            
            # Create refund
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount_cents,
                reason=stripe_reason,
                metadata={
                    'reason_detail': reason,
                    'original_amount_vnd': str(amount),
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
    
    def get_payment_methods(self, customer_id: str) -> list:
        """Get saved payment methods for a customer."""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
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
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=['card'],
            )
            return {
                'setup_intent_id': setup_intent.id,
                'client_secret': setup_intent.client_secret,
            }
        except stripe.error.StripeError as e:
            logger.exception(f"SetupIntent creation error: {e}")
            return {'error': str(e)}


# Import timezone for expires_at calculation
from django.utils import timezone
from datetime import timedelta
