# 🚀 Deploying Smart Expense Intelligence

## 1. Hosting the FastAPI Backend on Vercel
The project is configured for Vercel Serverless deployment via [vercel.json](file:///Users/anuragkodge/Resume%20/expense-intelligence/vercel.json) and [api/index.py](file:///Users/anuragkodge/Resume%20/expense-intelligence/api/index.py).

### Option A: Using Vercel CLI (Quickest)
Run in terminal:
```bash
npx vercel
```
1. Follow the interactive prompts.
2. Under project settings on your Vercel Dashboard, add your **Environment Variables**:
   - `JWT_SECRET`: (your JWT secret)
   - `BREVO_API_KEY`: (your Brevo API key)
   - `EMAIL_FROM`: seisystemver@gmail.com
   - `EMAIL_FROM_NAME`: Smart Expense Intelligence
   - `GEMINI_API_KEY`: (your Gemini API key)
   - `GOOGLE_API_KEY`: (your Google API key)

### Option B: Deploying via GitHub / Git Repository
1. Push `expense-intelligence` folder to your GitHub repo.
2. Go to [vercel.com/new](https://vercel.com/new) -> Import repository.
3. Configure the environment variables listed above.
4. Click **Deploy**!

---

## 2. Hosting the Interactive Streamlit UI (Streamlit Community Cloud)
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub repository.
3. Set Main file path: `frontend/app.py`
4. In **App Settings -> Secrets**, set:
   ```toml
   BACKEND_URL = "https://your-vercel-backend-app.vercel.app"
   GEMINI_API_KEY = "your_gemini_api_key"
   ```
5. Click **Deploy**!
