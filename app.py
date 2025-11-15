from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Database setup
DATABASE = 'greenspark.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraints
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Users table (must be created first as it's referenced by other tables)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            password TEXT NOT NULL,
            eco_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # NGOs table (must be created before campaigns as campaigns references it)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ngos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            contact TEXT,
            verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Campaigns table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            short_description TEXT,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            volunteers_needed INTEGER NOT NULL,
            volunteers_joined INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming',
            featured BOOLEAN DEFAULT 0,
            image TEXT,
            ngo_id INTEGER,
            requirements TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ngo_id) REFERENCES ngos(id)
        )
    ''')
    
    # Campaign volunteers (many-to-many relationship)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(campaign_id, user_id)
        )
    ''')
    
    # User badges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Insert sample data if tables are empty
    try:
        cursor.execute('SELECT COUNT(*) FROM campaigns')
        campaign_count = cursor.fetchone()[0]
        if campaign_count == 0:
            # Insert sample campaigns
            sample_campaigns = [
                ('Coastal Cleanup Drive', 
                 'Join us for a massive beach cleanup initiative to protect marine life and keep our coastlines clean. We will be collecting plastic waste, bottles, and other debris from the beach.',
                 'Join us for a massive beach cleanup initiative to protect marine life',
                 'cleanup', 'Mumbai Beach', '2025-12-20', '09:00', 100, 45, 'upcoming', 1, None, None, '["Bring gloves", "Wear comfortable shoes", "Bring water bottle"]'),
                ('Urban Reforestation', 
                 'Help us plant 500 trees to create a greener urban environment. This initiative aims to increase green cover in the city and improve air quality.',
                 'Help us plant 500 trees to create a greener urban environment',
                 'tree-planting', 'City Park', '2025-12-25', '08:00', 80, 30, 'upcoming', 0, None, None, '["No experience needed", "Tools provided", "Wear old clothes"]'),
                ('Waste Segregation Workshop', 
                 'Learn and teach proper waste management practices to the community. This workshop will cover recycling, composting, and reducing waste.',
                 'Learn and teach proper waste management practices to the community',
                 'awareness', 'Community Center', '2026-01-05', '10:00', 50, 20, 'upcoming', 0, None, None, '["Bring notebook", "Open to all ages"]'),
            ]
            
            for campaign in sample_campaigns:
                cursor.execute('''
                    INSERT INTO campaigns (title, description, short_description, category, location, date, time, 
                                         volunteers_needed, volunteers_joined, status, featured, image, ngo_id, requirements)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', campaign)
    except Exception as e:
        print(f"Error initializing sample data: {e}")
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template('login.html', error='Please fill in all fields')
        
        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register page"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        location = request.form.get('location')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([name, email, phone, location, password, confirm_password]):
            return render_template('register.html', error='Please fill in all fields')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        existing_user = cursor.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            conn.close()
            return render_template('register.html', error='Email already registered')
        
        # Create user
        hashed_password = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, phone, location, password)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, phone, location, hashed_password))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Auto login after registration
        session['user_id'] = user_id
        session['user_name'] = name
        session['user_email'] = email
        
        flash('Registration successful!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    # Get user info
    user = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    # Get user's campaigns
    my_campaigns = cursor.execute('''
        SELECT c.* FROM campaigns c
        INNER JOIN campaign_volunteers cv ON c.id = cv.campaign_id
        WHERE cv.user_id = ? AND c.status != 'completed'
        ORDER BY c.date ASC
        LIMIT 5
    ''', (user_id,)).fetchall()
    
    # Get stats
    campaigns_joined = cursor.execute('''
        SELECT COUNT(*) FROM campaign_volunteers WHERE user_id = ?
    ''', (user_id,)).fetchone()[0]
    
    eco_points = user['eco_points'] if user else 0
    
    badges_count = cursor.execute('''
        SELECT COUNT(*) FROM user_badges WHERE user_id = ?
    ''', (user_id,)).fetchone()[0]
    
    # Calculate impact score (simplified)
    impact_score = min(100, (campaigns_joined * 20) + (eco_points // 10))
    
    # Get badges
    badges = cursor.execute('''
        SELECT badge_name, badge_icon FROM user_badges WHERE user_id = ?
    ''', (user_id,)).fetchall()
    
    # Get recent activity (simplified)
    recent_activity = [
        {'title': 'Joined Campaign', 'description': 'You joined a new campaign', 'timestamp': '2 hours ago'},
        {'title': 'Earned Badge', 'description': 'You earned the Eco Warrior badge', 'timestamp': '1 day ago'},
    ]
    
    conn.close()
    
    return render_template('dashboard.html',
                         user={'id': user_id, 'name': session['user_name'], 'email': session['user_email']},
                         my_campaigns=my_campaigns,
                         stats={
                             'campaigns_joined': campaigns_joined,
                             'eco_points': eco_points,
                             'badges_count': badges_count,
                             'impact_score': impact_score
                         },
                         badges=[{'name': b['badge_name'], 'icon': b['badge_icon'] or 'medal'} for b in badges],
                         recent_activity=recent_activity)

@app.route('/campaigns')
def campaigns():
    """Campaigns listing page"""
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    location = request.args.get('location', '')
    page = int(request.args.get('page', 1))
    per_page = 9
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Build query
    query = 'SELECT * FROM campaigns WHERE 1=1'
    params = []
    
    if search:
        query += ' AND (title LIKE ? OR description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    if location:
        query += ' AND location LIKE ?'
        params.append(f'%{location}%')
    
    # Get total count
    count_query = query.replace('SELECT *', 'SELECT COUNT(*)')
    total = cursor.execute(count_query, params).fetchone()[0]
    
    # Get paginated results
    query += ' ORDER BY featured DESC, date ASC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    campaigns_list = cursor.execute(query, params).fetchall()
    conn.close()
    
    total_pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
    
    return render_template('campaigns.html',
                         campaigns=campaigns_list,
                         current_page=page,
                         total_pages=total_pages,
                         search=search,
                         category=category,
                         location=location,
                         user={'id': session.get('user_id'), 'name': session.get('user_name')} if 'user_id' in session else None)

@app.route('/campaigns/<int:campaign_id>')
def campaign_detail(campaign_id):
    """Campaign detail page"""
    conn = get_db()
    cursor = conn.cursor()
    
    campaign = cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
    
    if not campaign:
        conn.close()
        return render_template('campaign_detail.html', campaign=None)
    
    # Get NGO info if exists
    ngo = None
    if campaign['ngo_id']:
        ngo = cursor.execute('SELECT * FROM ngos WHERE id = ?', (campaign['ngo_id'],)).fetchone()
    
    # Get volunteers
    volunteers = cursor.execute('''
        SELECT u.name FROM users u
        INNER JOIN campaign_volunteers cv ON u.id = cv.user_id
        WHERE cv.campaign_id = ?
        LIMIT 10
    ''', (campaign_id,)).fetchall()
    
    # Check if user joined
    user_joined = False
    if 'user_id' in session:
        joined = cursor.execute('''
            SELECT id FROM campaign_volunteers 
            WHERE campaign_id = ? AND user_id = ?
        ''', (campaign_id, session['user_id'])).fetchone()
        user_joined = joined is not None
    
    # Parse requirements
    requirements = []
    if campaign['requirements']:
        try:
            requirements = json.loads(campaign['requirements'])
        except:
            requirements = []
    
    conn.close()
    
    return render_template('campaign_detail.html',
                         campaign=campaign,
                         ngo=ngo,
                         volunteers=volunteers,
                         user_joined=user_joined,
                         user={'id': session.get('user_id'), 'name': session.get('user_name')} if 'user_id' in session else None,
                         requirements=requirements)

@app.route('/campaigns/<int:campaign_id>/join', methods=['POST'])
@login_required
def join_campaign(campaign_id):
    """Join a campaign"""
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if campaign exists and has space
    campaign = cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
    if not campaign:
        conn.close()
        flash('Campaign not found', 'error')
        return redirect(url_for('campaigns'))
    
    if campaign['volunteers_joined'] >= campaign['volunteers_needed']:
        conn.close()
        flash('Campaign is full', 'error')
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    # Check if already joined
    existing = cursor.execute('''
        SELECT id FROM campaign_volunteers 
        WHERE campaign_id = ? AND user_id = ?
    ''', (campaign_id, user_id)).fetchone()
    
    if existing:
        conn.close()
        flash('You have already joined this campaign', 'error')
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    # Join campaign
    cursor.execute('''
        INSERT INTO campaign_volunteers (campaign_id, user_id)
        VALUES (?, ?)
    ''', (campaign_id, user_id))
    
    # Update volunteer count
    cursor.execute('''
        UPDATE campaigns 
        SET volunteers_joined = volunteers_joined + 1
        WHERE id = ?
    ''', (campaign_id,))
    
    # Award eco points
    cursor.execute('''
        UPDATE users 
        SET eco_points = eco_points + 10
        WHERE id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    
    flash('Successfully joined the campaign! You earned 10 eco points.', 'success')
    return redirect(url_for('campaign_detail', campaign_id=campaign_id))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

