import enum


class Role(str, enum.Enum):
    GUEST = "guest"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

