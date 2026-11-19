
import main

# Separate settings for daily landscape news video
# Keep the existing hourly news-card workflow unchanged.

main.OUTPUT_FILE = "news_reels.json"
main.STATE_FILE = "published_news_reels.json"
main.MAX_NEWS = 10

if __name__ == "__main__":
    main.main()
