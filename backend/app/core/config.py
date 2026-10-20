from decimal import Decimal
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:rootpassword@localhost:3306/supermarket_db?charset=utf8mb4"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # JWT Security (Must be at least 32 characters / bytes)
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "SupermarketAPI"
    JWT_AUDIENCE: str = "SupermarketApp"
    JWT_ADMIN_AUDIENCE: str = "SupermarketAdminApp"
    JWT_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_ADMIN_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    AUTH_RATE_LIMIT: str = "10/minute"
    ADMIN_AUTH_RATE_LIMIT: str = "5/minute"
    PAYMENT_CHECK_RATE_LIMIT: str = "60/minute"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # Store and Delivery Settings
    STORE_CURRENCY: str = "USD"
    DELIVERY_FLAT_FEE: Decimal = Decimal("1.50")
    DELIVERY_FREE_THRESHOLD: Decimal = Decimal("20.00")
    UNPAID_ORDER_EXPIRY_MINUTES: int = 30
    ENABLE_SANDBOX_PAYMENTS: bool = True

    # Bakong KHQR
    BAKONG_ENABLED: bool = False
    BAKONG_BASE_URL: str = "https://api-bakong.nbc.gov.kh"
    BAKONG_TOKEN: str = ""
    BAKONG_ACCOUNT_ID: str = ""
    BAKONG_ACCOUNT_TYPE: str = "Individual"  # "Individual" or "Merchant"
    BAKONG_MERCHANT_NAME: str = "Supermarket"
    BAKONG_MERCHANT_CITY: str = "Phnom Penh"
    BAKONG_CURRENCY: str = "USD"
    BAKONG_POLL_INTERVAL_SECONDS: int = 5
    BAKONG_PROXY_URL: str = ""

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError(
                "CRITICAL SECURITY ERROR: JWT_SECRET_KEY must be at least 32 bytes (256 bits) long. "
                "Refusing to start."
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()

