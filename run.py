# Starts the app locally over HTTPS, which Buffer's sign-in requires.

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=8000, ssl_context="adhoc")