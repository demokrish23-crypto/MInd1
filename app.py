import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, session, url_for, flash
from sqlalchemy import text
from models import db

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ensure instance folder exists (where SQLite file is created)
os.makedirs(app.instance_path, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session configuration - user stays logged in until logout
app.config["SESSION_PERMANENT"] = True  # Session cookie is permanent
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)  # 1 hour session timeout
app.config["SESSION_COOKIE_SECURE"] = False  # Set True in production with HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection


# Initialize db with app first
db.init_app(app)

# Import models to register them with SQLAlchemy metadata
from models.question_bank import Question  # noqa: F401, E402
from models.paper import Paper, PaperQuestion  # noqa: F401, E402
from models import SessionLog  # noqa: F401, E402

# Inject session_expiry_ts into all templates for authenticated users
@app.context_processor
def inject_session_expiry():
    import time
    user = session.get("user")
    session_expiry_ts = None
    if user:
        session_start = session.get("_session_start")
        session_lifetime = app.permanent_session_lifetime.total_seconds() if hasattr(app, 'permanent_session_lifetime') else 3600
        if session_start:
            if hasattr(session_start, 'timestamp'):
                session_start_ts = session_start.timestamp()
            else:
                from datetime import datetime
                try:
                    session_start_ts = datetime.strptime(str(session_start), "%Y-%m-%d %H:%M:%S.%f").timestamp()
                except Exception:
                    session_start_ts = time.time()
            session_expiry_ts = int(session_start_ts + session_lifetime)
        else:
            session_expiry_ts = int(time.time() + session_lifetime)
    return dict(session_expiry_ts=session_expiry_ts)

def get_ist_now():
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata"))
    except ImportError:
        # Fallback for Python <3.9: naive +5:30 offset (no tzinfo)
        from datetime import timedelta
        return datetime.utcnow() + timedelta(hours=5, minutes=30)

# Create all tables in app context
with app.app_context():
    db.create_all()
    db.session.commit()

    # ensure extra question fields exist for old question tables
    try:
        with db.engine.begin() as conn:
            check = conn.execute(text("PRAGMA table_info(question)")).fetchall()
            if check and not any(col[1] == "owner_email" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN owner_email VARCHAR(150) NOT NULL DEFAULT 'unknown'"))
            if check and not any(col[1] == "bloom_level" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN bloom_level VARCHAR(80)"))
            if check and not any(col[1] == "co_level" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN co_level VARCHAR(20)"))
    except Exception:
        pass

# Ensure tables still exist before the first request (safety net)
@app.before_request
def ensure_tables_exist():
    if not app.config.get("TABLES_CREATED"):
        from models.question_bank import Question  # noqa: F401
        from models.paper import Paper, PaperQuestion  # noqa: F401
        from models import SessionLog  # noqa: F401
        
        try:
            db.create_all()
            db.session.commit()
            
            with db.engine.begin() as conn:
                check = conn.execute(text("PRAGMA table_info(question)")).fetchall()
                if check and not any(col[1] == "owner_email" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN owner_email VARCHAR(150) NOT NULL DEFAULT 'unknown'"))
                if check and not any(col[1] == "bloom_level" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN bloom_level VARCHAR(80)"))
                if check and not any(col[1] == "co_level" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN co_level VARCHAR(20)"))
        except Exception:
            pass

        app.config["TABLES_CREATED"] = True

from routes.paper_generator import paper_bp  # noqa: E402
from routes.question_bank import question_bank_bp  # noqa: E402
from routes.admin import admin_bp  # noqa: E402

app.register_blueprint(paper_bp)
app.register_blueprint(question_bank_bp)
app.register_blueprint(admin_bp)

# Faculty delete account route
@app.route("/faculty/delete-account", methods=["POST"], endpoint="faculty_delete_account")
def faculty_delete_account():
    user = session.get("user")
    if not user:
        flash("You must be logged in to delete your account.", "error")
        return redirect("/login")

    password = request.form.get("password")
    if not password:
        flash("Password is required to delete your account.", "error")
        return redirect(url_for("faculty_settings"))

    # Validate password
    users = []
    try:
        with open("users.txt", "r") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",", 3)]
                if len(parts) != 4:
                    continue
                role, email, pwd, name = parts
                users.append({
                    "role": role,
                    "email": email,
                    "password": pwd,
                    "name": name,
                })
    except FileNotFoundError:
        pass

    found = False
    for u in users:
        if u["email"] == user["email"] and u["password"] == password and u["role"] == user["role"]:
            found = True
            break

    if not found:
        flash("Incorrect password. Account not deleted.", "error")
        return redirect(url_for("faculty_settings"))

    # Remove user from users.txt
    users = [u for u in users if not (u["email"] == user["email"] and u["role"] == user["role"])]
    with open("users.txt", "w") as f:
        for u in users:
            f.write(f"{u['role']},{u['email']},{u['password']},{u['name']}\n")

    # Optionally: Remove user's questions, papers, etc. (not implemented here)

    session.clear()
    flash("Your account has been deleted successfully.", "success")
    return redirect("/login")


def _read_all_users_from_file():
    users = []
    try:
        with open("users.txt", "r") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",", 3)]
                if len(parts) != 4:
                    continue
                role, email, password, name = parts
                users.append({
                    "role": role,
                    "email": email,
                    "password": password,
                    "name": name,
                })
    except FileNotFoundError:
        pass
    return users

def _write_all_users_to_file(users):
    with open("users.txt", "w") as f:
        for u in users:
            f.write(f"{u['role']},{u['email']},{u['password']},{u['name']}\n")

def load_users():
    users = []
    try:
        with open("users.txt") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",", 3)]
                if len(parts) != 4:
                    continue
                role, email, password, name = parts
                users.append({
                    "role": role,
                    "email": email,
                    "password": password,
                    "name": name
                })
    except FileNotFoundError:
        pass
    return users


@app.route("/")
def welcome():
    user = session.get("user")
    if user:
        if user.get("role") == "faculty":
            return redirect("/faculty/dashboard")
        if user.get("role") == "admin":
            return redirect("/admin-dev")
    return render_template("public/welcome.html")


@app.route("/landing")
def landing():
    user = session.get("user")
    if user:
        if user.get("role") == "faculty":
            return redirect("/faculty/dashboard")
        if user.get("role") == "admin":
            return redirect("/admin-dev")
    return render_template("public/landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    user = session.get("user")
    if user:
        if user.get("role") == "faculty":
            return redirect("/faculty/dashboard")
        if user.get("role") == "admin":
            return redirect("/admin-dev")
    error = None
    email_restore = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        email_restore = email

        if not email or not password or not role:
            error = "All fields are required."
        elif "@" not in email or len(email) < 5:
            error = "Please enter a valid email address."
        elif len(password) < 3:
            error = "Password must be at least 3 characters."
        else:
            for user in load_users():
                if user["email"] == email and user["password"] == password and user["role"] == role:
                    session.permanent = True  # Mark session as permanent (won't expire until logout)
                    session["user"] = user
                    # Store start time in UTC
                    from datetime import datetime
                    session["_session_start"] = datetime.utcnow()
                    # Log the session in IST
                    from models import SessionLog, db
                    try:
                        log = SessionLog(
                            email=email,
                            name=user.get("name", ""),
                            role=role,
                            login_time=get_ist_now(),  # IST
                            ip_address=request.remote_addr
                        )
                        db.session.add(log)
                        db.session.commit()
                    except Exception as e:
                        print(f"Failed to log session: {e}")
                    if role == "faculty":
                        return redirect("/faculty/dashboard")
                    if role == "admin":
                        return redirect("/admin-dev")
            error = "Invalid credentials. Please check your email, password, and role."
    return render_template("public/login.html", error=error, email_restore=email_restore)

def require_role(required_role):
    """Decorator to ensure user has required role"""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect("/login")
            if user.get("role") != required_role:
                flash(f"Access denied: {required_role} only", "error")
                if required_role == "admin":
                    return redirect(url_for("faculty_dashboard"))
                else:
                    return redirect(url_for("admin.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route("/faculty/dashboard")
@require_role("faculty")
def faculty_dashboard():
    user = session.get("user")
    from models.question_bank import Question
    from models.paper import Paper

    user_email = user.get("email")

    # Session timer logic
    import time
    session_start = session.get("_session_start")
    session_lifetime = app.permanent_session_lifetime.total_seconds() if hasattr(app, 'permanent_session_lifetime') else 3600
    if session_start:
        if hasattr(session_start, 'timestamp'):
            session_start_ts = session_start.timestamp()
        else:
            # If session_start is a string, parse it
            from datetime import datetime
            session_start_ts = datetime.strptime(session_start, "%Y-%m-%d %H:%M:%S.%f").timestamp()
        session_expiry_ts = session_start_ts + session_lifetime
    else:
        session_expiry_ts = int(time.time()) + session_lifetime

    try:
        if user.get("role") == "admin":
            total_questions = Question.query.count()
            total_papers = Paper.query.count()
            subjects_list = db.session.query(Question.subject).distinct().count()
            avg_difficulty_result = db.session.query(db.func.avg(db.cast(db.func.substr(Question.difficulty, 1, 1), db.Integer))).scalar() or 0
            total_paper_questions = db.session.query(db.func.count()).select_from(PaperQuestion).scalar() or 0
        else:
            total_questions = Question.query.filter_by(owner_email=user_email).count()
            total_papers = Paper.query.filter_by(owner_email=user_email).count()
            subjects_list = db.session.query(Question.subject).filter(Question.owner_email == user_email).distinct().count()
            avg_difficulty_result = db.session.query(db.func.avg(db.cast(db.func.substr(Question.difficulty, 1, 1), db.Integer))).filter(Question.owner_email == user_email).scalar() or 0
            total_paper_questions = db.session.query(db.func.count()).select_from(PaperQuestion).join(Paper).filter(Paper.owner_email == user_email).scalar() or 0
        average_questions_per_paper = round(total_paper_questions / total_papers, 1) if total_papers > 0 else 0
    except Exception:
        total_questions = 0
        total_papers = 0

    return render_template(
        "faculty/faculty_dashboard.html",
        faculty_name=user["name"],
        total_questions=total_questions,
        total_papers=total_papers,
        total_subjects=subjects_list,
        avg_difficulty=round(float(avg_difficulty_result), 1),
        average_questions_per_paper=average_questions_per_paper,
        session_expiry_ts=int(session_expiry_ts)
    )

# faculty question bank and paper generator routes are handled in blueprints

@app.route("/faculty/analytics")
@require_role("faculty")
def faculty_analytics():
    user = session.get("user")

    from models.question_bank import Question
    from models.paper import Paper

    try:
        import datetime
        from sqlalchemy import func, cast, Date, extract
        if user.get("role") == "admin":
            total_questions = Question.query.count() or 0
            subjects = list(db.session.query(Question.subject, db.func.count(Question.id)).group_by(Question.subject).all()) or []
            topics = list(db.session.query(Question.topic, db.func.count(Question.id)).group_by(Question.topic).all()) or []
            difficulty_dist = list(db.session.query(Question.difficulty, db.func.count(Question.id)).group_by(Question.difficulty).all()) or []
            bloom_dist = list(db.session.query(Question.bloom_level, db.func.count(Question.id)).group_by(Question.bloom_level).all()) or []
            co_dist = list(db.session.query(Question.co_level, db.func.count(Question.id)).group_by(Question.co_level).all()) or []
            total_papers = Paper.query.count() or 0
            papers_time = list(db.session.query(db.func.strftime('%Y-%m', Paper.created_at), db.func.count(Paper.id)).group_by(db.func.strftime('%Y-%m', Paper.created_at)).order_by(db.func.strftime('%Y-%m', Paper.created_at)).all()) or []
            # Day-wise, 6-hour bracket
            papers_day_bracket = list(db.session.query(
                func.strftime('%Y-%m-%d', Paper.created_at),
                ((extract('hour', Paper.created_at) / 6).cast(db.Integer) * 6).label('bracket'),
                func.count(Paper.id)
            ).group_by(func.strftime('%Y-%m-%d', Paper.created_at), 'bracket').order_by(func.strftime('%Y-%m-%d', Paper.created_at), 'bracket').all())
        else:
            user_email = user.get("email")
            total_questions = Question.query.filter_by(owner_email=user_email).count() or 0
            subjects = list(db.session.query(Question.subject, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.subject).all()) or []
            topics = list(db.session.query(Question.topic, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.topic).all()) or []
            difficulty_dist = list(db.session.query(Question.difficulty, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.difficulty).all()) or []
            bloom_dist = list(db.session.query(Question.bloom_level, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.bloom_level).all()) or []
            co_dist = list(db.session.query(Question.co_level, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.co_level).all()) or []
            total_papers = Paper.query.filter_by(owner_email=user_email).count() or 0
            papers_time = list(db.session.query(db.func.strftime('%Y-%m', Paper.created_at), db.func.count(Paper.id)).filter(Paper.owner_email == user_email).group_by(db.func.strftime('%Y-%m', Paper.created_at)).order_by(db.func.strftime('%Y-%m', Paper.created_at)).all()) or []
            papers_day_bracket = list(db.session.query(
                func.strftime('%Y-%m-%d', Paper.created_at),
                ((extract('hour', Paper.created_at) / 6).cast(db.Integer) * 6).label('bracket'),
                func.count(Paper.id)
            ).filter(Paper.owner_email == user_email)
            .group_by(func.strftime('%Y-%m-%d', Paper.created_at), 'bracket')
            .order_by(func.strftime('%Y-%m-%d', Paper.created_at), 'bracket').all())
    except Exception:
        total_questions = 0
        total_papers = 0
        subjects = []
        difficulty_dist = []
        bloom_dist = []
        co_dist = []
        papers_time = []

    return render_template(
        "faculty/faculty_analytics.html",
        total_questions=total_questions,
        total_papers=total_papers,
        subjects=subjects,
        topics=topics,
        difficulty_dist=difficulty_dist,
        bloom_dist=bloom_dist,
        co_dist=co_dist,
        papers_time=papers_time,
        papers_day_bracket=papers_day_bracket
    )

@app.route("/faculty/history")
@require_role("faculty")
def faculty_history():
    user = session.get("user")

    from models.paper import Paper

    if user.get("role") == "admin":
        papers = Paper.query.options(db.joinedload(Paper.questions)).order_by(Paper.created_at.desc()).all()
    else:
        papers = Paper.query.options(db.joinedload(Paper.questions)).filter_by(owner_email=user.get("email")).order_by(Paper.created_at.desc()).all()

    return render_template("faculty/faculty_history.html", papers=papers)

@app.route("/faculty/settings")
@require_role("faculty")
def faculty_settings():
    user = session.get("user")

    return render_template("faculty/faculty_settings.html", user=user)

@app.route("/faculty/settings/update", methods=["POST"])
@require_role("faculty")
def update_settings():
    user = session.get("user")
    original_email = user.get("email")  # Store original email before updating session

    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")

    # Update session
    if email:
        session["user"]["email"] = email
    if name:
        session["user"]["name"] = name
    if password:
        session["user"]["password"] = password

    # Persist to users.txt using original email to find the user
    users = _read_all_users_from_file()
    updated = False
    for u in users:
        if u["email"] == original_email:
            if email:
                u["email"] = email
            if name:
                u["name"] = name
            if password:
                u["password"] = password
            updated = True
            break

    if updated:
        _write_all_users_to_file(users)

    session.modified = True
    flash("Settings updated successfully", "success")
    return redirect(url_for("faculty_settings"))


@app.route("/admin-dev")
def admin_dev():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return redirect("/login")
    return redirect(url_for("admin.dashboard"))


@app.context_processor
def inject_user():
    user = session.get("user")
    import datetime
    session_start = session.get('_session_start')
    if session_start:
        now = datetime.datetime.utcnow()
        # If session_start is a string (from session), parse it
        if isinstance(session_start, str):
            from datetime import datetime
            try:
                session_start = datetime.fromisoformat(session_start)
            except Exception:
                session_start = now
        # Make both datetimes naive (no tzinfo)
        if hasattr(session_start, 'tzinfo') and session_start.tzinfo is not None:
            session_start = session_start.replace(tzinfo=None)
        session_duration = now - session_start
    else:
        session_duration = datetime.timedelta(0)
    
    return {
        "faculty_name": user["name"] if user else "Guest",
        "user_role": user["role"] if user else None,
        "session_duration": session_duration
        # Don't add session here - Flask provides it automatically in templates
    }


@app.route("/logout")
def logout():
    import datetime
    from models import SessionLog, db
    user = session.get("user")
    session_start = session.get('_session_start')
    now = get_ist_now()
    # Ensure both now and session_start are timezone-aware and in IST
    if user and session_start:
        email = user.get("email")
        # Try to parse session_start if string
        if isinstance(session_start, str):
            try:
                from datetime import datetime as dt
                from zoneinfo import ZoneInfo
                session_start = dt.fromisoformat(session_start)
                if session_start.tzinfo is None:
                    session_start = session_start.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except Exception:
                session_start = now
        elif hasattr(session_start, 'tzinfo') and session_start.tzinfo is None:
            try:
                from zoneinfo import ZoneInfo
                session_start = session_start.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except Exception:
                pass
        # Now both now and session_start should be aware and in IST
        duration = now - session_start
        duration_seconds = int(duration.total_seconds())
        try:
            log = SessionLog.query.filter_by(email=email).order_by(SessionLog.login_time.desc()).first()
            if log:
                log.logout_time = get_ist_now()  # IST
                log.session_duration_seconds = duration_seconds
                db.session.commit()
        except Exception as e:
            print(f"Error updating session log: {e}")
    session.clear()
    return redirect("/login")

# --- AUTO LOGOUT HANDLER ---
@app.before_request
def auto_logout_if_expired():
    import time
    from models import SessionLog, db
    user = session.get("user")
    session_start = session.get('_session_start')
    if user and session_start:
        session_lifetime = app.permanent_session_lifetime.total_seconds() if hasattr(app, 'permanent_session_lifetime') else 3600
        # Parse session_start if string
        if isinstance(session_start, str):
            try:
                from datetime import datetime as dt
                session_start_dt = dt.fromisoformat(session_start)
                session_start_ts = session_start_dt.timestamp()
            except Exception:
                session_start_ts = time.time()
        elif hasattr(session_start, 'timestamp'):
            session_start_ts = session_start.timestamp()
        else:
            session_start_ts = time.time()
        now_ts = time.time()
        if now_ts > session_start_ts + session_lifetime:
            # Session expired, log out user and update SessionLog
            email = user.get("email")
            now = get_ist_now()
            try:
                log = SessionLog.query.filter_by(email=email).order_by(SessionLog.login_time.desc()).first()
                if log and not log.logout_time:
                    log.logout_time = get_ist_now()  # IST
                    log.session_duration_seconds = int(now_ts - session_start_ts)
                    db.session.commit()
            except Exception as e:
                print(f"Error updating session log (auto logout): {e}")
            session.clear()
            flash("Session expired. You have been logged out.", "error")
            return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)