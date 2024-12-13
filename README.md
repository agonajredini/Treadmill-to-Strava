# Treadmill to Strava

Treadmill to Strava is a Python-based application that allows users to upload treadmill workout data to Strava by extracting relevant information from images of treadmill screens. This project includes two graphical user interfaces (GUIs) implemented using Tkinter and Kivy for better accessibility and functionality.

## Features

- Extract time and distance data from treadmill screen images using Google Vision API.
- Automatically fetch and refresh Strava API tokens for seamless integration.
- Upload activity data (including title, description, time, and distance) to Strava.
- Two GUI options:
  - **Tkinter-based GUI**: Simple and easy to use.
  - **Kivy-based GUI**: Modern and flexible for cross-platform usage.
- A no-GUI version for users who prefer command-line usage.
- Image processing includes reading EXIF data for activity start time.

## Requirements

### Software and Libraries

- Python 3.7+
- Dependencies (install using `pip install -r requirements.txt`):
  - `tkinter`
  - `kivy`
  - `google-cloud-vision`
  - `requests`
  - `requests-oauthlib`
  - `pillow`
  - `python-dotenv`

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```plaintext
GOOGLE_APPLICATION_CREDENTIALS="<path_to_your_google_credentials_json_file>"
STRAVA_CLIENT_ID=<your_strava_client_id>
STRAVA_CLIENT_SECRET=<your_strava_client_secret>
STRAVA_REDIRECT_URI="<your_redirect_uri>"
STRAVA_ACCESS_TOKEN=<your_initial_access_token>
STRAVA_REFRESH_TOKEN=<your_initial_refresh_token>
```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/agonajredini/treadmill-to-strava.git
   cd treadmill-to-strava
   ```

2. Install the required Python libraries:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your Google Vision API credentials and Strava API credentials as described in the **Requirements** section.

## Usage
### No-GUI Version

1. Run the command-line version:

   ```bash
   python treadmilltostrava.py
   ```

2. Make syre to:

   - Provide the path to the treadmill image.
   - Change additional details (e.g., title and description).

### Tkinter GUI

1. Run the Tkinter-based GUI application:

   ```bash
   python GUItreadmilltostrava.py
   ```

2. Use the interface to:

   - Select a treadmill image.
   - Extract time and distance data.
   - Enter additional details (e.g., title and description).
   - Upload the activity to Strava.

### Kivy GUI

1. Run the Kivy-based GUI application:

   ```bash
   python kivyGUI.py
   ```

2. Follow the prompts to:

   - Select an image of your treadmill screen.
   - Enter additional details (e.g., title and description).
   - Extract and review the workout data.
   - Upload the activity directly to Strava.


## Project Structure

```
├── treadmilltostrava.py     # Command-line application
├── GUItreadmilltostrava.py  # Tkinter-based GUI application
├── kivyGUI.py               # Kivy-based GUI application
├── pics/                    # Folder containing sample treadmill screen images
├── .env                     # Environment variables file
├── README.md                # Project documentation
└── requirements.txt         # Python dependencies
```

## Acknowledgments

- **Google Cloud Vision API**: For text recognition capabilities.
- **Strava API**: For uploading activities to Strava.
- **Kivy and Tkinter**: For building the graphical user interfaces.
