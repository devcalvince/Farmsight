import requests

def get_irrigation_advice(lon, lat):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation"
        "&forecast_days=1"
        "&timezone=auto"
    )
    try:
        response = requests.get(url, timeout=10).json()
        hourly = response.get("hourly", {})
        precipitation = hourly.get("precipitation", [])
        if not precipitation:
            return "Weather data unavailable. Inspect soil moisture."
        total_rain_mm = sum(precipitation)
        if total_rain_mm > 10:
            return f"🌧 Heavy rain expected ({total_rain_mm:.1f}mm). Avoid fertilizing and delay irrigation."
        elif total_rain_mm > 5:
            return f"🌧 Rain expected ({total_rain_mm:.1f}mm). Delay irrigation."
        elif total_rain_mm > 0:
            return f"🌦 Light rain expected ({total_rain_mm:.1f}mm). Reduce irrigation."
        else:
            return "☀️ No rain expected. Irrigate as planned."
    except Exception as e:
        return "Weather data unavailable. Inspect soil moisture."