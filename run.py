"""Simple startup entry point for normal local use.

Run this file to start the BugSleuth application without needing to remember the
Flask app module details.
"""

from app import app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
