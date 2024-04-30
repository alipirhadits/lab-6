import os
import sqlite3
import requests
import datetime
import uuid
import csv
import io
import hashlib
import geopy
from geopy.geocoders import Nominatim
from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify, send_file, send_from_directory, session
from werkzeug.utils import secure_filename
from transformers import pipeline

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE_PATH = os.path.join('test', 'geolocated_reports.db')
photo = os.path.join('test', 'photo')

if not os.path.exists('test'):
    os.makedirs('test')

def get_db_connection():
    conn = getattr(g, '_database', None)
    if conn is None:
        conn = g._database = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    user_identifier TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    api_key TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    datetime_entry TIMESTAMP NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    state TEXT,
                    county TEXT,
                    description TEXT,
                    filename TEXT,
                    ip_address TEXT NOT NULL,
                    weather TEXT,
                    temperature REAL,
                    humidity REAL,
                    wind_speed REAL,
                    description_category TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_identifier)
                )
            ''')
            conn.commit()
            print("Database initialization successful")
        except sqlite3.Error as e:
            print("Error initializing database:", e)
            conn.rollback()
        finally:
            conn.close()

init_db()

def save_report(username, latitude, longitude, description, description_category, filename, ip_address):
    print("Username:", username)  # Debugging print statement

    state, county = reverse_geocode(latitude, longitude)
    description_category = characterize_description(description)
    weather_data = get_weather(latitude, longitude)
    if weather_data:
        _, _, weather, temperature, humidity, wind_speed = weather_data
    else:
        weather = "N/A"
        temperature = "N/A"
        humidity = "N/A"
        wind_speed = "N/A"

    datetime_entry = datetime.datetime.now()

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = get_user_id(username)
    print("User ID:", user_id)  # Debugging print statement

    try:
        cursor.execute('''
            INSERT INTO reports (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed))

        conn.commit()
        print("Report saved successfully")
    except Exception as e:
        print("Error:", e)
        conn.rollback()
    finally:
        conn.close()


# Initialize the database
init_db()

# Hash password function and other database-related functions...

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    directory = os.path.abspath(photo)
    print("Directory:", directory)
    print("Requested Filename:", filename)

    # Check if the file exists in the directory
    file_path = os.path.join(directory, filename)
    print("File Path:", file_path)
    if os.path.exists(file_path):
        # Serve the file
        return send_from_directory(directory, filename, as_attachment=True)
    else:
        # If the file doesn't exist, return a 404 error
        return "File not found", 404

def get_user_id(username):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM users WHERE user_identifier = ?
    ''', (username,))
    result = cursor.fetchone()
    print("Result:", result)  # Debugging output
    conn.close()
    return result[0] if result else None

def get_weather(latitude, longitude):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto&forecast_days=16"
     
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

geolocator = Nominatim(user_agent="test.py/1.0 (Contact: alipirhadits@gmail.com) Geocoding Requests")

def get_location_details(latitude, longitude):
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    if location:
        address = location.address.split(', ')
        state = address[-2]
        country = address[-1]
        return state, country
    else:
        return None, None

def reverse_geocode(latitude, longitude):
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    if location:
        address = location.raw['address']
        state = address.get('state', 'N/A')
        county = address.get('county', 'N/A')
        return state, county
    else:
        return 'N/A', 'N/A'

# Initialize the language model
text_classification_model = pipeline("text-classification")

def characterize_description(description):
    result = text_classification_model(description)
    predicted_label = result[0]['label']
    return predicted_label

    # Extract the predicted label and return it
    predicted_label = result[0]['label']
    return predicted_label

def save_report(username, latitude, longitude, description, description_category, filename, ip_address):
    # Ensure username is not empty
    if not username:
        print("Error: Username cannot be empty")
        return  # Exit the function if username is empty

    # Retrieve the user_id using the username
    user_id = username  # Using username as user_id

    # Ensure that user_id is not None before proceeding
    if user_id is not None:
        # Get state and county from reverse geocoding
        state, county = reverse_geocode(latitude, longitude)

        # Automatically characterize the description
        description_category = characterize_description(description)

        # Get weather data from the API
        weather_data = get_weather(latitude, longitude)
        if weather_data:
            _, _, weather, temperature, humidity, wind_speed = weather_data
        else:
            # If weather data is not available, set default values or handle the error as needed
            weather = "N/A"
            temperature = "N/A"
            humidity = "N/A"
            wind_speed = "N/A"

        print("User ID:", user_id)
        print("Latitude:", latitude)
        print("Longitude:", longitude)
        print("State:", state)
        print("County:", county)
        print("Description:", description)
        print("Description Category:", description_category)
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
                INSERT INTO reports (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed))

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
    else:
        print("User not found for username:", username)


def get_reports_by_user_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM reports WHERE user_id = ?
    ''', (user_id,))
    reports = cursor.fetchall()
    conn.close()
    return reports


@app.route('/register', methods=['GET', 'POST'])
def register():
    def hash_password(password):
        # Define the hash_password function here
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

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

    return render_template('register.html')


@app.route('/', methods=['GET', 'POST'])
def login():
    def hash_password(password):
        # Define the hash_password function here
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    if request.method == 'POST':
        submit = request.form.get('submit')
        username = request.form.get('username')
        password = request.form.get('password')

        if submit == 'Login':
            cursor = g.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,))
            user = cursor.fetchone()

            if user and user[3] == hash_password(password):
                # Set the username in the session
                session['username'] = user[1]
                return redirect(url_for('user_dashboard', username=user[1]))
            else:
                flash('Invalid username or password')

    return render_template('login.html')



@app.route('/home/<username>', methods=['GET', 'POST'])
def user_dashboard(username):
    if request.method == 'POST':
        # Handle report submission
        # Placeholder: Add code for report submission...
        pass
    else:
        # Retrieve user details including the API key
        cursor = g.db.cursor()
        cursor.execute('''
            SELECT id, api_key FROM users WHERE user_identifier = ?
        ''', (username,))
        user_data = cursor.fetchone()

        if not user_data:
            flash('User not found')
            return redirect(url_for('login'))

        user_id, api_key = user_data

        # Query the database for the reports that belong to the current user
        cursor.execute('''
            SELECT * FROM reports WHERE user_id = ?
        ''', (user_id,))
        reports = cursor.fetchall()

        # Render the user dashboard template with the API key and reports
        return render_template('user_dashboard.html', username=username, api_key=api_key, reports=reports)


@app.route('/logout')
def logout():
    return redirect(url_for('login'))

# Update /report route
@app.route('/report', methods=['POST'])
def report():
    username = request.form.get('username')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    state = request.form.get('state')
    county = request.form.get('county')
    description = request.form.get('description')
    description_category = request.form.get('description_category')
    file = request.files.get('file')

    ip_address = request.remote_addr

    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(photo, filename))
    else:
        filename = None

    weather_data = get_weather(latitude, longitude)
    if weather_data:
        state, county, weather, temperature, humidity, wind_speed = weather_data
        save_report(username, latitude, longitude, description, description_category, filename, ip_address)
        flash('Report submitted successfully')
    else:
        weather = "N/A"
        temperature = 0.0
        humidity = 0.0
        wind_speed = 0.0
        save_report(username, latitude, longitude, description, description_category, filename, ip_address)
        flash("Failed to retrieve weather data. Report submitted with default weather values.")

    # Redirect to the sub_report page after submitting the report
    return redirect(url_for('sub_report', username=username))



# New endpoint for retrieving reports data
@app.route('/data', methods=['GET'])
def get_reports():
    output_format = request.args.get('output', 'html')
    username = session.get('username')  # Get the username from the session
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    dist = request.args.get('dist')
    max_reports = int(request.args.get('max')) if request.args.get('max') else None
    sort_order = request.args.get('sort', 'newest')
    state = request.args.get('state')
    county = request.args.get('county')

    # Query the database based on provided parameters
    query = "SELECT reports.*, users.name AS username FROM reports LEFT JOIN users ON reports.user_id = users.user_identifier WHERE 1=1"
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
    if state:
        query += " AND state = ?"
        params.append(state)
    if county:
        query += " AND county = ?"
        params.append(county)

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
        # Render HTML template with reports and username
        return render_template('report.html', reports=reports, username=username)

# New endpoint for saving reports in CSV format
from flask import Response

@app.route('/save_csv', methods=['GET'])
def save_reports_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    dist = request.args.get('dist')
    max_reports = int(request.args.get('max')) if request.args.get('max') else None
    sort_order = request.args.get('sort', 'newest')
    state = request.args.get('state')
    county = request.args.get('county')

    # Query the database based on provided parameters
    query = "SELECT reports.*, users.name AS username FROM reports LEFT JOIN users ON reports.user_id = users.user_identifier WHERE 1=1"
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
    if state:
        query += " AND state = ?"
        params.append(state)
    if county:
        query += " AND county = ?"
        params.append(county)

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

    # Generate CSV file content
    csv_output = io.StringIO()
    csv_writer = csv.writer(csv_output)
    csv_writer.writerow([i[0] for i in cursor.description])  # Write headers
    csv_writer.writerows(reports)
    csv_output.seek(0)

    # Create a Response object with CSV data
    response = Response(csv_output, mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=reports.csv'

    return response

@app.route('/ip_details/<ip_address>')
def show_ip_address_details(ip_address):
    print(f"IP Address: {ip_address}")

    # Retrieve the report data from the database
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM reports WHERE ip_address = ?", (ip_address,))
    result = cursor.fetchone()

    print(f"Query result: {result}")

    if result is None:
        flash('IP Address not found')
        return redirect(url_for('login'))

    # Retrieve the latitude and longitude values from the result
    latitude, longitude = result['latitude'], result['longitude']

    # Pass the latitude and longitude values to the template
    return render_template('ip_details.html', ip_address=ip_address, latitude=latitude, longitude=longitude)


@app.route('/sub_report/<username>', methods=['GET', 'POST'])
def sub_report(username):
    if request.method == 'POST':
        # Handle form submission
        # Retrieve form data
        # Process the submitted data
        # Redirect or render appropriate response
        pass
    else:
        # Query the database for the user's ID
        cursor = g.db.cursor()
        cursor.execute('SELECT id FROM users WHERE user_identifier = ?', (username,))
        user_id = cursor.fetchone()[0]

        # Query the database for the reports that belong to the current user
        cursor.execute('SELECT * FROM reports WHERE user_id = ?', (username,))
        reports = cursor.fetchall()

        print(reports)  # Add this line to print the fetched reports

        # Get the api key for the user
        cursor.execute('SELECT api_key FROM users WHERE user_identifier = ?', (username,))
        api_key = cursor.fetchone()[0]

        # Render the sub_report template with the reports and api key
        return render_template('sub_report.html', username=username, reports=reports, api_key=api_key)

from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

# Create a Nominatim geocoder instance with a longer timeout value
geolocator = Nominatim(user_agent="my_geocoder", timeout=10)
def do_geocode(address, attempt=1, max_attempts=5):
    geolocator = Nominatim(user_agent="my_geocoder", timeout=10)  # Adjust timeout value here
    try:
        return geolocator.geocode(address)
    except GeocoderTimedOut:
        if attempt <= max_attempts:
            return do_geocode(address, attempt=attempt+1)
        raise

if __name__ == '__main__':
    app.run(port=5000, debug=True)