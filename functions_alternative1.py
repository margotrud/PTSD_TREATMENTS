import praw
from transformers import pipeline
import pandas as pd
import time
import os
import re



# ✅ First-hand experience regex (allows indirect mentions)
first_hand_experience_regex = re.compile(
    r"\b(I (tried|started|completed|did|went through|had) (EMDR|it)|"
    r"after (X sessions|doing|my) (EMDR|it)|"
    r"during my (EMDR|it) (session|therapy)|"
    r"my (EMDR )?(therapist|session|experience|treatment)|"
    r"(EMDR|it) (helped|changed|made me feel|worked for) me)\b",
    re.IGNORECASE
)

# ❌ Exclude indirect mentions that do not describe personal experience
indirect_mentions_regex = re.compile(
    r"\b(my friend|people say|I've read|my therapist recommended|I heard about|considering EMDR|thinking about (EMDR|it)|"
    r"haven’t (started|done) (EMDR|it)|not sure if I will do (EMDR|it)|scared to try (EMDR|it)|wondering about (EMDR|it)|trauma therapy)\b",
    re.IGNORECASE
)

non_emdr_therapy_regex = re.compile(
    r"\b(?!EMDR )(?:[\w\s]+ therapy)\b",  # Matches any phrase ending in "therapy" EXCEPT "EMDR therapy"
    re.IGNORECASE
)

class RedditAPI:
    """Handles Reddit authentication and data retrieval using PRAW."""

    def __init__(self, client_id, client_secret, user_agent):
        """Initialize Reddit API connection."""
        self.reddit = praw.Reddit(client_id=client_id,
                                  client_secret=client_secret,
                                  user_agent=user_agent)

    def search_subreddit(self, subreddit_name, search_term, limit=50, time_filter='year', after=None):
        """Search for posts containing a specific term in a subreddit."""
        subreddit = self.reddit.subreddit(subreddit_name)
        search_results = subreddit.search(
            search_term, limit=limit, time_filter=time_filter, params={"after": after}
        )
        return search_results


class TextClassifier:
    """Uses Hugging Face's Zero-Shot Classification to identify personal EMDR experiences in posts and comments."""

    def __init__(self):
        """Initialize the NLP model."""
        self.classifier = pipeline('zero-shot-classification', model="facebook/bart-large-mnli")
        self.labels = ['personal experience', 'theoretical discussion', 'testimony', 'question', 'opinion']

    # def classify_post(self, text):
    #     """Classifies a Reddit post using NLP to detect personal EMDR experiences."""
    #     result = self.classifier(text, candidate_labels=self.labels)
    #     return result['labels'][0]  # Return the most likely classification

    def classify_post(self, text):
        """Classifies a Reddit post using regex for first-hand EMDR experiences."""
        result = self.classifier(text, candidate_labels=self.labels)
        top_label = result['labels'][0]

        # ✅ First-hand EMDR experience detection
        if first_hand_experience_regex.search(text) and not indirect_mentions_regex.search(text):
            return "personal experience"

        return top_label  # Default to NLP classification

    # def classify_comment(self, text):
    #     """Classifies a Reddit comment using NLP to detect implicit EMDR experiences."""
    #     result = self.classifier(text, candidate_labels=self.labels)
    #     top_label = result['labels'][0]  # Most likely classification
    #
    #     # ✅ If the classifier already detects personal experience, return it
    #     if top_label in ['personal experience', 'testimony']:
    #         return top_label
    #
    #     # ✅ Fallback: Check for common testimony phrases
    #     experience_keywords = [
    #         "it didn't help me", "i tried emdr", "my experience with emdr", "i did emdr", "i had a session",
    #         "my emdr journey", "after emdr therapy", "i went through emdr", "i started emdr", "i have done emdr"
    #     ]
    #     if any(keyword in text.lower() for keyword in experience_keywords):
    #         return "personal experience"
    #
    #     return top_label  # Default to NLP classification

    import re

    def classify_comment(self, text, parent_post_text=None):
        """
        Classifies a Reddit comment while rejecting mentions of non-EMDR therapies.
        - ✅ Approves first-hand EMDR experiences.
        - ❌ Rejects third-party stories, supportive messages, bot messages.
        - ❌ Rejects mentions of other therapies (e.g., "CBT therapy") unless it's "EMDR therapy."
        """

        result = self.classifier(text, candidate_labels=self.labels)
        top_label = result['labels'][0]  # Most likely classification

        text_lower = text.lower()

        # ✅ First-hand EMDR experience detection
        first_hand_experience_regex = re.compile(
            r"\b(I (tried|started|completed|did|went through|had) EMDR|"
            r"after (X sessions|doing|my) EMDR|"
            r"during my (EMDR|it) (session|therapy)|"
            r"my (EMDR )?(therapist|session|experience|treatment)|"
            r"(EMDR|it) (was life changing|was a waste of time|helped|changed|made me feel|worked for) me)\b",
            re.IGNORECASE
        )

        # ❌ Exclude non-EMDR therapy mentions
        non_emdr_therapy_regex = re.compile(
            r"\b(?!EMDR )(?:[\w\s]+ therapy)\b",  # Matches any phrase ending in "therapy" EXCEPT "EMDR therapy"
            re.IGNORECASE
        )

        # ❌ Reject if discussing a non-EMDR therapy
        if non_emdr_therapy_regex.search(text_lower):
            return "non_emdr_therapy"

        # ✅ Approve if EMDR is explicitly mentioned and the user describes an experience
        if "emdr" in text_lower and first_hand_experience_regex.search(text_lower):
            return "personal experience"

        return top_label  # Default to NLP classification

    def is_related_to_emdr(self, text):
        """Checks if the text is related to EMDR even if 'EMDR' is not explicitly mentioned."""
        keywords = ["emdr", "eye movement desensitization"]
        return any(word in text.lower() for word in keywords)


class RedditExperienceScraper:
    """Manages scraping, filtering, and saving Reddit posts and comments."""

    def __init__(self, client_id, client_secret, user_agent, save_every=5):
        """Initialize the scraper with Reddit API and text classifier."""
        self.reddit_api = RedditAPI(client_id, client_secret, user_agent)
        self.text_classifier = TextClassifier()
        self.subreddit = "PTSD"
        self.data = []
        self.denied_data = []  # ✅ Store rejected posts/comments
        self.save_every = save_every

    def get_comments(self, post, post_is_emdr_experience, post_is_question):
        """Extracts and filters relevant comments from a Reddit post."""
        post_text = f"{post.title} {post.selftext}"  # Parent post content

        post.comments.replace_more(limit=0)

        for comment in post.comments.list():
            text = comment.body.lower().strip()

            # Exclude deleted/removed comments
            if "[deleted]" in text or "[removed]" in text:
                continue

            # Classify the comment, passing parent post text
            classification = self.text_classifier.classify_comment(comment.body, parent_post_text=post_text)

            # ✅ Store approved comments
            if classification in ['personal experience', 'testimony']:
                entry = ["(From Question)", "(No Post Saved)", "testimony", comment.body, post.url, post.created_utc]
                self.data.append(entry)

            # ❌ Store denied comments
            else:
                entry = ["Comment", classification, comment.body, post.url, post.created_utc]
                self.denied_data.append(entry)

            self.check_and_save()

    def check_and_save(self):
        """Checks if we have at least `save_every` entries and saves both approved & denied entries."""
        if len(self.data) >= self.save_every or len(self.denied_data) >= self.save_every:
            print(f"💾 Saving approved: {len(self.data)} | denied: {len(self.denied_data)}")
            self.save_to_csv()
            self.data.clear()
            self.denied_data.clear()

    def scrape_and_filter_posts(self, search_term="EMDR", limit=50, time_filter='year'):
        """Searches r/PTSD for EMDR-related posts and filters them based on criteria."""
        print(f"🔍 Searching r/PTSD for posts containing '{search_term}'...")

        after = None

        while len(self.data) < limit:
            search_results = self.reddit_api.search_subreddit(self.subreddit, search_term, limit=limit,
                                                              time_filter=time_filter, after=after)

            for post in search_results:
                post_text = f"{post.title} {post.selftext}"

                # ✅ Ensure the post is about EMDR
                if not self.text_classifier.is_related_to_emdr(post_text):
                    self.denied_data.append(["Post", "Not Related", post.title, post.url, post.created_utc])
                    continue

                classification = self.text_classifier.classify_post(post_text)

                post_is_emdr_experience = classification in ["personal experience", "testimony"]
                post_is_question = classification == "question"

                # ✅ Store post if it's a personal EMDR experience
                if post_is_emdr_experience:
                    self.get_comments(post, post_is_emdr_experience, post_is_question)  # Pass to get_comments

                    entry = [post.title, post.selftext, classification, post.url, post.created_utc]
                    self.data.append(entry)

                # ❌ Store denied post
                else:
                    self.denied_data.append(["Post", classification, post.title, post.url, post.created_utc])

                self.check_and_save()

            after = post.fullname if post else None
            time.sleep(2)

        # ✅ Final save for remaining data
        if self.data or self.denied_data:
            print(f"🎉 Final save complete! Approved: {len(self.data)}, Denied: {len(self.denied_data)}")
            self.save_to_csv()

    import os

    def save_to_csv(self):
        """Save both approved & denied entries to separate CSV files, appending to existing files."""

        # ✅ Save Approved Entries
        if self.data:
            filename_approved = "approved_reddit_emdr_experiences.csv"
            df_approved = pd.DataFrame(self.data,
                                       columns=["Title", "Body", "Classification", "Comments", "URL", "Timestamp"])

            # ✅ Append to existing file without overwriting
            if os.path.exists(filename_approved):
                df_approved.to_csv(filename_approved, mode='a', header=False, index=False, encoding="utf-8")
            else:
                df_approved.to_csv(filename_approved, mode='w', header=True, index=False, encoding="utf-8")

            print(f"✅ Appended {len(df_approved)} approved entries to {filename_approved}")

        # ✅ Save Denied Entries
        if self.denied_data:
            filename_denied = "denied_reddit_entries.csv"
            df_denied = pd.DataFrame(self.denied_data,
                                     columns=["Type", "Classification", "Title/Body", "URL", "Timestamp"])

            # ✅ Append to existing file without overwriting
            if os.path.exists(filename_denied):
                df_denied.to_csv(filename_denied, mode='a', header=False, index=False, encoding="utf-8")
            else:
                df_denied.to_csv(filename_denied, mode='w', header=True, index=False, encoding="utf-8")

            print(f"❌ Appended {len(df_denied)} denied entries to {filename_denied}")
