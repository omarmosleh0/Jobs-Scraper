# Manual Setup Steps

Before running the scraper, complete these steps.

## 1. Run Supabase Schema

1. Go to [Supabase Dashboard](https://supabase.com/dashboard) > your project
2. Open **SQL Editor**
3. Copy the contents of `supabase/schema.sql`
4. Paste and run it

**Note:** If you get permission errors when the scraper inserts jobs, use the **service_role** key (not anon/publishable) from Project Settings > API.

## 2. Ollama

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull qwen2.5:7b

# Verify
ollama run qwen2.5:7b "Hello"
```

## 3. Telegram

1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, follow prompts
2. Create a channel (e.g. `@job_scraping_tech`)
3. Add your bot as channel admin
4. Put bot token and channel username in `.env`

## 4. Environment

Copy `.env.example` to `.env` and fill in your values.
