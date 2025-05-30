from pydantic import BaseModel
from typing import Optional
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class OrderCreate(BaseModel):
    customer_id: str
    product_id: str
    quantity: int
    price: float

class Order(BaseModel):
    id: str
    customer_id: str
    product_id: str
    quantity: int
    price: float
    status: OrderStatus
    created_at: str
    processed_at: Optional[str] = None
