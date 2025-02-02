from functions import RedditScrapper, load_api_credentials

if __name__ == "__main__":
    # Load API credentials
    credentials = load_api_credentials()

    # Initialize the RedditScraper class
    scrapper = RedditScrapper(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        user_agent=credentials["user_agent"]    )

    # define keywords
    therapy = "emdr"
    subreddit_name = "PTSD"

    output_file = f"incremental_{therapy}_results.csv"

    # Scrape and filter data:
    filtered_data = scrapper.scrape_and_filter(
        subreddit_name=subreddit_name,
        therapy=therapy,
        limit=100,  # Specify the number of rows you want in the final CSV
        output_file = output_file,
        save_every=50,
        limit_comment=None
    )



