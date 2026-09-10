# NMS Dashboard — GitHub Pages deployment

This package is ready to upload into a new GitHub repository such as `NMS-Dashboard`.

## Repository files

`index.html` must be at the repository root. Keep all of these files/folders:

- index.html
- nms-data.json
- manifest.webmanifest
- sw.js
- icon-192.png
- icon-512.png
- requirements.txt
- scripts/update_nms_data.py
- .github/workflows/nms-sync-and-deploy.yml

## 1. Create repository

Create a new repository named `NMS-Dashboard` under your GitHub account. Extract this ZIP first, then upload the CONTENTS. Do not upload the ZIP as one file.

## 2. Add Google service-account secret

Repository > Settings > Secrets and variables > Actions > New repository secret

Name: `GOOGLE_CREDENTIALS`

Value: the complete private JSON key for the Google service account that already has Viewer access to the NMS spreadsheet.

Never put the private JSON inside index.html or any committed file.

## 3. Configure GitHub Pages

Repository > Settings > Pages > Build and deployment > Source: `GitHub Actions`

This package intentionally uses GitHub Actions for deployment. Do not choose “Deploy from a branch” for this version.

## 4. Run first sync/deploy

Repository > Actions > `NMS Sync and Deploy` > Run workflow > Run workflow

When the run is green, Settings > Pages will show the live URL. If the repository is named `NMS-Dashboard`, the expected URL is:

https://YOUR-USERNAME.github.io/NMS-Dashboard/

The workflow automatically checks the Google Sheet once per hour and redeploys the current dashboard.

## 5. Desktop use

Open the GitHub Pages URL in Chrome/Edge and bookmark it. The dashboard starts on Daily > Latest automatically.

## 6. Android test as an app

Open the GitHub Pages URL in Chrome on Android > menu > Install app / Add to Home screen. The PWA uses the same live `nms-data.json` snapshot as desktop.

## Privacy warning

GitHub Pages sites are public on the internet. Do not publish live internal sales/purchasing/stock data this way unless you are comfortable with anyone who finds the URL being able to access it. A visual password prompt inside the HTML does not make the underlying JSON private.

For a private production version, keep GitHub for source code but put the live data behind an authenticated API (for example Cloudflare Access/Worker, Firebase, or another authenticated backend). The Android app can then use the same protected data source.
