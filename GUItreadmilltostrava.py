import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import simpledialog
from PIL import ImageTk, Image
from google.cloud import vision
import webbrowser
import io
import re
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
from PIL.ExifTags import TAGS
import threading

# Load environment variables
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
    response_data = response.json()
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
                    env_file.write(f"STRAVA_REFRESH_TOKEN={new_refresh_token}\n")
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
    webbrowser.open(auth_link[0])
    
    newWin = tk.Tk()
    newWin.withdraw()
    
    authorization_response = simpledialog.askstring("Authorization", 
        "Please enter the full callback URL after you authorize the app in your browser:", parent=newWin)
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
    
    access_token = token['access_token']  # Save the new access_token globally
    
    with open('.env', 'r') as env_file:
        content = env_file.read()
        
        if 'STRAVA_ACCESS_TOKEN' not in content or 'STRAVA_REFRESH_TOKEN' not in content:
            with open('.env', 'a') as env_file:
                env_file.write(f"STRAVA_ACCESS_TOKEN={access_token}\n")
                env_file.write(f"STRAVA_REFRESH_TOKEN={token['refresh_token']}\n")
        else:
            print("Tokens already exist in the .env file.")
    newWin.destroy()
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


def extract_text_from_image(image_path):
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description.replace(" ", "")
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
        
    # Extract the date and time when the picture was taken
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



# Tkinter UI Application

class StravaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Treadmill to Strava")
        
        self.image_path = None
        
        # Hardcoded title and description
        self.default_title = "Treadmill Run"
        self.default_description = "Uploaded from TreadmilltoStrava"

        # Create StringVars for title and description
        self.title_var = tk.StringVar(value=self.default_title)
        self.description_var = tk.StringVar(value=self.default_description)

        # Image display
        self.image_label = tk.Label(root, text="No image selected", width=40, height=10)
        self.image_label.pack(padx=10, pady=10)
        
        # Buttons
        self.select_button = tk.Button(root, text="Select Image", command=self.select_image)
        self.select_button.pack(pady=10)

        self.upload_button = tk.Button(root, text="Upload to Strava", state=tk.DISABLED, command=self.upload_to_strava)
        self.upload_button.pack(pady=10)

        # Loading Label (Initially hidden)
        self.loading_label = tk.Label(root, text="Processing...", fg="blue")
        self.loading_label.pack(pady=10)
        self.loading_label.pack_forget()  # Hide initially

        # Uploading Label (Initially hidden)
        self.uploading_label = tk.Label(root, text="Uploading...", fg="green")
        self.uploading_label.pack(pady=10)
        self.uploading_label.pack_forget()  # Hide initially

        # Time and Distance Entry Fields (Smaller size for numbers)
        self.time_label = tk.Label(root, text="Time:")
        self.time_entry = tk.Entry(root, width=10)  # Smaller width for time
        self.time_entry.insert(0, "Not available")  # Default value for time
        self.time_label.pack(pady=5)
        self.time_entry.pack(pady=5)

        self.distance_label = tk.Label(root, text="Distance:")
        self.distance_entry = tk.Entry(root, width=10)  # Smaller width for distance
        self.distance_entry.insert(0, "Not available") # Default value for distance
        self.distance_label.pack(pady=5)
        self.distance_entry.pack(pady=5)
        
        #Initially hide the time and distance fields
        self.time_label.pack_forget()
        self.time_entry.pack_forget()
        self.distance_label.pack_forget()
        self.distance_entry.pack_forget()
        
        # Title and Description Entry Fields (Initially hidden)
        self.title_label = tk.Label(root, text="Activity Title:")
        self.title_entry = tk.Entry(root, textvariable=self.title_var, width=40)
        self.description_label = tk.Label(root, text="Activity Description:")
        self.description_entry = tk.Entry(root, textvariable=self.description_var, width=40)

        # Initially hide title and description fields
        self.title_label.pack_forget()
        self.title_entry.pack_forget()
        self.description_label.pack_forget()
        self.description_entry.pack_forget()


        

    def select_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if file_path:
            self.image_path = file_path
            self.display_image(file_path)
            self.loading_label.pack()  # Show loading label
            self.upload_button.config(state=tk.DISABLED)
            threading.Thread(target=self.process_image, args=(file_path,)).start()  # Use a thread to process image in background

    def display_image(self, image_path):
        image = Image.open(image_path)
        
        # Check EXIF data for orientation and rotate if needed
        try:
            exif = image._getexif()
            if exif is not None:
                orientation = next((tag for tag, value in exif.items() if TAGS.get(tag) == 'Orientation'), None)
                if orientation:
                    if exif[orientation] == 3:
                        image = image.rotate(180, expand=True)
                    elif exif[orientation] == 6:
                        image = image.rotate(270, expand=True)
                    elif exif[orientation] == 8:
                        image = image.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            # In case there's no EXIF or it doesn't have the Orientation tag
            pass
        
        # Resize the image to fit within a specified maximum size, maintaining aspect ratio
        max_size = 500  # Maximum size of the image
        image.thumbnail((max_size, max_size))  # Resize while maintaining aspect ratio
        
        # Create a Tkinter-compatible photo image
        img = ImageTk.PhotoImage(image)
        
        # Update the image on the label and clear the text
        self.image_label.config(image=img, text="")
        self.image_label.image = img  # Keep reference to avoid garbage collection
        
        # Optionally, update the label's width and height to match the image size
        self.image_label.config(width=image.width, height=image.height)
        
    def process_image(self, image_path):
        try:
            text = extract_text_from_image(image_path)
            if text:
                time, distance = extract_time_and_distance(text)
                self.time_entry.delete(0, tk.END)  # Clear the previous value
                self.time_entry.insert(0, time)  # Insert the detected time
                self.distance_entry.delete(0, tk.END)  # Clear the previous value
                self.distance_entry.insert(0, distance)  # Insert the detected distance
                self.upload_button.config(state=tk.NORMAL)

                #Show time and distance fields after image is processed
                self.time_label.pack(pady=5)
                self.time_entry.pack(pady=5)
                self.distance_label.pack(pady=5)
                self.distance_entry.pack(pady=5)
                
                # Show title and description fields after image is processed
                self.title_label.pack(pady=5)
                self.title_entry.pack(pady=5)
                self.description_label.pack(pady=5)
                self.description_entry.pack(pady=5)
                

            else:
                self.show_error("Text not found in the image.")
        except Exception as e:
            self.show_error(str(e))
        finally:
            self.loading_label.pack_forget()  # Hide loading label once processing is complete

    def upload_to_strava(self):
        if self.image_path:
            try:
                time = self.time_entry.get()  # Get time from the entry field
                distance = self.distance_entry.get()  # Get distance from the entry field
                title = self.title_var.get()  # Get title from the entry field
                description = self.description_var.get()  # Get description from the entry field
                
                if time != "Not available" and distance != "Not available":
                    # Show uploading label
                    self.uploading_label.pack()
                    # Perform upload in a separate thread
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
                messagebox.showinfo("Success", "Activity uploaded to Strava successfully!")
                self.reset_ui()
            else:
                self.show_error("Failed to upload to Strava." + response.text)
        finally:
            # Hide uploading label after upload is complete
            self.uploading_label.pack_forget()

    def show_error(self, message):
        messagebox.showerror("Error", message)
        
    def reset_ui(self):
        # Reset the image display to show the default text
        self.image_label.config(image=None, text="No image selected")
        
        # Clear the image reference to avoid lingering in memory
        self.image_label.image = None
        
        # Hide the title and description entry fields
        self.title_label.pack_forget()
        self.title_entry.pack_forget()
        self.description_label.pack_forget()
        self.description_entry.pack_forget()
        
        # Hide the time and distance entry fields
        self.time_label.pack_forget()
        self.time_entry.pack_forget()
        self.distance_label.pack_forget()
        self.distance_entry.pack_forget()

        # Reset the labels for time and distance
        self.time_entry.delete(0, tk.END)
        self.time_entry.insert(0, "Not available")
        self.distance_entry.delete(0, tk.END)
        self.distance_entry.insert(0, "Not available")

        # Clear title and description entry fields
        self.title_var.set(self.default_title)
        self.description_var.set(self.default_description)

        # Disable the upload button again
        self.upload_button.config(state=tk.DISABLED)
        
        # Hide loading and uploading labels
        self.loading_label.pack_forget()
        self.uploading_label.pack_forget()



if __name__ == "__main__":
    root = tk.Tk()
    app = StravaApp(root)
    root.mainloop()