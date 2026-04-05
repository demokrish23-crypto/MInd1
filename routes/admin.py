from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.question_bank import Question
from models.paper import Paper, PaperQuestion

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin/paper/<int:paper_id>", endpoint="view_paper_admin")
def admin_view_paper(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    return render_template("paper/paper_preview.html", subject=paper.subject, paper=paper)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.question_bank import Question
from models.paper import Paper, PaperQuestion

admin_bp = Blueprint("admin", __name__)

@admin_bp.before_request
def check_admin():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        flash("Access denied: Admin only", "error")
        return redirect(url_for("faculty_dashboard"))

@admin_bp.route("/admin/dashboard")
def dashboard():
    from sqlalchemy import func, cast, String
    
    file_users = _read_all_users_from_file()
    total_users = len(file_users)
    faculty_count = len([u for u in file_users if u["role"] == "faculty"])
    
    try:
        total_questions = Question.query.count()
    except Exception:
        total_questions = 0
    
    try:
        total_papers = Paper.query.count()
    except Exception:
        total_papers = 0
    
    try:
        total_subjects = db.session.query(Question.subject).distinct().count()
    except Exception:
        total_subjects = 0
    
    try:
        faculty_q = db.session.query(func.count(Question.id)).scalar() or 0
    except Exception:
        faculty_q = 0
    
    avg_q_per_faculty = faculty_q / faculty_count if faculty_count > 0 else 0
    
    try:
        faculty_p = db.session.query(func.count(Paper.id)).scalar() or 0
    except Exception:
        faculty_p = 0
    
    avg_p_per_faculty = faculty_p / faculty_count if faculty_count > 0 else 0
    
    import os
    from flask import current_app
    db_path = os.path.join(current_app.instance_path, 'app.db')
    
    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        total_questions=total_questions,
        total_papers=total_papers,
        faculty_count=faculty_count,
        total_subjects=total_subjects,
        avg_q_per_faculty=avg_q_per_faculty,
        avg_p_per_faculty=avg_p_per_faculty,
        db_path=db_path
    )


def _read_all_users_from_file():
    users = []
    try:
        with open("users.txt", "r") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",")]
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


@admin_bp.route("/admin/users")
def manage_users():
    current_admin = session.get("user", {})
    current_admin_email = current_admin.get("email")

    file_users = _read_all_users_from_file()
    users = []

    for u in file_users:
        q_count = Question.query.filter_by(owner_email=u["email"]).count()
        p_count = Paper.query.filter_by(owner_email=u["email"]).count()
        password = u["password"]

        users.append({
            "id": u["email"],
            "email": u["email"],
            "name": u["name"],
            "role": u["role"],
            "password": password,
            "question_count": q_count,
            "paper_count": p_count
        })

    return render_template("admin/admin_users.html", users=users)


@admin_bp.route("/admin/add-user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        admin_add_pass = request.form.get("admin_add_pass", "").strip()

        if not email or not name or not password or not role or not admin_add_pass:
            flash("All fields are required", "error")
            return render_template("admin/add_user.html")

        if role not in ["faculty", "admin"]:
            flash("Invalid role selected.", "error")
            return render_template("admin/add_user.html")

        if admin_add_pass != "addme":
            flash("Incorrect admin add password.", "error")
            return render_template("admin/add_user.html")

        users = []
        try:
            with open("users.txt", "r") as f:
                for line in f:
                    parts = [p.strip() for p in line.strip().split(",")]
                    if len(parts) == 4 and parts[1].lower() == email.lower():
                        flash("A user with this email already exists.", "error")
                        return render_template("admin/add_user.html")
        except FileNotFoundError:
            pass

        try:
            with open("users.txt", "a") as f:
                f.write(f"{role},{email},{password},{name}\n")
            flash(f"User {email} created successfully", "success")
            return redirect(url_for("admin.manage_users"))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "error")
            return render_template("admin/add_user.html")

    return render_template("admin/add_user.html")


@admin_bp.route("/admin/edit-user/<user_id>")
def edit_user(user_id):
    file_users = _read_all_users_from_file()
    user = None
    for u in file_users:
        if u["email"] == user_id:
            user = u
            break
    
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("admin.manage_users"))
    
    return render_template(
        "admin/admin_edit_user.html",
        user_email=user["email"],
        user_name=user["name"]
    )


@admin_bp.route("/admin/edit-user/<user_id>/update", methods=["POST"])
def edit_user_update(user_id):
    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")
    
    if not email or not name:
        flash("Email and name are required", "danger")
        return redirect(url_for("admin.edit_user", user_id=user_id))
    
    
    file_users = _read_all_users_from_file()
    
    
    updated = False
    for user in file_users:
        if user["email"] == user_id:
            user["email"] = email
            user["name"] = name
            if password:
                user["password"] = password
            updated = True
            break
    
    if not updated:
        flash("User not found", "danger")
        return redirect(url_for("admin.manage_users"))
    
    
    _write_all_users_to_file(file_users)
    
    flash(f"User {name} updated successfully!", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/admin/delete-user/<user_id>", methods=["POST"])
def delete_user(user_id):
    
    Question.query.filter_by(owner_email=user_id).delete()
    Paper.query.filter_by(owner_email=user_id).delete()
    db.session.commit()

    
    users = _read_all_users_from_file()
    users = [u for u in users if u["email"] != user_id]
    _write_all_users_to_file(users)

    flash(f"User {user_id} and their content deleted", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/admin/questions")
def manage_questions():
    questions = Question.query.all()
    subjects = list(set(q.subject for q in questions))
    
    return render_template("admin/admin_questions.html", questions=questions, subjects=subjects)


@admin_bp.route("/admin/questions/delete/<int:q_id>", methods=["POST"])
def delete_question(q_id):
    question = Question.query.get_or_404(q_id)
    db.session.delete(question)
    db.session.commit()
    
    flash("Question deleted", "success")
    return redirect(url_for("admin.manage_questions"))


@admin_bp.route("/admin/papers")
def manage_papers():
    papers = Paper.query.options(db.joinedload(Paper.questions)).all()
    
    return render_template("admin/admin_papers.html", papers=papers)


@admin_bp.route("/admin/papers/delete/<int:paper_id>", methods=["POST"])
def delete_paper(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    db.session.delete(paper)
    db.session.commit()
    
    flash("Paper deleted", "success")
    return redirect(url_for("admin.manage_papers"))


@admin_bp.route("/admin/analytics")
def system_analytics():
    from sqlalchemy import func
    
    difficulty_dist = db.session.query(Question.difficulty, func.count(Question.id)).group_by(Question.difficulty).all()
    
    top_subjects = db.session.query(Question.subject, func.count(Question.id)).group_by(Question.subject).order_by(func.count(Question.id).desc()).limit(5).all()
    
    papers_by_diff = db.session.query(Paper.difficulty, func.count(Paper.id)).group_by(Paper.difficulty).all()
    
    faculty_emails = db.session.query(Question.owner_email).distinct().union(
        db.session.query(Paper.owner_email).distinct()
    ).all()
    faculty_emails = [e[0] for e in faculty_emails if e[0]]
    
    faculty_stats = []
    for email in faculty_emails:
        q_count = Question.query.filter_by(owner_email=email).count()
        p_count = Paper.query.filter_by(owner_email=email).count()
        faculty_stats.append((email, {"questions": q_count, "papers": p_count}))
    
    return render_template(
        "admin/admin_analytics.html",
        difficulty_dist=difficulty_dist,
        top_subjects=top_subjects,
        papers_by_diff=papers_by_diff,
        faculty_stats=faculty_stats
    )


@admin_bp.route("/admin/analytics/session-timeline")
def session_timeline_data():
    from models import SessionLog
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    try:
        now = datetime.utcnow()
        start_time = now - timedelta(hours=24)
        
        hourly_sessions = db.session.query(
            func.strftime('%Y-%m-%d %H:00', SessionLog.login_time).label('hour'),
            func.count(SessionLog.id).label('count')
        ).filter(SessionLog.login_time >= start_time).group_by('hour').all()
        
        hours = [h[0] if h[0] else '00:00' for h in hourly_sessions]
        counts = [h[1] for h in hourly_sessions]
        
        if not hours:
            hours = [(now - timedelta(hours=i)).strftime('%H:00') for i in range(24, -1, -1)]
            counts = [0] * 25
        
        return jsonify({"hours": hours, "counts": counts})
    except Exception as e:
        print(f"Error loading session timeline: {e}")
        return jsonify({"hours": [], "counts": []}), 500


@admin_bp.route("/admin/settings")
def admin_settings():
    user = session.get("user")
    from sqlalchemy import func
    import os
    from flask import current_app
    from datetime import datetime
    
    file_users = _read_all_users_from_file()
    total_users = len(file_users)
    faculty_count = len([u for u in file_users if u["role"] == "faculty"])
    
    try:
        total_questions = Question.query.count()
        total_papers = Paper.query.count()
        total_subjects = db.session.query(Question.subject).distinct().count()
    except Exception:
        total_questions = 0
        total_papers = 0
        total_subjects = 0
    
    db_path = os.path.join(current_app.instance_path, 'app.db')
    current_date = datetime.now().strftime("%B %d, %Y")
    
    return render_template(
        "admin/admin_settings.html",
        user=user,
        total_users=total_users,
        total_questions=total_questions,
        total_papers=total_papers,
        total_subjects=total_subjects,
        faculty_count=faculty_count,
        db_path=db_path,
        current_date=current_date
    )

@admin_bp.route("/admin/settings/update", methods=["POST"])
def admin_settings_update():
    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")
    
    current_email = session.get("user", {}).get("email")
    
    all_users = _read_all_users_from_file()
    
    for user in all_users:
        if user["email"] == current_email:
            user["email"] = email
            user["name"] = name
            if password:
                user["password"] = password
            break
    
    _write_all_users_to_file(all_users)
    
    session["user"]["email"] = email
    session["user"]["name"] = name
    
    flash("Settings updated successfully!", "success")
    return redirect(url_for("admin.admin_settings"))


@admin_bp.route("/admin/delete-database", methods=["POST"])
def delete_database():
    from flask import jsonify
    import os
    from flask import current_app
    
    provided_password = request.form.get("password", "")
    correct_password = "deleteme"
    
    if provided_password != correct_password:
        return jsonify({"success": False, "message": "Incorrect password"}), 401
    
    try:
        db.drop_all()
        
        db.create_all()
        db.session.commit()
        
        db_file = os.path.join(current_app.instance_path, 'app.db')
        if os.path.exists(db_file):
            os.remove(db_file)
        
        db.create_all()
        db.session.commit()
        
        return jsonify({"success": True, "message": "Database deleted and reset successfully"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@admin_bp.route("/admin/session-logs")
def session_logs():
    from models import SessionLog
    from sqlalchemy import func, desc

    try:
        logs_query = SessionLog.query.order_by(desc(SessionLog.login_time))
        total_logs = logs_query.count()
        show_all = request.args.get("all", "false").lower() in ("1", "true", "yes")

        if show_all:
            logs = logs_query.all()
        else:
            logs = logs_query.limit(200).all()

        faculty_logs = SessionLog.query.filter_by(role="faculty").count()
        admin_logs = SessionLog.query.filter_by(role="admin").count()
        unique_users = db.session.query(func.count(func.distinct(SessionLog.email))).scalar() or 0
    except Exception as e:
        logs = []
        total_logs = 0
        faculty_logs = 0
        admin_logs = 0
        unique_users = 0
        print(f"Error fetching session logs: {e}")

    return render_template(
        "admin/session_logs.html",
        logs=logs,
        total_logs=total_logs,
        faculty_logs=faculty_logs,
        admin_logs=admin_logs,
        unique_users=unique_users,
        show_all=show_all
    )


@admin_bp.route("/admin/session-logs/data")
def session_logs_data():
    from models import SessionLog
    from sqlalchemy import desc

    try:
        logs = SessionLog.query.order_by(desc(SessionLog.login_time)).all()
        data = []
        for log in logs:
            data.append({
                "email": log.email,
                "name": log.name,
                "role": log.role,
                "login_time": log.login_time.isoformat() if log.login_time else None,
                "logout_time": log.logout_time.isoformat() if log.logout_time else None,
                "duration_seconds": log.session_duration_seconds,
                "ip_address": log.ip_address,
            })
        return jsonify({"success": True, "logs": data, "total_logs": len(data)})
    except Exception as e:
        print(f"Error fetching session logs data: {e}")
        return jsonify({"success": False, "error": str(e), "logs": []}), 500
