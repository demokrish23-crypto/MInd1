from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import random

from models import db
from models.paper import Paper, PaperQuestion
from services.syllabus_parser import parse_syllabus
from services.bloom_engine import generate_question

paper_bp = Blueprint("paper", __name__)

ITEMS_PER_PAGE = 10

@paper_bp.before_request
def check_faculty_access():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    if user.get("role") == "admin":
        flash("Admins cannot access faculty features", "error")
        return redirect(url_for("admin.dashboard"))

@paper_bp.route("/faculty/paper-generator", methods=["GET", "POST"])
def paper_generator():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        syllabus_text = request.form.get("syllabus", "").strip()
        marks_raw = request.form.get("marks") or request.form.getlist("marks")
        if isinstance(marks_raw, str):
            marks_selected = [int(m) for m in marks_raw.split(",") if m.isdigit() and int(m) in (2, 4, 8)]
        else:
            marks_selected = [int(m) for m in marks_raw if str(m).isdigit() and int(m) in (2, 4, 8)]
        blooms_raw = request.form.get("blooms", "")
        selected_blooms = [b.strip() for b in blooms_raw.split(",") if b.strip()]
        BLOOM_MAP = {
            "Remember": "Remembering",
            "Understand": "Understanding",
            "Apply": "Applying",
            "Analyze": "Analyzing",
            "Evaluate": "Evaluating",
            "Create": "Creating"
        }
        selected_blooms = [BLOOM_MAP.get(b, b) for b in selected_blooms]

        try:
            duration = int(request.form.get("duration", 120))
            if duration < 30 or duration > 240:
                duration = 120
        except (TypeError, ValueError):
            duration = 120

        try:
            difficulty = int(request.form.get("difficulty", 2))
        except ValueError:
            difficulty = 2

        if not subject or not syllabus_text or not marks_selected or not selected_blooms:
            flash("All fields are required", "error")
            return render_template("faculty/faculty_paper_generator.html")

        topics = parse_syllabus(syllabus_text)
        if not topics:
            flash("Invalid syllabus text: no topics found",  "error")
            return render_template("faculty/faculty_paper_generator.html")

        user = session.get("user")
        paper = Paper(subject=subject, difficulty=difficulty, owner_email=user.get("email"))
        session["current_paper_duration"] = duration

        db.session.add(paper)
        db.session.commit()

        used_questions = set()
        question_count = min(60, max(5, len(topics) * difficulty + len(marks_selected) * 2))

        generated = 0
        max_attempts = question_count * 10
        attempts = 0
        while generated < question_count and attempts < max_attempts:
            topic = random.choice(topics)
            marks = random.choice(marks_selected)
            found = False
            question_text = bloom_level = co_level = None
            for _ in range(20):
                qt, bl, cl = generate_question(topic, marks, used_questions, difficulty=difficulty, index=generated)
                if bl in selected_blooms:
                    question_text, bloom_level, co_level = qt, bl, cl
                    found = True
                    break
            if found:
                q_item = PaperQuestion(
                    paper_id=paper.id,
                    topic=topic,
                    marks=marks,
                    text=question_text,
                    bloom_level=bloom_level,
                    co_level=co_level,
                    is_selected=False
                )
                db.session.add(q_item)
                generated += 1
            attempts += 1
        if generated == 0:
            flash("Could not generate any questions with the selected marks and Bloom's levels. Try different options.", "error")
            return render_template("faculty/faculty_paper_generator.html")

        db.session.commit()

        session["current_paper_id"] = paper.id
        return redirect(url_for("paper.review_questions", paper_id=paper.id))

    return render_template("faculty/faculty_paper_generator.html")


@paper_bp.route("/faculty/paper-delete/<int:paper_id>", methods=["POST"])
def delete_paper(paper_id):
    user = session.get("user")
    if not user:
        flash("You must be logged in to delete a paper.", "error")
        return redirect(url_for("login"))
    paper = Paper.query.get_or_404(paper_id)
    if paper.owner_email != user.get("email"):
        flash("You do not have permission to delete this paper.", "error")
        return redirect(url_for("faculty_history"))
    PaperQuestion.query.filter_by(paper_id=paper_id).delete()
    db.session.delete(paper)
    db.session.commit()
    flash("Paper deleted successfully.", "success")
    return redirect(url_for("faculty_history"))


@paper_bp.route("/faculty/paper-review/<int:paper_id>", methods=["GET", "POST"])
def review_questions(paper_id):
    paper = Paper.query.get_or_404(paper_id)

    bloom_filter = request.args.get("bloom", "all").strip()
    co_filter = request.args.get("co", "all").strip()
    topic_filter = request.args.get("topic", "all").strip()
    sort_filter = request.args.get("sort", "id").strip()
    exclude_filter = request.args.get("exclude", "").strip()
    show_selected_filter = request.args.get("show_selected", "0").strip() == "1"
    marks_filter = request.args.get("marks", "all").strip()
    search_filter = request.args.get("search", "").strip()

    if request.method == "POST":
        selected_ids = [int(q_id) for q_id in request.form.getlist("select_question") if q_id.isdigit()]
        bloom_filter = request.form.get("bloom", bloom_filter).strip()

        if not selected_ids:
            flash("Select at least one question", "error")
            query = PaperQuestion.query.filter_by(paper_id=paper_id)
            if bloom_filter and bloom_filter.lower() != "all":
                query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))
            questions = query.order_by(PaperQuestion.id).all()
            duration = session.get("current_paper_duration", 120)
            return render_template("faculty/faculty_review_questions.html", questions=questions, paper=paper, has_more=False, duration=duration, bloom_filter=bloom_filter)

        PaperQuestion.query.filter_by(paper_id=paper_id).update({"is_selected": False})
        PaperQuestion.query.filter(PaperQuestion.id.in_(selected_ids)).update({"is_selected": True}, synchronize_session=False)
        db.session.commit()

        return redirect(url_for("paper.export_paper", paper_id=paper_id))


    query = PaperQuestion.query.filter_by(paper_id=paper_id)
    if bloom_filter and bloom_filter.lower() != "all":
        query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))
    if co_filter and co_filter.lower() != "all":
        co_vals = [c.strip() for c in co_filter.split(",") if c.strip()]
        if co_vals:
            query = query.filter(PaperQuestion.co_level.in_(co_vals))
    if topic_filter and topic_filter.lower() != "all":
        topic_vals = [t.strip() for t in topic_filter.split(",") if t.strip()]
        if topic_vals:
            query = query.filter(PaperQuestion.topic.in_(topic_vals))
        if exclude_filter:
            import re
            exclude_words = re.split(r'[\s,]+', exclude_filter)
            for w in exclude_words:
                w = w.strip()
                if w:
                    query = query.filter(~PaperQuestion.text.op('~*')(fr'\\m{re.escape(w)}\\M'))
        if show_selected_filter:
            query = query.filter(PaperQuestion.is_selected == True)
    if marks_filter and marks_filter.lower() != "all":
        try:
            marks_val = int(marks_filter)
            query = query.filter(PaperQuestion.marks == marks_val)
        except ValueError:
            pass
    if search_filter:
        query = query.filter(PaperQuestion.text.ilike(f"%{search_filter}%"))

    if sort_filter == "marks":
        query = query.order_by(PaperQuestion.marks.desc())
    elif sort_filter == "bloom_level":
        query = query.order_by(PaperQuestion.bloom_level)
    elif sort_filter == "co_level":
        query = query.order_by(PaperQuestion.co_level)
    elif sort_filter == "topic":
        query = query.order_by(PaperQuestion.topic)
    else:
        query = query.order_by(PaperQuestion.id)
    questions = query.all()
    duration = session.get("current_paper_duration", 120)

    avg_difficulty = 'N/A'
    from models.question_bank import Question
    qids = [q.id for q in questions]
    if qids:
        qbank = {q.id: q for q in Question.query.filter(Question.id.in_(qids)).all()}
        diffs = []
        for q in questions:
            qbank_q = qbank.get(q.id)
            if qbank_q:
                try:
                    diffs.append(float(qbank_q.difficulty))
                except Exception:
                    pass
        if diffs:
            avg_difficulty = round(sum(diffs) / len(diffs), 1)

    co_levels = [row[0] for row in db.session.query(PaperQuestion.co_level).filter_by(paper_id=paper_id).distinct().order_by(PaperQuestion.co_level).all() if row[0]]
    topics = [row[0] for row in db.session.query(PaperQuestion.topic).filter_by(paper_id=paper_id).distinct().order_by(PaperQuestion.topic).all() if row[0]]

    return render_template(
        "faculty/faculty_review_questions.html",
        questions=questions,
        paper=paper,
        has_more=False,
        duration=duration,
        bloom_filter=bloom_filter,
        co_filter=co_filter,
        topic_filter=topic_filter,
        marks_filter=marks_filter,
        search_filter=search_filter,
        sort_filter=sort_filter,
        exclude_filter=exclude_filter,
        show_selected_filter=show_selected_filter,
        co_levels=co_levels,
        topics=topics,
        avg_difficulty=avg_difficulty
    )


@paper_bp.route("/faculty/paper-review/<int:paper_id>/questions")
def review_questions_page(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", ITEMS_PER_PAGE, type=int)
    bloom_filter = request.args.get("bloom", "all").strip()

    query = PaperQuestion.query.filter_by(paper_id=paper_id)
    if bloom_filter and bloom_filter.lower() != "all":
        query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))

    query = query.order_by(PaperQuestion.id)
    total = query.count()
    questions = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "paper_id": paper_id,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_more": (page * per_page) < total,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "marks": q.marks,
                "topic": q.topic,
                "bloom_level": q.bloom_level,
                "co_level": q.co_level,
                "is_selected": q.is_selected,
            }
            for q in questions
        ],
    })


@paper_bp.route("/export/<int:paper_id>")
def export_paper(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    selected_questions = PaperQuestion.query.filter_by(paper_id=paper_id, is_selected=True).all()

    if not selected_questions:
        return "No questions selected for export. Go back to review and choose questions.", 400

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        return "reportlab package not found. Install with pip install reportlab.", 500

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Question Paper: {paper.subject}", styles["Title"]))
    story.append(Paragraph(f"Date: {paper.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    for idx, q in enumerate(selected_questions, start=1):
        story.append(Paragraph(f"{idx}. ({q.marks} Marks) {q.text}", styles["BodyText"]))
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    buffer.seek(0)

    file_name = f"{paper.subject.replace(' ', '_')}_paper_{paper.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=file_name, mimetype="application/pdf")


@paper_bp.route("/faculty/paper-review/delete-question/<int:qid>", methods=["POST"])
def delete_question_from_paper(qid):
    user = session.get("user")
    if not user:
        return jsonify(success=False, error="Not logged in"), 401
    q = PaperQuestion.query.get_or_404(qid)
    paper = Paper.query.get(q.paper_id)
    if not paper or paper.owner_email != user.get("email"):
        return jsonify(success=False, error="Permission denied"), 403
    db.session.delete(q)
    db.session.commit()
    return jsonify(success=True)


@paper_bp.route("/faculty/paper-review/delete-question/bulk", methods=["POST"])
def bulk_delete_questions():
    user = session.get("user")
    if not user:
        return jsonify(success=False, error="Not logged in"), 401
    data = request.get_json()
    ids = data.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify(success=False, error="No IDs provided"), 400
    deleted_ids = []
    failed_ids = []
    for qid in ids:
        try:
            q = PaperQuestion.query.get(qid)
            if not q:
                failed_ids.append(qid)
                continue
            paper = Paper.query.get(q.paper_id)
            if not paper or paper.owner_email != user.get("email"):
                failed_ids.append(qid)
                continue
            db.session.delete(q)
            deleted_ids.append(qid)
        except Exception:
            failed_ids.append(qid)
    if deleted_ids:
        db.session.commit()
    return jsonify(success=True, deleted_ids=deleted_ids, failed_ids=failed_ids)
