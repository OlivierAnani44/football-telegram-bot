import tweepy

auth = tweepy.OAuth1UserHandler(
    "API_KEY",
    "API_SECRET",
    "ACCESS_TOKEN",
    "ACCESS_SECRET"
)

api = tweepy.API(auth)

def publish_twitter(text):
    api.update_status(text[:280])
