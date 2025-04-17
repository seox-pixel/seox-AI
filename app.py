from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from openrouter_api import call_openrouter_api
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import csv

# Set up logging
if not os.path.exists('logs'):
    os.makedirs('logs')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'seox_secret_key_for_waitlist'  # Added secret key for flash messages

# Configure logging
handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Waitlist storage - in a real app, this would be a database
waitlist_emails = []

# Ensure the CSV file exists with headers
def ensure_csv_exists():
    if not os.path.exists('waitlist.csv'):
        with open('waitlist.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Email', 'Feedback', 'Timestamp'])  # Write header row
        app.logger.info("Created waitlist.csv file with headers")

# Function to log waitlist signups to a file for persistence
def log_waitlist_signup(email):
    try:
        with open('logs/waitlist.log', 'a') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} - {email}\n")
    except Exception as e:
        app.logger.error(f"Error logging waitlist signup: {str(e)}")

# Function to simulate sending a confirmation email
# In a production environment, you would use a real email service
def send_confirmation_email(email):
    try:
        # Log the email sending attempt
        app.logger.info(f"Would send confirmation email to: {email}")
        return True
    except Exception as e:
        app.logger.error(f"Error sending confirmation email: {str(e)}")
        return False

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    app.logger.error(f"Page not found: {request.path}")
    return render_template('results.html', error="Page not found", keyword=""), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors"""
    app.logger.error(f"Server error: {str(e)}")
    return render_template('results.html', error="Internal server error. Please try again later.", keyword=""), 500

@app.route('/')
def landing():
    """Render the landing page"""
    app.logger.info("Landing page accessed")
    return render_template('landing.html')

@app.route('/beta.html')
def beta_page():
    """Render the beta page"""
    app.logger.info("Beta page accessed")
    return render_template('beta.html')

@app.route('/waitlist.html')
def waitlist_page():
    """Render the waitlist page"""
    app.logger.info("Waitlist page accessed")
    return render_template('waitlist.html')

@app.route('/input')
def input_page():
    """Redirect to beta page"""
    app.logger.info("Input page accessed - redirecting to beta page")
    return redirect('/beta.html')

@app.route('/research', methods=['POST'])
def research():
    """Handle the form submission and call the OpenRouter API"""
    # Get the keyword from the form
    keyword = request.form.get('keyword', '')
    
    if not keyword:
        app.logger.warning("Empty keyword submitted")
        return render_template('results.html', error="Please enter a keyword", keyword="")
    
    app.logger.info(f"Research requested for keyword: {keyword}")
    
    try:
        # Call the OpenRouter API
        result = call_openrouter_api(keyword)
        
        if result['success']:
            app.logger.info(f"Successfully retrieved {len(result['data'])} keyword suggestions")
            # If successful, render the results template with the keyword data
            return render_template('results.html', 
                                keyword=keyword, 
                                keywords=result['data'],
                                error=None)
        else:
            app.logger.error(f"API error: {result['error']}")
            # If there was an error, render the results template with the error message
            return render_template('results.html', 
                                keyword=keyword, 
                                keywords=None,
                                error=result['error'])
    except Exception as e:
        app.logger.error(f"Unexpected error in research route: {str(e)}")
        return render_template('results.html',
                            keyword=keyword,
                            keywords=None,
                            error="An unexpected error occurred. Please try again later.")

@app.route('/waitlist', methods=['POST'])
def waitlist():
    """Handle waitlist form submission"""
    email = request.form.get('email', '').strip()
    feedback = request.form.get('feedback', '').strip()
    
    # Validate email is not empty
    if not email:
        app.logger.warning("Empty email submitted to waitlist")
        return render_template('waitlist.html', error="Email is required"), 400
    
    # Log the waitlist signup
    log_waitlist_signup(email)
    app.logger.info(f"Waitlist form submitted with email: {email}")
    
    # Ensure CSV file exists
    ensure_csv_exists()
    
    # Save to CSV file
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('waitlist.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([email, feedback, timestamp])
        app.logger.info(f"Saved waitlist entry to CSV: {email}")
    except Exception as e:
        app.logger.error(f"Error saving to CSV: {str(e)}")
    
    # In a real app, you would save this to a database
    is_new_signup = email not in waitlist_emails
    if is_new_signup:
        waitlist_emails.append(email)
        app.logger.info(f"New email added to waitlist: {email}")
        
        # Send confirmation email
        email_sent = send_confirmation_email(email)
        
        return render_template('thank_you.html', 
                              email=email, 
                              feedback=feedback,
                              email_sent=email_sent)
    else:
        app.logger.info(f"Email already in waitlist: {email}")
        return render_template('thank_you.html', 
                              email=email,
                              feedback=feedback,
                              already_registered=True)

# Route to view all waitlist emails (admin only - would require authentication in production)
@app.route('/admin/waitlist', methods=['GET'])
def view_waitlist():
    """View all waitlist emails - for demonstration purposes only"""
    try:
        # Read from the waitlist log file
        waitlist_entries = []
        if os.path.exists('logs/waitlist.log'):
            with open('logs/waitlist.log', 'r') as f:
                waitlist_entries = f.readlines()
        
        # Read from the CSV file
        csv_entries = []
        if os.path.exists('waitlist.csv'):
            with open('waitlist.csv', 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header row
                csv_entries = list(reader)
        
        return render_template('admin_waitlist.html', 
                              waitlist_emails=waitlist_emails,
                              waitlist_entries=waitlist_entries,
                              csv_entries=csv_entries)
    except Exception as e:
        app.logger.error(f"Error viewing waitlist: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Debug route to test if the application is working correctly
@app.route('/debug')
def debug():
    """Debug route to test if the application is working correctly"""
    app.logger.info("Debug route accessed")
    return jsonify({
        "status": "ok",
        "message": "SEOX application is running correctly",
        "routes": {
            "/": "Landing page",
            "/beta.html": "Beta page for keyword research",
            "/waitlist.html": "Waitlist signup page",
            "/research": "Process keyword research (POST)",
            "/waitlist": "Join waitlist (POST)",
            "/admin/waitlist": "View waitlist entries",
            "/debug": "This debug endpoint"
        }
    })

if __name__ == '__main__':
    # Ensure the CSV file exists when the app starts
    ensure_csv_exists()
    app.logger.info("Starting SEOX application")
    app.run(host='0.0.0.0', port=5000, debug=True)
