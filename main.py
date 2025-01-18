from functions import RedditScrapper, load_api_credentials

if __name__ == "__main__":
    # Load API credentials
    credentials = load_api_credentials()

    # Initialize the RedditScraper class
    scrapper = RedditScrapper(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        user_agent=credentials["user_agent"]
    )

    # define keywords
    therapy =  "emdr"
    subreddit_name = "PTSD"
    question_keywords = [
        r"anyone (tried|done|have|gotten|experienced)", r"have you (tried|done|used|experienced)",
        r"anyone here (used|tried|have|gotten)",
        r"is it (any )?good", rf"can {therapy} help", rf"does (it|this|{therapy}) work",
        rf"is {therapy} (effective|helpful|worth it)",
        rf"What was your experience with (it|{therapy}|this)", rf"how has (it|{therapy}) worked for you",
        rf"how did (it|{therapy}) go for you", rf"has (it|{therapy}) helped you",
        rf"What did you think about (it|{therapy}|this)", rf"what are your thoughts on (it|{therapy}|this)",
        rf"{therapy} experiences\?",
        rf"what happened during (it|{therapy}|your sessions)",]

    inclusion_keywords = [
        rf"my {therapy}", rf"for me (it|{therapy}) (was|helped|worked)", rf"what (it|{therapy}) did for me",
        rf"(it|{therapy}) (has been|has made|was|changed|played a role|)", rf"my sessions with (it|{therapy})",
        r"sessions (were|was|helpful)", rf"{therapy} (session|steps|process|method)",
        rf"I[' ]?(had|did|tried|started|have (done|doing|trying|tried|used|completed|experienced)) (it|{therapy})",
        rf"I[' ]?(got|went through|have been (in|using)|am doing) (it|{therapy})",

        rf"I found that (it|{therapy})", rf"I[' ]?(completed|attended|participated in) (it|{therapy})",
        rf"I went (to|through) (it|{therapy})", r"the process", r"I experience(d)?",
        r"it (help(ed)?|work(ed)?|made a difference|did(n't)? help)",
        rf"(it|{therapy}) (saved|changed|traumatized|retraumatized|made a difference|did nothing|does not work)",
        r"(life (changing|saving)|recommend)",
        r"I[' ]?(felt|have experienced|am finding|worked|works|tried|have taken it)",
        rf"during the {therapy}"
    ]

    exclusion_keywords = [
        rf"I[' ]?am a therapist", rf"{therapy} therapist here", r"coming from a board[-]?certified", r"my clients",
        r"I[' ]?m ineligible", r"I did (DBT|CBT|other therapies)", r"have you found",
        r"someone who did it", r"not a problem for me", r"(tapping|research)", r"^How.*\?$",
    ]

    output_file = f"incremental_{therapy}_results.csv"

    # Scrape and filter data:
    filtered_data = scrapper.scrape_and_filter(
        subreddit_name=subreddit_name,
        therapy=therapy,
        inclusion_keywords=inclusion_keywords,
        question_keywords=question_keywords,
        exclusion_keywords=exclusion_keywords,
        limit=500,  # Specify the number of rows you want in the final CSV
        output_file = output_file,
        save_every=50
    )

    # Save filtered data to a CSV file
    output_file = f"{therapy}_filtered_results.csv"
    scrapper.save_to_csv(filtered_data, output_file)


