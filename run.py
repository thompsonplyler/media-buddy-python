from src.media_buddy import create_app
import os

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000) 