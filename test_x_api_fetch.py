import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_x_api_fetch(username="beast_ico"):
    """Test fetching X posts to see date distribution"""

    url = "https://twitter-api45.p.rapidapi.com/timeline.php"
    headers = {
        "x-rapidapi-key": os.getenv('X_RAPID_API_KEY'),
        "x-rapidapi-host": "twitter-api45.p.rapidapi.com"
    }

    querystring = {"screenname": username}

    all_posts = []
    cursor = None
    six_months_ago = datetime.now() - timedelta(days=180)

    print(f"Fetching posts for {username}")
    print(f"Six months ago cutoff: {six_months_ago.strftime('%Y-%m-%d')}")
    print("-" * 80)

    page = 0
    max_pages = 30  # Limit to 30 pages to see how far back it goes
    while len(all_posts) < 1000 and page < max_pages:  # Target 1000 posts like the real code
        page += 1

        if cursor:
            querystring["cursor"] = cursor

        print(f"\nPage {page}: Fetching...")
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.reason}")
            break

        data = response.json()
        tweets = data.get('timeline', [])

        print(f"Page {page}: Got {len(tweets)} tweets from API")

        # Process tweets
        page_posts = []
        stopped_at_6months = False

        for tweet in tweets:
            created_at = tweet.get('created_at', '')
            if created_at:
                try:
                    tweet_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                    tweet_date_local = tweet_date.replace(tzinfo=None)

                    # Only add non-retweets (removed 6-month check to see full history)
                    if not tweet.get('retweeted', False):
                        page_posts.append({
                            'date': tweet_date_local.strftime('%Y-%m-%d'),
                            'created_at': created_at,
                            'text': tweet.get('text', '')[:50],
                            'is_retweet': tweet.get('retweeted', False)
                        })
                except Exception as e:
                    print(f"Error parsing date: {e}")

        all_posts.extend(page_posts)
        print(f"Page {page}: Added {len(page_posts)} non-retweet posts (total now: {len(all_posts)})")

        if stopped_at_6months:
            print(f"\nStopped at 6-month cutoff")
            break

        # Check for next cursor
        if 'next_cursor' in data:
            cursor = data['next_cursor']
            print(f"Page {page}: Has next cursor, will continue...")
        else:
            print(f"Page {page}: No more pages available")
            break

    print("\n" + "=" * 80)
    print(f"FINAL RESULTS:")
    print(f"Total non-retweet posts fetched: {len(all_posts)}")

    if all_posts:
        # Get unique dates
        all_dates = [post['date'] for post in all_posts]
        unique_dates = sorted(set(all_dates))

        print(f"Unique days with posts: {len(unique_dates)}")
        print(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")
        print(f"\nAll unique dates with post counts:")

        # Count posts per date
        date_counts = {}
        for date in all_dates:
            date_counts[date] = date_counts.get(date, 0) + 1

        for date in sorted(date_counts.keys()):
            print(f"  {date}: {date_counts[date]} posts")

        # Show around the 200-post mark
        if len(all_posts) >= 200:
            print(f"\n" + "=" * 80)
            print(f"Posts around the 200-mark:")
            for i in range(195, min(205, len(all_posts))):
                post = all_posts[i]
                print(f"  Post {i+1}: {post['date']} - {post['text']}")

if __name__ == "__main__":
    test_x_api_fetch()
