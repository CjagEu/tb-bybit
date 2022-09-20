import os
from dotenv import load_dotenv

load_dotenv()

MY_API_KEY = os.getenv('API_KEY')
MY_SECRET_KEY = os.getenv('API_SECRET')
