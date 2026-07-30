from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, BigInteger, text, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class IPOStatus(enum.Enum):
    Open = "Open"
    Closed = "Closed"
    Allotment_Announced = "Allotment Announced"

class ResultStatus(enum.Enum):
    Allotted = "Allotted"
    Not_Allotted = "Not Allotted"
    Website_Error = "Website Error"
    Invalid_PAN = "Invalid PAN"
    Timeout = "Timeout"
    Server_Busy = "Server Busy"

class BatchStatus(enum.Enum):
    Queued = "Queued"
    In_Progress = "In Progress"
    Completed = "Completed"
    Failed = "Failed"

class EndpointType(enum.Enum):
    api = "api"
    browser_automation = "browser_automation"

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    pan = Column(String(10), unique=True, nullable=True)
    client_code = Column(String(50), nullable=True)
    boid_dpid = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    allotment_results = relationship("AllotmentResult", back_populates="client")

class IPO(Base):
    __tablename__ = "ipos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    open_date = Column(DateTime, nullable=True)
    close_date = Column(DateTime, nullable=True)
    status = Column(Enum(IPOStatus), nullable=False)
    source = Column(String(100), nullable=True)
    synced_at = Column(DateTime, nullable=True)
    auto_detected = Column(Boolean, nullable=False, server_default=text("0"))
    validated = Column(Boolean, nullable=False, server_default=text("0"))

    allotment_results = relationship("AllotmentResult", back_populates="ipo")
    batch_ipos = relationship("BatchIPO", back_populates="ipo")

class Registrar(Base):
    __tablename__ = "registrars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    priority = Column(Integer, nullable=False)
    endpoint_type = Column(Enum(EndpointType), nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("1"))

    allotment_results = relationship("AllotmentResult", back_populates="registrar")

class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    row_count = Column(Integer, nullable=False)
    valid_row_count = Column(Integer, nullable=False)
    invalid_row_count = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)
    status = Column(Enum(BatchStatus), nullable=False)

    batch_ipos = relationship("BatchIPO", back_populates="batch", cascade="all, delete")
    allotment_results = relationship("AllotmentResult", back_populates="batch")
    run_logs = relationship("RunLog", back_populates="batch")

class BatchIPO(Base):
    __tablename__ = "batch_ipos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False)
    ipo_id = Column(Integer, ForeignKey("ipos.id", ondelete="RESTRICT"), nullable=False)

    batch = relationship("UploadBatch", back_populates="batch_ipos")
    ipo = relationship("IPO", back_populates="batch_ipos")

class AllotmentResult(Base):
    __tablename__ = "allotment_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    ipo_id = Column(Integer, ForeignKey("ipos.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=True)
    registrar_id = Column(Integer, ForeignKey("registrars.id"), nullable=True)
    status = Column(Enum(ResultStatus), nullable=False)
    checked_at = Column(DateTime, nullable=False)
    served_from_cache = Column(Boolean, nullable=False, server_default=text("0"))
    cache_expires_at = Column(DateTime, nullable=True)
    captcha_path = Column(String(50), nullable=True)

    client = relationship("Client", back_populates="allotment_results")
    ipo = relationship("IPO", back_populates="allotment_results")
    batch = relationship("UploadBatch", back_populates="allotment_results")
    registrar = relationship("Registrar", back_populates="allotment_results")

    __table_args__ = (
        Index('idx_allotment_cache', 'client_id', 'ipo_id', 'cache_expires_at'),
    )

class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, nullable=False, server_default=text("0"))
    failure_count = Column(Integer, nullable=False, server_default=text("0"))
    timeout_count = Column(Integer, nullable=False, server_default=text("0"))
    cache_hit_count = Column(Integer, nullable=False, server_default=text("0"))
    registrars_used = Column(String(255), nullable=True)

    batch = relationship("UploadBatch", back_populates="run_logs")
