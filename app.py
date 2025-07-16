from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import random
import pytesseract
import easyocr
import pdfplumber
import json

app = Flask(__name__)
app.secret_key = 'your-very-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthapp.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath, lang='eng'):
    ext = os.path.splitext(filepath)[1].lower()
    text = ''
    if ext == '.pdf':
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ''
        if not text.strip():
            # Fallback to OCR for scanned PDFs
            import cv2
            from pdf2image import convert_from_path
            images = convert_from_path(filepath)
            for img in images:
                text += pytesseract.image_to_string(img, lang=lang)
    elif ext in ['.jpg', '.jpeg', '.png']:
        try:
            reader = easyocr.Reader([lang])
            result = reader.readtext(filepath, detail=0)
            text = '\n'.join(result)
        except Exception:
            text = pytesseract.image_to_string(filepath, lang=lang)
    return text

def parse_medical_values(text):
    # Simple regex-based extraction for demo
    import re
    values = {}
    patterns = {
        'hemoglobin': r'hemoglobin\s*[:=]?\s*([\d.]+)',
        'sugar': r'sugar\s*[:=]?\s*([\d.]+)',
        'cholesterol': r'cholesterol\s*[:=]?\s*([\d.]+)',
        'glucose': r'glucose\s*[:=]?\s*([\d.]+)',
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            values[key] = m.group(1)
    # Example condition detection
    conditions = []
    if 'sugar' in values and float(values['sugar']) > 140:
        conditions.append('High Blood Sugar')
    if 'cholesterol' in values and float(values['cholesterol']) > 200:
        conditions.append('High Cholesterol')
    return values, conditions

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    goal = db.Column(db.String(32), default='weight_loss')
    role = db.Column(db.String(16), default='user')
    reports = db.relationship('MedicalReport', backref='user', lazy=True)

class MedicalReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    values = db.Column(db.Text)  # JSON string of extracted values
    conditions = db.Column(db.Text)  # JSON string of detected conditions
    diet_chart = db.Column(db.Text)  # JSON string of diet chart
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    steps = db.Column(db.Integer)
    exercise = db.Column(db.String(100))
    calories = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class HealthReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    extracted_values = db.Column(db.Text)  # JSON/text
    conditions = db.Column(db.Text)        # JSON/text
    diet_plan = db.Column(db.Text)        # JSON/text
    doctor_comment = db.Column(db.Text)   # Doctor's comment
    shared_with_doctor = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        age = request.form['age']
        gender = request.form['gender']
        height = request.form['height']
        weight = request.form['weight']
        role = request.form.get('role', 'user')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, password=password, age=age, gender=gender, height=height, weight=weight, role=role)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

# Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    reports = HealthReport.query.filter_by(user_id=current_user.id).order_by(HealthReport.timestamp.desc()).all()
    for report in reports:
        report.values_dict = json.loads(report.extracted_values or '{}')
        report.conds_list = json.loads(report.conditions or '[]')
    activity_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.date.desc()).all()
    # Report comparison logic
    comparison = {}
    if len(reports) >= 2:
        latest = json.loads(reports[0].extracted_values)
        prev = json.loads(reports[1].extracted_values)
        for key in set(latest.keys()).union(prev.keys()):
            v_new = float(latest.get(key, 0))
            v_old = float(prev.get(key, 0))
            if v_new > v_old:
                status = 'worse'
            elif v_new < v_old:
                status = 'improved'
            else:
                status = 'no_change'
            comparison[key] = {'latest': v_new, 'previous': v_old, 'status': status}
    # Trend data for Chart.js
    trend_data = {}
    for key in ['hemoglobin', 'sugar', 'cholesterol', 'glucose']:
        trend_data[key] = [float(json.loads(r.extracted_values).get(key, 0)) for r in reversed(reports)]
    trend_labels = [r.timestamp.strftime('%Y-%m-%d') for r in reversed(reports)]
    # Personalized diet chart with explanations
    goal = current_user.goal or 'weight_loss'
    if goal == 'weight_loss':
        diet_chart = [
            {'meal': 'Breakfast', 'items': 'Oatmeal (50g), Banana (1)', 'calories': 220, 'reason': 'High fiber, keeps you full with fewer calories.'},
            {'meal': 'Lunch', 'items': 'Grilled Chicken (100g), Brown Rice (100g), Salad', 'calories': 350, 'reason': 'Lean protein and complex carbs for sustained energy.'},
            {'meal': 'Snack', 'items': 'Apple (1), Almonds (10g)', 'calories': 100, 'reason': 'Low-calorie, nutrient-dense snack.'},
            {'meal': 'Dinner', 'items': 'Steamed Fish (80g), Quinoa (80g), Veggies', 'calories': 250, 'reason': 'Light, protein-rich meal for the evening.'},
        ]
    elif goal == 'muscle_gain':
        diet_chart = [
            {'meal': 'Breakfast', 'items': 'Eggs (3), Whole Wheat Toast (2)', 'calories': 350, 'reason': 'Protein and carbs to start muscle recovery.'},
            {'meal': 'Lunch', 'items': 'Chicken Breast (150g), Rice (150g), Veggies', 'calories': 500, 'reason': 'High protein and carbs for muscle growth.'},
            {'meal': 'Snack', 'items': 'Greek Yogurt (100g), Mixed Nuts (20g)', 'calories': 200, 'reason': 'Protein and healthy fats for sustained energy.'},
            {'meal': 'Dinner', 'items': 'Paneer (100g), Roti (2), Salad', 'calories': 400, 'reason': 'Casein protein for overnight muscle repair.'},
        ]
    elif goal == 'diabetes_control':
        diet_chart = [
            {'meal': 'Breakfast', 'items': 'Moong Dal Chilla (2), Tomato', 'calories': 180, 'reason': 'Low glycemic, high protein breakfast.'},
            {'meal': 'Lunch', 'items': 'Grilled Fish (100g), Brown Rice (80g), Veggies', 'calories': 300, 'reason': 'Balanced meal with slow carbs.'},
            {'meal': 'Snack', 'items': 'Cucumber, Walnuts (10g)', 'calories': 80, 'reason': 'Low sugar, healthy fats.'},
            {'meal': 'Dinner', 'items': 'Tofu (80g), Stir-fried Veggies, Millet Roti (1)', 'calories': 220, 'reason': 'Low carb, high fiber for stable sugar.'},
        ]
    else:
        diet_chart = []
    # Fun, gamified milestones (all unlocked for demo)
    milestones = [
        {'icon': '🏅', 'name': 'First Report Uploaded', 'desc': 'Upload your first medical report', 'unlocked': True},
        {'icon': '🚶‍♂️', 'name': 'Step Master', 'desc': 'Walk 10,000 steps in a day', 'unlocked': True},
        {'icon': '🔥', 'name': '7-Day Streak', 'desc': 'Log activity 7 days in a row', 'unlocked': True},
        {'icon': '🥗', 'name': 'Diet Pro', 'desc': 'Log your diet for a week', 'unlocked': True},
    ]
    # Static wellness score and random tip
    wellness_score = 87  # out of 100
    wellness_tips = [
        "Drink plenty of water throughout the day!",
        "Take a short walk every hour to stay active.",
        "Eat a variety of colorful fruits and vegetables.",
        "Prioritize 7-8 hours of sleep each night.",
        "Practice deep breathing or meditation for stress relief.",
        "Celebrate your small health wins!"
    ]
    wellness_tip = random.choice(wellness_tips)
    return render_template('dashboard.html', user=current_user, reports=reports, activity_logs=activity_logs, diet_chart=diet_chart, milestones=milestones, wellness_score=wellness_score, wellness_tip=wellness_tip, comparison=comparison, trend_data=trend_data, trend_labels=trend_labels)

# Upload Medical Report (POST)
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'report_file' not in request.files:
        flash('No file part.', 'danger')
        return redirect(url_for('dashboard'))
    file = request.files['report_file']
    if file.filename == '':
        flash('No selected file.', 'danger')
        return redirect(url_for('dashboard'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        lang = request.form.get('ocr_language', 'eng')
        text = extract_text_from_file(save_path, lang=lang)
        values, conditions = parse_medical_values(text)
        shared = bool(request.form.get('shared_with_doctor'))
        report = HealthReport(
            filename=filename,
            user_id=current_user.id,
            extracted_values=json.dumps(values),
            conditions=json.dumps(conditions),
            diet_plan='{}',
            shared_with_doctor=shared
        )
        db.session.add(report)
        db.session.commit()
        flash('Medical report uploaded and processed successfully!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid file type. Only PDF, JPG, JPEG, PNG allowed.', 'danger')
        return redirect(url_for('dashboard'))

# Activity Log (POST)
@app.route('/activity-log', methods=['POST'])
@login_required
def activity_log():
    steps = request.form.get('steps')
    exercise = request.form.get('exercise')
    calories = request.form.get('calories')
    log = ActivityLog(
        steps=steps,
        exercise=exercise,
        calories=calories,
        user_id=current_user.id
    )
    db.session.add(log)
    db.session.commit()
    flash('Activity log added!', 'success')
    return redirect(url_for('dashboard'))

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/update-goal', methods=['POST'])
@login_required
def update_goal():
    goal = request.form.get('goal')
    if goal in ['weight_loss', 'muscle_gain', 'diabetes_control']:
        current_user.goal = goal
        db.session.commit()
        flash('Health goal updated!', 'success')
    else:
        flash('Invalid goal selected.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/doctor/comment/<int:report_id>', methods=['POST'])
@login_required
def doctor_comment(report_id):
    if current_user.role != 'doctor':
        flash('Access denied: Doctors only.', 'danger')
        return redirect(url_for('dashboard'))
    report = HealthReport.query.get_or_404(report_id)
    comment = request.form.get('doctor_comment', '').strip()
    if comment:
        report.doctor_comment = comment
        db.session.commit()
        flash('Comment added.', 'success')
    else:
        flash('Comment cannot be empty.', 'danger')
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        flash('Access denied: Doctors only.', 'danger')
        return redirect(url_for('dashboard'))
    reports = HealthReport.query.filter_by(shared_with_doctor=True).order_by(HealthReport.timestamp.desc()).all()
    for report in reports:
        report.values_dict = json.loads(report.extracted_values or '{}')
        report.conds_list = json.loads(report.conditions or '[]')
    users = {u.id: u for u in User.query.all()}
    return render_template('doctor_dashboard.html', reports=reports, users=users)

@app.route('/')
def home():
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 