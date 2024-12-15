import os
import re
import webbrowser
import threading
from datetime import datetime
from PIL import Image, ImageTk
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image as KivyImage
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.switch import Switch
from kivy.clock import Clock
from google.cloud import vision
import io
from io import BytesIO
import requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
from PIL.ExifTags import TAGS


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

        # Update .env file with new tokens
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


def get_strava_access_token():
    global access_token
    if access_token:
        return access_token

    client_id = os.getenv('STRAVA_CLIENT_ID')
    client_secret = os.getenv('STRAVA_CLIENT_SECRET')
    redirect_url = "https://tekksparrow-programs.github.io/website/"

    session = OAuth2Session(client_id=client_id, redirect_uri=redirect_url)
    session.scope = ["activity:write"]
    auth_link = session.authorization_url(STRAVA_AUTH_URL)
    webbrowser.open(auth_link[0])

    # Get the authorization response from user
    authorization_response = input("Please enter the full callback URL after you authorize the app in your browser: ")
    if not authorization_response:
        print("Authorization failed. No URL was provided.")
        return None

    token = session.fetch_token(
        token_url=STRAVA_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        authorization_response=authorization_response,
        include_client_id=True,
    )

    access_token = token['access_token']

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
    image = Image.open(image_path)
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
        
        headers = {"Authorization": f"Bearer {access_token}"}
        test_response = requests.get(f"{STRAVA_API_URL}/athlete", headers=headers)
        
        if test_response.status_code != 200:
            print("Failed to authenticate with the refreshed token.")
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

#Window.size = (800, 900)
class StravaApp(App):
    def build(self):
        self.root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.scroll_view = ScrollView(size_hint=(1, None), size=(Window.width, Window.height - 120))
        self.scroll_layout = BoxLayout(orientation='vertical', padding=10, spacing=50, size_hint_y=None)
        self.scroll_layout.bind(minimum_height=self.scroll_layout.setter('height'))

        self.image_path = None
        self.title_var = TextInput(text="Treadmill Run", multiline=False, size_hint_y=None, height=40)
        self.description_var = TextInput(text="Uploaded from TreadmilltoStrava", multiline=False, size_hint_y=None, height=40)

        self.displayed_image = KivyImage(source="pics\\noimage.PNG", size_hint=(1, None), height=400)
        self.image_label = Label(text="No image selected", size_hint_y=None, height=40)
        self.select_button = Button(text="Select Image", size_hint=(None,None), height=40, width=400)
        self.upload_button = Button(text="Upload to Strava", size_hint=(None,None), height=40, width=400, disabled=True)

        self.select_button.bind(on_press=self.select_image)
        self.upload_button.bind(on_press=self.upload_to_strava)

        self.scroll_layout.add_widget(self.displayed_image)
        self.scroll_layout.add_widget(self.image_label)
        
        self.scroll_view.add_widget(self.scroll_layout)
        
        self.root.add_widget(self.scroll_view)
        self.root.add_widget(self.select_button)
        self.root.add_widget(self.upload_button)
        
        self.select_button.pos_hint = {'center_x': 0.5}
        self.upload_button.pos_hint = {'center_x': 0.5}
        

        return self.root

    def select_image(self, instance):
        file_chooser = FileChooserIconView()
        
         # Only show image files (e.g., jpg, png, etc.)
        file_chooser.filters = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff']
        popup = Popup(title="Select Image", content=file_chooser, size_hint=(0.9, 0.9))
        file_chooser.bind(on_submit=lambda *args: self.display_image(file_chooser, file_chooser.selection, popup))
        popup.open()

    def display_image(self, filechooser, selected_file, popup, *args):
        if selected_file:
            self.image_path = selected_file[0]
            self.image_label.text = ""
            img = Image.open(self.image_path)
            try:
                exif = img._getexif()
                if exif is not None:
                    orientation_tag = 274
                    if orientation_tag in exif:
                        orientation = exif[orientation_tag]
                        if orientation == 3:
                            img = img.rotate(180, expand=True)
                        elif orientation == 6:
                            img = img.rotate(270, expand=True)
                        elif orientation == 8:
                            img = img.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                pass
            
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            image = CoreImage(img_byte_arr, ext='png')
            self.displayed_image.texture = image.texture
            popup.dismiss()
            
            self.process_image(self.image_path)
            

    def process_image(self, image_path):
        threading.Thread(target=self.process_image_thread, args=(image_path,)).start()

    def process_image_thread(self, image_path):
        Clock.schedule_once(lambda dt: self.show_processing_message())
        try:
            text = extract_text_from_image(image_path)
            time, distance = extract_time_and_distance(text)
            title = self.title_var.text
            description = self.description_var.text
            
            Clock.schedule_once(lambda dt: self.update_ui_with_time_and_distance(time, distance,title,description))

        except Exception as e:
            self.show_error(str(e))
        finally:
            Clock.schedule_once(lambda dt: self.hide_processing_message())
            
    def show_processing_message(self):
        self.processing_label = Label(text="Processing...", size_hint_y=None, height=40, color=(0, 0, 1, 1))
        self.root.add_widget(self.processing_label)
    
    def hide_processing_message(self):
        if hasattr(self, 'processing_label'):
            self.root.remove_widget(self.processing_label)

    def update_ui_with_time_and_distance(self, time, distance,title,description):
        
        main_layout = BoxLayout(orientation='vertical', size_hint=(None, None), width=400, padding=10, spacing=50)
        
        title_layout = BoxLayout(orientation='horizontal')
        description_layout = BoxLayout(orientation='horizontal')
        time_layout = BoxLayout(orientation='horizontal')
        distance_layout = BoxLayout(orientation='horizontal')
        
        if not hasattr(self, 'title_input'):
            title_layout.add_widget(Label(text="Title:", size_hint=(None,None), height=40, width=90))
            self.title_input = TextInput(text=f"{title}", multiline=False, size_hint=(None,None), height=40, width=250)
            title_layout.add_widget(self.title_input)
        else:
            self.title_input.text = f"{title}"
        if not hasattr(self, 'description_input'):
            description_layout.add_widget(Label(text="Description:", size_hint=(None,None), height=40, width=90))
            self.description_input = TextInput(text=f"{description}", multiline=False, size_hint=(None,None), height=40, width=250)
            description_layout.add_widget(self.description_input)
        else:
            self.description_input.text = f"{description}"
        if not hasattr(self, 'time_input'):
            time_layout.add_widget(Label(text="Time:", size_hint=(None,None), height=40, width=90))
            self.time_input = TextInput(text=f"{time}", multiline=False, size_hint=(None,None), height=40, width=90)
            time_layout.add_widget(self.time_input)
        else:
            self.time_input.text = f"{time}"
        if not hasattr(self, 'distance_input'):
            distance_layout.add_widget(Label(text="Distance:", size_hint=(None,None), height=40, width=90))
            self.distance_input = TextInput(text=f"{distance}", multiline=False, size_hint=(None,None), height=40, width=70)
            distance_layout.add_widget(self.distance_input)
        else:
            self.distance_input.text = f"{distance}"
        
        # # Center the inputs horizontally within the BoxLayout
        # self.time_input.pos_hint = {'center_x': 0.5}  
        # self.distance_input.pos_hint = {'center_x': 0.5} 
        # self.title_input.pos_hint = {'center_x': 0.5}
        # self.description_input.pos_hint = {'center_x': 0.5}
        
        # Enable the upload button
        self.upload_button.disabled = False
        
        main_layout.add_widget(title_layout)
        main_layout.add_widget(description_layout)
        main_layout.add_widget(time_layout)
        main_layout.add_widget(distance_layout)
        
        self.scroll_layout.add_widget(main_layout)
        main_layout.pos_hint = {'center_x': 0.5}
        
    def upload_to_strava(self, instance):
        if self.image_path:
            self.upload_button.disabled = True
            try:
                text = extract_text_from_image(self.image_path)
                time = self.time_input.text
                distance = self.distance_input.text
                # time = "00:00"  # Default time if not available
                # distance = "0.0"  # Default distance if not available
                title = self.title_input.text
                description = self.description_input.text

                response = upload_activity_to_strava(time, distance, self.image_path, title, description)
                if response and response.status_code == 201:
                    self.show_success("Activity uploaded to Strava successfully!")
                else:
                    self.show_error("Failed to upload to Strava.", response.content)
            except Exception as e:
                self.show_error(f"Failed to upload: {e}")
            finally:
                self.upload_button.disabled = False
        else:
            self.show_error("No image selected.")

    def show_error(self, message):
        Clock.schedule_once(lambda dt: self.create_error_popup(message))
    
    def create_error_popup(self, message):
        popup = Popup(title="Error", content=Label(text=message), size_hint=(0.6, 0.4))
        popup.open()

    def show_success(self, message):
        popup = Popup(title="Success", content=Label(text=message), size_hint=(0.6, 0.4))
        popup.open()


if __name__ == "__main__":
    StravaApp().run()