# Get-Placed

**Your personal AI-powered job search assistant.**

Get-Placed helps streamline off-campus job applications. It discovers jobs using search queries tailored to your profile, evaluates them against your skills and preferences, ranks relevant opportunities, drafts customized LaTeX resumes, and tracks your applications through Google Sheets.

## Features

- **Job Discovery:** Scrapes jobs using personalized search queries from FreeHire and LinkedIn.
- **Job Matching:** Evaluates jobs against your profile, filters mismatches, removes duplicates, and ranks relevant opportunities.
- **Resume Tailoring:** Generates customized, single-page LaTeX resumes for specific job descriptions.
- **Application Tracking:** Updates your Google Sheets tracker with application details and statuses.
- **Analytics:** Analyzes your application history, response times, and conversion rates.
- **Query Debugging:** Investigates irrelevant results and improves job search queries.

## Getting Started

No manual configuration required. Let your AI coding agent set everything up.

**Paste this prompt into your AI coding agent (Antigravity, Claude Code, etc.):**

```text
Clone https://github.com/TushN101/Get-Placed

Read AGENTS.md and all the skills under .agents/skills/
before making any changes.

Initialize Get-Placed for me.

1. Ask me for my current resume and preferred LaTeX
   resume template, if I have one.

2. Analyze my resume to understand my education,
   experience, skills, projects and target roles.

3. Based on my profile, generate personalized
   LinkedIn and FreeHire search queries.

4. Configure the candidate profile, preferences,
   resume template and search queries.

5. Verify all configurations against AGENTS.md
   and the relevant agent skills.

6. Check that everything is ready to use.

Do not invent candidate information or overwrite
existing user data.

Once everything is ready, summarize the setup
and tell me how to use Get-Placed.
```

## Usage

Once initialized, simply ask your agent to use the relevant skill: `find-jobs`, `debug-proj`, `analyze-jobs`, or `draft-resume`.

## Screenshots

| Job Discovery · Antigravity Desktop | Query Debugging · Antigravity Desktop |
|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/8c498398-1ab6-4a71-b6cd-88722073062a" width="100%" alt="Job Discovery"/> | <img src="https://github.com/user-attachments/assets/cfdada8c-4eb2-4c80-8c54-39d26249d997" width="100%" alt="Query Debugging"/> |
| **Application Analytics · Antigravity Desktop** | **Antigravity CLI** |
| <img src="https://github.com/user-attachments/assets/c1be02ab-c858-4cba-84d7-6cac1b4fb1c9" width="100%" alt="Application Analytics"/> | <img src="https://github.com/user-attachments/assets/2772d921-43a4-43a4-baa5-155ec606632b" width="100%" alt="Antigravity CLI"/> |

