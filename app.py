import os
import json
import sqlite3
import uuid
import email
from io import BytesIO
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from dotenv import load_dotenv # 1..env load karnyasathi
from groq import Groq # 2. Fakt 1 dach import
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

#.env file madhun variables load kara
load_dotenv()

app = Flask(__name__)
app.secret_key = "careerlens_ai_secret_2026"
UPLOAD_FOLDER = os.path.join(
    app.static_folder,
    "uploads",
    "profile"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)
# Database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "careerlens.db")

# Groq client -.env madhun key gheil
JOBS_API_KEY = os.getenv("JOBS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Please set it in.env file")

groq_client = Groq(api_key=GROQ_API_KEY)



# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

 # =========================================================
# CREATE DATABASE TABLES
# =========================================================

def init_db():

    conn = get_db()
    

    print("DATABASE USED:", DATABASE)
    print("REGISTER EMAIL:", email)
    cur = conn.cursor()

    # =====================================================
    # USERS TABLE
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            age INTEGER,

            gender TEXT,

            city TEXT,

            email TEXT UNIQUE NOT NULL,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            photo TEXT DEFAULT 'default.png',

            role TEXT NOT NULL DEFAULT 'student',

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)
    #===============================================
    # feedback
    # ===============================================    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        email TEXT,
        rating INTEGER,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # =====================================================
    # STUDENT PROFILE
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS student_profiles (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER UNIQUE NOT NULL,

            phone TEXT,

            education TEXT,

            college TEXT,

            branch TEXT,

            passing_year TEXT,

            percentage REAL DEFAULT 0,

            cgpa REAL DEFAULT 0,

            career_goal TEXT,

            skills TEXT,

            interests TEXT,

            certifications TEXT,

            projects TEXT,

            internships TEXT,

            achievements TEXT,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)


    # =====================================================
    # JOBS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company TEXT NOT NULL,

            role TEXT NOT NULL,

            description TEXT,

            skills TEXT,

            eligibility TEXT,

            location TEXT,

            package TEXT,

            deadline TEXT
        )
    """)


    # =====================================================
    # TEST RESULTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_results (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            test_name TEXT,

            score REAL,

            total REAL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
        )
    """)


    # =====================================================
    # CAREER ANALYSIS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS career_analysis (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            career TEXT,

            match_percentage REAL,

            reason TEXT,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
        )
    """)


    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            message TEXT,

            is_read INTEGER DEFAULT 0,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
        )
    """)


    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin = cur.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        ("admin@careerlens.ai",)
    ).fetchone()


    if not admin:

        cur.execute(
            """
            INSERT INTO users
            (
                name,
                age,
                gender,
                city,
                email,
                username,
                password,
                photo,
                role
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,

            (
                "CareerLens Admin",
                25,
                "",
                "",
                "admin@careerlens.ai",
                "admin",
                generate_password_hash("admin123"),
                "default.png",
                "admin"
            )
        )


    conn.commit()
  

    

    conn.close()

# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function



# =========================================================
# ROLE REQUIRED
# =========================================================

def role_required(role):

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):

            if session.get("role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("home"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator

@app.route("/ai_voice_interview")
def ai_voice_interview():
    
    return render_template("ai_voice_interviewer.html", groq_api_key=GROQ_API_KEY)
#=========================================================
# 2. AI FEEDBACK SATHI API ROUTE
@app.route("/ai_feedback", methods=["POST"])
def ai_feedback():
    data = request.get_json()
    question = data.get("question")
    answer = data.get("answer")

    prompt = f"""
    You are a professional HR interviewer for CareerLens AI.
    Question: "{question}"
    Candidate Answer: "{answer}"

    Give short 1 line feedback on the answer. Be supportive.
    Then ask the next logical interview question in a friendly tone.
    Keep total reply under 3 sentences. English only.
    """

    try:
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        reply = res.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        print("Groq Error:", e) # error terminal var disel
        return jsonify({"reply": "Sorry, I couldn't process that. Let's try the next question."}), 500

# =========================================================
# PHOTO UPLOAD SETTINGS
# =========================================================

UPLOAD_FOLDER = "static/uploads/profile"

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )
@app.route("/feedback", methods=["GET", "POST"])
def feedback():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        rating = request.form.get("rating", "5")
        message = request.form.get("message", "").strip()

        if not message:
            flash("Please enter your feedback.", "warning")
            return redirect(url_for("feedback"))

        try:
            rating = int(rating)

            if rating < 1 or rating > 5:
                rating = 5

        except ValueError:
            rating = 5

        user_id = session.get("user_id")

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO feedback
                (
                    user_id,
                    name,
                    email,
                    rating,
                    message
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                name,
                email,
                rating,
                message
            ))

            conn.commit()

            flash(
                "Thank you! Your feedback has been submitted.",
                "success"
            )

        except Exception as e:

            conn.rollback()

            print(
                "FEEDBACK ERROR:",
                e
            )

            flash(
                "Something went wrong while submitting feedback.",
                "danger"
            )

        finally:
            conn.close()

        return redirect(
            url_for("feedback")
        )

    return render_template(
        "feedback.html"
    )
@app.route("/job-details/<int:job_id>")
@login_required
def job_details(job_id):

    conn = get_db()

    try:
        job = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,)
        ).fetchone()

        if not job:
            flash("Job not found.", "warning")
            return redirect(url_for("jobs"))

        return render_template(
            "job_details.html",
            job=job
        )

    finally:
        conn.close()

@app.route("/career_readiness")
@login_required
def career_readiness():

    user_id = session.get("user_id")

    conn = get_db()

    try:

        # -----------------------------
        # TEST SCORES
        # -----------------------------

        aptitude = conn.execute("""
            SELECT
                COALESCE(SUM(score), 0) AS score,
                COALESCE(SUM(total), 0) AS total
            FROM test_results
            WHERE user_id = ?
            AND LOWER(test_name) LIKE '%aptitude%'
        """, (user_id,)).fetchone()

        technical = conn.execute("""
            SELECT
                COALESCE(SUM(score), 0) AS score,
                COALESCE(SUM(total), 0) AS total
            FROM test_results
            WHERE user_id = ?
            AND (
                LOWER(test_name) LIKE '%technical%'
                OR LOWER(test_name) LIKE '%technical mcq%'
            )
        """, (user_id,)).fetchone()

        interview = conn.execute("""
            SELECT
                COALESCE(SUM(score), 0) AS score,
                COALESCE(SUM(total), 0) AS total
            FROM test_results
            WHERE user_id = ?
            AND LOWER(test_name) LIKE '%interview%'
        """, (user_id,)).fetchone()


        # -----------------------------
        # SCORE FUNCTION
        # -----------------------------

        def calculate_score(row):

            if not row:
                return 0

            score = float(row["score"] or 0)
            total = float(row["total"] or 0)

            if total <= 0:
                return 0

            percentage = (score / total) * 100

            return round(min(percentage, 100))


        aptitude_score = calculate_score(aptitude)
        technical_score = calculate_score(technical)
        interview_score = calculate_score(interview)


        # -----------------------------
        # STUDENT PROFILE
        # -----------------------------

        profile = conn.execute("""
            SELECT *
            FROM student_profiles
            WHERE user_id = ?
        """, (user_id,)).fetchone()


        # -----------------------------
        # RESUME COMPLETION
        # -----------------------------

        resume_score = 0

        if profile:

            fields = [
                "education",
                "college",
                "branch",
                "career_goal",
                "skills",
                "interests",
                "certifications",
                "projects",
                "internships",
                "achievements"
            ]

            completed = 0

            for field in fields:

                value = profile[field]

                if value and str(value).strip():
                    completed += 1

            resume_score = round(
                (completed / len(fields)) * 100
            )


        # -----------------------------
        # OVERALL READINESS
        # -----------------------------

        overall = round(
            (
                aptitude_score +
                technical_score +
                interview_score +
                resume_score
            ) / 4
        )


        # -----------------------------
        # AI SUGGESTIONS
        # -----------------------------

        suggestions = []

        if aptitude_score < 70:
            suggestions.append(
                "Practice aptitude and logical reasoning regularly."
            )

        if technical_score < 70:
            suggestions.append(
                "Improve your technical concepts and coding skills."
            )

        if interview_score < 70:
            suggestions.append(
                "Practice more interview questions and improve communication."
            )

        if resume_score < 70:
            suggestions.append(
                "Complete your profile, projects, skills and certifications."
            )

        if not suggestions:
            suggestions.append(
                "Great progress! Keep practicing and stay consistent."
            )


        return render_template(
            "career_readiness.html",
            aptitude_score=aptitude_score,
            technical_score=technical_score,
            interview_score=interview_score,
            resume_score=resume_score,
            overall=overall,
            suggestions=suggestions
        )

    finally:

        conn.close()
#========================================
@app.route("/guidance")
def guidance():
    return render_template("guindance.html")


@app.route("/api/career-guidance", methods=["POST"])
def career_guidance_api():

    data = request.get_json()

    education = data.get("education", "")
    year = data.get("year", "")
    interest = data.get("interest", "")
    experience = data.get("experience", "")
    skills = data.get("skills", [])
    goal = data.get("goal", "")

    prompt = f"""
You are CareerLens.ai, an AI career guidance assistant.

Student information:

Education: {education}
Current Year: {year}
Career Interest: {interest}
Experience: {experience}
Skills: {skills}
Career Goal: {goal}

Give personalized career guidance.

Return ONLY valid JSON:

{{
    "career_title": "",
    "description": "",
    "why": "",
    "skills": [],
    "learning": [],
    "placement_focus": "",
    "roadmap": []
}}
"""

    try:

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": "You are a professional AI career counselor."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.4
        )

        result_text = response.choices[0].message.content.strip()

        # AI ने markdown JSON दिल्यास ते remove कर
        if result_text.startswith(""):

            result_text = result_text.replace(
                "json", ""
            )

            result_text = result_text.replace(
                "```", ""
            )

            result_text = result_text.strip()

        import json

        result = json.loads(result_text)

        return jsonify({
            "success": True,
            "result": result
        })

    except Exception as e:

        print("CAREER GUIDANCE ERROR:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/aptitude")
def aptitude():
    return render_template("aptitude.html")

@app.route("/technical_mcq")
def technical_mcq():
    return render_template("technical_mcq.html")    

@app.route("/company-jobs")
def company_jobs():

    query = request.args.get("q", "software developer").strip()
    location = request.args.get("location", "India").strip()

    jobs = []
    error = None

    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        error = "Job API credentials are missing."

    else:

        url = (
            "https://api.adzuna.com/v1/api/"
            "jobs/in/search/1"
        )

        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 20,
            "what": query,
            "where": location,
            "content-type": "application/json"
        }

        try:

            response = requests.get(
                url,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            jobs = data.get("results", [])

        except requests.RequestException as e:

            print("JOB API ERROR:", e)

            error = (
                "Unable to load live jobs right now. "
                "Please try again."
            )

    return render_template(
        "jobs.html",
        jobs=jobs,
        query=query,
        location=location,
        error=error
    )




#=======================================    
@app.route("/ai_assistant")
def ai_assistant():
    return render_template("ai_assistant.html")


@app.route("/ai_assistant/chat", methods=["POST"])
def ai_assistant_chat():

    try:

        data = request.get_json()

        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({
                "success": False,
                "reply": "Please enter a question."
            })

        system_prompt = """
You are CareerLens AI Assistant.

CareerLens.ai is an AI-powered career and placement guidance platform
for students.

Your main responsibilities are:

1. Career guidance
2. Placement preparation
3. Interview preparation
4. Resume guidance
5. Technical skill guidance
6. Soft-skill guidance
7. Career roadmap creation
8. Explaining CareerLens features
9. Helping students choose suitable technologies and learning paths

Rules:

- Give clear and practical answers.
- Use simple language suitable for students.
- Prefer structured answers with headings and bullet points.
- Give step-by-step guidance when appropriate.
- Do not invent CareerLens features that were not provided.
- If you do not know something about the CareerLens project,
  clearly say that you don't have enough project information.
- Encourage learning and practice.
- Do not give dangerous or illegal instructions.
"""

        completion = groq_client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],

            temperature=0.7,

            max_tokens=800
        )

        reply = completion.choices[0].message.content

        return jsonify({
            "success": True,
            "reply": reply
        })

    except Exception as e:

        print("AI ASSISTANT ERROR:", e)

        return jsonify({
            "success": False,
            "reply": "AI Assistant is temporarily unavailable."
        }), 500
# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # =================================================
        # PERSONAL INFORMATION
        # =================================================

        name = request.form.get(
            "name",
            ""
        ).strip()

        age = request.form.get(
            "age",
            ""
        ).strip()

        gender = request.form.get(
            "gender",
            ""
        ).strip()

        city = request.form.get(
            "city",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()


        # =================================================
        # EDUCATION
        # =================================================

        education = request.form.get(
            "education",
            ""
        ).strip()

        branch = request.form.get(
            "branch",
            ""
        ).strip()

        college = request.form.get(
            "college",
            ""
        ).strip()

        career_goal = request.form.get(
            "career_goal",
            ""
        ).strip()


        # =================================================
        # ACCOUNT
        # =================================================

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # =================================================
        # BASIC VALIDATION
        # =================================================

        if not name:
            flash(
                "Please enter your name.",
                "danger"
            )
            return redirect(url_for("register"))


        if not email:
            flash(
                "Please enter your email.",
                "danger"
            )
            return redirect(url_for("register"))


        if not username:
            flash(
                "Please create a username.",
                "danger"
            )
            return redirect(url_for("register"))


        if not password:
            flash(
                "Please create a password.",
                "danger"
            )
            return redirect(url_for("register"))


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        # =================================================
        # PHOTO UPLOAD
        # =================================================

        photo = request.files.get("photo")

        photo_filename = "default.png"


        if photo and photo.filename:

            if not allowed_file(photo.filename):

                flash(
                    "Only JPG, JPEG, PNG and WEBP images are allowed.",
                    "danger"
                )

                return redirect(
                    url_for("register")
                )


            extension = photo.filename.rsplit(
                ".",
                1
            )[1].lower()


            unique_name = (
                str(uuid.uuid4())
                + "."
                + extension
            )


            photo_filename = secure_filename(
                unique_name
            )


            photo_path = os.path.join(

                app.config["UPLOAD_FOLDER"],

                photo_filename

            )


            photo.save(photo_path)


        # =================================================
        # PASSWORD HASH
        # =================================================

        password_hash = generate_password_hash(
            password
        )


        # =================================================
        # DATABASE
        # =================================================

        conn = get_db()


        try:

            # ---------------------------------------------
            # CHECK EMAIL
            # ---------------------------------------------

            existing_email = conn.execute(
                """
                SELECT id
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()


            if existing_email:

                flash(
                    "This email is already registered.",
                    "warning"
                )

                return redirect(
                    url_for("register")
                )


            # ---------------------------------------------
            # CHECK USERNAME
            # ---------------------------------------------

            existing_username = conn.execute(
                """
                SELECT id
                FROM users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()


            if existing_username:

                flash(
                    "Username already exists. Please choose another.",
                    "warning"
                )

                return redirect(
                    url_for("register")
                )


            # =============================================
            # INSERT USER
            # =============================================

            cursor = conn.execute(
                """
                INSERT INTO users
                (
                    name,
                    age,
                    gender,
                    city,
                    email,
                    username,
                    password,
                    photo,
                    role
                )

                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,

                (
                    name,
                    age if age else None,
                    gender,
                    city,
                    email,
                    username,
                    password_hash,
                    photo_filename,
                    "student"
                )
            )


            user_id = cursor.lastrowid


            # =============================================
            # INSERT STUDENT PROFILE
            # =============================================

            conn.execute(
                """
                INSERT INTO student_profiles
                (
                    user_id,
                    phone,
                    education,
                    college,
                    branch,
                    career_goal
                )

                VALUES
                (?, ?, ?, ?, ?, ?)
                """,

                (
                    user_id,
                    phone,
                    education,
                    college,
                    branch,
                    career_goal
                )
            )


            # =============================================
            # SAVE
            # =============================================

            conn.commit()


            flash(
                "Account created successfully! Please login.",
                "success"
            )


            return redirect(
                url_for("login")
            )


        except sqlite3.IntegrityError as e:

            conn.rollback()

            print(
                "REGISTER DATABASE ERROR:",
                e
            )

            flash(
                "Email or username already exists.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        except Exception as e:

            conn.rollback()

            print(
                "REGISTER ERROR:",
                e
            )

            flash(
                "Something went wrong while creating your account.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        finally:

            conn.close()


    # =====================================================
    # GET
    # =====================================================

    return render_template(
        "register.html"
    )
# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("home.html")

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        print("====================================")
        print("LOGIN ATTEMPT")
        print("EMAIL:", repr(email))
        print("PASSWORD ENTERED:", bool(password))

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not email or not password:

            flash(
                "Please enter email and password.",
                "warning"
            )

            return redirect(url_for("login"))

        conn = get_db()

        try:

            # -------------------------------------------------
            # FIND USER
            # -------------------------------------------------

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(TRIM(email)) = ?
                LIMIT 1
                """,
                (email,)
            ).fetchone()

            # -------------------------------------------------
            # DEBUG
            # -------------------------------------------------

            if user:

                print("USER FOUND")
                print("USER ID:", user["id"])
                print("USER NAME:", user["name"])
                print("USER EMAIL:", user["email"])
                print("USER ROLE:", user["role"])
                print("PASSWORD HASH EXISTS:", bool(user["password"]))

            else:

                print("USER NOT FOUND FOR EMAIL:", email)

        finally:

            conn.close()

        # -------------------------------------------------
        # USER NOT FOUND
        # -------------------------------------------------

        if not user:

            flash(
                "No account found with this email.",
                "danger"
            )

            return redirect(url_for("login"))

        # -------------------------------------------------
        # PASSWORD CHECK
        # -------------------------------------------------

        try:

            password_correct = check_password_hash(
                user["password"],
                password
            )

        except Exception as e:

            print("PASSWORD CHECK ERROR:", e)

            password_correct = False

        print("PASSWORD CORRECT:", password_correct)

        # -------------------------------------------------
        # WRONG PASSWORD
        # -------------------------------------------------

        if not password_correct:

            flash(
                "Incorrect password.",
                "danger"
            )

            return redirect(url_for("login"))

        # =================================================
        # LOGIN SUCCESS
        # =================================================

        session.clear()

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["email"] = user["email"]
        session["role"] = user["role"]
        session["photo"] = user["photo"]

        print("LOGIN SUCCESS")
        print("REDIRECT ROLE:", user["role"])
        print("====================================")

        # -------------------------------------------------
        # ADMIN
        # -------------------------------------------------

        if user["role"] == "admin":

            return redirect(
                url_for("admin_dashboard")
            )

        # -------------------------------------------------
        # STUDENT
        # -------------------------------------------------

        return redirect(
            url_for("student_dashboard")
        )

    # =====================================================
    # GET
    # =====================================================

    return render_template("login.html")
# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("home"))
@app.route("/about")
def about():
    return render_template("about.html")
@app.route("/students")
@login_required
@role_required("admin")
def students():

    conn = get_db()

    try:
        search = request.args.get("search", "").strip()
        branch = request.args.get("branch", "").strip()
        page = request.args.get("page", 1, type=int)

        per_page = 8
        offset = (page - 1) * per_page

        # -----------------------------
        # FILTER CONDITIONS
        # -----------------------------

        conditions = ["LOWER(u.role) = 'student'"]
        params = []

        if search:
            conditions.append("""
                (
                    LOWER(u.name) LIKE ?
                    OR LOWER(u.email) LIKE ?
                    OR LOWER(u.username) LIKE ?
                    OR LOWER(sp.college) LIKE ?
                    OR LOWER(sp.branch) LIKE ?
                )
            """)

            search_value = f"%{search.lower()}%"

            params.extend([
                search_value,
                search_value,
                search_value,
                search_value,
                search_value
            ])

        if branch:
            conditions.append(
                "LOWER(sp.branch) = ?"
            )
            params.append(branch.lower())

        where_clause = " AND ".join(conditions)

        # -----------------------------
        # TOTAL STUDENTS
        # -----------------------------

        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN student_profiles sp
                ON u.id = sp.user_id
            WHERE {where_clause}
            """,
            params
        ).fetchone()[0]

        # -----------------------------
        # STUDENTS
        # -----------------------------

        students = conn.execute(
            f"""
            SELECT
                u.id,
                u.name,
                u.age,
                u.gender,
                u.city,
                u.email,
                u.username,
                u.photo,
                u.created_at,

                sp.education,
                sp.college,
                sp.branch,
                sp.passing_year,
                sp.percentage,
                sp.cgpa,
                sp.career_goal,
                sp.skills,
                sp.interests,
                sp.certifications,
                sp.projects,
                sp.internships,
                sp.achievements

            FROM users u

            LEFT JOIN student_profiles sp
                ON u.id = sp.user_id

            WHERE {where_clause}

            ORDER BY u.id DESC

            LIMIT ?
            OFFSET ?
            """,
            params + [per_page, offset]
        ).fetchall()

        # -----------------------------
        # BRANCH FILTER OPTIONS
        # -----------------------------

        branches = conn.execute("""
            SELECT DISTINCT branch
            FROM student_profiles
            WHERE branch IS NOT NULL
            AND TRIM(branch) != ''
            ORDER BY branch
        """).fetchall()

        total_pages = max(
            1,
            (total + per_page - 1) // per_page
        )

        return render_template(
            "students.html",
            students=students,
            branches=branches,
            search=search,
            selected_branch=branch,
            page=page,
            total_pages=total_pages,
            total_students=total
        )

    finally:
        conn.close()
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    
    if request.method == "POST":
        try:
            name = request.form.get("name")
            email = request.form.get("email")

            conn = sqlite3.connect("careerLens.db")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (name, email)
                VALUES (?, ?)
            """, (name, email))

            conn.commit()
            conn.close()

            return redirect(url_for("students"))

        except Exception as e:
            print("ADD STUDENT ERROR:", e)
            return "Something went wrong: " + str(e)

    return render_template("add_student.html")
# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student_dashboard")
@login_required
@role_required("student")
def student_dashboard():

    conn = get_db()

    user = conn.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    profile = conn.execute("""
        SELECT * FROM student_profiles
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    jobs = conn.execute("""
        SELECT * FROM jobs
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    notifications = conn.execute("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        user=user,
        profile=profile,
        jobs=jobs,
        notifications=notifications
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin_dashboard")
@login_required
@role_required("admin")
def admin_dashboard():

    conn = get_db()

    total_students = conn.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'student'
    """).fetchone()["count"]

    total_jobs = conn.execute("""
        SELECT COUNT(*) AS count
        FROM jobs
    """).fetchone()["count"]

    total_tests = conn.execute("""
        SELECT COUNT(*) AS count
        FROM test_results
    """).fetchone()["count"]

    total_analysis = conn.execute("""
        SELECT COUNT(*) AS count
        FROM career_analysis
    """).fetchone()["count"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_jobs=total_jobs,
        total_tests=total_tests,
        total_analysis=total_analysis
    )

#========================================================
#ADD JOB
#========================================================
@app.route("/add_job", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_job():

    if request.method == "POST":

        company = request.form.get("company", "").strip()
        role = request.form.get("role", "").strip()
        description = request.form.get("description", "").strip()
        skills = request.form.get("skills", "").strip()
        eligibility = request.form.get("eligibility", "").strip()
        location = request.form.get("location", "").strip()
        package = request.form.get("package", "").strip()
        deadline = request.form.get("deadline", "").strip()

        conn = get_db()

        conn.execute("""
            INSERT INTO jobs
            (
                company,
                role,
                description,
                skills,
                eligibility,
                location,
                package,
                deadline
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company,
            role,
            description,
            skills,
            eligibility,
            location,
            package,
            deadline
        ))

        conn.commit()
        conn.close()

        flash("Job added successfully!", "success")

        return redirect(url_for("jobs"))

    return render_template("add_job.html")
#=========================================================
# MY PROFILE
#=========================================================
@app.route("/my_profile")
@login_required
def my_profile():

    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("login"))

    conn = sqlite3.connect("career_lens.db")
    conn.row_factory = sqlite3.Row

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if user is None:
        return redirect(url_for("login"))

    return render_template(
        "my_profile.html",
        student=user
    )
@app.route("/check_db")
def check_db():

    conn = sqlite3.connect("careerlens.db")

    tables = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
    """).fetchall()

    conn.close()

    return "<br>".join([table[0] for table in tables])

#========================================================
#Assignment
#========================================================
@app.route("/career_test", methods=["GET", "POST"])
@login_required
@role_required("student")
def career_test():

    if request.method == "POST":

        answers = [
            request.form.get("q1"),
            request.form.get("q2"),
            request.form.get("q3"),
            request.form.get("q4"),
            request.form.get("q5")
        ]

        # Career categories चे scores
        scores = {
            "Technology": answers.count("technology"),
            "Business & Management": answers.count("business"),
            "Creative & Design": answers.count("creative"),
            "Communication & People": answers.count("communication")
        }

        # Highest score
        recommended_career = max(
            scores,
            key=scores.get
        )

        score = scores[recommended_career]
        total = 5

        # Result database मध्ये save
        conn = get_db()

        conn.execute("""
            INSERT INTO test_results
            (
                user_id,
                test_name,
                score,
                total
            )
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            "Career Assessment",
            score,
            total
        ))

        conn.commit()
        conn.close()

        return render_template(
            "career_result.html",
            career=recommended_career,
            score=score,
            total=total,
            scores=scores
        )

    return render_template("career_test.html")
#========================================================
#RESULT oF aSSIGNMENT
#=========================================================
@app.route("/career_result", methods=["GET", "POST"])
@login_required
@role_required("student")
def career_result():

    if request.method == "POST":

        q1 = request.form.get("q1")
        q2 = request.form.get("q2")
        q3 = request.form.get("q3")

        answers = [q1, q2, q3]

        score = 0

        # Simple assessment scoring
        if q1 in ["technology", "design"]:
            score += 1

        if q2 in ["computer", "math"]:
            score += 1

        if q3 in ["technical", "creative"]:
            score += 1

        total = 3

        percentage = (score / total) * 100

        conn = get_db()

        conn.execute("""
            INSERT INTO test_results
            (
                user_id,
                test_name,
                score,
                total
            )
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            "Career Assessment",
            percentage,
            100
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("career_result"))

    return render_template("career_result.html")
#========================================================
#CAREER Analysis
#========================================================
@app.route("/career-analysis")
@login_required
@role_required("student")
def career_analysis():

    conn = get_db()

    result = conn.execute("""
        SELECT career, match_percentage, reason
        FROM career_analysis
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()

    conn.close()

    if result:
        career = result["career"]
        match_percentage = result["match_percentage"]
        reason = result["reason"]
    else:
        career = "Career Analysis Pending"
        match_percentage = 0
        reason = "Please complete your Career Assessment first."

    return render_template(
        "career_analysis.html",
        career=career,
        match_percentage=match_percentage,
        reason=reason
    )
#========================================================
#Job
#========================================================
@app.route("/jobs")
@login_required
@role_required("student")
def jobs():

    conn = get_db()

    jobs = conn.execute("""
        SELECT *
        FROM jobs
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "jobs.html",
        jobs=jobs
    )
#===============================================
#==============================================
@app.route("/check_jobs")
@login_required
def check_jobs():

    conn = get_db()

    jobs = conn.execute("""
        SELECT * FROM jobs
    """).fetchall()

    conn.close()

    return "<br>".join([
        f"{job['id']} - {job['company']} - {job['role']}"
        for job in jobs
    ]) or "NO JOBS IN DATABASE"
#===============================================
#==============================================
#========================================================
@app.route("/notifications")
@login_required
@role_required("student")
def notifications():

    conn = get_db()

    notifications = conn.execute("""
        SELECT
            id,
            message,
            is_read,
            created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "notification.html",
        notifications=notifications
    )

#========================================================
# add notify
# =======================================================
@app.route("/admin/add-notification", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_notification():

    if request.method == "POST":

        message = request.form.get("message", "").strip()

        if not message:
            flash("Please enter a notification message.", "warning")
            return redirect(url_for("add_notification"))

        conn = get_db()

        # सर्व students ना notification पाठवणे
        students = conn.execute("""
            SELECT id
            FROM users
            WHERE role = 'student'
        """).fetchall()

        for student in students:

            conn.execute("""
                INSERT INTO notifications
                (user_id, message)
                VALUES (?, ?)
            """, (
                student["id"],
                message
            ))

        conn.commit()
        conn.close()

        flash(
            "Notification sent successfully!",
            "success"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "add_notifications.html"
    )    
#===============================================
#==============================================
@app.route("/resume_builder", methods=["GET", "POST"])
def resume_builder():

    resume = None

    if request.method == "POST":

        resume = {
            "name": request.form.get("name", ""),
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
            "location": request.form.get("location", ""),

            "objective": request.form.get("objective", ""),
            "education": request.form.get("education", ""),
            "skills": request.form.get("skills", ""),

            "project_name": request.form.get("project_name", ""),
            "project_tech": request.form.get("project_tech", ""),
            "project_description": request.form.get(
                "project_description", ""
            ),

            "company": request.form.get("company", ""),
            "role": request.form.get("role", ""),
            "duration": request.form.get("duration", ""),
            "experience": request.form.get("experience", ""),

            "certificates": request.form.get(
                "certificates", ""
            ),

            "achievements": request.form.get(
                "achievements", ""
            ),

            "languages": request.form.get(
                "languages", ""
            ),

            "linkedin": request.form.get(
                "linkedin", ""
            ),

            "github": request.form.get(
                "github", ""
            )
        }

    return render_template(
        "resume_builder.html",
        resume=resume
    )
#===============================================
#==============================================
@app.route("/company_preparation")
def company_preparation():
    return render_template("company_preparation.html")
#===============================================
#==============================================
@app.route("/coading_practice")
def coading_practice():
    return render_template("coading_practice.html")
#===============================================
#==============================================
@app.route("/hr_interview")
def hr_interview():
    return render_template("hr_interview.html")    
#===============================================
#Learning
#=============================================
@app.route("/learning")
@login_required
@role_required("student")
def learning_hub():

    
    return render_template(
        "learning.html"
    )
#========================================================
#Certificate
#=======================================================

@app.route("/certificate")
def certificate():

    name = request.args.get("name", "Student")

    score = request.args.get("score", "85")

    certificate_id = request.args.get(
        "id",
        "CL-" + datetime.now().strftime("%Y%m%d%H%M")
    )

    photo = request.args.get(
        "photo",
        "default-profile.png"
    )

    completion_date = datetime.now().strftime(
        "%d %B %Y"
    )

    modules = [
        "Aptitude",
        "Technical MCQ",
        "Coding Practice",
        "AI Interviewer",
        "Technical Interview",
        "HR Interview"
    ]

    return render_template(
        "certificate.html",
        name=name,
        score=score,
        certificate_id=certificate_id,
        photo=photo,
        completion_date=completion_date,
        modules=modules
    )

#===============================================
#edit profile 
#================================================
@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
@role_required("student")
def edit_profile():

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    profile = conn.execute(
        "SELECT * FROM student_profiles WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":

        # -----------------------------
        # PERSONAL INFORMATION
        # -----------------------------

        name = request.form.get("name", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        city = request.form.get("city", "").strip()

        # -----------------------------
        # PROFILE INFORMATION
        # -----------------------------

        phone = request.form.get("phone", "").strip()
        education = request.form.get("education", "").strip()
        college = request.form.get("college", "").strip()
        branch = request.form.get("branch", "").strip()
        passing_year = request.form.get("passing_year", "").strip()

        percentage = request.form.get("percentage", "").strip()
        cgpa = request.form.get("cgpa", "").strip()

        career_goal = request.form.get(
            "career_goal", ""
        ).strip()

        skills = request.form.get(
            "skills", ""
        ).strip()

        interests = request.form.get(
            "interests", ""
        ).strip()

        certifications = request.form.get(
            "certifications", ""
        ).strip()

        projects = request.form.get(
            "projects", ""
        ).strip()

        internships = request.form.get(
            "internships", ""
        ).strip()

        achievements = request.form.get(
            "achievements", ""
        ).strip()

        # -----------------------------
        # UPDATE USERS
        # -----------------------------

        conn.execute("""
            UPDATE users
            SET
                name = ?,
                age = ?,
                gender = ?,
                city = ?
            WHERE id = ?
        """, (
            name,
            age if age else None,
            gender,
            city,
            session["user_id"]
        ))

        # -----------------------------
        # UPDATE STUDENT PROFILE
        # -----------------------------

        if profile:

            conn.execute("""
                UPDATE student_profiles
                SET
                    phone = ?,
                    education = ?,
                    college = ?,
                    branch = ?,
                    passing_year = ?,
                    percentage = ?,
                    cgpa = ?,
                    career_goal = ?,
                    skills = ?,
                    interests = ?,
                    certifications = ?,
                    projects = ?,
                    internships = ?,
                    achievements = ?

                WHERE user_id = ?
            """, (
                phone,
                education,
                college,
                branch,
                passing_year,
                float(percentage) if percentage else 0,
                float(cgpa) if cgpa else 0,
                career_goal,
                skills,
                interests,
                certifications,
                projects,
                internships,
                achievements,
                session["user_id"]
            ))

        else:

            conn.execute("""
                INSERT INTO student_profiles
                (
                    user_id,
                    phone,
                    education,
                    college,
                    branch,
                    passing_year,
                    percentage,
                    cgpa,
                    career_goal,
                    skills,
                    interests,
                    certifications,
                    projects,
                    internships,
                    achievements
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                phone,
                education,
                college,
                branch,
                passing_year,
                float(percentage) if percentage else 0,
                float(cgpa) if cgpa else 0,
                career_goal,
                skills,
                interests,
                certifications,
                projects,
                internships,
                achievements
            ))

        conn.commit()
        conn.close()

        flash(
            "Profile updated successfully!",
            "success"
        )

        return redirect(
            url_for("my_profile")
        )

    conn.close()

    return render_template(
        "edit_profile.html",
        user=user,
        profile=profile
    )
#========================================================
#Feature: 
#========================================================
@app.route("/feature")
def feature():
    return render_template("feature.html")

@app.route("/placement")
def placement():
    return render_template("placement.html")

@app.route("/interview-practice")
def interview_practice():
    return render_template("interview_practice.html")
#=====================================
#resume dowload
#====================================
@app.route("/download-resume")
@login_required
@role_required("student")
def download_resume():

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    profile = conn.execute("""
        SELECT *
        FROM profiles
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    pdf_buffer = BytesIO()

    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

    width, height = A4

    y = height - 50

    # Name
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, y, user["name"] or "Student")

    y -= 25

    # Contact
    pdf.setFont("Helvetica", 10)

    contact = user["email"] or ""

    if profile["phone"]:
        contact += " | " + profile["phone"]

    if user["city"]:
        contact += " | " + user["city"]

    pdf.drawString(50, y, contact)

    y -= 40


    def add_section(title, value):

        nonlocal y

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, title)

        y -= 20

        pdf.setFont("Helvetica", 10)

        text = value or "Not provided"

        # Simple line wrapping
        words = str(text).split()
        line = ""

        for word in words:

            if len(line + " " + word) > 85:

                pdf.drawString(55, y, line)
                y -= 15
                line = word

            else:

                line += " " + word

        if line:
            pdf.drawString(55, y, line)
            y -= 15

        y -= 15


    add_section(
        "EDUCATION",
        profile["education"]
    )

    add_section(
        "COLLEGE",
        profile["college"]
    )

    add_section(
        "BRANCH",
        profile["branch"]
    )

    add_section(
        "SKILLS",
        profile["skills"]
    )

    add_section(
        "PROJECTS",
        profile["projects"]
    )

    add_section(
        "CERTIFICATIONS",
        profile["certifications"]
    )

    add_section(
        "INTERNSHIPS",
        profile["internships"]
    )

    add_section(
        "ACHIEVEMENTS",
        profile["achievements"]
    )


    pdf.save()

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="CareerAI_Resume.pdf",
        mimetype="application/pdf"
    )        
init_db()
# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

  

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )