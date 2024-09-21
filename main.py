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

# Async API Call for weather
async def fetch_weather_async(api_key, city_name, country_code):
    """Fetch weather asynchronously using aiohttp."""
    async with ClientSession() as session:
        try:
            api_url = f"https://api.weatherbit.io/v2.0/current?city={city_name}&country={country_code}&key={api_key}"
            async with session.get(api_url) as response:
                weather_data = await response.json()
                if weather_data and "data" in weather_data:
                    data = weather_data["data"][0]
                    return f"Weather in {data['city_name']}, {data['country_code']}: {data['temp']}°C, {data['weather']['description']}."
                return "No weather information."
        except Exception as e:
            logging.error(f"Error fetching weather: {e}")
            return "Weather information is unavailable."

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
async def fetch_updates(news_api_key, weather_api_key, city, country):
    news = await fetch_news_async(news_api_key, categories="technology,science,health")
    weather = await fetch_weather_async(weather_api_key, city, country)
    return news, weather

# Send email
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
                <p>{weather_content}</p>
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
            weather_content=weather,
            tasks_content=tasks_content
        )

        # Set the email content
        text_part = MIMEText("Your daily update is ready. Please view this email in HTML format.", "plain")
        html_part = MIMEText(html_content, "html")

        msg.attach(text_part)
        msg.attach(html_part)

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

# Main function for running everything
def main():
    load_environment_variables()

    news_api_key = os.getenv("NEWS_API_KEY")
    todoist_api_key = os.getenv("TODOIST_API_KEY")
    weather_api_key = os.getenv("WEATHER_API_KEY")
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = sender  # Sending the email to yourself

    # Get tasks synchronously
    tasks = get_tasks(todoist_api_key)

    # Run news and weather fetch asynchronously
    city, country = "Chennai", "IN"
    news, weather = asyncio.run(fetch_updates(news_api_key, weather_api_key, city, country))

    # Construct email body
    message_body = (
        f"Good morning! Here's your update:\n\n"
        f"---- NEWS ----\n{news}\n\n"
        f"---- WEATHER ----\n{weather}\n\n"
        f"---- TO-DO LIST ----\n{tasks}\n"
    )

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
