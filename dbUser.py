import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    return psycopg2.connect(db_url)
