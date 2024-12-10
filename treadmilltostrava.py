from google.cloud import vision
import io
import re
import os 

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"C:\Users\Life's Good\Desktop\Treadmill to Strava\treadmilltostrava-e53176500f19.json"
client = vision.ImageAnnotatorClient()
image_path = 'treadmill.jpg'
with io.open(image_path, 'rb') as image_file:
    content = image_file.read()
    
image = vision.Image(content=content)
response = client.text_detection(image=image)
if response.error.message:
    raise Exception(f'{response.error.message}')

text = response.text_annotations[0].description
    
time = None
distance = None
    
# Regex for time (format MM:SS, where MM is 2 digits, SS is 2 digits)
time_match = re.search(r'\b(\d{2}:\d{2})\b', text)

# Regex for distance (format as a float, e.g., 2.93 km)
distance_match = re.search(r"(\d{1,2}\.\d{2})", text)
    
if time_match:
    time = time_match.group(0)
else:
    print('Time not found in image')
if distance_match:
    distance = distance_match.group(0)
else:
    print('Distance not found in image')
        

print(f'Time: {time}, Distance: {distance}')