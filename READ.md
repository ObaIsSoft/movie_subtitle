Quoted - Deployment Guide for Fly.io

This guide provides the step-by-step commands to deploy your "Quoted" application to the fly.io platform.

1. Prerequisites

Install flyctl: If you don't have it, install the fly.io command-line tool.

brew install flyctl


Install Docker Desktop: flyctl uses Docker on your Mac to build your app's image. You must download and install Docker Desktop and make sure it is running before you continue.

Log in to Fly:

fly auth login


2. Launch the App (Initial Setup)

This command will create your fly.io app and generate the fly.toml file.

fly launch --no-deploy


App Name: It will ask you for an app name. Choose a unique name (e.g., quoted-app-obafemi).

Region: Select a region close to you (e.g., iad - Ashburn, VA (US)).

Use fly.toml? It will detect the fly.toml I provided. Say Yes to use it.

Postgres? It will ask "Would you like to set up a Postgres database now?" Say No. We will do this manually for more control.

Redis? It will ask about Redis. Say No.

Deploy now? It will ask "Would you like to deploy now?" Say No. We still need to create our database and set secrets.

3. Create and Attach the Database

Create a Postgres Database:

fly pg create


Select a region (choose the same region as your app).

Select a plan (the "Development - Shared CPU" is free).

Attach the Database to Your App:
This is the most important step. It creates the database user and automatically sets the DATABASE_URL secret in your app. Replace [your-db-name] with the name fly pg create gave you (e.g., quoted-db-obafemi).

fly pg attach [your-db-name]


4. Set Application Secrets

Your app needs the OpenSubtitles API credentials to work. These commands add them to your fly.io app as secure environment variables.

fly secrets set API_KEY="CfMhD6DoAOOBIPsDUKvzFaFWDSXynPsZ"
fly secrets set USERNAME="dev_gru"
fly secrets set PASSWORD="Olorioko2003"


Your app is now fully configured.

5. Deploy the Application

This single command will:

Build your app's image using the Dockerfile.

Push the image to fly.io.

Run the release_command from fly.toml (which is flask init-db), setting up your tables and pg_trgm.

Start your app.

fly deploy


Wait for it to finish. Your app is now live!

6. Populate the Live Database

Your app is live, but its database is empty. We need to run our fetch_from_api.py script inside the live server.

Open an SSH shell into your running app:

fly ssh console


(Your terminal prompt will change, e.g., root@...:/app#)

Run the script:

python3 fetch_from_api.py


Watch the output. You will see it log in (✅ Login successful...) and start importing movies (✅ Successfully imported...). This will take a few minutes.

Exit the shell when it's done:

exit
