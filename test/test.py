from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import requests
import datetime
import uuid
import csv
import io
import hashlib
from geopy.geocoders import Nominatim
import sqlite3

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Define your database path and upload folder
DATABASE_PATH = 'geolocated_reports.db'
UPLOAD_FOLDER = 'UPLOAD_FOLDER'  # Update this path to a valid one on your virtual machine

# Database connection function
def get_db_connection():
    conn = getattr(g, '_database', None)
    if conn is None:
        conn = g._database = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
    return conn

# Database initialization function (if needed)
def init_db():
    with app.app_context():
        conn = get_db_connection()
        with app.open_resource('schema.sql', mode='r') as f:
            conn.cursor().executescript(f.read())
        conn.commit()

# Hash password function
def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# Other database-related functions here...

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

UPLOAD_FOLDER = 'test'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

geolocator = Nominatim(user_agent="geoapiExercises")

def init_db():
    with app.app_context():
        conn = get_db_connection()
        with app.open_resource('schema.sql', mode='r') as f:
            conn.cursor().executescript(f.read())
        conn.commit()
        conn.close()

def get_user_id(username):
    conn = sqlite3.connect('geolocated_reports.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM users WHERE user_identifier = ?
    ''', (username,))
    result = cursor.fetchone()
    print("Result:", result)  # Debugging output
    conn.close()
    return result[0] if result else None

def get_weather(latitude, longitude):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=America%2FAnchorage&forecast_days=16"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "current" in data.keys():
            current_data = data["current"]
            temperature = current_data.get("temperature_2m", "N/A")
            humidity = current_data.get("relative_humidity_2m", "N/A")
            wind_speed = current_data.get("wind_speed_10m", "N/A")
            weather = current_data.get("weather_code", "N/A")
            state = current_data.get("state", "N/A")
            county = current_data.get("county", "N/A")
            return state, county, weather, temperature, humidity, wind_speed
        else:
            return None
    except requests.exceptions.RequestException as e:
        print("Error fetching weather data:", e)
        return None

def save_report(user_id, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed):
    print("User ID:", user_id)
    print("Latitude:", latitude)
    print("Longitude:", longitude)
    print("State:", state)
    print("County:", county)
    print("Description:", description)
    print("Filename:", filename)
    print("IP Address:", ip_address)
    print("Weather:", weather)
    print("Temperature:", temperature)
    print("Humidity:", humidity)
    print("Wind Speed:", wind_speed)

    # Get the current date and time
    datetime_entry = datetime.datetime.now()

    # Open database connection
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Execute SQL INSERT statement
        cursor.execute('''
            INSERT INTO reports (user_id, datetime_entry, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, datetime_entry, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed))

        # Commit changes to the database
        conn.commit()
        print("Report saved successfully")
    except Exception as e:
        # Handle any exceptions
        print("Error:", e)
        conn.rollback()
    finally:
        # Close database connection
        conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submit = request.form.get('submit')
        username = request.form.get('username')
        password = request.form.get('password')

        if submit == 'Login':
            cursor = g.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,))
            user = cursor.fetchone()

            if user and user[3] == hash_password(password):
                return redirect(url_for('user_dashboard', username=user[1]))
            else:
                flash('Invalid username or password')
        elif submit == 'Register':
            cursor = g.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,))
            existing_user = cursor.fetchone()

            if not existing_user:
                api_key = str(uuid.uuid4())
                cursor.execute("INSERT INTO users (name, user_identifier, password_hash, api_key) VALUES (?, ?, ?, ?)", (username, username, hash_password(password), api_key))
                g.db.commit()
                return redirect(url_for('user_dashboard', username=username))
            else:
                flash('Username already exists')

    return render_template('login.html')

@app.route('/home/<username>', methods=['GET', 'POST'])
def user_dashboard(username):
    if request.method == 'POST':
        # Handle report submission
        gps_coordinates = request.form.get('gps_coordinates')
        if gps_coordinates:
            latitude, longitude = split_coordinates(gps_coordinates)
        else:
            flash('GPS coordinates are required')
            return redirect(url_for('user_dashboard', username=username))

        description = request.form.get('description')
        file = request.files.get('file')
        state = request.form.get('state')
        county = request.form.get('county')
        weather = request.form.get('weather')
        temperature = request.form.get('temperature')
        humidity = request.form.get('humidity')
        wind_speed = request.form.get('wind_speed')

        # Retrieve user_id based on username
        user_id = get_user_id(username)
        print("User ID:", user_id)  # Debugging output

        if user_id is None:
            flash('User ID not found')
            return redirect(url_for('login'))

        # Print user_id before calling save_report function
        print("User ID before saving report:", user_id)

        # Save the report to the database
        save_report(user_id, latitude, longitude, state, county, description, file.filename if file else None, request.remote_addr, weather, temperature, humidity, wind_speed)

        flash('Report submitted successfully')
        return redirect(url_for('user_dashboard', username=username))

    else:
        # Query the database for the reports that belong to the current user
        conn = sqlite3.connect('geolocated_reports.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reports WHERE user_id = ?
        ''', (get_user_id(username),))
        reports = cursor.fetchall()
        conn.close()

        # Render the user dashboard template
        return render_template('user_dashboard.html', username=username, reports=reports)


@app.route('/logout')
def logout():
    return redirect(url_for('login'))

# Update /report route
@app.route('/report', methods=['POST'])
def report():
    # Retrieve form data
    username = request.form.get('username')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    state = request.form.get('state')
    county = request.form.get('county')
    description = request.form.get('description')
    file = request.files.get('file')
    ip_address = request.form.get('ip_address')

    # Retrieve user_id based on username
    user_id = get_user_id(username)
    if user_id is None:
        flash('User ID not found')
        return redirect(url_for('login'))

    # Retrieve weather data using latitude and longitude
    weather_data = get_weather(latitude, longitude)
    if weather_data:
        _, _, weather, temperature, humidity, wind_speed = weather_data

        # Save the file
        filename = None
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        # Save the report to the database
        save_report(user_id, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed)
        flash('Report submitted successfully')
    else:
        flash("Failed to retrieve weather data. Please try again.")

    return redirect(url_for('login'))

# New endpoint for retrieving reports data
@app.route('/data', methods=['GET'])
def get_reports():
    output_format = request.args.get('output', 'html')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    dist = request.args.get('dist')
    max_reports = int(request.args.get('max')) if request.args.get('max') else None
    sort_order = request.args.get('sort', 'newest')

    # Query the database based on provided parameters
    query = "SELECT * FROM reports WHERE 1=1"
    params = []

    if start_date:
        query += " AND datetime_entry >= ?"
        params.append(start_date)
    if end_date:
        query += " AND datetime_entry <= ?"
        params.append(end_date)
    if lat and lng and dist:
        query += " AND ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) <= ? * ?"
        params.extend([lat, lat, lng, lng, dist, dist])

    if sort_order == 'newest':
        query += " ORDER BY datetime_entry DESC"
    elif sort_order == 'oldest':
        query += " ORDER BY datetime_entry ASC"

    if max_reports:
        query += " LIMIT ?"
        params.append(max_reports)

    cursor = g.db.cursor()
    cursor.execute(query, params)
    reports = cursor.fetchall()

    if output_format == 'csv':
        # Generate CSV file and return it
        csv_output = io.StringIO()
        csv_writer = csv.writer(csv_output)
        csv_writer.writerow([i[0] for i in cursor.description])  # Write headers
        csv_writer.writerows(reports)
        csv_output.seek(0)
        return send_file(csv_output, as_attachment=True, attachment_filename='reports.csv', mimetype='text/csv')
    elif output_format == 'json':
        # Convert reports to JSON and return
        report_dicts = [dict(row) for row in reports]
        return jsonify(report_dicts)
    else:
        # Render HTML template with reports
        return render_template('report.html', reports=reports)

@app.route('/ip_details/<ip_address>')
def show_ip_details(ip_address):
    # Logic to handle IP address details
    return render_template('ip_details.html', ip_address=ip_address)


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

if __name__ == '__main__':
    app.run(port=5000, debug=True)