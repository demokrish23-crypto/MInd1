from . import db

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(db.String(30), nullable=False)
    bloom_level = db.Column(db.String(80), nullable=True)
    co_level = db.Column(db.String(30), nullable=True)
    owner_email = db.Column(db.String(150), nullable=False)

    def __repr__(self):
        return f"<Question {self.id} ({self.subject})>"

    