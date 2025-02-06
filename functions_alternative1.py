import praw
from transformers import pipeline
import pandas as pd
import time
import os
import re

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

    def classify_post(self, text):
        """Classifies a Reddit post using regex for first-hand EMDR experiences."""
        result = self.classifier(text, candidate_labels=self.labels)
        top_label = result['labels'][0]

        first_hand_experience_regex = re.compile(
            r"\b(I (tried|started|completed|did|went through|had) EMDR|"
            r"after (\d+ sessions|doing|my) EMDR|"
            r"during my (EMDR|it) (session|therapy)|"
            r"my (EMDR )?(therapist|session|experience|treatment)|"
            r"(EMDR|it) (was (life changing|a waste of time|intense|helpful|too much for me|worth it|tough)|"
            r"helped|changed|made me feel|worked for) me|"
            r"EMDR was (amazing|horrible|really hard|so intense|so worth it|difficult at first))\b",
            re.IGNORECASE
        )

        #Regex to reject indirect mentions
        undecided_or_third_party_regex = re.compile(
            r"\b(thinking about EMDR|considering EMDR|scared to try EMDR|not sure if I will do EMDR|"
            r"haven’t started EMDR|was recommended EMDR|was supposed to do EMDR but|"
            r"was told EMDR wouldn’t work for me|my therapist denied me EMDR|"
            r"never actually started EMDR|my friend did EMDR|someone I know did EMDR|"
            r"I plan to do EMDR|I'm waiting to try EMDR|I might do EMDR in the future|"
            r"I'm preparing for EMDR|I decided not to do EMDR)\b"
            r"\b(too unwell for EMDR|not ready for EMDR|therapist refused EMDR|"
            r"not stable enough for EMDR|my therapist denied me EMDR)\b"
            r"\b(denied EMDR|refused EMDR|not allowed to do EMDR|was not approved for EMDR|"
            r"not stable enough for EMDR|told I can't do EMDR|not a candidate for EMDR)\b"
            r"\b(planning to do EMDR|thinking about trying EMDR|considering EMDR|scared to try EMDR|"
            r"haven’t started EMDR yet|waiting to start EMDR|preparing for EMDR)\b"
            r"couldn't start EMDR|my therapist stopped EMDR before it started|"
            r"\b(EMDR was not an option for me)\b"
            r"\b(scared to try EMDR|not sure about EMDR|not everyone is a candidate for EMDR|"
            r"thinking about doing EMDR|wondering if EMDR is right for me|"
            r"glad I was refused EMDR|I may try EMDR one day)\b"

            ,
            re.IGNORECASE
        )

        # Reject indirect mentions
        if undecided_or_third_party_regex.search(text):
            return "indirect_reference"

        # Approve if regex confirms firsthand experience
        if first_hand_experience_regex.search(text):
            return "personal experience"

        # If classified as testimony but regex does NOT match, mark it as uncertain
        if top_label == "testimony":
            return "uncertain testimony"

        return top_label

    def log_false_positives(self, text, classification, url=None):
        """Log false positives for further analysis."""
        with open("false_positive_log.txt", "a", encoding="utf-8") as f:
            f.write(f"Classified as: {classification} | Text: {text[:200]} | URL: {url if url else 'No URL'}\n")

    def classify_comment(self, text, parent_post_text=None):
        """Classifies a Reddit comment based on explicit or implicit mention of the author's EMDR experience."""
        text_lower = text.lower()

        undecided_or_third_party_regex = re.compile(
            r"\b(thinking about EMDR|considering EMDR|scared to try EMDR|not sure if I will do EMDR|"
            r"haven’t started EMDR|was recommended EMDR|was supposed to do EMDR but|"
            r"was told EMDR wouldn’t work for me|my therapist denied me EMDR|"
            r"never actually started EMDR|my friend did EMDR|someone I know did EMDR|"
            r"I plan to do EMDR|I'm waiting to try EMDR|I might do EMDR in the future|"
            r"I'm preparing for EMDR|I decided not to do EMDR)\b"
            r"\b(too unwell for EMDR|not ready for EMDR|therapist refused EMDR|"
            r"not stable enough for EMDR|my therapist denied me EMDR)\b"
            r"\b(denied EMDR|refused EMDR|not allowed to do EMDR|was not approved for EMDR|"
            r"not stable enough for EMDR|told I can't do EMDR|not a candidate for EMDR)\b"
            r"\b(planning to do EMDR|thinking about trying EMDR|considering EMDR|scared to try EMDR|"
            r"haven’t started EMDR yet|waiting to start EMDR|preparing for EMDR"
            r"couldn't start EMDR|my therapist stopped EMDR before it started|"
            r"EMDR was not an option for me)\b"
            r"\b(scared to try EMDR|not sure about EMDR|not everyone is a candidate for EMDR|"
            r"thinking about doing EMDR|wondering if EMDR is right for me|"
            r"glad I was refused EMDR|I may try EMDR one day)\b"

            ,
            re.IGNORECASE
        )

        congratulatory_regex = re.compile(
            r"\b(congratulations|so happy for you|proud of you|great job|you’re amazing|well done|"
            r"thank you for sharing|that’s inspiring|sending good vibes|wishing you well|"
            r"happy to hear this|that’s wonderful news|good to know|best of luck)\b"
            r"best of luck|gives me hope|brilliant! enjoy your freedom|"
            r"glad to hear this|cheers to your recovery|"
            r"\b(best wishes on your journey|you're strong)\b"
            ,

            re.IGNORECASE
        )

        other_therapy_regex = re.compile(
            r"\b(DBT|CBT|ART|IFS|somatic therapy|talk therapy|exposure therapy)\b",
            re.IGNORECASE
        )
        if undecided_or_third_party_regex.search(text_lower):
            return "indirect_reference"

        if congratulatory_regex.search(text_lower):
            return "congratulatory_message"



        result = self.classifier(text, candidate_labels=self.labels)
        top_label = result['labels'][0]

        first_hand_experience_regex = re.compile(
            r"\b(I|my|me).*?(tried|started|completed|did|went through|had).*?EMDR\b",
            re.IGNORECASE
        )

        has_personal_experience = first_hand_experience_regex.search(text_lower) is not None
        if other_therapy_regex.search(text_lower) and not first_hand_experience_regex.search(text_lower):
            return "generic_therapy_discussion"

        if has_personal_experience:
            return "personal experience"

        if top_label in ["testimony", "opinion"] and not has_personal_experience:
            self.log_false_positives(text, top_label)

        return top_label


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
                while len(entry) < 6:
                    entry.append("N/A")  # Add missing values
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

                    entry = [post.title, post.selftext, classification, "(No Comments)", post.url, post.created_utc]
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

        print(
            f"✅ Checking Data Structure: Expected 6 columns, but found {[len(row) for row in self.data]}")  # Debugging step

        # Ensure every row has exactly 6 elements before saving
        cleaned_data = []
        for row in self.data:
            if len(row) < 6:
                print("⚠️ Fixing Row with Incorrect Length:", row)
                while len(row) < 6:
                    row.append("N/A")  # Fill missing fields
            elif len(row) > 6:
                print("⚠️ Removing Extra Columns from Row:", row)
                row = row[:6]  # Trim extra columns
            cleaned_data.append(row)

        # ✅ Save Approved Entries
        if cleaned_data:
            filename_approved = "approved_reddit_emdr_experiences.csv"
            try:
                df_approved = pd.DataFrame(cleaned_data,
                                           columns=["Title", "Body", "Classification", "Comments", "URL", "Timestamp"])
                df_approved.to_csv(filename_approved, mode='a', header=False, index=False, encoding="utf-8")
                print(f"✅ Appended {len(df_approved)} approved entries to {filename_approved}")
            except ValueError as e:
                print("❌ DataFrame Creation Error:", e)
