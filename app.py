import os # Import the os module for working with the file system
import sqlite3 # Import the sqlite3 module for working with SQLite databases
import requests # Import the requests module for making HTTP requests
import datetime # Import the datetime module for working with dates and times
import uuid # Import the uuid module for generating unique identifiers
import csv # Import the csv module for working with CSV files
import io # Import the io module for working with input/output operations
import hashlib # Import the hashlib module for generating hash digests
import geopy # Import the geopy module for working with geospatial data
from geopy.geocoders import Nominatim # Import the Nominatim class from the geopy.geocoders module for geocoding addresses
from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify, send_file, send_from_directory, session # Import various Flask-related modules for building the web application
from werkzeug.utils import secure_filename # Import the secure_filename function from the werkzeug.utils module for securing file names
from transformers import pipeline # Import the pipeline function from the transformers module for natural language processing tasks

app = Flask(__name__) # Create a Flask web application
app.secret_key = os.urandom(24) # Generate a secret key for the Flask application

DATABASE_PATH = os.path.join('test', 'geolocated_reports.db') # Define the path to the SQLite database
photo = os.path.join('test', 'photo') # Define the path to the photo directory

if not os.path.exists('test'): # If the 'test' directory does not exist
    os.makedirs('test') # Create the 'test' directory

def get_db_connection(): # Define a function to get a connection to the SQLite database
    conn = getattr(g, '_database', None) # Get the database connection object
    if conn is None: # If the connection object does not exist
        conn = g._database = sqlite3.connect(DATABASE_PATH) # Create a new connection object
        conn.row_factory = sqlite3.Row # Set the row factory to return rows as dictionaries
    return conn # Return the connection object

def init_db(): # Define a function to initialize the SQLite database
    with app.app_context(): # Create an application context
        conn = get_db_connection() # Get a connection to the database
        cursor = conn.cursor() # Create a cursor object
        try: # Try to execute the following code
            cursor.execute(''' # Create the 'users' table
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    user_identifier TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    api_key TEXT NOT NULL
                )
            ''')
            cursor.execute(''' # Create the 'reports' table
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
            conn.commit() # Commit the changes to the database
            print("Database initialization successful") # Print a success message
        except sqlite3.Error as e: # If an error occurs
            print("Error initializing database:", e) # Print an error message
            conn.rollback() # Roll back the changes to the database
        finally: # Regardless of whether an error occurred
            conn.close() # Close the database connection

init_db() # Initialize the database

def save_report(username, latitude, longitude, description, description_category, filename, ip_address): # Define a function to save a report to the database
    print("Username:", username) # Print the username for debugging purposes

    state, county = reverse_geocode(latitude, longitude) # Get the state and county from the latitude and longitude
    description_category = characterize_description(description) # Get the description category from the description
    weather_data = get_weather(latitude, longitude) # Get the weather data from the latitude and longitude
    if weather_data: # If weather data exists
        _, _, weather, temperature, humidity, wind_speed = weather_data # Extract the weather, temperature, humidity, and wind speed from the weather data
    else: # Otherwise
        weather = "N/A" # Set the weather to "N/A"
        temperature = "N/A" # Set the temperature to "N/A"
        humidity = "N/A" # Set the humidity to "N/A"
        wind_speed = "N/A" # Set the wind speed to "N/A"

    datetime_entry = datetime.datetime.now() # Get the current date and time

    conn = get_db_connection() # Get a connection to the database
    cursor = conn.cursor() # Create a cursor object

    user_id = get_user_id(username) # Get the user ID from the username
    print("User ID:", user_id) # Print the user ID for debugging purposes

    try: # Try to execute the following code
        cursor.execute(''' # Insert the report into the 'reports' table
            INSERT INTO reports (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, datetime_entry, latitude, longitude, state, county, description, description_category, filename, ip_address, weather, temperature, humidity, wind_speed))

        conn.commit() # Commit the changes to the database
        print("Report saved successfully") # Print a success message
    except Exception as e: # If an error occurs
        print("Error:", e) # Print an error message
        conn.rollback() # Roll back the changes to the database
    finally: # Regardless of whether an error occurred
        conn.close() # Close the database connection

# Initialize the database
init_db()

# Hash password function and other database-related functions...

@app.before_request # Define a function to execute before each request
def before_request():
    g.db = get_db_connection() # Get a connection to the database and store it in the global 'g' object

@app.teardown_request # Define a function to execute after each request
def teardown_request(exception):
    db = getattr(g, '_database', None) # Get the database connection object from the global 'g' object
    if db is not None: # If the connection object exists
        db.close() # Close the connection

@app.route('/download/<filename>', methods=['GET']) # Define a route to download a file
def download_file(filename):
    directory = os.path.abspath(photo) # Get the absolute path to the photo directory
    print("Directory:", directory) # Print the directory for debugging purposes
    print("Requested Filename:", filename) # Print the requested filename for debugging purposes

    # Check if the file exists in the directory
    file_path = os.path.join(directory, filename) # Join the directory and filename to get the file path
    print("File Path:", file_path) # Print the file path for debugging purposes
    if os.path.exists(file_path): # If the file exists
        # Serve the file
        return send_from_directory(directory, filename, as_attachment=True) # Send the file as an attachment
    else: # Otherwise
        # If the file doesn't exist, return a 404 error
        return "File not found", 404 # Return a "File not found" error message with a 404 status code

def get_user_id(username): # Define a function to get the user ID from the username
    conn = sqlite3.connect(DATABASE_PATH) # Get a connection to the database
    cursor = conn.cursor() # Create a cursor object
    cursor.execute(''' # Select the ID from the 'users' table where the user identifier matches the username
        SELECT id FROM users WHERE user_identifier = ?
    ''', (username,))
    result = cursor.fetchone() # Get the result of the query
    print("Result:", result) # Print the result for debugging purposes
    conn.close() # Close the database connection
    return result[0] if result else None # Return the ID if it exists, otherwise return None

def get_weather(latitude, longitude): # Define a function to get the weather data from the latitude and longitude
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=America%2FAnchorage&forecast_days=16" # Create the URL for the weather API
    try: # Try to execute the following code
        response = requests.get(url) # Send a GET request to the weather API
        response.raise_for_status() # Raise an exception if the status code is not 200 OK
        data = response.json() # Parse the response as JSON
        if "current" in data.keys(): # If the 'current' key exists in the JSON data
            current_data = data["current"] # Get the current weather data
            temperature = current_data.get("temperature_2m", "N/A") # Get the temperature from the current weather data
            humidity = current_data.get("relative_humidity_2m", "N/A") # Get the humidity from the current weather data
            wind_speed = current_data.get("wind_speed_10m", "N/A") # Get the wind speed from the current weather data
            weather = current_data.get("weather_code", "N/A") # Get the weather code from the current weather data
            state = current_data.get("state", "N/A") # Get the state from the current weather data
            county = current_data.get("county", "N/A") # Get the county from the current weather data
            return state, county, weather, temperature, humidity, wind_speed # Return the state, county, weather, temperature, humidity, and wind speed
        else: # Otherwise
            return None # Return None
    except requests.exceptions.RequestException as e: # If a request exception occurs
        print("Error fetching weather data:", e) # Print an error message
        return None # Return None

geolocator = Nominatim(user_agent="test.py/1.0 (Contact: ali.pirhadi@uga.edu) Geocoding Requests") # Create a Nominatim geolocator object for geocoding addresses

def get_location_details(latitude, longitude): # Define a function to get the state and county from the latitude and longitude
    location = geolocator.reverse((latitude, longitude), exactly_one=True) # Get the location details from the latitude and longitude
    if location: # If the location exists
        address = location.address.split(', ') # Split the address into components
        state = address[-2] # Get the state from the address
        country = address[-1] # Get the country from the address
        return state, country # Return the state and country
    else: # Otherwise
        return None, None # Return None for both state and country

def reverse_geocode(latitude, longitude): # Define a function to get the state and county from the latitude and longitude using reverse geocoding
    location = geolocator.reverse((latitude, longitude), exactly_one=True) # Get the location details from the latitude and longitude
    if location: # If the location exists
        address = location.raw['address'] # Get the raw address details
        state = address.get('state', 'N/A') # Get the state from the address
        county = address.get('county', 'N/A') # Get the county from the address
        return state, county # Return the state and county
    else: # Otherwise
        return 'N/A', 'N/A' # Return "N/A" for both state and county

# Initialize the language model
text_classification_model = pipeline("text-classification")

def characterize_description(description): # Define a function to characterize the description using natural language processing
    result = text_classification_model(description) # Classify the description using the language model
    predicted_label = result[0]['label'] # Get the predicted label from the classification result
    return predicted_label # Return the predicted label

# Define a function to save a report to the database
def save_report(username, latitude, longitude, description, description_category, filename, ip_address):
    # Ensure username is not empty
    if not username:
        print("Error: Username cannot be empty")
        return # Exit the function if username is empty

    # Retrieve the user_id using the username
    user_id = username # Using username as user_id

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

def get_reports_by_user_id(user_id): # Define a function to get all reports for a given user ID
    conn = get_db_connection() # Get a connection to the database
    cursor = conn.cursor() # Create a cursor object
    cursor.execute(''' # Select all reports from the 'reports' table where the user ID matches the given user ID
        SELECT * FROM reports WHERE user_id = ?
    ''', (user_id,))
    reports = cursor.fetchall() # Get all the reports from the cursor
    conn.close() # Close the database connection
    return reports # Return the reports

@app.route('/register', methods=['GET', 'POST']) # Define a route for user registration
def register():
    def hash_password(password): # Define a function to hash a password
        # Define the hash_password function here
        return hashlib.sha256(password.encode('utf-8')).hexdigest() # Hash the password using SHA-256

    if request.method == 'POST': # If the request method is POST
        username = request.form.get('username') # Get the username from the form
        password = request.form.get('password') # Get the password from the form

        cursor = g.db.cursor() # Create a cursor object
        cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,)) # Select the user from the 'users' table where the user identifier matches the username
        existing_user = cursor.fetchone() # Get the user from the cursor

        if not existing_user: # If the user does not exist
            api_key = str(uuid.uuid4()) # Generate a new API key
            cursor.execute("INSERT INTO users (name, user_identifier, password_hash, api_key) VALUES (?, ?, ?, ?)", (username, username, hash_password(password), api_key)) # Insert the new user into the 'users' table
            g.db.commit() # Commit the changes to the database
            return redirect(url_for('user_dashboard', username=username)) # Redirect the user to the dashboard
        else: # Otherwise
            flash('Username already exists') # Show a flash message indicating that the username already exists

    return render_template('register.html') # Render the registration template

@app.route('/', methods=['GET', 'POST']) # Define a route for user login
def login():
    def hash_password(password): # Define a function to hash a password
        # Define the hash_password function here
        return hashlib.sha256(password.encode('utf-8')).hexdigest() # Hash the password using SHA-256

    if request.method == 'POST': # If the request method is POST
        submit = request.form.get('submit') # Get the submit button value from the form
        username = request.form.get('username') # Get the username from the form
        password = request.form.get('password') # Get the password from the form

        if submit == 'Login': # If the submit button value is "Login"
            cursor = g.db.cursor() # Create a cursor object
            cursor.execute("SELECT * FROM users WHERE user_identifier = ?", (username,)) # Select the user from the 'users' table where the user identifier matches the username
            user = cursor.fetchone() # Get the user from the cursor

            if user and user[3] == hash_password(password): # If the user exists and the hashed password matches the stored password hash
                # Set the username in the session
                session['username'] = user[1]
                return redirect(url_for('user_dashboard', username=user[1])) # Redirect the user to the dashboard
            else: # Otherwise
                flash('Invalid username or password') # Show a flash message indicating that the username or password is invalid

    return render_template('login.html') # Render the login template

@app.route('/home/<username>', methods=['GET', 'POST']) # Define a route for the user dashboard
def user_dashboard(username):
    if request.method == 'POST': # If the request method is POST
        # Handle report submission
        # Placeholder: Add code for report submission...
        pass
    else: # Otherwise
        # Retrieve user details including the API key
        cursor = g.db.cursor() # Create a cursor object
        cursor.execute(''' # Select the ID and API key from the 'users' table where the user identifier matches the username
            SELECT id, api_key FROM users WHERE user_identifier = ?
        ''', (username,))
        user_data = cursor.fetchone() # Get the user data from the cursor

        if not user_data: # If the user data does not exist
            flash('User not found') # Show a flash message indicating that the user was not found
            return redirect(url_for('login')) # Redirect the user to the login page

        user_id, api_key = user_data # Unpack the user ID and API key from the user data

        # Query the database for the reports that belong to the current user
        cursor.execute(''' # Select all reports from the 'reports' table where the user ID matches the current user ID
            SELECT * FROM reports WHERE user_id = ?
        ''', (user_id,))
        reports = cursor.fetchall() # Get all the reports from the cursor

        # Render the user dashboard template with the API key and reports
        return render_template('user_dashboard.html', username=username, api_key=api_key, reports=reports)

@app.route('/logout') # Define a route for user logout
def logout():
    return redirect(url_for('login')) # Redirect the user to the login page

# Update /report route
@app.route('/report', methods=['POST']) # Define a route for submitting a report
def report():
    username = request.form.get('username') # Get the username from the form
    latitude = request.form.get('latitude') # Get the latitude from the form
    longitude = request.form.get('longitude') # Get the longitude from the form
    state = request.form.get('state') # Get the state from the form
    county = request.form.get('county') # Get the county from the form
    description = request.form.get('description') # Get the description from the form
    description_category = request.form.get('description_category') # Get the description category from the form
    file = request.files.get('file') # Get the file from the form

    ip_address = request.remote_addr # Get the IP address of the client

    if file: # If a file was uploaded
        filename = secure_filename(file.filename) # Secure the filename
        file.save(os.path.join(photo, filename)) # Save the file to the photo directory
    else: # Otherwise
        filename = None # Set the filename to None

    weather_data = get_weather(latitude, longitude) # Get the weather data from the latitude and longitude
    if weather_data: # If weather data exists
        state, county, weather, temperature, humidity, wind_speed = weather_data # Unpack the weather data
        save_report(username, latitude, longitude, description, description_category, filename, ip_address) # Save the report to the database
        flash('Report submitted successfully') # Show a flash message indicating that the report was submitted successfully
    else: # Otherwise
        weather = "N/A" # Set the weather to "N/A"
        temperature = 0.0 # Set the temperature to 0.0
        humidity = 0.0 # Set the humidity to 0.0
        wind_speed = 0.0 # Set the wind speed to 0.0
        save_report(username, latitude, longitude, description, description_category, filename, ip_address) # Save the report to the database
        flash("Failed to retrieve weather data. Report submitted with default weather values.") # Show a flash message indicating that the weather data could not be retrieved

    # Redirect to the sub_report page after submitting the report
    return redirect(url_for('sub_report', username=username))

# New endpoint for retrieving reports data
@app.route('/data', methods=['GET'])
def get_reports():
    output_format = request.args.get('output', 'html') # Get the output format from the query string, default to 'html'
    username = session.get('username') # Get the username from the session
    start_date = request.args.get('start_date') # Get the start date from the query string
    end_date = request.args.get('end_date') # Get the end date from the query string
    lat = request.args.get('lat') # Get the latitude from the query string
    lng = request.args.get('lng') # Get the longitude from the query string
    dist = request.args.get('dist') # Get the distance from the query string
    max_reports = int(request.args.get('max')) if request.args.get('max') else None # Get the maximum number of reports from the query string, or set to None if not provided
    sort_order = request.args.get('sort', 'newest') # Get the sort order from the query string, default to 'newest'
    state = request.args.get('state') # Get the state from the query string
    county = request.args.get('county') # Get the county from the query string

    # Query the database based on provided parameters
    query = "SELECT reports.*, users.name AS username FROM reports LEFT JOIN users ON reports.user_id = users.user_identifier WHERE 1=1" # Start the query with a dummy condition
    params = [] # Initialize an empty list for query parameters

    if start_date: # If a start date is provided
        query += " AND datetime_entry >= ?" # Add a condition to the query
        params.append(start_date) # Add the start date to the query parameters
    if end_date: # If an end date is provided
        query += " AND datetime_entry <= ?" # Add a condition to the query
        params.append(end_date) # Add the end date to the query parameters
    if lat and lng and dist: # If a latitude, longitude, and distance are provided
        query += " AND ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) <= ? * ?" # Add a condition to the query
        params.extend([lat, lat, lng, lng, dist, dist]) # Add the latitude, longitude, and distance to the query parameters
    if state: # If a state is provided
        query += " AND state = ?" # Add a condition to the query
        params.append(state) # Add the state to the query parameters
    if county: # If a county is provided
        query += " AND county = ?" # Add a condition to the query
        params.append(county) # Add the county to the query parameters

    if sort_order == 'newest': # If the sort order is 'newest'
        query += " ORDER BY datetime_entry DESC" # Add an ORDER BY clause to the query
    elif sort_order == 'oldest': # If the sort order is 'oldest'
        query += " ORDER BY datetime_entry ASC" # Add an ORDER BY clause to the query

    if max_reports: # If a maximum number of reports is provided
        query += " LIMIT ?" # Add a LIMIT clause to the query
        params.append(max_reports) # Add the maximum number of reports to the query parameters

    cursor = g.db.cursor() # Create a cursor object
    cursor.execute(query, params) # Execute the query with the provided parameters
    reports = cursor.fetchall() # Get all the reports from the cursor

    if output_format == 'csv': # If the output format is 'csv'
        # Generate CSV file and return it
        csv_output = io.StringIO() # Create an in-memory string buffer for the CSV output
        csv_writer = csv.writer(csv_output) # Create a CSV writer object
        csv_writer.writerow([i[0] for i in cursor.description]) # Write the header row to the CSV output
        csv_writer.writerows(reports) # Write the report data to the CSV output
        csv_output.seek(0) # Reset the buffer position to the beginning
        return send_file(csv_output, as_attachment=True, attachment_filename='reports.csv', mimetype='text/csv') # Send the CSV output as a file download
    elif output_format == 'json': # If the output format is 'json'
        # Convert reports to JSON and return
        report_dicts = [dict(row) for row in reports] # Convert the report data to a list of dictionaries
        return jsonify(report_dicts) # Send the report data as JSON
    else: # Otherwise
        # Render HTML template with reports
        # Render HTML template with reports and username
        return render_template('report.html', reports=reports, username=username) # Render the report template with the report data and username

# New endpoint for saving reports in CSV format
from flask import Response

@app.route('/save_csv', methods=['GET'])
def save_reports_csv():
    start_date = request.args.get('start_date') # Get the start date from the query string
    end_date = request.args.get('end_date') # Get the end date from the query string
    lat = request.args.get('lat') # Get the latitude from the query string
    lng = request.args.get('lng') # Get the longitude from the query string
    dist = request.args.get('dist') # Get the distance from the query string
    max_reports = int(request.args.get('max')) if request.args.get('max') else None # Get the maximum number of reports from the query string, or set to None if not provided
    sort_order = request.args.get('sort', 'newest') # Get the sort order from the query string, default to 'newest'
    state = request.args.get('state') # Get the state from the query string
    county = request.args.get('county') # Get the county from the query string

    # Query the database based on provided parameters
    query = "SELECT reports.*, users.name AS username FROM reports LEFT JOIN users ON reports.user_id = users.user_identifier WHERE 1=1" # Start the query with a dummy condition
    params = [] # Initialize an empty list for query parameters

    if start_date: # If a start date is provided
        query += " AND datetime_entry >= ?" # Add a condition to the query
        params.append(start_date) # Add the start date to the query parameters
    if end_date: # If an end date is provided
        query += " AND datetime_entry <= ?" # Add a condition to the query
        params.append(end_date) # Add the end date to the query parameters
    if lat and lng and dist: # If a latitude, longitude, and distance are provided
        query += " AND ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) <= ? * ?" # Add a condition to the query
        params.extend([lat, lat, lng, lng, dist, dist]) # Add the latitude, longitude, and distance to the query parameters
    if state: # If a state is provided
        query += " AND state = ?" # Add a condition to the query
        params.append(state) # Add the state to the query parameters
    if county: # If a county is provided
        query += " AND county = ?" # Add a condition to the query
        params.append(county) # Add the county to the query parameters

    if sort_order == 'newest': # If the sort order is 'newest'
        query += " ORDER BY datetime_entry DESC" # Add an ORDER BY clause to the query
    elif sort_order == 'oldest': # If the sort order is 'oldest'
        query += " ORDER BY datetime_entry ASC" # Add an ORDER BY clause to the query

    if max_reports: # If a maximum number of reports is provided
        query += " LIMIT ?" # Add a LIMIT clause to the query
        params.append(max_reports) # Add the maximum number of reports to the query parameters

    cursor = g.db.cursor() # Create a cursor object
    cursor.execute(query, params) # Execute the query with the provided parameters
    reports = cursor.fetchall() # Get all the reports from the cursor

    # Generate CSV file content
    csv_output = io.StringIO() # Create an in-memory string buffer for the CSV output
    csv_writer = csv.writer(csv_output) # Create a CSV writer object
    csv_writer.writerow([i[0] for i in cursor.description]) # Write the header row to the CSV output
    csv_writer.writerows(reports) # Write the report data to the CSV output
    csv_output.seek(0) # Reset the buffer position to the beginning

    # Create a Response object with CSV data
    response = Response(csv_output, mimetype='text/csv') # Create a Response object with the CSV data
    response.headers['Content-Disposition'] = 'attachment; filename=reports.csv' # Set the Content-Disposition header to indicate that the response is a file download

    return response # Return the Response object

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

        print(reports) # Add this line to print the fetched reports

        # Get the api key for the user
        cursor.execute('SELECT api_key FROM users WHERE user_identifier = ?', (username,))
        api_key = cursor.fetchone()[0]

        # Render the sub_report template with the reports and api key
        return render_template('sub_report.html', username=username, reports=reports, api_key=api_key)

if __name__ == '__main__':
    app.run(port=5000, debug=True) # Run the Flask application on port 5000 in debug mode
