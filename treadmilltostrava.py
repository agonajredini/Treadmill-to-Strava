from google.cloud import vision
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
import re
import os 
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
import requests
from datetime import datetime

load_dotenv()

access_token = os.getenv('STRAVA_ACCESS_TOKEN')
refresh_token = os.getenv('STRAVA_REFRESH_TOKEN')

STRAVA_API_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

def refresh_access_token():
    global access_token  # Ensure you update the global access_token variable
    token_url = STRAVA_TOKEN_URL
    params = {
        "client_id": os.getenv('STRAVA_CLIENT_ID'),
        "client_secret": os.getenv('STRAVA_CLIENT_SECRET'),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    response = requests.post(token_url, params)
    response_data = response.json()  # Fix response.data to response.json()
    if response.status_code == 200:
        new_access_token = response_data["access_token"]
        new_refresh_token = response_data["refresh_token"]
        
        # Update .env file with new tokens
        with open('.env', 'r') as env_file:
            lines = env_file.readlines()
        
        with open(".env", "w") as env_file:  # Use 'w' mode to overwrite the file
            for line in lines:
                if line.startswith("STRAVA_ACCESS_TOKEN"):
                    env_file.write(f'STRAVA_ACCESS_TOKEN={new_access_token}\n')
                elif line.startswith("STRAVA_REFRESH_TOKEN"):
                    env_file.write(f'STRAVA_REFRESH_TOKEN={new_refresh_token}\n')
                else:
                    env_file.write(line)
                    
        access_token = new_access_token  # Update the global access_token
        print("Token refreshed successfully!")
        return new_access_token
    else:
        print(f"Failed to refresh token: {response.content}")
        return None
    
def get_strava_access_token():
    global access_token  # Ensure you're using the global access_token
    if access_token:  # If there's an existing valid token, no need to authenticate
        return access_token
    
    client_id = os.getenv('STRAVA_CLIENT_ID')
    client_secret = os.getenv('STRAVA_CLIENT_SECRET')
    redirect_url = "https://tekksparrow-programs.github.io/website/"
    
    session = OAuth2Session(client_id=client_id, redirect_uri=redirect_url)
    session.scope = ["activity:write"]
    auth_link = session.authorization_url(STRAVA_AUTH_URL)
    print(f"Click Here to authorize the app: {auth_link[0]}")
    
    authorization_response = input('Enter the full callback URL: ')
    token = session.fetch_token(
        token_url=STRAVA_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        authorization_response=authorization_response,
        include_client_id=True,
    )
    
    access_token = token['access_token']  # Save the new access_token globally
    
    with open('.env', 'r') as env_file:
        content = env_file.read()
        
        if 'STRAVA_ACCESS_TOKEN' not in content or 'STRAVA_REFRESH_TOKEN' not in content:
            with open('.env', 'a') as env_file:
                env_file.write(f"STRAVA_ACCESS_TOKEN={access_token}\n")
                env_file.write(f"STRAVA_REFRESH_TOKEN={token['refresh_token']}\n")
        else:
            print("Tokens already exist in the .env file.")
    return access_token

def get_image_datetime(image_path):
    # Open the image and get the EXIF data
    image = Image.open(image_path)
    exif_data = image._getexif()
    
    if not exif_data:
        raise ValueError("No EXIF data found in image.")
    
    # Loop through EXIF data to find the DateTimeOriginal tag
    for tag, value in exif_data.items():
        tag_name = TAGS.get(tag, tag)
        if tag_name == 'DateTimeOriginal':  # Look for the DateTimeOriginal tag
            # Return the value in a proper format
            return value
    
    raise ValueError("No DateTimeOriginal tag found in EXIF data.")

def upload_activity_to_strava(time,distance):
    global access_token
    if not access_token:
        print("Access token not found. Please authenticate.")
        access_token = get_strava_access_token()
    
    headers = {"Authorization": f"Bearer {access_token}"}
    test_response = requests.get(f"{STRAVA_API_URL}/athlete", headers=headers)
    
    if test_response.status_code == 401:
        print("Access token expired. Refreshing token...")
        access_token = refresh_access_token()
        if not access_token:
            print("Failed to refresh token. Please authenticate.")
            return
        
    # Extract the date and time when the picture was taken
    try:
        start_date_local = get_image_datetime(image_path)
        # Ensure the format is correct for Strava (ISO 8601 format)
        start_date_local = datetime.strptime(start_date_local, "%Y:%m:%d %H:%M:%S").isoformat() + "Z"
    except ValueError as e:
        print(f"Error extracting date and time from image: {e}")
        return
    
    activity_data = {
        "name": "Treadmill Run",
        "type": "Run",
        "start_date_local": start_date_local,
        "elapsed_time": convert_time_to_seconds(time),
        "distance": float(distance) * 1000,
        "description": "Uploaded from TreadmilltoStrava",
    }
    response = requests.post(f"{STRAVA_API_URL}/activities", headers=headers, data=activity_data)
    if response.status_code == 201:
        print("Activity uploaded successfully!")
    else:
        print(f"Failed to upload activity: {response.content , response.status_code, response.headers}")
        remaining = response.headers.get('X-RateLimit-Remaining')
        reset_time = response.headers.get('X-RateLimit-Reset')

        print(f"Remaining requests: {remaining}")
        print(f"Rate limit reset time: {reset_time}")
    
def extract_text_from_image(image_path):
    client=vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    else:
        return 'No text found'
    
def extract_time_and_distance(text):
    time_pattern = r'\b(\d{2}:\d{2})\b'
    distance_pattern = r"(\d{1,2}\.\d{2})"
    time_match = re.search(time_pattern, text)
    distance_match = re.search(distance_pattern, text)
    time = time_match.group(0) if time_match else 'Time not found'
    distance = distance_match.group(0) if distance_match else 'Distance not found'
    
    return time, distance

def convert_time_to_seconds(time):
    minutes, seconds = time.split(':')
    return int(minutes) * 60 + int(seconds)


def main(image_path):
    text = extract_text_from_image(image_path)
    if text:
        time, distance = extract_time_and_distance(text)
        print(f'Time: {time}, Distance: {distance}')
        if time != 'Time not found' and distance != 'Distance not found':
            upload_activity_to_strava(time, distance)

if __name__ == '__main__':
    image_path = 'pics\treadmill2.jpg'
    main(image_path)