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

    def is_personal_experience(self, text):
        """
         Checks if a post or comment indicates a personal experience.
        """
        personal_patterns =  [
            r"\b(I|me|my|mine|we|our|us)\b",
            r"\b(felt|tried|experienced|found|helped|worked|changed|improved|saved my life)\b",
            r"\b(during|while|after|when I did|it was|it felt like)\b",
            r"\b(life changing|breakthrough|trauma processing|emotional release|triggered|ground myself|unlock memory)\b",
            r"\b(separate the past from the present|panic attack|PTSD|C-PTSD|reliving moments|healing journey|symptomatic|remission)\b",
            r"\b(it didn’t help|it helped immensely|it worked for me|it made things worse|it was worth it|recommend it)\b"
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in personal_patterns)

    def is_exclusion(self, text):
        """
            Checks if a post or comment matches exclusion criteria.
            This method looks both before and after the exclusion term
            to ensure we only exclude posts that are undecided and have no mention of trying EMDR.
        """

        # Check if the comment starts with the exact automated response phrase
        automated_response_prefix = "r/ptsd has generated this automated response that is appended to every post"
        if text.lstrip().startswith(automated_response_prefix):
            print("Skipping automated response")  # Debug print to confirm
            return False  # Don't exclude this comment

        exclusion_patterns = [
            # Comments where the author hasn't tried EMDR and is considering it
            r"\b(debating (on whether|whether|if) (I'?d try|to try)|If I (do|start) EMDR|I'm about to start EMDR|Should I try EMDR|Has (anybody|anyone)( here)? tried EMDR( therapy)?|wanted some advice|haven’t tried it|not sure if I'm ready)\b",

            # Comments where the author is expressing uncertainty or fear about starting EMDR
            r"\b(I'm (apprehensive|unsure|scared of reliving)|I (can't|could) handle it|I should (hold off|wait) on EMDR|I'm scared (of trying|to try) it|too scared)\b",

            # Extended to catch uncertainty or lack of understanding while still being willing to try EMDR
            r"\b((want|willing) to try it|I don't understand how eye movement moves a memory|I'm curious about how EMDR works|I might try)\b",

            # Comments about therapy advice without having tried EMDR yet (indicating uncertainty or hesitation)
            r"\b(not stable enough|I (haven't|have not) tried it yet|I dissociate a lot|I (wasn't|am not) ready for EMDR|I (don't|cannot) know if I want to try|I was supposed to begin EMDR|I'm still considering)\b",

            # Exclude specific concerns about readiness for EMDR, especially involving BPD or dissociation
            r"\b(I (was supposed to|should have|was going to) (begin|start) EMDR (but|however) I (have BPD|dissociate(a lot| frequently)|(am|was) not stable enough|cannot handle it|don’t feel ready))\b",

            # Comments where someone is asking about EMDR without having tried it yet
            r"\b(Should clarify that I have not had any trauma therapy yet|How was (online EMDR|it)?|Should I try it|Do you think I should do it|Is EMDR safe for someone like me|I don’t know if I’m in the right place for EMDR|I’m concerned about whether EMDR is right for me|I know addressing trauma would help, but I’m not sure if I should start EMDR)\b",

            # New patterns to exclude comments where the user agreed to try EMDR but backed out or was too scared
            r"\b(agreed to try (EMDR|it) but (was too scared|didn't follow through|backed out|couldn't handle it|changed my mind))\b",
            r"\b((I was|I’m) too scared (to start|to follow through with|to try) (EMDR|it)|backed out of (trying|doing) (EMDR|it)|changed my mind about (trying|doing) (EMDR|it))\b",

            # Exclude comments about certification or professional advice from certified therapists
            r"\b(EMDR certified therapist|board certified psychiatrist|certified EMDR practitioner|certified as an EMDR practitioner|accredited EMDR teacher|clinical psychologist|licensed social worker|ongoing consultation)\b"

            # Exclude specific generic comments that are not personal experiences but just offering general advice or information
            r"\b(People have all sorts of experiences with EMDR|EMDR is not the only type of neurotherapy)\b",

            # Catch negative or concern-based comments about EMDR's effectiveness or its drawbacks
            r"\b(concerns around|controversy about|ethical concerns|effectiveness of EMDR|not sure if EMDR is effective|not working for me|considering other forms of therapy)\b",

            # Exclude automated responses from bots or rules-based content
            r"(Welcome to r/ptsd|We are a supportive & respectful community|Your safety always comes first!|Do NOT exchange DMs or personal info|Please contact your GP/doctor|If you or someone you know is in immediate danger|suicide and support hotlines|Gatekeeping is not allowed here|I am a bot|this action was performed automatically|contact the moderators)"
        ]
        # First check if the text matches any exclusion pattern
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in exclusion_patterns):
            # If it matches, check if there's any mention of having already tried EMDR
            if re.search(r"\b(already tried|have done|completed)\s*EMDR", text, re.IGNORECASE):
                return False  # Include this post because EMDR was already tried
            return True  # Exclude this post because it's uncertain about trying EMDR or doesn't mention it yet

        # If none of the exclusion patterns match, return False (don't exclude)
        return False

    def scrape_and_filter(self, subreddit_name, therapy, limit, output_file, save_every, limit_comment):
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

                    # Determine if the post content is relevant
                    post_content_included = (self.is_personal_experience(post.selftext) and
                                             not self.is_exclusion(post.selftext))

                    if post_content_included:
                        batch_results.append({
                            "id": post.id,
                            "content": post.selftext
                        })
                        processed_ids.add(post.id)
                    else:
                        # Scrape relevant comments from this post
                        post.comments.replace_more(limit=limit_comment)
                        for comment in post.comments.list():
                            if (
                                    comment.id not in processed_ids and  # Check for duplicates
                                    self.is_personal_experience(comment.body) and not self.is_exclusion(comment.body)
                            ):
                                batch_results.append({
                                    "id": comment.id,
                                    "content": comment.body
                                })
                                processed_ids.add(comment.id)  # Mark as processed

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
