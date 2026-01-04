"""
Common Core - Field Validators.

Reusable validators for common field types across the application.
Includes phone, email, slug, password, Vietnamese-specific validators.
"""
import re
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


# ==================== Phone Validators ====================

# Phone number validator for Vietnam (+84 or 0 prefix)
phone_validator = RegexValidator(
    regex=r'^(\+84|0)[3-9]\d{8}$',
    message='Số điện thoại phải bắt đầu bằng +84 hoặc 0, theo sau bởi 9 chữ số.'
)


def validate_vietnamese_phone(phone: str) -> bool:
    """
    Validate Vietnamese phone number format.
    
    Valid formats:
    - 0xxxxxxxxx (10 digits starting with 0)
    - +84xxxxxxxxx (starts with +84)
    """
    pattern = r'^(\+84|0)[3-9]\d{8}$'
    return bool(re.match(pattern, phone))


# ==================== Slug Validators ====================

# Slug validator - only lowercase letters, numbers, and hyphens
slug_validator = RegexValidator(
    regex=r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
    message='Slug chỉ chứa chữ thường, số và dấu gạch ngang.'
)


def validate_slug(slug: str) -> bool:
    """Validate slug format."""
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, slug))


# ==================== Password Validators ====================

def validate_password_strength(password: str) -> dict:
    """
    Validate password strength.
    
    Returns dict with:
    - valid: bool
    - score: 0-5
    - errors: list of error messages
    """
    errors = []
    score = 0
    
    if len(password) < 8:
        errors.append('Mật khẩu phải có ít nhất 8 ký tự')
    else:
        score += 1
    
    if len(password) >= 12:
        score += 1
    
    if re.search(r'[a-z]', password):
        score += 1
    else:
        errors.append('Mật khẩu phải có ít nhất 1 chữ thường')
    
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        errors.append('Mật khẩu phải có ít nhất 1 chữ hoa')
    
    if re.search(r'\d', password):
        score += 1
    else:
        errors.append('Mật khẩu phải có ít nhất 1 chữ số')
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    
    return {
        'valid': len(errors) == 0,
        'score': min(score, 5),
        'errors': errors,
        'strength': _get_strength_label(score)
    }


def _get_strength_label(score: int) -> str:
    """Get password strength label."""
    labels = {
        0: 'Rất yếu',
        1: 'Yếu',
        2: 'Trung bình',
        3: 'Khá',
        4: 'Mạnh',
        5: 'Rất mạnh'
    }
    return labels.get(min(score, 5), 'Không xác định')


# ==================== Email Validators ====================

def validate_email_format(email: str) -> bool:
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def normalize_email(email: str) -> str:
    """Normalize email address."""
    if not email:
        return email
    return email.lower().strip()


# ==================== Vietnamese ID Validators ====================

def validate_vietnamese_id(id_number: str) -> dict:
    """
    Validate Vietnamese ID number (CMND/CCCD).
    
    - CMND (old): 9 digits
    - CCCD (new): 12 digits
    """
    if not id_number:
        return {'valid': False, 'type': None, 'error': 'ID không được để trống'}
    
    # Remove spaces
    id_number = id_number.replace(' ', '')
    
    if len(id_number) == 9 and id_number.isdigit():
        return {'valid': True, 'type': 'CMND', 'number': id_number}
    elif len(id_number) == 12 and id_number.isdigit():
        return {'valid': True, 'type': 'CCCD', 'number': id_number}
    else:
        return {'valid': False, 'type': None, 'error': 'Số CMND/CCCD không hợp lệ'}


# ==================== Tax Code Validators ====================

def validate_tax_code(tax_code: str) -> bool:
    """
    Validate Vietnamese tax code (MST).
    
    Format: 10 or 13 digits (10 digits + optional 3 digit branch code)
    """
    if not tax_code:
        return False
    
    tax_code = tax_code.replace('-', '').replace(' ', '')
    
    if len(tax_code) == 10 or len(tax_code) == 13:
        return tax_code.isdigit()
    
    return False


# ==================== Bank Account Validators ====================

def validate_bank_account(account_number: str) -> bool:
    """
    Basic bank account validation.
    
    Most Vietnamese bank accounts are 9-19 digits.
    """
    if not account_number:
        return False
    
    account_number = account_number.replace(' ', '').replace('-', '')
    
    if not account_number.isdigit():
        return False
    
    return 9 <= len(account_number) <= 19


# ==================== File Validators ====================

def validate_image_extension(filename: str) -> bool:
    """Validate image file extension."""
    allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'}
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in allowed


def validate_document_extension(filename: str) -> bool:
    """Validate document file extension."""
    allowed = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'}
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in allowed


def validate_file_size(size_bytes: int, max_mb: int = 10) -> bool:
    """Validate file size."""
    max_bytes = max_mb * 1024 * 1024
    return size_bytes <= max_bytes


# ==================== URL Validators ====================

def validate_url(url: str) -> bool:
    """Basic URL validation."""
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url, re.IGNORECASE))


