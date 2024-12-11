import kivy
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.spinner import Spinner
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserIconView
from kivy.clock import Clock
import threading
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from google.cloud import vision
import os
import io
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session

# Load environment variables
load_dotenv()

access_token = os.getenv('STRAVA_ACCESS_TOKEN')
refresh_token = os.getenv('STRAVA_REFRESH_TOKEN')

STRAVA_API_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def refresh_access_token():
    global access_token
    token_url = STRAVA_TOKEN_URL
    params = {
        "client_id": os.getenv('STRAVA_CLIENT_ID'),
        "client_secret": os.getenv('STRAVA_CLIENT_SECRET'),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    response = requests.post(token_url, params)
    response_data = response.json()
    if response.status_code == 200:
        new_access_token = response_data["access_token"]
        new_refresh_token = response_data["refresh_token"]

        with open('.env', 'r') as env_file:
            lines = env_file.readlines()

        with open(".env", "w") as env_file:
            for line in lines:
                if line.startswith("STRAVA_ACCESS_TOKEN"):
                    env_file.write(f'STRAVA_ACCESS_TOKEN={new_access_token}\n')
                elif line.startswith("STRAVA_REFRESH_TOKEN"):
                    env_file.write(f"STRAVA_REFRESH_TOKEN={new_refresh_token}\n")
                else:
                    env_file.write(line)

        access_token = new_access_token
        print("Token refreshed successfully!")
        return new_access_token
    else:
        print(f"Failed to refresh token: {response.content}")
        return None


def get_image_datetime(image_path):
    image = PILImage.open(image_path)
    exif_data = image._getexif()

    if not exif_data:
        raise ValueError("No EXIF data found in image.")

    for tag, value in exif_data.items():
        tag_name = TAGS.get(tag, tag)
        if tag_name == 'DateTimeOriginal':
            return value

    raise ValueError("No DateTimeOriginal tag found in EXIF data.")


def extract_text_from_image(image_path):
    client = vision.ImageAnnotatorClient()
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


def upload_activity_to_strava(time, distance, image_path, title, description):
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

    try:
        start_date_local = get_image_datetime(image_path)
        start_date_local = datetime.strptime(start_date_local, "%Y:%m:%d %H:%M:%S").isoformat() + "Z"
    except ValueError as e:
        print(f"Error extracting date and time from image: {e}")
        return

    activity_data = {
        "name": title,
        "type": "Run",
        "start_date_local": start_date_local,
        "elapsed_time": convert_time_to_seconds(time),
        "distance": float(distance) * 1000,
        "description": description,
    }
    response = requests.post(f"{STRAVA_API_URL}/activities", headers=headers, data=activity_data)
    return response


def convert_time_to_seconds(time):
    minutes, seconds = time.split(':')
    return int(minutes) * 60 + int(seconds)


class StravaApp(App):
    def build(self):
        self.title = 'Treadmill to Strava'

        self.image_path = None

        self.default_title = "Treadmill Run"
        self.default_description = "Uploaded from TreadmilltoStrava"

        self.title_input = TextInput(text=self.default_title, multiline=False)
        self.description_input = TextInput(text=self.default_description, multiline=False)

        self.time_input = TextInput(hint_text="Not available", multiline=False)
        self.distance_input = TextInput(hint_text="Not available", multiline=False)

        self.select_button = Button(text="Select Image", on_press=self.select_image)
        self.upload_button = Button(text="Upload to Strava", on_press=self.upload_to_strava, disabled=True)

        self.image_label = Image()

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(self.image_label)
        layout.add_widget(self.select_button)
        layout.add_widget(self.upload_button)

        time_distance_layout = BoxLayout(orientation='horizontal')
        time_distance_layout.add_widget(Label(text="Time:"))
        time_distance_layout.add_widget(self.time_input)
        time_distance_layout.add_widget(Label(text="Distance:"))
        time_distance_layout.add_widget(self.distance_input)
        layout.add_widget(time_distance_layout)

        title_layout = BoxLayout(orientation='horizontal')
        title_layout.add_widget(Label(text="Activity Title:"))
        title_layout.add_widget(self.title_input)
        layout.add_widget(title_layout)

        description_layout = BoxLayout(orientation='horizontal')
        description_layout.add_widget(Label(text="Activity Description:"))
        description_layout.add_widget(self.description_input)
        layout.add_widget(description_layout)

        return layout

    def select_image(self, instance):
        filechooser = FileChooserIconView()
        filechooser.bind(on_selection=lambda *x: self.load_image(filechooser.selection))
        popup = Popup(title="Select Image", content=filechooser, size_hint=(0.9, 0.9))
        popup.open()

    def load_image(self, selection):
        if selection:
            self.image_path = selection[0]
            self.display_image(self.image_path)
            threading.Thread(target=self.process_image, args=(self.image_path,)).start()

    def display_image(self, image_path):
        img = PILImage.open(image_path)
        img.thumbnail((500, 500))  # Resize image for display
        kivy_img = Image()
        kivy_img.texture = self.pil_image_to_texture(img)
        self.image_label.texture = kivy_img.texture

    def pil_image_to_texture(self, pil_image):
        from kivy.graphics.texture import Texture
        import numpy as np
        pil_image = pil_image.convert('RGBA')
        data = np.array(pil_image)
        texture = Texture.create(size=(pil_image.width, pil_image.height), colorfmt='rgba')
        texture.blit_buffer(data.tobytes(), colorfmt='rgba', bufferfmt='ubyte')
        return texture

    def process_image(self, image_path):
        try:
            text = extract_text_from_image(image_path)
            if text:
                time, distance = extract_time_and_distance(text)
                self.time_input.text = time
                self.distance_input.text = distance
                self.upload_button.disabled = False
            else:
                self.show_error("Text not found in the image.")
        except Exception as e:
            self.show_error(str(e))

    def upload_to_strava(self, instance):
        if self.image_path:
            try:
                time = self.time_input.text
                distance = self.distance_input.text
                title = self.title_input.text
                description = self.description_input.text

                if time != "Not available" and distance != "Not available":
                    threading.Thread(target=self.upload_thread, args=(time, distance, title, description)).start()
                else:
                    self.show_error("Invalid time or distance.")
            except Exception as e:
                self.show_error(f"Failed to upload: {e}")
        else:
            self.show_error("No image selected.")

    def upload_thread(self, time, distance, title, description):
        try:
            response = upload_activity_to_strava(time, distance, self.image_path, title, description)
            if response and response.status_code == 201:
                self.show_success("Activity uploaded to Strava successfully!")
            else:
                self.show_error("Failed to upload to Strava.")
        except Exception as e:
            self.show_error(str(e))

    def show_success(self, message):
        popup = Popup(title="Success", content=Label(text=message), size_hint=(0.6, 0.6))
        popup.open()

    def show_error(self, message):
        popup = Popup(title="Error", content=Label(text=message), size_hint=(0.6, 0.6))
        popup.open()

if __name__ == '__main__':
    StravaApp().run()
