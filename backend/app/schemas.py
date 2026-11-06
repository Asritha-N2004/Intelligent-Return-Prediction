from typing import Literal
from datetime import date
from pydantic import BaseModel, Field, model_validator
from .data import CATEGORIES,LOCATIONS
class OrderCreate(BaseModel):
    order_id: str=Field(pattern=r'^[A-Za-z0-9_-]{1,50}$')
    customer_id: str=Field(min_length=1,max_length=50)
    product_id: str=Field(min_length=1,max_length=50)
    product_category: Literal['Apparel','Electronics','Footwear','Home','Beauty','Sports']
    product_price: float=Field(gt=0,le=10000000)
    quantity: int=Field(default=1,ge=1,le=100)
    order_date: date
    delivery_date: date
    payment_method: Literal['Card','UPI','Cash on delivery']='UPI'
    customer_location: Literal['Mumbai','Delhi','Bengaluru','Chennai','Hyderabad','Kolkata']
    product_rating: float=Field(default=4,ge=0,le=5)
    discount_percentage: float=Field(default=0,ge=0,le=100)
    previous_orders: int=Field(default=1,ge=0,le=100000)
    previous_returns: int=Field(default=0,ge=0,le=100000)
    delivery_delay: int=Field(default=0,ge=0,le=365)
    @model_validator(mode='after')
    def valid_history(self):
        if self.previous_returns>self.previous_orders: raise ValueError('Returns cannot exceed prior orders')
        if self.delivery_date<self.order_date: raise ValueError('Delivery precedes order')
        return self
class OrderRef(BaseModel):
    order_id: str=Field(min_length=1,max_length=50)
class LogisticsRequest(OrderRef):
    environmental_penalty: float=Field(default=2,ge=0,le=1000)
    deadline_days: int=Field(default=10,ge=1,le=90)
    transport_capacity: int=Field(default=100,ge=1,le=100000)
class Inspection(OrderRef):
    inspected: bool=False
    condition: Literal['new','opened','damaged','unsafe','unknown']='unknown'
    resale_value: float=Field(default=0,ge=0,le=10000000)
    repair_cost: float=Field(default=0,ge=0,le=10000000)
class RefundRequest(OrderRef):
    requested_date: date
    proof_of_purchase: bool=True
class WorkflowRequest(OrderRef):
    inspection: Inspection | None=None
    requested_date: date | None=None
    @model_validator(mode='after')
    def same_order(self):
        if self.inspection and self.inspection.order_id!=self.order_id: raise ValueError('Inspection belongs to another order')
        return self
class Approval(BaseModel):
    approved: bool
    reviewer: str=Field(min_length=2,max_length=100)
    note: str=Field(min_length=3,max_length=1000)
class ChatRequest(BaseModel):
    question: str=Field(default='Summarize returns',min_length=1,max_length=2000)
