import os
from dotenv import load_dotenv

# Carregas as informações de config.env
load_dotenv('config.env')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    DATABASE_URI = os.getenv('DATABASE_URI')