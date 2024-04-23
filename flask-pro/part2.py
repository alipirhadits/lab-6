from flask import Flask, render_template, request, redirect, url_for, flash, g
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
import us
from geopy.geocoders import Nominatim
import requests
import datetime
import uuid  # Import uuid module to generate unique API keys

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Set up database connection
def get_db_connection():
    conn = sqlite3.connect('C:/Users/ap94221/info8000/labs-alipirhadits/lab6\database/geolocated_reports.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

# Set up geocoder
geolocator = Nominatim(user_agent="geoapiExercises")

def get_user_id(username):
    conn = sqlite3.connect('C:/Users/ap94221/info8000/labs-alipirhadits/lab6\database/geolocated_reports.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM users WHERE user_identifier = ?
    ''', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

import requests

def get_weather(latitude, longitude):
    # Construct the API endpoint URL with dynamic latitude and longitude
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=America%2FAnchorage&forecast_days=16"
    # Send a GET request to the API
    response = requests.get(url)
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        print(data)
        # Check if the response contains the expected data structure
        if "current" in data.keys():
            # Extract weather information from the "current" section
            current_data = data["current"]
            temperature = current_data.get("temperature_2m", "N/A")
            humidity = current_data.get("relative_humidity_2m", "N/A")
            wind_speed = current_data.get("wind_speed_10m", "N/A")
            weather = current_data.get("weather_code", "N/A")
            state = current_data.get("state", "N/A")
            county = current_data.get("county", "N/A")

            return state, county, weather, temperature, humidity, wind_speed
    else:
        # If the request was not successful, print an error message
        print("Error fetching weather data. Status code:", response.status_code)
        return None

    
    # Get the filename (if a file was uploaded)
def save_report(user_id, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed):
    # Get the current date and time
    datetime_entry = datetime.datetime.now()

    # Get the user ID
   # user_id =get_user_id(username)

    # Get the filename (if a file was uploaded)
    filename = None
    if filename:
        if hasattr(filename, 'filename'):
            filename = secure_filename(filename.filename)
            # Save the file to disk
            filename.save(os.path.join('C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database/UPLOAD_FOLDER', filename))

    # Save the report to the database
    conn = sqlite3.connect('C:/Users/ap94221/info8000/labs-alipirhadits/lab6\database/geolocated_reports.db')
    cursor = conn.cursor()
    filename = 'yy'
    print("we are here")
    print(weather)
    cursor.execute('''
        INSERT INTO reports (user_id, datetime_entry, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, datetime_entry, latitude, longitude, state, county, description, filename,ip_address, weather, temperature, humidity, wind_speed))
    
    conn.commit()
    conn.close()

# Set up routing
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submit = request.form.get('submit')
        username = request.form.get('username')
        password = request.form.get('password')

        if submit == 'Login':
            # Handle login
            cursor = g.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,))
            user = cursor.fetchone()

            if user and user[3] == hash_password(password):
                return redirect(url_for('user_dashboard', username=user[1], api_key=user[4]))
            else:
                flash('Invalid username or password')
        elif submit == 'Register':
            # Handle registration
            cursor = g.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,))
            existing_user = cursor.fetchone()

            if not existing_user:
             # Generate a unique API key using UUID
             api_key = str(uuid.uuid4())
             cursor.execute("INSERT INTO users (name, user_identifier, password_hash, api_key) VALUES (?, ?, ?, ?)", (username, username, hash_password(password), api_key))
             g.db.commit()
             # Pass the api_key variable to the template
             return redirect(url_for('user_dashboard', username=username, api_key=api_key))
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
        print("hereeee")
        print(description)
        file = request.files.get('file')
        state = request.form.get('state')
        county = request.form.get('county')
        weather = request.form.get('weather')
        temperature = request.form.get('temperature')
        humidity = request.form.get('humidity')
        wind_speed = request.form.get('wind_speed')

        # Save the report to the database
        save_report(username, latitude, longitude, state, county, description, file, weather, temperature, humidity, wind_speed)

        flash('Report submitted successfully')
        return redirect(url_for('user_dashboard', username=username, api_key=request.form.get('api_key')))

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
        return render_template('user_dashboard.html', username=username, api_key=request.args.get('api_key'))















@app.route('/report', methods=['POST'])
def report():
    # Retrieve form data
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    state = request.form.get('state')
    county = request.form.get('county')
    description = request.form.get('description')
    file = request.files.get('file')
    weather = request.form.get('weather')
    temperature = request.form.get('temperature')
    humidity = request.form.get('humidity')
    wind_speed = request.form.get('wind_speed')
    ip_address = request.form.get('ip_address')
    #user_id = request.form.get('ip_address')


    # Debug statements
    print("Form Data:")
    #print("GPS Coordinates:", gps_coordinates)
    print("State:", state)
    print("County:", county)
    print("Description:", description)
    print("File:", file)
    print("Weather:", weather)
    print("Temperature:", temperature)
    print("Humidity:", humidity)
    print("Wind Speed:", wind_speed)
    print("ip_address:", ip_address)

    # Check if GPS coordinates were provided
    if latitude and longitude:
        # Split GPS coordinates into latitude and longitude
        #latitude, longitude = split_coordinates(gps_coordinates)

        # Debug statement
        print("Latitude:", latitude)
        print("Longitude:", longitude)

        # Get weather data
        user_id ="she"
        weather_data = get_weather(latitude, longitude)
        if weather_data:
            state, county, weather, temperature, humidity, wind_speed = weather_data

            # Save the file
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join('C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database', filename))

            # Save the report to the database

            save_report(user_id, latitude, longitude, state, county, description, filename, ip_address, weather, temperature, humidity, wind_speed)
            print(weather_data)
            print("herer")

            return redirect(url_for('user_dashboard', username='user', api_key=request.form.get('api_key')))
    else:
        flash("GPS coordinates are required.")
        print(f"Gps coordinates: {latitude, longitude}")

    return "Submission Done "


























@app.route('/logout')
def logout():
    # Handle user logout
    return redirect(url_for('login'))

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

if __name__ == '__main__':
    app.run(debug=True)




















    from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify, send_file
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
import requests
import datetime
import uuid
from geopy.geocoders import Nominatim
import csv
import io
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE_PATH = 'C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database/geolocated_reports.db'
UPLOAD_FOLDER = 'C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database/UPLOAD_FOLDER'

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
    conn = sqlite3.connect('C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database/geolocated_reports.db')
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
        conn = sqlite3.connect('C:/Users/ap94221/info8000/labs-alipirhadits/lab6/database/geolocated_reports.db')
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


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

if __name__ == '__main__':
    app.run(debug=True)
