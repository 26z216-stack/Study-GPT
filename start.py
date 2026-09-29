import os

from dotenv import load_dotenv

load_dotenv()  # read .env before the app reads its config

from kanal import create_app  # noqa: E402

app = create_app()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true',
            port=int(os.environ.get('PORT', 5000)))
