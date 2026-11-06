import os
from redis import Redis
from rq import Queue

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(redis_url)
review_queue = Queue("reviews", connection=redis_conn)

def process_review_job(content_version_id: str):
    print(f"Processing review for content version: {content_version_id}")
    return True
