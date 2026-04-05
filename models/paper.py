from datetime import datetime
from . import db

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(120), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_email = db.Column(db.String(150), nullable=False)
    questions = db.relationship("PaperQuestion", backref="paper", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Paper {self.id} {self.subject} [{self.difficulty}]>"

class PaperQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("paper.id"), nullable=False)
    topic = db.Column(db.String(120), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    bloom_level = db.Column(db.String(80), nullable=True)
    co_level = db.Column(db.String(30), nullable=True)
    is_selected = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<PaperQuestion {self.id} paper={self.paper_id} marks={self.marks} bloom={self.bloom_level} co={self.co_level}>"
