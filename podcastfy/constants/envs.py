import os
from dotenv import load_dotenv, find_dotenv
from podcastfy.utils import setup_logger

logger = setup_logger(__name__)

dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)

AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
