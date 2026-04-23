import africastalking

def send_farmer_alert(phone, name, crop, delta, irrigation_advice, sms_client):
    message = f"""
FarmSight Alert:
Hello {name}, your {crop} field health dropped by {abs(delta):.2f}.
{irrigation_advice}
"""
    try:
        response = sms_client.send(message, [phone])
        print(f"📩 SMS sent to {name}")
    except Exception as e:
        print(f"❌ SMS failed: {e}")