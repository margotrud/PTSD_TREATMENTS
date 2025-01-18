import pandas as pd
import praw
import os
import prawcore
from dotenv import load_dotenv
import re
import time


class RedditScrapper:
    def __init__(self, client_id, client_secret, user_agent):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )

    def scrape_and_filter(self, subreddit_name, therapy, question_keywords, inclusion_keywords, exclusion_keywords,
                          limit, output_file, save_every, limit_comment):
        results = []
        subreddit = self.reddit.subreddit(subreddit_name)
        fetched_posts = 0
        after = None
        processed_ids = set()  # Set to track processed IDs

        # Load existing data if the file exists
        if os.path.exists(output_file):
            existing_data = pd.read_csv(output_file)
            processed_ids = set(existing_data["id"])  # Add existing IDs to the set
            results = existing_data.to_dict("records")
            print(f"Loaded {len(processed_ids)} existing records from {output_file}")

        def append_to_csv(file_path, new_data):
            """Append new data to the CSV without overwriting."""
            try:
                if not os.path.exists(file_path):
                    pd.DataFrame(new_data).to_csv(file_path, index=False)
                else:
                    pd.DataFrame(new_data).to_csv(file_path, mode='a', header=False, index=False)
            except PermissionError as e:
                print(f"Permission error while writing to {file_path}: {e}")
                print("Retrying in 5 seconds...")
                time.sleep(5)
                append_to_csv(file_path, new_data)

        while len(results) < limit:
            try:
                search_results = subreddit.search(
                    therapy, limit=20, time_filter='year', params={"after": after}
                )
                search_results = list(search_results)  # Convert ListingGenerator to list
                print(f"Fetched {len(search_results)} posts in this batch.")

                if not search_results:
                    print("No more posts found. Stopping.")
                    break

                batch_results = []
                for post in search_results:
                    fetched_posts += 1

                    # Skip duplicates
                    if post.id in processed_ids:
                        print(f"Skipping duplicate post ID: {post.id}")
                        continue

                    # Check if the post is a question
                    is_question_post = any(
                        re.search(pattern, post.title, re.IGNORECASE) for pattern in question_keywords)

                    if is_question_post:
                        # Process only the first 5 comments
                        post.comments.replace_more(limit=limit_comment)
                        for comment in post.comments[:100]:
                            if (
                                    comment.id not in processed_ids and  # Check for duplicates
                                    any(re.search(kw, comment.body, re.IGNORECASE) for kw in inclusion_keywords) and
                                    not any(
                                        re.search(ex_kw, comment.body, re.IGNORECASE) for ex_kw in exclusion_keywords)
                            ):
                                batch_results.append({
                                    "id": comment.id,
                                    "content": comment.body
                                })
                                processed_ids.add(comment.id)  # Mark as processed
                    else:
                        # Process the post itself if it's not a question
                        if (
                                post.id not in processed_ids and  # Check for duplicates
                                any(re.search(kw, post.selftext, re.IGNORECASE) for kw in inclusion_keywords) and
                                not any(re.search(ex_kw, post.selftext, re.IGNORECASE) for ex_kw in exclusion_keywords)
                        ):
                            batch_results.append({
                                "id": post.id,
                                "content": post.selftext
                            })
                            processed_ids.add(post.id)  # Mark as processed

                # Append new results to the CSV and results list
                results.extend(batch_results)
                append_to_csv(output_file, batch_results)

                # Update 'after' for pagination
                if search_results:
                    after = search_results[-1].fullname  # Set 'after' to the last post's fullname
                    print(f"Updated pagination token (after): {after}")
                else:
                    print("No new posts in this batch.")
                    break

                # Log progress every 10 posts
                if fetched_posts % save_every == 0:
                    print(f"Processed {fetched_posts} posts, retained {len(results)} results...")

                # Break the loop if we have enough results
                if len(results) >= limit:
                    break

            except prawcore.exceptions.TooManyRequests:
                print("Rate limit reached. Waiting for 60 seconds...")
                time.sleep(30)  # Wait and retry
                continue

        print(f"Final save: {len(results[:limit])} records written to {output_file}")
        return pd.DataFrame(results[:limit])

    def save_to_csv(self, data, filename):
        data.to_csv(filename, index=False)
        print(f"Data saved to {filename} with {len(data)} lines.")


def load_api_credentials():
    """
    Loads Reddit API credentials from a .env file.
    """
    load_dotenv()  # Load environment variables from .env file
    return {
        "client_id": os.getenv("client_id"),
        "client_secret": os.getenv("client_secret"),
        "user_agent": os.getenv("user_agent"),
        "username": os.getenv("username"),  # Optional: Use if authentication requires username
        "password": os.getenv("password")   # Optional: Use if authentication requires password
    }
