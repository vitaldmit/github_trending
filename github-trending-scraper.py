import os
import json
import logging

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="logs.log",
    filemode="w",
)


def scrape_github_trending(timeframe="weekly"):
    """
    Извлекает информацию о трендовых репозиториях GitHub.

    Args:
        timeframe: Временной период (daily, weekly, monthly)

    Returns:
        Список словарей с информацией о репозиториях
    """
    url = f"https://github.com/trending?since={timeframe}"

    # Добавляем User-Agent для имитации браузера, чтобы избежать блокировки
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Делаем запрос к странице
    response = requests.get(url, headers=headers)

    # Проверяем успешность запроса
    if response.status_code != 200:
        logging.info(f"Error while requesting: {response.status_code}")
        return None

    # Парсим HTML страницу
    soup = BeautifulSoup(response.text, "html.parser")

    # Находим все блоки с репозиториями
    repo_blocks = soup.select("article.Box-row")

    results = []

    for repo in repo_blocks:
        try:
            # Извлекаем название и ссылку репозитория
            repo_link_element = repo.select_one("h2 a")
            relative_link = repo_link_element.get("href", "")
            full_link = f"https://github.com{relative_link}"
            
            # Получаем название репозитория (автор/название)
            repo_name = relative_link.strip("/")
            
            # Извлекаем описание
            description_element = repo.select_one("p")
            description = description_element.text.strip() if description_element else "Нет описания"
            
            results.append({
                "name": repo_name,
                "url": full_link,
                "description": description
            })
            
        except Exception as e:
            logging.info(f"Error processing repository: {e}")

    return results


def send_to_telegram(chat_id, message, token):
    """
    Отправляет сообщение в Telegram канал или группу.
    
    Args:
        chat_id: ID канала/группы
        message: текст сообщения
        token: Telegram Bot API токен
    """
    if not token:
        raise ValueError("Требуется указать TELEGRAM_BOT_TOKEN как переменную окружения или передать как параметр")

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    response = requests.post(api_url, data=payload)
    
    if response.status_code != 200:
        logging.info(f"Error sending to Telegram: {response.status_code}")
        logging.info(response.text)
        return False

    return True


def main():
    load_dotenv()

    telegram_channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    logging.info("Get the trending GitHub repositories of the week...")
    trending_repos = scrape_github_trending("weekly")

    if trending_repos is not None and trending_repos:
        logging.info(f"Found {len(trending_repos)} repositories")

        # Сохраняем в JSON
        with open("github_trending_repos.json", "w", encoding="utf-8") as f:
            json.dump(trending_repos, f, ensure_ascii=False, indent=4)

        logging.info("The results are saved to the file 'github_trending_repos.json'")

        # Формируем сообщение для Telegram
        message = "<b>🔥 GitHub Trending Репозитории за неделю</b>\n\n"

        for i, repo in enumerate(trending_repos, 1):
            repo_name = repo["name"]
            repo_url = repo["url"]
            repo_desc = repo["description"]

            # Ограничиваем количество репозиториев в одном сообщении,
            # так как Telegram имеет лимит на длину сообщения в 4096 символов
            if i <= 10:
                message += f"<b>{i}. <a href='{repo_url}'>{repo_name}</a></b>\n"
                message += f"{repo_desc}\n\n"
            else:
                # Если репозиториев больше 10, отправляем их в следующем сообщении
                if i == 11:
                    # Отправляем первую часть сообщения
                    logging.info("We are sending the first part of repositories to Telegram...")
                    send_to_telegram(telegram_channel_id, message, token)
                    
                    # Начинаем новое сообщение
                    message = "<b>🔥 GitHub Trending Репозитории (продолжение)</b>\n\n"
                
                message += f"<b>{i}. <a href='{repo_url}'>{repo_name}</a></b>\n"
                message += f"{repo_desc}\n\n"
                
                # Отправляем по частям каждые 10 репозиториев
                if i % 10 == 0 or i == len(trending_repos):
                    logging.info(f"Sending {i//10 + (1 if i % 10 else 0)} part of repositories to Telegram...")
                    send_to_telegram(telegram_channel_id, message, token)
                    message = "<b>🔥 GitHub Trending Репозитории (продолжение)</b>\n\n"

        # Отправляем оставшиеся репозитории, если их меньше 10
        if len(trending_repos) <= 10:
            logging.info("Sending repositories to Telegram...")
            send_to_telegram(telegram_channel_id, message, token)

        logging.info("All data has been successfully sent to the Telegram channel!")
    else:
        logging.info("Failed to retrieve trending repositories data")


if __name__ == "__main__":
    main()
