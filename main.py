import json
import os
import random
import smtplib
import logging
from datetime import datetime, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI
from pathlib import Path
from smtplib import SMTPException
from aiohttp import ClientSession
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio

# Load environment variables
def load_environment_variables():
    """Load environment variables from .env file."""
    script_dir = Path(__file__).resolve().parent
    env_file_path = script_dir / ".env"
    load_dotenv(env_file_path)

# Async API Call for news
async def fetch_news_async(news_api_key, categories="general"):
    """Fetch news asynchronously using aiohttp."""
    async with ClientSession() as session:
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            params = {
                "access_key": news_api_key,
                "languages": "en",
                "sort": "published_desc",
                "date": current_date,
                "limit": 3,
                "categories": categories
            }
            async with session.get("http://api.mediastack.com/v1/news", params=params) as response:
                news_items = await response.json()
                if "data" in news_items:
                    return "\n\n".join(
                        f"Title: {item.get('title', 'No title')}\nDescription: {item.get('description', 'No description')}\nURL: {item.get('url', 'No URL')}"
                        for item in news_items["data"]
                    )
                return "No news found."
        except Exception as e:
            logging.error(f"Error fetching news: {e}")
            return "Error fetching news."
        
# Weather API
async def fetch_weather_from_weatherapi(session, api_key, city_name):
    """Fetch weather from WeatherAPI.com with enhanced formatting."""
    try:
        api_url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={city_name}&aqi=no"
        async with session.get(api_url) as response:
            if response.status != 200:
                raise Exception(f"WeatherAPI.com returned status {response.status}")
            
            weather_data = await response.json()
            if weather_data and "current" in weather_data:
                current = weather_data["current"]
                location = weather_data["location"]
                return {
                    "source": "WeatherAPI.com",
                    "location": {
                        "city": location['name'],
                        "country": location['country']
                    },
                    "current": {
                        "temp_c": current['temp_c'],
                        "condition": current['condition']['text'],
                        "humidity": current['humidity'],
                        "wind_kph": current['wind_kph'],
                        "feels_like": current['feelslike_c'],
                        "last_updated": current['last_updated']
                    }
                }
            raise Exception("Invalid response format from WeatherAPI.com")
    except Exception as e:
        logging.error(f"WeatherAPI.com error: {e}")
        return None

async def fetch_weather_from_weatherbit(session, api_key, city_name, country_code):
    """Fetch weather from Weatherbit (fallback) with enhanced formatting."""
    try:
        api_url = f"https://api.weatherbit.io/v2.0/current?city={city_name}&country={country_code}&key={api_key}"
        async with session.get(api_url) as response:
            if response.status != 200:
                raise Exception(f"Weatherbit returned status {response.status}")
            
            weather_data = await response.json()
            if weather_data and "data" in weather_data and weather_data["data"]:
                data = weather_data["data"][0]
                return {
                    "source": "Weatherbit",
                    "location": {
                        "city": data['city_name'],
                        "country": data['country_code']
                    },
                    "current": {
                        "temp_c": data['temp'],
                        "condition": data['weather']['description'],
                        "humidity": data['rh'],
                        "wind_kph": data['wind_spd'] * 3.6,  # Convert m/s to kph
                        "feels_like": data['app_temp'],
                        "last_updated": data['ob_time']
                    }
                }
            raise Exception("Invalid response format from Weatherbit")
    except Exception as e:
        logging.error(f"Weatherbit error: {e}")
        return None
    
#Function for fault tolerance for the APIs
async def fetch_weather_async(weatherapi_key, weatherbit_key, city_name, country_code):
    """Fetch weather with fault tolerance and enhanced formatting."""
    async with ClientSession() as session:
        weather_result = await fetch_weather_from_weatherapi(session, weatherapi_key, city_name)
        if weather_result:
            logging.info("Weather fetched successfully from WeatherAPI.com")
            return weather_result

        logging.warning("WeatherAPI.com failed, trying Weatherbit...")
        weather_result = await fetch_weather_from_weatherbit(session, weatherbit_key, city_name, country_code)
        if weather_result:
            logging.info("Weather fetched successfully from Weatherbit")
            return weather_result

        return {
            "error": True,
            "message": "Weather information is unavailable from all sources."
        }
        
# Synchronous task fetching
def get_tasks(todoist_api_key):
    """Fetch tasks using Todoist API and return as list of dictionaries."""
    try:
        api = TodoistAPI(todoist_api_key)
        tasks = api.get_tasks()
        return [task.to_dict() for task in tasks]
    except Exception as e:
        logging.error(f"Error fetching tasks: {e}")
        return []

# Async task for fetching news and weather concurrently
async def fetch_updates(news_api_key, weatherapi_key, weatherbit_key, city, country):
    news = await fetch_news_async(news_api_key, categories="technology,science,health")
    weather = await fetch_weather_async(weatherapi_key, weatherbit_key, city, country)
    return news, weather

def format_weather_html(weather_data):
    """Format weather data into HTML."""
    if "error" in weather_data:
        return f"""
        <div class="weather-error">
            <p>{weather_data['message']}</p>
        </div>
        """
    
    # Get weather icon based on condition
    def get_weather_icon(condition):
        condition = condition.lower()
        if "rain" in condition:
            return "🌧️"
        elif "cloud" in condition:
            return "☁️"
        elif "snow" in condition:
            return "❄️"
        elif "clear" in condition or "sunny" in condition:
            return "☀️"
        elif "thunder" in condition or "storm" in condition:
            return "⛈️"
        elif "mist" in condition or "fog" in condition:
            return "🌫️"
        return "🌤️"

    weather_icon = get_weather_icon(weather_data['current']['condition'])
    
    return f"""
    <div class="weather-container">
        <div class="weather-header">
            <h3>{weather_data['location']['city']}, {weather_data['location']['country']}</h3>
            <span class="weather-source">Source: {weather_data['source']}</span>
        </div>
        
        <div class="weather-main">
            <div class="weather-temp">
                <span class="temp-big">{weather_data['current']['temp_c']}°C</span>
                <span class="condition">{weather_icon} {weather_data['current']['condition']}</span>
            </div>
            
            <div class="weather-details">
                <div class="weather-detail-item">
                    <span class="detail-label">Feels Like</span>
                    <span class="detail-value">{weather_data['current']['feels_like']}°C</span>
                </div>
                <div class="weather-detail-item">
                    <span class="detail-label">Humidity</span>
                    <span class="detail-value">{weather_data['current']['humidity']}%</span>
                </div>
                <div class="weather-detail-item">
                    <span class="detail-label">Wind Speed</span>
                    <span class="detail-value">{round(weather_data['current']['wind_kph'], 1)} km/h</span>
                </div>
            </div>
        </div>
        
        <div class="weather-footer">
            Last updated: {weather_data['current']['last_updated']}
        </div>
    </div>
    """

# Add these styles to your HTML template's <style> section:
weather_styles = """
    .weather-container {
        background: linear-gradient(135deg, #6dd5fa, #2980b9);
        color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }

    .weather-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    .weather-header h3 {
        color: white;
        margin: 0;
        font-size: 1.5em;
    }

    .weather-source {
        font-size: 0.8em;
        opacity: 0.8;
    }

    .weather-main {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    .weather-temp {
        text-align: center;
    }

    .temp-big {
        font-size: 3em;
        font-weight: bold;
        display: block;
    }

    .condition {
        font-size: 1.2em;
        display: block;
        margin-top: 5px;
    }

    .weather-details {
        display: grid;
        grid-template-columns: repeat(1, 1fr);
        gap: 10px;
    }

    .weather-detail-item {
        background: rgba(255, 255, 255, 0.1);
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }

    .detail-label {
        display: block;
        font-size: 0.9em;
        opacity: 0.9;
    }

    .detail-value {
        display: block;
        font-size: 1.1em;
        font-weight: bold;
        margin-top: 5px;
    }

    .weather-footer {
        text-align: right;
        font-size: 0.8em;
        opacity: 0.8;
        margin-top: 10px;
    }

    .weather-error {
        background: #ff6b6b;
        color: white;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
"""

# Update your send_email function to use the new weather formatting:
def send_email(sender, recipient, subject, news, weather, tasks, smtp_server, smtp_port, password):
    """Send email with creatively formatted HTML and task display."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        news_content = ""
        for item in news.split("\n\n"):
            title = item.split("Title: ")[1].split("\n")[0] if "Title: " in item else "No title"
            description = item.split("Description: ")[1].split("\n")[0] if "Description: " in item else "No description"
            url = item.split("URL: ")[1] if "URL: " in item else "#"
            news_content += f"""
            <div class="news-item">
                <h3><a href="{url}">{title}</a></h3>
                <p>{description}</p>
            </div>
            """

        # Filter and categorize tasks
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        today_tasks = []
        tomorrow_tasks = []

        for task in tasks:
            due_date = task['due']['date'] if task['due'] else None
            if due_date:
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
                if due_date < today:
                    continue  # Skip past tasks
                elif due_date > day_after_tomorrow:
                    continue  # Skip tasks due after tomorrow
                elif due_date == today:
                    today_tasks.append(task)
                elif due_date == tomorrow:
                    tomorrow_tasks.append(task)

        # Function to get a random task emoji
        def get_task_emoji():
            emojis = ["🚀", "💻", "📚", "🎨", "🔧", "📝", "🔬", "🏋️", "🧘", "🎵"]
            return random.choice(emojis)

        # Create tasks content
        tasks_content = ""
        if today_tasks:
            tasks_content += f"""
            <div class="task-group today">
                <h3>Today's Mission</h3>
                <div class="progress-bar" style="--progress: {len(today_tasks) * 10}%; padding-left: 20px;">
                    <span>{len(today_tasks)} task{'s' if len(today_tasks) > 1 else ''}</span>
                </div>
                <ul>
            """
            for task in today_tasks:
                tasks_content += f"<li>{get_task_emoji()} {task['content']}</li>"
            tasks_content += "</ul></div>"

        if tomorrow_tasks:
            tasks_content += f"""
            <div class="task-group tomorrow">
                <h3>On the Horizon</h3>
                <ul>
            """
            for task in tomorrow_tasks:
                tasks_content += f"<li>{get_task_emoji()} {task['content']}</li>"
            tasks_content += "</ul></div>"

        # HTML template with updated styling
            html_template = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Your Daily Update</title>
                <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                    text-align: center;
                }}
                h2 {{
                    color: #2980b9;
                    text-align: center;
                }}
                h3 {{
                    color: #34495e;
                    margin-bottom: 10px;
                }}
                .section {{
                    background-color: #ffffff;
                    border-radius: 10px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .news-item {{
                    margin-bottom: 15px;
                    border-left: 3px solid #3498db;
                    padding-left: 10px;
                }}
                .news-item h3 {{
                    margin-bottom: 5px;
                }}
                .news-item p {{
                    margin-top: 0;
                }}
                .news-item a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                .news-item a:hover {{
                    text-decoration: underline;
                }}
                .task-group {{
                    margin-bottom: 20px;
                    padding: 15px;
                    border-radius: 5px;
                }}
                .today {{
                    background-color: #e8f4f8;
                }}
                .tomorrow {{
                    background-color: #fff4e6;
                }}
                ul {{
                    list-style-type: none;
                    padding-left: 0;
                }}
                li {{
                    margin-bottom: 10px;
                    font-size: 16px;
                }}
                .progress-bar {{
                    background-color: #e0e0e0;
                    border-radius: 10px;
                    height: 20px;
                    width: 100%;
                    margin-bottom: 15px;
                    position: relative;
                    overflow: hidden;
                }}
                .progress-bar::before {{
                    content: '';
                    display: block;
                    height: 100%;
                    width: var(--progress);
                    background-color: #4caf50;
                    transition: width 0.5s ease-in-out;
                }}
                .progress-bar span {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    color: #333;
                    font-weight: bold;
                }}
                {weather_styles}
            </style>
        </head>
        <body>
            <h1>🌟 Your Daily Launchpad 🚀</h1>
            
            <div class="section">
                <h2>📰 News Flash</h2>
                {news_content}
            </div>
            
            <div class="section">
                <h2>🌤️ Weather Update</h2>
                {weather_content}
            </div>
            
            <div class="section">
                <h2>📝 Mission Control</h2>
                {tasks_content}
            </div>
        </body>
        </html>
        """

        # Format the HTML content
        html_content = html_template.format(
            news_content=news_content,
            weather_content=format_weather_html(weather),
            tasks_content=tasks_content,
            weather_styles=weather_styles
        )
        # Set the email content
        text_part = MIMEText("Your daily update is ready. Please view this email in HTML format.", "plain")
        html_part = MIMEText(html_content, "html")

        msg.attach(text_part)  #notification part
        msg.attach(html_part)  #actuall email

        with smtplib.SMTP(smtp_server, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(sender, password)
            smtp.send_message(msg)
        return "Email sent successfully."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error: {e}")
        return f"Failed to send email: {e}"
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return f"An unexpected error occurred: {e}"

def main():
    load_environment_variables()

    news_api_key = os.getenv("NEWS_API_KEY")
    todoist_api_key = os.getenv("TODOIST_API_KEY")
    weatherapi_key = os.getenv("WEATHERAPI_KEY")  # Primary weather API key
    weatherbit_key = os.getenv("WEATHERBIT_KEY")  # Fallback weather API key
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = sender  # Sending the email to myself

    # Get tasks synchronously
    tasks = get_tasks(todoist_api_key)

    # Run news and weather fetch asynchronously with fault tolerance for weather
    city, country = "Chennai", "IN"
    news, weather = asyncio.run(fetch_updates(
        news_api_key, 
        weatherapi_key,
        weatherbit_key, 
        city, 
        country
    ))

    # Send the email
    send_status = send_email(
        sender=sender,
        recipient=recipient,
        subject="Your Morning Update 🚀",
        news=news,
        weather=weather,
        tasks=tasks,
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        password=password,
    )
    print(send_status)

if __name__ == "__main__":
    main()
