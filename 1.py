# import requests

# def upload_image(image_file):
#     url = "https://api.imgbb.com/1/upload"
#     payload = {
#         "key": "9ec85c4527360d6a73fbda72ce62dd80",
#         "image": image_file, # Can be base64 string or URL
#     }
#     res = requests.post(url, payload)
#     print(res.json())

# upload_image("./logo.png")  # Replace with your image URL or base64 string


import requests
import base64

def upload_image(image_path):
    url = "https://api.imgbb.com/1/upload"

    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "key": "9ec85c4527360d6a73fbda72ce62dd80",
        "image": base64_image
    }

    response = requests.post(url, data=payload)
    print(response.json())

upload_image("logo.png")
