from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

from sqlalchemy.types import TypeDecorator, DateTime as SQLAlchemyDateTime
import datetime
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    IST = None

class TZDateTime(TypeDecorator):
    impl = SQLAlchemyDateTime
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is not None and IST is not None and value.tzinfo is None:
            value = value.replace(tzinfo=IST)
        return value
    def process_result_value(self, value, dialect):
        if value is not None and IST is not None and value.tzinfo is None:
            value = value.replace(tzinfo=IST)
        return value

class SessionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    name = db.Column(db.String(100))
    role = db.Column(db.String(30))
    login_time = db.Column(TZDateTime, default=lambda: datetime.datetime.now(IST) if IST else datetime.datetime.utcnow())
    logout_time = db.Column(TZDateTime, nullable=True)
    session_duration_seconds = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(50))
    def __repr__(self):
        return f"<SessionLog {self.email} at {self.login_time}>"