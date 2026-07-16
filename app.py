from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
def configure():
      api_key = os.getenv("api_key")

      if not api_key:
          raise RuntimeError("api_key is missing from the .env file")

      return api_key


api_key = configure()

app = Flask(__name__)

@app.route('/check', methods=['POST'])
def check_url():
    url = request.json['url']
    # Here you would implement the logic to check if the URL is a scam or not.
    # For demonstration purposes, let's assume all URLs are scams.
    scam_status = 'Scam'  # You can replace this with actual scam detection logic

    return jsonify({'scamStatus': scam_status})

if __name__ == '__main__':
    app.run(debug=True)

def main():
    configure()
