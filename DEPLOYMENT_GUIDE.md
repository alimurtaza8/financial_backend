# Vercel Deployment Guide for RFP Proposal Generator

This guide will help you deploy your FastAPI application to Vercel.

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Account**: Your code should be in a GitHub repository
3. **Environment Variables**: Prepare your environment variables

## Files Created for Vercel Deployment

1. **`vercel.json`** - Vercel configuration file
2. **`api/index.py`** - Entry point for Vercel
3. **`.vercelignore`** - Files to ignore during deployment
4. **Updated `requirements.txt`** - Cleaned up dependencies

## Step-by-Step Deployment Instructions

### 1. Push Code to GitHub

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit changes
git commit -m "Prepare for Vercel deployment"

# Add remote repository (replace with your GitHub repo URL)
git remote add origin https://github.com/yourusername/your-repo-name.git

# Push to GitHub
git push -u origin main
```

### 2. Deploy to Vercel

#### Option A: Deploy via Vercel Dashboard
1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "New Project"
3. Import your GitHub repository
4. Vercel will automatically detect it's a Python project
5. Configure environment variables (see section below)
6. Click "Deploy"

#### Option B: Deploy via Vercel CLI
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy from your project directory
vercel

# Follow the prompts:
# - Set up and deploy? Yes
# - Which scope? (choose your account)
# - Link to existing project? No
# - Project name? (enter your project name)
# - Directory? ./
# - Override settings? No
```

### 3. Configure Environment Variables

In your Vercel dashboard, go to your project settings and add these environment variables:

#### Required Environment Variables:
```
SECRET_KEY=your-super-secret-key-change-in-production
GEMINI_API_KEY=your-gemini-api-key
DATABASE_URL=your-database-connection-string
```

#### Optional Environment Variables:
```
PYTHONPATH=/var/task
```

### 4. Database Configuration

**Important**: Vercel functions are stateless, so SQLite won't work in production.

#### Recommended Database Options:

1. **Vercel Postgres** (Recommended)
   ```
   DATABASE_URL=postgresql://username:password@host:port/database
   ```

2. **Supabase** (Free PostgreSQL)
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project
   - Get connection string from Settings > Database
   
3. **PlanetScale** (MySQL)
   ```
   DATABASE_URL=mysql://username:password@host:port/database
   ```

4. **Railway** (PostgreSQL/MySQL)
   ```
   DATABASE_URL=postgresql://username:password@host:port/database
   ```

### 5. File Storage Configuration

Since Vercel functions are stateless, file uploads won't persist. Consider these options:

#### Option 1: Vercel Blob Storage
```python
# Install vercel blob
# pip install vercel-blob

# Update your code to use Vercel Blob for file storage
```

#### Option 2: AWS S3
```python
# Install boto3
# pip install boto3

# Configure S3 for file storage
```

#### Option 3: Cloudinary
```python
# Install cloudinary
# pip install cloudinary

# Use Cloudinary for image and document storage
```

### 6. Modify Code for Production

You may need to make these changes for production:

#### Update Database Configuration in `ex.py`:
```python
# Replace SQLite with PostgreSQL for production
import os
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

# Ensure it uses PostgreSQL driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
```

#### Update File Paths:
```python
# Use temporary directories for Vercel
import tempfile
UPLOAD_DIR = tempfile.mkdtemp()
OUTPUT_DIR = tempfile.mkdtemp()
```

### 7. Testing Your Deployment

1. Wait for deployment to complete
2. Visit your Vercel URL (e.g., `https://your-project.vercel.app`)
3. Test the following endpoints:
   - `GET /` - Should return 404 (expected, as there's no root endpoint)
   - `GET /docs` - Should show FastAPI documentation
   - `POST /auth/register` - Test user registration
   - `POST /auth/login` - Test user login

### 8. Custom Domain (Optional)

1. In Vercel dashboard, go to your project settings
2. Click "Domains"
3. Add your custom domain
4. Configure DNS records as instructed

## Troubleshooting

### Common Issues:

1. **Import Errors**
   - Ensure all dependencies are in `requirements.txt`
   - Check Python path configuration

2. **Database Connection Errors**
   - Verify DATABASE_URL environment variable
   - Ensure database service is accessible from Vercel

3. **File Upload Issues**
   - Remember Vercel functions are stateless
   - Use cloud storage for persistent file storage

4. **Timeout Errors**
   - Vercel has a 30-second timeout for serverless functions
   - Consider splitting long operations into background tasks

5. **Large Dependencies**
   - Some packages (like PyTorch) might be too large for Vercel
   - Consider alternatives or use Vercel Pro for larger limits

### Logs and Debugging:

1. View logs in Vercel dashboard under "Functions" tab
2. Use `vercel logs` command for CLI access
3. Add print statements for debugging (they'll appear in logs)

## Environment Variables Reference

Create a `.env` file locally with these variables for development:

```bash
# .env (for local development only)
SECRET_KEY=your-local-secret-key
GEMINI_API_KEY=your-gemini-api-key
DATABASE_URL=sqlite:///./proposal_generator.db
```

**Note**: Never commit `.env` file to git. It's already in `.gitignore`.

## Production Checklist

- [ ] Code pushed to GitHub
- [ ] Vercel project created and deployed
- [ ] Environment variables configured
- [ ] Database migrated to production service
- [ ] File storage configured for cloud provider
- [ ] Custom domain configured (if needed)
- [ ] SSL certificate working
- [ ] All endpoints tested
- [ ] Error monitoring set up (optional)

## Support and Next Steps

1. **Monitoring**: Consider adding error tracking (Sentry)
2. **Analytics**: Add Vercel Analytics for usage insights
3. **Scaling**: Monitor function usage and upgrade plan if needed
4. **Security**: Review CORS settings for production
5. **Backup**: Set up database backups

For more help, refer to:
- [Vercel Documentation](https://vercel.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vercel Python Runtime](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
