from functions_alternative1 import RedditExperienceScraper
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    # Set your Reddit API credentials
    client_id = os.getenv("client_id")
    client_secret = os.getenv("client_secret")
    user_agent = os.getenv("user_agent")

    # Define the subreddits to scrape
    subreddits = ["PTSD", ]

    # Initialize and run the scraper
    scraper = RedditExperienceScraper(client_id, client_secret, user_agent)
    scraper.scrape_and_filter_posts(search_term="EMDR", limit=100, time_filter='year')
    scraper.save_to_csv()