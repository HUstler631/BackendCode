# Terabox Downloader API

A Flask API that can download files from Terabox.

## Deployment on Koyeb

This application can be deployed to Koyeb in a few simple steps:

1. Push this code to a GitHub repository
2. Create a Koyeb account at [koyeb.com](https://koyeb.com)
3. Create a new app, selecting GitHub as the deployment method
4. Select your repository, branch, and set the following:
   - Runtime: Docker
   - No need to override the Docker command
5. Configure the following environment variables if needed:
   - `PORT`: 8080 (default)
   - `FLASK_ENV`: production (default)
6. Deploy the application

## Local Development

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python flask_app.py
   ``` 