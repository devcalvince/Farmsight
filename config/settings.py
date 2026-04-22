%%writefile settings.py
from google.colab import userdata

DB_URL = userdata.get('DB_URL')
AT_API_KEY = userdata.get('AT_API_KEY')
GEE_PROJECT_ID = userdata.get('GEE_PROJECT_ID')