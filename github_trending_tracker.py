#!/usr/bin/env python3
import os
import json
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime

from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# File to store repository data
DATA_FILE = "github_trending_history.json"
CONFIG_FILE = "telegram_config.json"


def fetch_trending_repos():
    """Fetch trending repositories from GitHub"""
    url = "https://github.com/trending"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error fetching data: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    repo_articles = soup.select("article.Box-row")

    repos = []
    for article in repo_articles:
        # Extract repository name (username/repo)
        repo_link = article.select_one("h2 a")
        if repo_link:
            repo_path = repo_link.get("href", "").strip("/")

            # Extract description
            description_elem = article.select_one("p")
            description = description_elem.text.strip() if description_elem else ""

            # Extract language
            language_elem = article.select_one("span[itemprop='programmingLanguage']")
            language = language_elem.text.strip() if language_elem else "Unknown"

            # Extract stars
            stars_elem = article.select("a.Link--muted")[0] if article.select("a.Link--muted") else None
            stars = stars_elem.text.strip() if stars_elem else "0"

            repos.append({
                "repo": repo_path,
                "description": description,
                "language": language,
                "stars": stars,
                "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    return repos

def load_history():
    """Load previously saved repository data"""
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error reading {DATA_FILE}, starting with empty history")
        return {}

def save_history(history):
    """Save repository data to file"""
    with open(DATA_FILE, "w") as f:
        json.dump(history, f, indent=2)

def return_telegram_config():
    """Return Telegram configuration"""
    load_dotenv()
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    config = {"token": token, "chat_id": chat_id}
    return config

def send_to_telegram(message, config):
    """Send message to Telegram"""
    token = config["token"]
    chat_id = config["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True  # Disable URL previews
    }

    response = requests.post(url, data=payload)
    return response.status_code == 200

def format_repos_for_telegram(repos):
    """Format all new repositories for a single Telegram message"""
    today = datetime.now().strftime("%Y-%m-%d")

    if not repos:
        return f"<b>GitHub Trending Update ({today})</b> No new trending repositories found today."

    message = f"<b>🔥 New GitHub Trending Repositories ({today})</b>\n\n"

    for i, repo in enumerate(repos, 1):
        repo_url = f"https://github.com/{repo['repo']}"
        message += (
            f"{i}. <a href='{repo_url}'>{repo['repo']}</a>\n"
            f"<b>Language:</b> {repo['language']} | <b>Stars:</b> {repo['stars']}\n"
            f"<b>Description:</b> {repo['description']}\n\n"
        )

    message += f"Total new repositories: {len(repos)}"
    return message

def main():
    # Load Telegram configuration
    telegram_config = return_telegram_config()

    # Load existing history
    history = load_history()

    # Fetch current trending repositories
    current_repos = fetch_trending_repos()

    # Find new repositories
    new_repos = []
    for repo in current_repos:
        repo_name = repo["repo"]
        if repo_name not in history:
            new_repos.append(repo)
            history[repo_name] = repo

    # Save updated history
    save_history(history)

    # Display results
    if new_repos:
        logger.info(f"Found {len(new_repos)} new trending repositories:")

    # Send all new repositories as a single message to Telegram
    message = format_repos_for_telegram(new_repos)
    success = send_to_telegram(message, telegram_config)

    if success:
        logger.info("Sent update to Telegram ✓")
    else:
        logger.error("Failed to send update to Telegram ✗")

    logger.info(f"Total repositories tracked: {len(history)}")


if __name__ == "__main__":
    main()
