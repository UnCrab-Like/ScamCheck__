import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app


if __name__ == "__main__":
    app.run(debug=True, port=5000)
