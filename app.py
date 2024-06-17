import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from datetime import datetime
import sqlite3
import random
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secret key of your choice

# Database setup
def init_db():
    if not os.path.exists('events.db'):
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                time TEXT NOT NULL,
                category TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                FOREIGN KEY (event_id) REFERENCES event_list(id)
            )
        ''')
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pin TEXT NOT NULL,
                role TEXT NOT NULL,
                sia_number TEXT,
                sia_expiry DATE,
                full_name TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE event_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL
            )
        ''')
        # Add some sample data
        c.execute('INSERT INTO users (name, pin, role, sia_number, sia_expiry, full_name) VALUES (?, ?, ?, ?, ?, ?)', ('Alice', '1234', 'admin', '12345678', '2024-12-31', 'Alice Admin'))
        c.execute('INSERT INTO users (name, pin, role, sia_number, sia_expiry, full_name) VALUES (?, ?, ?, ?, ?, ?)', ('Bob', '5678', 'user', '87654321', '2024-12-31', 'Bob User'))
        conn.commit()
        conn.close()

init_db()

def generate_id():
    return str(random.randint(100000, 999999))





def scrape_sia_license(license_no):
    try:
        print(f"Starting scrape for license number: {license_no}")

        # Make a POST request to the SIA website to perform the search
        response = requests.post(
            'https://services.sia.homeoffice.gov.uk/PublicRegister/SearchPublicRegisterByLicence',
            data={'LicenseNo': license_no}
        )

        # Check if the response is valid
        if response.status_code != 200:
            print("Failed to retrieve data")
            return {'valid': False, 'error': 'Failed to retrieve data'}

        # Parse the HTML response
        soup = BeautifulSoup(response.text, 'html.parser')

        # Log the HTML content for debugging
        with open("response.html", "w", encoding="utf-8") as file:
            file.write(soup.prettify())
        print("HTML response written to response.html")

        # Find the ax_horizontal_line to locate the starting point
        horizontal_line_div = soup.find('div', class_='ax_horizontal_line')
        if not horizontal_line_div:
            print("Horizontal line divider not found")
            return {'valid': False, 'error': 'Horizontal line divider not found'}

        # Navigate to the panel body after the horizontal line
        panel_body = horizontal_line_div.find_next('div', class_='panel-body')
        if not panel_body:
            print("Panel body not found")
            return {'valid': False, 'error': 'Panel body not found'}

        def extract_text_by_label(panel, label):
            label_elem = panel.find(lambda tag: tag.name == 'span' and label.lower() in tag.text.lower())
            if not label_elem:
                print(f"Label '{label}' not found")
                return None
            value_elem = label_elem.find_next('div', class_='form-group').find('div', class_='ax_h5' if 'name' in label.lower() or 'surname' in label.lower() else 'ax_h4')
            if not value_elem:
                print(f"Value element for label '{label}' not found")
                return None
            return value_elem.text.strip()

        def extract_status(panel):
            status_elem = panel.find('span', class_='ax_h4_green')
            if not status_elem:
                print(f"Status element not found")
                return None
            status_text = status_elem.text.strip()
            next_sibling = status_elem.find_next_sibling()
            if next_sibling:
                status_text += ' ' + next_sibling.text.strip()
            return status_text

        # Extract information based on labels
        first_name = extract_text_by_label(panel_body, 'First name')
        surname = extract_text_by_label(panel_body, 'Surname')
        license_number = extract_text_by_label(panel_body, 'Licence number')
        role = extract_text_by_label(panel_body, 'Role')
        expiry_date = extract_text_by_label(panel_body, 'Expiry date')
        status = extract_status(panel_body)

        # Log the found elements for debugging
        print(f"First Name: {first_name}")
        print(f"Surname: {surname}")
        print(f"License Number: {license_number}")
        print(f"Role: {role}")
        print(f"Expiry Date: {expiry_date}")
        print(f"Status: {status}")

        if not all([first_name, surname, license_number, role, expiry_date, status]):
            print("Missing one or more fields")
            return {'valid': False, 'error': 'Missing one or more fields'}

        return {
            'valid': True,
            'firstName': first_name,
            'surname': surname,
            'licenseNumber': license_number,
            'role': role,
            'expiryDate': expiry_date,
            'status': status
        }
    except Exception as e:
        print(f"Error scraping SIA website: {e}")
        return {'valid': False, 'error': str(e)}

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    license_no = data.get('licenseNo')

    if not license_no:
        return jsonify({'error': 'License number is required'}), 400

    license_info = scrape_sia_license(license_no)
    if not license_info['valid']:
        return jsonify({'error': 'Invalid SIA License number or unable to scrape data', 'details': license_info.get('error')}), 400

    return jsonify(license_info)

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = c.fetchall()
    
    c.execute('SELECT category, COUNT(*) FROM events GROUP BY category')
    event_counts = c.fetchall()
    
    c.execute('SELECT strftime("%Y-%m-%d", time) as date, COUNT(*) FROM events GROUP BY date')
    event_dates = c.fetchall()
    
    conn.close()

    return render_template('dashboard.html', users=users, event_counts=event_counts, event_dates=event_dates)

@app.route('/index', methods=['GET'])
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    filter_category = request.args.get('filter-category', '')
    filter_date = request.args.get('filter-date', '')
    filter_name = request.args.get('filter-name', '')
    search = request.args.get('search', '')

    query = 'SELECT * FROM events WHERE 1=1'
    params = []

    if filter_category:
        query += ' AND category = ?'
        params.append(filter_category)
    if filter_date:
        query += ' AND date(time) = ?'
        params.append(filter_date)
    if filter_name:
        query += ' AND name LIKE ?'
        params.append('%' + filter_name + '%')
    if search:
        query += ' AND text LIKE ?'
        params.append('%' + search + '%')

    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute(query, params)
    events = c.fetchall()

    c.execute('SELECT * FROM categories')
    categories = c.fetchall()

    c.execute('SELECT * FROM event_list')
    event_list = c.fetchall()
    
    conn.close()

    message = request.args.get('message', '')
    return render_template('index.html', events=events, categories=categories, event_list=event_list, message=message)

@app.route('/log_event', methods=['POST'])
def log_event():
    try:
        name = session.get('name')
        text = request.form['text']
        time = request.form['time']
        category = request.form['category']
        event_id = request.form['event']
        event_log_id = generate_id()
        time = datetime.strptime(time, '%Y-%m-%dT%H:%M').strftime('%d/%m/%Y %H:%M')

        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('INSERT INTO events (id, name, text, time, category, event_id) VALUES (?, ?, ?, ?, ?, ?)', 
                  (event_log_id, name, text, time, category, event_id))
        conn.commit()
        conn.close()

        # Emit event to all connected clients
        socketio.emit('new_event', {'text': text, 'time': time, 'category': category, 'event_id': event_id})

        # Redirect with success message
        return redirect(url_for('index', message='success'))
    except Exception as e:
        # Log the error for debugging
        print(f"Error logging event: {e}")
        # Redirect with error message
        return redirect(url_for('index', message='error'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        pin = request.form['pin']
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE name = ? AND pin = ?', (name, pin))
        user = c.fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['name'] = name
            session['role'] = user[3]  # Ensure role is set in the session
            return redirect(url_for('select_event'))
        else:
            return 'Invalid name or PIN', 403
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('name', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        pin = request.form['pin']
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (name, pin, role, sia_number, sia_expiry, full_name) VALUES (?, ?, ?, ?, ?, ?)', (name, pin, 'user', '00000000', '2024-12-31', 'John Doe'))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/users')
def list_users():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users')
        users = c.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error fetching users: {e}")
        return render_template('error.html', error=str(e))
    
    return render_template('list_users.html', users=users)


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        sia_number = request.form['sia_number']
        full_name = request.form['full_name']
        sia_expiry = request.form['sia_expiry']
        name = request.form['name']
        pin = request.form['pin']
        role = request.form['role']
        
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (name, pin, role, sia_number, sia_expiry, full_name) VALUES (?, ?, ?, ?, ?, ?)', (name, pin, role, sia_number, sia_expiry, full_name))
        conn.commit()
        conn.close()
        
        return redirect(url_for('list_users'))
    
    return render_template('add_user.html')

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        pin = request.form['pin']
        role = request.form['role']
        sia_number = request.form['sia_number']
        sia_expiry = request.form['sia_expiry']
        full_name = request.form['full_name']
        c.execute('UPDATE users SET name = ?, pin = ?, role = ?, sia_number = ?, sia_expiry = ?, full_name = ? WHERE id = ?', (name, pin, role, sia_number, sia_expiry, full_name, id))
        conn.commit()
        conn.close()
        return redirect(url_for('list_users'))
    
    c.execute('SELECT * FROM users WHERE id = ?', (id,))
    user = c.fetchone()
    conn.close()
    
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:id>', methods=['GET'])
def delete_user(id):
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('list_users'))

@app.route('/select_event', methods=['GET', 'POST'])
def select_event():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('SELECT * FROM event_list')
    event_list = c.fetchall()
    conn.close()

    if request.method == 'POST':
        selected_event_id = request.form['event']
        session['selected_event_id'] = selected_event_id
        return redirect(url_for('index'))

    return render_template('select_event.html', event_list=event_list)

@app.route('/delete_event/<int:id>', methods=['GET'])
def remove_event(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('DELETE FROM events WHERE id = ?', (id,))
        conn.commit()
        conn.close()

        return '', 204
    except Exception as e:
        print(f"Error deleting event: {e}")
        return '', 500

@app.route('/update_event/<int:id>', methods=['POST'])
def update_event(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    try:
        data = request.get_json()
        name = data['name']
        text = data['text']
        time = datetime.strptime(data['time'], '%d/%m/%Y %H:%M')
        category = data['category']
        event = data['event']

        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('UPDATE events SET name = ?, text = ?, time = ?, category = ?, event_id = ? WHERE id = ?', 
                  (name, text, time, category, event, id))
        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating event: {e}")
        return jsonify({'success': False}), 500

@app.route('/admin')
def admin():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('SELECT * FROM categories')
    categories = c.fetchall()
    c.execute('SELECT * FROM event_list')
    events = c.fetchall()
    conn.close()
    
    return render_template('admin.html', categories=categories, events=events)

@app.route('/add_category', methods=['POST'])
def add_category():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    name = request.form['name']
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('INSERT INTO categories (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

@app.route('/delete_category/<int:id>', methods=['GET'])
def delete_category(id):
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('DELETE FROM categories WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

@app.route('/add_event', methods=['POST'])
def add_event():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    name = request.form['name']
    description = request.form['description']
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('INSERT INTO event_list (name, description) VALUES (?, ?)', (name, description))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

@app.route('/delete_event/<int:id>', methods=['GET'])
def delete_event_list(id):
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('DELETE FROM event_list WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
