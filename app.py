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
    
    # Users table
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
    
    # NGOs table - with authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ngos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            description TEXT,
            contact TEXT,
            address TEXT,
            verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migrate existing ngos table if needed
    try:
        cursor.execute('SELECT email FROM ngos LIMIT 1')
    except sqlite3.OperationalError:
        try:
            cursor.execute('ALTER TABLE ngos ADD COLUMN email TEXT')
            cursor.execute('ALTER TABLE ngos ADD COLUMN password TEXT')
            cursor.execute('ALTER TABLE ngos ADD COLUMN address TEXT')
        except:
            pass

    
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
    
    # Campaign volunteers - Added status
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'joined',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(campaign_id, user_id)
        )
    ''')
    
    # Check for missing columns in campaign_volunteers (for migration)
    try:
        cursor.execute('SELECT status FROM campaign_volunteers LIMIT 1')
    except sqlite3.OperationalError:
        print("Migrating campaign_volunteers table: adding status")
        cursor.execute("ALTER TABLE campaign_volunteers ADD COLUMN status TEXT DEFAULT 'joined'")

    
    # User badges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            badge_description TEXT,
            campaign_id INTEGER,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    ''')
    
    # Activity log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            campaign_id INTEGER,
            activity_type TEXT NOT NULL,
            description TEXT,
            points_earned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    ''')
    
    # Campaign completion tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_by_ngo BOOLEAN DEFAULT 0,
            verified_by INTEGER,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (verified_by) REFERENCES ngos(id),
            UNIQUE(campaign_id, user_id)
        )
    ''')
    
    # Insert sample data if tables are empty
    try:
        cursor.execute('SELECT COUNT(*) FROM campaigns')
        campaign_count = cursor.fetchone()[0]
        if campaign_count == 0:
            # Insert sample campaigns (same as before)
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

# Helper functions
def award_badge(user_id, badge_name, badge_icon, badge_description=None, campaign_id=None):
    """Award a badge to a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user already has this badge
    existing = cursor.execute('''
        SELECT id FROM user_badges 
        WHERE user_id = ? AND badge_name = ?
    ''', (user_id, badge_name)).fetchone()
    
    if not existing:
        cursor.execute('''
            INSERT INTO user_badges (user_id, badge_name, badge_icon, badge_description, campaign_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, badge_name, badge_icon, badge_description, campaign_id))
        conn.commit()
    conn.close()

def log_activity(user_id, activity_type, description, points_earned=0, campaign_id=None):
    """Log an activity for a user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO activities (user_id, campaign_id, activity_type, description, points_earned)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, campaign_id, activity_type, description, points_earned))
    
    # Update user's eco points
    if points_earned > 0:
        cursor.execute('''
            UPDATE users SET eco_points = eco_points + ? WHERE id = ?
        ''', (points_earned, user_id))
    
    conn.commit()
    conn.close()

def check_and_award_badges(user_id):
    """Check user's progress and award badges accordingly"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get user stats
    campaigns_completed = cursor.execute('''
        SELECT COUNT(*) FROM campaign_completions WHERE user_id = ?
    ''', (user_id,)).fetchone()[0]
    
    total_points = cursor.execute('''
        SELECT eco_points FROM users WHERE id = ?
    ''', (user_id,)).fetchone()[0] or 0
    
    # Award badges based on milestones
    if campaigns_completed >= 1:
        award_badge(user_id, 'First Steps', 'seedling', 'Completed your first campaign!')
    if campaigns_completed >= 5:
        award_badge(user_id, 'Eco Warrior', 'shield-alt', 'Completed 5 campaigns!')
    if campaigns_completed >= 10:
        award_badge(user_id, 'Green Champion', 'trophy', 'Completed 10 campaigns!')
    if campaigns_completed >= 25:
        award_badge(user_id, 'Environmental Hero', 'medal', 'Completed 25 campaigns!')
    
    if total_points >= 100:
        award_badge(user_id, 'Point Collector', 'coins', 'Earned 100 eco points!')
    if total_points >= 500:
        award_badge(user_id, 'Point Master', 'star', 'Earned 500 eco points!')
    if total_points >= 1000:
        award_badge(user_id, 'Point Legend', 'crown', 'Earned 1000 eco points!')
    
    conn.close()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def ngo_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'ngo_id' not in session:
            flash('Please login as NGO to access this page', 'error')
            return redirect(url_for('ngo_login'))
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
    
    # Check if user owns an NGO
    owned_ngo = cursor.execute('SELECT * FROM ngos WHERE owner_id = ?', (user_id,)).fetchone()
    owned_campaigns = []
    
    if owned_ngo:
        owned_campaigns = cursor.execute('''
            SELECT * FROM campaigns WHERE ngo_id = ? ORDER BY date DESC
        ''', (owned_ngo['id'],)).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         user={'id': user_id, 'name': session['user_name'], 'email': session['user_email']},
                         my_campaigns=my_campaigns,
                         owned_ngo=owned_ngo,
                         owned_campaigns=owned_campaigns,
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

@app.route('/ngo/register', methods=['GET', 'POST'])
@login_required
def register_ngo():
    """Register a new NGO"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        contact = request.form.get('contact')
        
        if not all([name, contact]):
            return render_template('register_ngo.html', error='Please fill in name and contact')
            
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO ngos (name, description, contact, owner_id)
                VALUES (?, ?, ?, ?)
            ''', (name, description, contact, session['user_id']))
            conn.commit()
            flash('NGO registered successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error registering NGO: {e}', 'error')
            return render_template('register_ngo.html')
        finally:
            conn.close()
            
    return render_template('register_ngo.html')

@app.route('/campaign/create', methods=['GET', 'POST'])
@login_required
def create_campaign():
    """Create a new campaign"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user owns an NGO
    ngo = cursor.execute('SELECT * FROM ngos WHERE owner_id = ?', (session['user_id'],)).fetchone()
    
    if not ngo:
        conn.close()
        flash('You must register an NGO to create campaigns', 'error')
        return redirect(url_for('register_ngo'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        short_desc = request.form.get('short_description')
        category = request.form.get('category')
        location = request.form.get('location')
        date = request.form.get('date')
        time = request.form.get('time')
        needed = request.form.get('volunteers_needed')
        image = request.form.get('image_url')
        requirements = request.form.get('requirements')
        
        # Format requirements as JSON list
        req_list = [r.strip() for r in requirements.split('\n') if r.strip()]
        req_json = json.dumps(req_list)
        
        try:
            cursor.execute('''
                INSERT INTO campaigns (title, description, short_description, category, location, date, time, 
                                     volunteers_needed, ngo_id, image, requirements)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, desc, short_desc, category, location, date, time, needed, ngo['id'], image, req_json))
            conn.commit()
            flash('Campaign created successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error creating campaign: {e}', 'error')
        finally:
            conn.close()
            
    conn.close()
    return render_template('create_campaign.html')

@app.route('/campaign/<int:campaign_id>/manage')
@ngo_login_required
def manage_campaign(campaign_id):
    """Manage campaign volunteers"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify ownership
    campaign = cursor.execute('''
        SELECT c.* FROM campaigns c 
        WHERE c.id = ? AND c.ngo_id = ?
    ''', (campaign_id, session['ngo_id'])).fetchone()
    
    if not campaign:
        conn.close()
        flash('Access denied', 'error')
        return redirect(url_for('ngo_dashboard'))
        
    # Get volunteers with status and completion info
    volunteers = cursor.execute('''
        SELECT u.id as user_id, u.name, u.email, cv.status, 
               cc.id as completion_id, cc.verified_by_ngo
        FROM campaign_volunteers cv
        JOIN users u ON cv.user_id = u.id
        LEFT JOIN campaign_completions cc ON cv.campaign_id = cc.campaign_id AND cv.user_id = cc.user_id
        WHERE cv.campaign_id = ?
        ORDER BY cv.joined_at DESC
    ''', (campaign_id,)).fetchall()
    
    conn.close()
    return render_template('manage_campaign.html', campaign=campaign, volunteers=volunteers)

@app.route('/campaign/<int:campaign_id>/verify/<int:user_id>', methods=['POST'])
@ngo_login_required
def verify_volunteer(campaign_id, user_id):
    """Verify volunteer completion and award points/badges"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify ownership
    campaign = cursor.execute('''
        SELECT c.* FROM campaigns c 
        WHERE c.id = ? AND c.ngo_id = ?
    ''', (campaign_id, session['ngo_id'])).fetchone()
    
    if not campaign:
        conn.close()
        flash('Access denied', 'error')
        return redirect(url_for('ngo_dashboard'))
    
    # Mark as verified in completions
    cursor.execute('''
        UPDATE campaign_completions 
        SET verified_by_ngo = 1, verified_by = ?
        WHERE campaign_id = ? AND user_id = ?
    ''', (session['ngo_id'], campaign_id, user_id))
    
    # Update volunteer status
    cursor.execute('''
        UPDATE campaign_volunteers 
        SET status = 'verified' 
        WHERE campaign_id = ? AND user_id = ?
    ''', (campaign_id, user_id))
    
    # Award bonus points for verification
    log_activity(user_id, 'campaign_verified', f'Campaign verified by NGO: {campaign["title"]}', 10, campaign_id)
    
    # Check for badges
    check_and_award_badges(user_id)
    
    conn.commit()
    conn.close()
    
    flash('Volunteer verified successfully!', 'success')
    return redirect(url_for('manage_campaign', campaign_id=campaign_id))

def check_badges(user_id, cursor):
    """Check and award badges based on stats"""
    # Count completed campaigns
    count = cursor.execute('''
        SELECT COUNT(*) FROM campaign_volunteers 
        WHERE user_id = ? AND status = 'completed'
    ''', (user_id,)).fetchone()[0]
    
    badges_to_award = []
    
    if count >= 1:
        badges_to_award.append(('First Step', 'seedling'))
    if count >= 5:
        badges_to_award.append(('High Five', 'hand-holding-heart'))
    if count >= 10:
        badges_to_award.append(('Eco Warrior', 'leaf'))
        
    for name, icon in badges_to_award:
        exists = cursor.execute('''
            SELECT 1 FROM user_badges 
            WHERE user_id = ? AND badge_name = ?
        ''', (user_id, name)).fetchone()
        
        if not exists:
            cursor.execute('''
                INSERT INTO user_badges (user_id, badge_name, badge_icon)
                VALUES (?, ?, ?)
            ''', (user_id, name, icon))

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
        INSERT INTO campaign_volunteers (campaign_id, user_id, status)
        VALUES (?, ?, 'joined')
    ''', (campaign_id, user_id))
    
    # Update volunteer count
    cursor.execute('''
        UPDATE campaigns 
        SET volunteers_joined = volunteers_joined + 1
        WHERE id = ?
    ''', (campaign_id,))
    
    # Log activity and award points
    log_activity(user_id, 'campaign_joined', f'Joined campaign: {campaign["title"]}', 10, campaign_id)
    
    # Check for badges
    check_and_award_badges(user_id)
    
    conn.commit()
    conn.close()
    
    flash('Successfully joined the campaign! You earned 10 eco points.', 'success')
    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

@app.route('/ngo/register', methods=['GET', 'POST'])
def ngo_register():
    """NGO Registration"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        description = request.form.get('description')
        contact = request.form.get('contact')
        address = request.form.get('address')
        
        if not all([name, email, password, contact]):
            return render_template('ngo_register.html', error='Please fill in all required fields')
        
        if password != confirm_password:
            return render_template('ngo_register.html', error='Passwords do not match')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email exists
        existing = cursor.execute('SELECT id FROM ngos WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            return render_template('ngo_register.html', error='Email already registered')
        
        hashed_password = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO ngos (name, email, password, description, contact, address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, hashed_password, description, contact, address))
        
        ngo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        session['ngo_id'] = ngo_id
        session['ngo_name'] = name
        session['ngo_email'] = email
        
        flash('NGO registered successfully!', 'success')
        return redirect(url_for('ngo_dashboard'))
    
    return render_template('ngo_register.html')

@app.route('/ngo/login', methods=['GET', 'POST'])
def ngo_login():
    """NGO Login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return render_template('ngo_login.html', error='Please fill in all fields')
        
        conn = get_db()
        cursor = conn.cursor()
        ngo = cursor.execute('SELECT * FROM ngos WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if ngo and check_password_hash(ngo['password'], password):
            session['ngo_id'] = ngo['id']
            session['ngo_name'] = ngo['name']
            session['ngo_email'] = ngo['email']
            return redirect(url_for('ngo_dashboard'))
        else:
            return render_template('ngo_login.html', error='Invalid email or password')
    
    return render_template('ngo_login.html')

@app.route('/ngo/logout')
def ngo_logout():
    """NGO Logout"""
    session.pop('ngo_id', None)
    session.pop('ngo_name', None)
    session.pop('ngo_email', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/ngo/dashboard')
@ngo_login_required
def ngo_dashboard():
    """NGO Dashboard"""
    ngo_id = session['ngo_id']
    conn = get_db()
    cursor = conn.cursor()
    
    ngo = cursor.execute('SELECT * FROM ngos WHERE id = ?', (ngo_id,)).fetchone()
    
    # Get NGO's campaigns
    campaigns = cursor.execute('''
        SELECT * FROM campaigns WHERE ngo_id = ? ORDER BY created_at DESC
    ''', (ngo_id,)).fetchall()
    
    # Get stats
    total_campaigns = len(campaigns)
    total_volunteers = cursor.execute('''
        SELECT COUNT(DISTINCT cv.user_id) FROM campaign_volunteers cv
        INNER JOIN campaigns c ON cv.campaign_id = c.id
        WHERE c.ngo_id = ?
    ''', (ngo_id,)).fetchone()[0]
    
    conn.close()
    
    return render_template('ngo_dashboard.html', ngo=ngo, campaigns=campaigns,
                         stats={'total_campaigns': total_campaigns, 'total_volunteers': total_volunteers})

@app.route('/ngo/campaign/create', methods=['GET', 'POST'])
@ngo_login_required
def ngo_create_campaign():
    """Create campaign as NGO"""
    ngo_id = session['ngo_id']
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        short_description = request.form.get('short_description')
        category = request.form.get('category')
        location = request.form.get('location')
        date = request.form.get('date')
        time = request.form.get('time')
        volunteers_needed = int(request.form.get('volunteers_needed', 0))
        image = request.form.get('image_url')
        requirements = request.form.get('requirements', '')
        
        req_list = [r.strip() for r in requirements.split('\n') if r.strip()]
        req_json = json.dumps(req_list)
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO campaigns (title, description, short_description, category, location, date, time,
                                     volunteers_needed, ngo_id, image, requirements)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, description, short_description, category, location, date, time,
                  volunteers_needed, ngo_id, image, req_json))
            conn.commit()
            flash('Campaign created successfully!', 'success')
            return redirect(url_for('ngo_dashboard'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        finally:
            conn.close()
    
    return render_template('ngo_create_campaign.html')

@app.route('/campaigns/<int:campaign_id>/complete', methods=['POST'])
@login_required
def complete_campaign(campaign_id):
    """Mark campaign as completed by volunteer"""
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user joined the campaign
    joined = cursor.execute('''
        SELECT id FROM campaign_volunteers 
        WHERE campaign_id = ? AND user_id = ?
    ''', (campaign_id, user_id)).fetchone()
    
    if not joined:
        conn.close()
        flash('You must join the campaign first', 'error')
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    # Check if already completed
    completed = cursor.execute('''
        SELECT id FROM campaign_completions 
        WHERE campaign_id = ? AND user_id = ?
    ''', (campaign_id, user_id)).fetchone()
    
    if completed:
        conn.close()
        flash('You have already marked this campaign as completed', 'error')
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    # Mark as completed (pending NGO verification)
    cursor.execute('''
        INSERT INTO campaign_completions (campaign_id, user_id, verified_by_ngo)
        VALUES (?, ?, 0)
    ''', (campaign_id, user_id))
    
    # Update volunteer status
    cursor.execute('''
        UPDATE campaign_volunteers SET status = 'completed' 
        WHERE campaign_id = ? AND user_id = ?
    ''', (campaign_id, user_id))
    
    # Award points for completion (will be verified by NGO)
    log_activity(user_id, 'campaign_completed', f'Completed campaign: {campaign_id}', 20, campaign_id)
    
    # Check for badges
    check_and_award_badges(user_id)
    
    conn.commit()
    conn.close()
    
    flash('Campaign marked as completed! Waiting for NGO verification. You earned 20 eco points.', 'success')
    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

@app.route('/leaderboard')
def leaderboard():
    """Leaderboard page"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get top users by eco points
    top_users = cursor.execute('''
        SELECT u.id, u.name, u.eco_points, u.location,
               COUNT(DISTINCT ub.id) as badge_count,
               COUNT(DISTINCT cc.id) as campaigns_completed
        FROM users u
        LEFT JOIN user_badges ub ON u.id = ub.user_id
        LEFT JOIN campaign_completions cc ON u.id = cc.user_id
        GROUP BY u.id
        ORDER BY u.eco_points DESC, campaigns_completed DESC
        LIMIT 50
    ''').fetchall()
    
    conn.close()
    
    return render_template('leaderboard.html', top_users=top_users,
                         user={'id': session.get('user_id'), 'name': session.get('user_name')} if 'user_id' in session else None)

@app.route('/activities')
@login_required
def activities():
    """User activity feed"""
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    activities_list = cursor.execute('''
        SELECT a.*, c.title as campaign_title
        FROM activities a
        LEFT JOIN campaigns c ON a.campaign_id = c.id
        WHERE a.user_id = ?
        ORDER BY a.created_at DESC
        LIMIT 50
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    return render_template('activities.html', activities=activities_list,
                         user={'id': user_id, 'name': session['user_name']})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

