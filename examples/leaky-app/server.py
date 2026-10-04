import os

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.environ["REDIS_URL"]          # never declared -> envguard flags it
STRIPE_KEY = "sk_live_51HxxQwErTyUiOpAsDfGh"  # hardcoded -> envguard flags it
