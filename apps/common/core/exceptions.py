"""Common Core - Domain Exceptions."""
from typing import Any, Dict, List, Optional


class DomainException(Exception):
    """Base exception for all domain-specific errors."""
    code: str = 'DOMAIN_ERROR'
    default_message: str = 'Đã xảy ra lỗi'
    http_status: int = 400

    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None, code: Optional[str] = None):
        self.message = message or self.default_message
        self.details = details or {}
        if code:
            self.code = code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        result = {'code': self.code, 'message': self.message}
        if self.details:
            result['details'] = self.details
        return result

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# Validation Errors
class ValidationError(DomainException):
    code = 'VALIDATION_ERROR'
    default_message = 'Dữ liệu không hợp lệ'
    http_status = 400

    def __init__(self, message: Optional[str] = None, field_errors: Optional[Dict[str, List[str]]] = None, **kwargs):
        super().__init__(message, **kwargs)
        if field_errors:
            self.details['field_errors'] = field_errors


class InvalidPhoneNumber(ValidationError):
    code = 'INVALID_PHONE'
    default_message = 'Số điện thoại không hợp lệ'


class InvalidEmail(ValidationError):
    code = 'INVALID_EMAIL'
    default_message = 'Email không hợp lệ'


class InvalidAddress(ValidationError):
    code = 'INVALID_ADDRESS'
    default_message = 'Địa chỉ không hợp lệ'


class InvalidFileType(ValidationError):
    code = 'INVALID_FILE_TYPE'
    default_message = 'Loại file không được hỗ trợ'


class FileTooLarge(ValidationError):
    code = 'FILE_TOO_LARGE'
    default_message = 'File vượt quá kích thước cho phép'


# Not Found Errors
class NotFoundError(DomainException):
    code = 'NOT_FOUND'
    default_message = 'Không tìm thấy tài nguyên'
    http_status = 404


class UserNotFound(NotFoundError):
    code = 'USER_NOT_FOUND'
    default_message = 'Không tìm thấy người dùng'


class ProductNotFound(NotFoundError):
    code = 'PRODUCT_NOT_FOUND'
    default_message = 'Không tìm thấy sản phẩm'


class OrderNotFound(NotFoundError):
    code = 'ORDER_NOT_FOUND'
    default_message = 'Không tìm thấy đơn hàng'


class PaymentNotFound(NotFoundError):
    code = 'PAYMENT_NOT_FOUND'
    default_message = 'Không tìm thấy giao dịch thanh toán'


class CartNotFound(NotFoundError):
    code = 'CART_NOT_FOUND'
    default_message = 'Không tìm thấy giỏ hàng'


class CouponNotFound(NotFoundError):
    code = 'COUPON_NOT_FOUND'
    default_message = 'Không tìm thấy mã giảm giá'


# Business Rule Violations
class BusinessRuleViolation(DomainException):
    code = 'BUSINESS_RULE_VIOLATION'
    default_message = 'Vi phạm quy tắc nghiệp vụ'
    http_status = 422


class InsufficientStock(BusinessRuleViolation):
    code = 'INSUFFICIENT_STOCK'
    default_message = 'Không đủ hàng trong kho'

    def __init__(self, product_name: str = '', available: int = 0, requested: int = 0, **kwargs):
        message = kwargs.get('message') or f'Sản phẩm {product_name} chỉ còn {available}, bạn yêu cầu {requested}'
        super().__init__(message=message, details={'product': product_name, 'available': available, 'requested': requested}, **kwargs)


class CartEmpty(BusinessRuleViolation):
    code = 'CART_EMPTY'
    default_message = 'Giỏ hàng trống'


class OrderCannotBeCancelled(BusinessRuleViolation):
    code = 'ORDER_CANNOT_BE_CANCELLED'
    default_message = 'Không thể hủy đơn hàng ở trạng thái hiện tại'


class InvalidStateTransition(BusinessRuleViolation):
    code = 'INVALID_STATE_TRANSITION'
    default_message = 'Không thể chuyển trạng thái'

    def __init__(self, from_state: str = '', to_state: str = '', **kwargs):
        message = kwargs.get('message') or f'Không thể chuyển từ {from_state} sang {to_state}'
        super().__init__(message=message, details={'from_state': from_state, 'to_state': to_state}, **kwargs)


class PaymentAlreadyCompleted(BusinessRuleViolation):
    code = 'PAYMENT_ALREADY_COMPLETED'
    default_message = 'Thanh toán đã hoàn tất'


class RefundExceedsPayment(BusinessRuleViolation):
    code = 'REFUND_EXCEEDS_PAYMENT'
    default_message = 'Số tiền hoàn vượt quá số tiền thanh toán'


class CouponExpired(BusinessRuleViolation):
    code = 'COUPON_EXPIRED'
    default_message = 'Mã giảm giá đã hết hạn'


class CouponUsageLimitReached(BusinessRuleViolation):
    code = 'COUPON_USAGE_LIMIT'
    default_message = 'Mã giảm giá đã hết lượt sử dụng'


class MinimumOrderNotMet(BusinessRuleViolation):
    code = 'MINIMUM_ORDER_NOT_MET'
    default_message = 'Đơn hàng chưa đạt giá trị tối thiểu'


class ReturnWindowExpired(BusinessRuleViolation):
    code = 'RETURN_WINDOW_EXPIRED'
    default_message = 'Đã quá thời hạn đổi/trả hàng'


# Authentication Errors
class AuthenticationError(DomainException):
    code = 'AUTHENTICATION_ERROR'
    default_message = 'Xác thực thất bại'
    http_status = 401


class InvalidCredentials(AuthenticationError):
    code = 'INVALID_CREDENTIALS'
    default_message = 'Email hoặc mật khẩu không đúng'


class AccountLocked(AuthenticationError):
    code = 'ACCOUNT_LOCKED'
    default_message = 'Tài khoản đã bị khóa'


class AccountDisabled(AuthenticationError):
    code = 'ACCOUNT_DISABLED'
    default_message = 'Tài khoản đã bị vô hiệu hóa'


class EmailNotVerified(AuthenticationError):
    code = 'EMAIL_NOT_VERIFIED'
    default_message = 'Email chưa được xác thực'


class TwoFactorRequired(AuthenticationError):
    code = '2FA_REQUIRED'
    default_message = 'Yêu cầu xác thực 2 yếu tố'


class InvalidTwoFactorCode(AuthenticationError):
    code = 'INVALID_2FA_CODE'
    default_message = 'Mã xác thực không đúng'


class TokenExpired(AuthenticationError):
    code = 'TOKEN_EXPIRED'
    default_message = 'Token đã hết hạn'


class InvalidToken(AuthenticationError):
    code = 'INVALID_TOKEN'
    default_message = 'Token không hợp lệ'


class SessionExpired(AuthenticationError):
    code = 'SESSION_EXPIRED'
    default_message = 'Phiên đăng nhập đã hết hạn'


# Authorization Errors
class AuthorizationError(DomainException):
    code = 'AUTHORIZATION_ERROR'
    default_message = 'Không có quyền truy cập'
    http_status = 403


class PermissionDenied(AuthorizationError):
    code = 'PERMISSION_DENIED'
    default_message = 'Không có quyền thực hiện thao tác này'


class ResourceAccessDenied(AuthorizationError):
    code = 'RESOURCE_ACCESS_DENIED'
    default_message = 'Không có quyền truy cập tài nguyên này'


# External Service Errors
class ExternalServiceError(DomainException):
    code = 'EXTERNAL_SERVICE_ERROR'
    default_message = 'Lỗi dịch vụ bên ngoài'
    http_status = 502

    def __init__(self, message: Optional[str] = None, service: str = '', **kwargs):
        super().__init__(message, **kwargs)
        if service:
            self.details['service'] = service


class PaymentGatewayError(ExternalServiceError):
    code = 'PAYMENT_GATEWAY_ERROR'
    default_message = 'Lỗi cổng thanh toán'


class ShippingProviderError(ExternalServiceError):
    code = 'SHIPPING_PROVIDER_ERROR'
    default_message = 'Lỗi nhà vận chuyển'


class EmailServiceError(ExternalServiceError):
    code = 'EMAIL_SERVICE_ERROR'
    default_message = 'Lỗi dịch vụ email'


class SMSServiceError(ExternalServiceError):
    code = 'SMS_SERVICE_ERROR'
    default_message = 'Lỗi dịch vụ SMS'


class StorageServiceError(ExternalServiceError):
    code = 'STORAGE_SERVICE_ERROR'
    default_message = 'Lỗi dịch vụ lưu trữ'


# Rate Limit & Conflict Errors
class RateLimitError(DomainException):
    code = 'RATE_LIMIT_EXCEEDED'
    default_message = 'Bạn đã thực hiện quá nhiều yêu cầu, vui lòng thử lại sau'
    http_status = 429

    def __init__(self, retry_after: int = 60, **kwargs):
        super().__init__(**kwargs)
        self.details['retry_after'] = retry_after


class ConflictError(DomainException):
    code = 'CONFLICT'
    default_message = 'Xung đột dữ liệu'
    http_status = 409


class DuplicateEntry(ConflictError):
    code = 'DUPLICATE_ENTRY'
    default_message = 'Dữ liệu đã tồn tại'


class OptimisticLockError(ConflictError):
    code = 'OPTIMISTIC_LOCK_ERROR'
    default_message = 'Dữ liệu đã bị thay đổi bởi người khác, vui lòng tải lại'
