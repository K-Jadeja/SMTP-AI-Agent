import os
import smtplib
import logging
from datetime import datetime
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
async def fetch_news_async(news_api_key):
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
    """Fetch tasks using Todoist API."""
    try:
        api = TodoistAPI(todoist_api_key)
        tasks = api.get_tasks()
        if tasks:
            return "Here are your open tasks: " + ", ".join(task.content for task in tasks)
        return "No open tasks."
    except Exception as e:
        logging.error(f"Error fetching tasks: {e}")
        return "Could not fetch tasks."

# Async task for fetching news and weather concurrently
async def fetch_updates(news_api_key, weather_api_key, city, country):
    news = await fetch_news_async(news_api_key)
    weather = await fetch_weather_async(weather_api_key, city, country)
    return news, weather

# Send email
def send_email(sender, recipient, subject, news, weather, tasks, smtp_server, smtp_port, password):
    """Send email with improved HTML formatting."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        # Create news content
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

        # HTML template (inline to avoid file reading issues)
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your Daily Update</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #2980b9;
                }}
                .section {{
                    background-color: #f9f9f9;
                    border-radius: 5px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
                .news-item {{
                    margin-bottom: 15px;
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
            </style>
        </head>
        <body>
            <h1>Good morning! Here's your daily update 🚀</h1>
            
            <div class="section">
                <h2>📰 News</h2>
                {news_content}
            </div>
            
            <div class="section">
                <h2>🌤️ Weather</h2>
                <p>{weather_content}</p>
            </div>
            
            <div class="section">
                <h2>📝 To-Do List</h2>
                <p>{tasks_content}</p>
            </div>
        </body>
        </html>
        """

        # Format the HTML content
        html_content = html_template.format(
            news_content=news_content,
            weather_content=weather,
            tasks_content=tasks
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
