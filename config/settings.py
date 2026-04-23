import os

# Try to get Colab secrets, otherwise fallback to standard OS environment variables
try:
    from google.colab import userdata
    DB_URL = userdata.get('DB_URL')
    AT_API_KEY = userdata.get('AT_API_KEY')
    GEE_PROJECT_ID = userdata.get('GEE_PROJECT_ID')
except ImportError:
    # This part runs on GitHub Actions / Render
    DB_URL = os.getenv('DB_URL')
    AT_API_KEY = os.getenv('AT_API_KEY')
    GEE_PROJECT_ID = os.getenv('GEE_PROJECT_ID')

# Validation check
if not DB_URL:
    print("❌ ERROR: Database URL not found in environment variables!")