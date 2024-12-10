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


STRAVA_API_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

def get_strava_access_token():
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
    return token

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
      # Extract the date and time when the picture was taken
    try:
        start_date_local = get_image_datetime(image_path)
        # Ensure the format is correct for Strava (ISO 8601 format)
        start_date_local = datetime.strptime(start_date_local, "%Y:%m:%d %H:%M:%S").isoformat() + "Z"
    except ValueError as e:
        print(f"Error extracting date and time from image: {e}")
        return
    token = get_strava_access_token()
    activity_data = {
        "name": "Treadmill Run",
        "type": "Run",
        "start_date_local": start_date_local,
        "elapsed_time": convert_time_to_seconds(time),
        "distance": float(distance) * 1000,
        "description": "Uploaded from TreadmilltoStrava",
    }
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    response = requests.post(f"{STRAVA_API_URL}/activities", headers=headers, data=activity_data)
    print("Response Status Code:", response.status_code)
    try:
        print("Response Content:", response.json())  # Print the response as JSON
    except ValueError:
        print("Response Content is not in JSON format:", response.content)
    if response.status_code == 201:
        print("Activity uploaded successfully!")
    else:
        print(f"Failed to upload activity: {response.content}")
    
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
    image_path = 'treadmill2.jpg'
    main(image_path)