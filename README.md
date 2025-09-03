
# Medical Dictionary — Streamlit Edition

A minimal Streamlit web app to search medical terms, add new ones, and practice with a 5‑pair quiz.

## 1) Files to add to your new GitHub repo

- `app.py` — the Streamlit app
- `requirements.txt` — Python deps for Streamlit Cloud
- `medical_terms.csv` — your data (a small sample is included)
- `.streamlit/secrets.toml` — (optional) Google Drive service account settings (see template)

## 2) Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## 3) Deploy to Streamlit Community Cloud

1. Push these files to your GitHub repo (root).
2. Go to https://share.streamlit.io and select your repo/branch.
3. Set **Main file path** to `app.py`.
4. Deploy. You’ll get a public URL.

## 4) CSV format

`medical_terms.csv` should have at least these columns (lowercase):

```
latin,english,german,slovak,definition_en
```

## 5) (Optional) Google Drive uploads

If you want the app to upload `user_added.csv`/`user_review.csv` to your shared Drive folder:

1. Create a **Service Account** in Google Cloud and generate a JSON key.
2. Share your Drive **folder** with the service account email.
3. In Streamlit Cloud → your app → **Settings → Secrets**, paste a TOML like:

```toml
[gdrive]
folder_id = "YOUR_DRIVE_FOLDER_ID"  # optional; if omitted, uploads go to My Drive
service_account = { 
  "type" = "service_account",
  "project_id" = "...",
  "private_key_id" = "...",
  "private_key" = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email" = "...@....iam.gserviceaccount.com",
  "client_id" = "...",
  "token_uri" = "https://oauth2.googleapis.com/token"
  # ...the rest of your JSON fields
}
```

**Tip:** Keep the entire JSON object under `service_account = { ... }` in TOML format.

## 6) Notes

- Free Streamlit servers are ephemeral; download or upload files to Drive for persistence.
- Edit and push to GitHub to redeploy automatically.
