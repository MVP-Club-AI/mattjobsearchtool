# Drop Your LinkedIn Data Export Here

Unzip your LinkedIn data export into this folder. Claude Code will find it automatically.

## How to get your LinkedIn data

1. Go to **LinkedIn.com**
2. Click your profile icon → **Settings & Privacy**
3. Go to **Data Privacy** → **Get a copy of your data**
4. Select these categories:
   - **Connections** (required — this is the most important one)
   - **Jobs** (recommended — includes your saved jobs)
   - **Company Follows** (recommended — companies you follow)
5. Click **Request archive**
6. LinkedIn emails you a ZIP file within **~24 hours**
7. **Unzip it into this folder**

## What this folder should look like after unzipping

```
linkedin-data/
  DROP_LINKEDIN_EXPORT_HERE.md   ← this file
  Connections.csv                ← your connections (required)
  Saved Jobs.csv                 ← your saved jobs (optional)
  Company Follows.csv            ← companies you follow (optional)
  Profile.csv                    ← your profile data (optional)
  Skills.csv                     ← your skills (optional)
  Positions.csv                  ← your work history (optional)
  ...                            ← other LinkedIn export files
```

## What Claude Code does with this

- **Connections.csv** → Network matching. The tool flags every job where you know someone at the company. Those matches get boosted because a warm intro changes your odds.
- **Saved Jobs.csv** → ATS expansion. The tool auto-detects career pages for companies in your saved jobs and monitors them.
- **Company Follows.csv** → More ATS expansion. Same as above, for companies you follow.

## Privacy

- **Nothing leaves your machine** — all LinkedIn data is gitignored and stays local
- The tool only reads the CSV files — it doesn't access your LinkedIn account
- You can delete the export anytime and the tool still works (just without network matching)

## Don't have it yet?

No problem. The tool works without LinkedIn data. You can add it anytime — just unzip the export here and tell Claude Code "I added my LinkedIn data."
