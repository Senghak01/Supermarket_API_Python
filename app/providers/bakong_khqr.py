import hashlib
import logging
from decimal import Decimal
from typing import Optional
import httpx
from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment, PaymentMethod
from app.providers.base import (
    BasePaymentProvider,
    BasePaymentVerifier,
    PaymentInitResult,
    PaymentVerification,
)

logger = logging.getLogger("supermarket.bakong")


def calculate_crc16(payload: str) -> str:
    """Calculate CRC16-CCITT checksum for EMVCo QR code."""
    crc = 0xFFFF
    for b in payload.encode("utf-8"):
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def tlv(tag: str, value: str) -> str:
    """Helper to format Tag-Length-Value chunk."""
    val_bytes = value.encode("utf-8")
    return f"{tag}{len(val_bytes):02d}{value}"


def build_khqr_string(
    account_id: str,
    account_type: str,
    merchant_name: str,
    merchant_city: str,
    currency: str,
    amount: Decimal,
    bill_number: str,
    mobile_number: str = "",
    store_label: str = "",
) -> str:
    """Generates standard dynamic EMVCo KHQR code."""
    # Currency numeric code
    curr_code = "116" if currency.upper() == "KHR" else "840"

    parts = [
        tlv("00", "01"),  # Payload format indicator
        tlv("01", "12"),  # 12 = Dynamic QR
    ]

    # Account information
    if account_type.lower() == "merchant":
        account_info = tlv("00", account_id)
        parts.append(tlv("30", account_info))
    else:
        account_info = tlv("00", account_id)
        parts.append(tlv("29", account_info))

    parts.append(tlv("52", "5411"))  # Grocery Stores / Supermarkets
    parts.append(tlv("53", curr_code))
    parts.append(tlv("54", f"{amount:.2f}"))
    parts.append(tlv("58", "KH"))
    parts.append(tlv("59", merchant_name[:25]))
    parts.append(tlv("60", merchant_city[:15]))

    # Tag 62: Additional Data Field
    sub_62 = [tlv("01", bill_number)]
    if mobile_number:
        sub_62.append(tlv("02", mobile_number))
    if store_label:
        sub_62.append(tlv("03", store_label))
    parts.append(tlv("62", "".join(sub_62)))

    # CRC tag header
    pre_crc = "".join(parts) + "6304"
    crc_val = calculate_crc16(pre_crc)
    return pre_crc + crc_val


class BakongKhqrProvider(BasePaymentProvider, BasePaymentVerifier):
    def __init__(self) -> None:
        self.base_url = settings.BAKONG_BASE_URL.rstrip("/")
        self.token = settings.BAKONG_TOKEN
        self.account_id = settings.BAKONG_ACCOUNT_ID
        self.account_type = settings.BAKONG_ACCOUNT_TYPE
        self.merchant_name = settings.BAKONG_MERCHANT_NAME
        self.merchant_city = settings.BAKONG_MERCHANT_CITY
        self.currency = settings.BAKONG_CURRENCY

    @property
    def method(self) -> PaymentMethod:
        return PaymentMethod.Khqr

    @property
    def requires_online_payment(self) -> bool:
        return True

    async def initiate(self, order: Order, payment: Payment) -> PaymentInitResult:
        bill_number = f"P{payment.id}"
        qr = build_khqr_string(
            account_id=self.account_id,
            account_type=self.account_type,
            merchant_name=self.merchant_name,
            merchant_city=self.merchant_city,
            currency=self.currency,
            amount=payment.amount,
            bill_number=bill_number,
        )
        md5 = hashlib.md5(qr.encode("utf-8")).hexdigest()
        return PaymentInitResult(transaction_id=md5, qr_data=qr)

    async def verify(self, payment: Payment) -> PaymentVerification:
        if not payment.transaction_id:
            return PaymentVerification(paid=False)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/v1/check_transaction_by_md5"

        proxies = settings.BAKONG_PROXY_URL if settings.BAKONG_PROXY_URL else None

        async with httpx.AsyncClient(timeout=10.0, proxy=proxies) as client:
            try:
                resp = await client.post(url, json={"md5": payment.transaction_id}, headers=headers)
                if resp.status_code in (401, 403):
                    logger.warning(f"Bakong API returned {resp.status_code}. Token may be invalid or IP not allowed.")
                    return PaymentVerification(paid=False)

                if resp.status_code == 404:
                    return PaymentVerification(paid=False)

                resp.raise_for_status()
                data = resp.json()

                if data.get("responseCode") != 0:
                    return PaymentVerification(paid=False)

                tx_data = data.get("data", {})
                tx_amount = Decimal(str(tx_data.get("amount", 0)))
                tx_currency = str(tx_data.get("currency", "")).upper()
                tx_hash = tx_data.get("hash")

                # Validate exact amount and currency match
                if tx_amount != payment.amount:
                    logger.warning(
                        f"Bakong amount mismatch for payment {payment.id}: expected {payment.amount}, got {tx_amount}"
                    )
                    return PaymentVerification(paid=False)

                if tx_currency != self.currency.upper():
                    logger.warning(
                        f"Bakong currency mismatch for payment {payment.id}: expected {self.currency}, got {tx_currency}"
                    )
                    return PaymentVerification(paid=False)

                return PaymentVerification(paid=True, provider_reference=tx_hash)

            except Exception as ex:
                logger.error(f"Error checking Bakong payment {payment.id}: {ex}")
                return PaymentVerification(paid=False)

