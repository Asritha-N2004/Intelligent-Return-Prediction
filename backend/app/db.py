from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship
from .config import DATABASE_URL

def now(): return datetime.now(timezone.utc)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_pragmas(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Timestamp:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Customer(Timestamp, Base):
    __tablename__='customers'
    id: Mapped[str]=mapped_column(String(50), primary_key=True)
    location: Mapped[str]=mapped_column(String(100))
    previous_orders: Mapped[int]=mapped_column(Integer)
    previous_returns: Mapped[int]=mapped_column(Integer)
    orders: Mapped[list['Order']]=relationship(back_populates='customer')
class Product(Timestamp, Base):
    __tablename__='products'
    id: Mapped[str]=mapped_column(String(50),primary_key=True)
    category: Mapped[str]=mapped_column(String(60),index=True)
    price: Mapped[float]=mapped_column(Float)
    rating: Mapped[float]=mapped_column(Float)
class Warehouse(Timestamp, Base):
    __tablename__='warehouses'
    id: Mapped[str]=mapped_column(String(50),primary_key=True)
    location: Mapped[str]=mapped_column(String(100))
    latitude: Mapped[float]=mapped_column(Float)
    longitude: Mapped[float]=mapped_column(Float)
    capacity: Mapped[int]=mapped_column(Integer)
    used: Mapped[int]=mapped_column(Integer,default=0)
    processing_cost: Mapped[float]=mapped_column(Float)
    processing_days: Mapped[int]=mapped_column(Integer)
    capabilities: Mapped[list]=mapped_column(JSON)
class Order(Timestamp, Base):
    __tablename__='orders'
    id: Mapped[str]=mapped_column(String(50),primary_key=True)
    customer_id: Mapped[str]=mapped_column(ForeignKey('customers.id'),index=True)
    product_id: Mapped[str]=mapped_column(ForeignKey('products.id'),index=True)
    order_date: Mapped[str]=mapped_column(String(30),index=True)
    return_requested: Mapped[bool]=mapped_column(Boolean,default=False)
    data: Mapped[dict]=mapped_column(JSON)
    customer: Mapped[Customer]=relationship(back_populates='orders')
    items: Mapped[list['OrderItem']]=relationship(back_populates='order')
class OrderItem(Timestamp, Base):
    __tablename__='order_items'
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[str]=mapped_column(ForeignKey('orders.id'),index=True)
    product_id: Mapped[str]=mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int]=mapped_column(Integer)
    unit_price: Mapped[float]=mapped_column(Float)
    order: Mapped[Order]=relationship(back_populates='items')
class Return(Timestamp, Base):
    __tablename__='returns'
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[str]=mapped_column(ForeignKey('orders.id'),index=True,unique=True)
    reason: Mapped[str]=mapped_column(String(200))
    refund_amount: Mapped[float]=mapped_column(Float)
    warehouse_id: Mapped[str]=mapped_column(ForeignKey('warehouses.id'))
class Record(Timestamp):
    id: Mapped[int]=mapped_column(primary_key=True)
    order_id: Mapped[str | None]=mapped_column(ForeignKey('orders.id'),nullable=True,index=True)
    payload: Mapped[dict]=mapped_column(JSON)
class Prediction(Record,Base): __tablename__='return_predictions'
class RiskProfile(Record,Base): __tablename__='customer_risk_profiles'
class Anomaly(Record,Base): __tablename__='anomaly_detections'
class Logistics(Record,Base): __tablename__='logistics_optimizations'
class Disposition(Record,Base): __tablename__='disposition_recommendations'
class Refund(Record,Base): __tablename__='refund_decisions'
class Decision(Record,Base): __tablename__='decision_reports'
class AgentLog(Record,Base):
    __tablename__='agent_execution_logs'
    execution_id: Mapped[str]=mapped_column(String(50),index=True)
    agent: Mapped[str]=mapped_column(String(100),index=True)
    status: Mapped[str]=mapped_column(String(30))
    duration_ms: Mapped[float]=mapped_column(Float)
class ModelVersion(Timestamp,Base):
    __tablename__='model_versions'
    id: Mapped[int]=mapped_column(primary_key=True)
    version: Mapped[str]=mapped_column(String(80),unique=True)
    metrics: Mapped[dict]=mapped_column(JSON)
class Audit(Timestamp,Base):
    __tablename__='audit_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    action: Mapped[str]=mapped_column(String(100),index=True)
    payload: Mapped[dict]=mapped_column(JSON)

class AuthSession(Timestamp,Base):
    __tablename__='auth_sessions'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    email: Mapped[str]=mapped_column(String(254))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class AuthUser(Timestamp,Base):
    __tablename__='auth_users'
    email: Mapped[str]=mapped_column(String(254),primary_key=True)
    name: Mapped[str]=mapped_column(String(100))
    password_hash: Mapped[str]=mapped_column(String(256))
    role: Mapped[str]=mapped_column(String(20),default='member')
    active: Mapped[bool]=mapped_column(Boolean,default=True)
