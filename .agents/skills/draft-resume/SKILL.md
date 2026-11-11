---
name: draft-resume
description: Tailor a one-page LaTeX resume to a specific job description using the user's template (uploads/ResumeTemplate.tex) and their real profile. Use when the user says they like a role, asks for a resume for a job, or asks to tweak a resume they already have.
---

# Draft Resume

Produce a clean, one-page, job-tailored `.tex` resume by **filling the user's template with their real information**. You are editing content, not designing a layout. The template already has a good layout; your job is to not break it.

No scripts are needed for this skill. If a shell with a LaTeX compiler is available, use the optional compile check in Step 6. If not, follow the rules below carefully and tell the user the file was not compiled.

## Inputs

| Input | Where | Notes |
|---|---|---|
| Template | `uploads/ResumeTemplate.tex` | **Always** use this. Never write a resume from scratch or switch to another template. |
| User facts | `database/user/userProfile.json` | The only source of truth for experience, projects, skills, education. |
| Job description | From the user, or fetched from the job link | If you only have a title or a bare link and cannot fetch the full JD, ask the user to paste it. |

If the template file is missing, **stop and tell the user.** Do not invent a template.

## Output

- Save to `database/deliverables/<company>_<role>_<YYYY-MM-DD>.tex` (lowercase, underscores, no spaces).
- Never overwrite an existing file. Add `_v2`, `_v3` and so on.
- Hand the file to the user, then give a short summary (Step 7).

## Process

### Step 1: Read the template first

Before writing anything, read the entire template and learn:
- Which custom commands and environments it defines (for example a subheading command, an item-list environment, a skills block) and exactly how they are called.
- Which sections exist and their order.
- How long a typical bullet is (it should fit on one or two lines).

Then **reuse those exact commands the same way the template does.** Copy an existing entry as the pattern for each new one.

### Step 2: Analyze the job description

Extract:
- Must-have skills and tools, and the keywords repeated most.
- Core responsibilities (what the person will actually do).
- Seniority and domain (backend, ML, data, frontend, and so on).

### Step 3: Match with the user's real experience

Map each JD requirement to something true in `userProfile.json`. Choose the **most relevant** projects, experiences and skills. Cut or shorten the rest. A tailored one-page resume is selective, not exhaustive.

### Step 4: Ask about gaps (once, in one batch)

If the JD asks for something not in the profile, or a project is missing details you need (what the user built, the stack, a measurable result), ask all your questions in one message. Example:

> The JD asks for Kubernetes and CI/CD. Have you used either in a project? Also, for the payments project, do you have a number for users, latency or time saved?

Do not guess and do not ask one question at a time. If the user does not answer, leave the item out.

### Step 5: Write the resume

**Content rules**
- **Never invent** employers, titles, degrees, dates, skills or metrics. Only rewrite, reorder and emphasize what is true.
- Use keywords from the JD **only where they honestly apply.**
- Write bullets as: strong action verb + what you did + how (tech) + result. Add numbers only if the user gave them.
- Keep bullets concise: aim for one line, **two lines at most**. No paragraph bullets.
- Keep the same number of bullets per entry as the template shows, roughly 2 to 4 each. Fewer, stronger bullets beat many weak ones.
- Order sections and entries by relevance to this job.
- Use consistent tense (past for finished work, present for current roles) and consistent date formatting.

**Layout rules (these prevent the "cramped, overlapping, ugly" output)**
- **Do not change the preamble.** Leave document class, packages, margins, font size, line spacing and custom command definitions alone, unless the user asks.
- **Do not fix overflow by shrinking things.** Never reduce font size, margins or line spacing, and never use negative `\vspace`, `\scalebox`, `\tiny` or similar hacks to squeeze content in.
- **If it does not fit on one page, cut content**, not formatting. Remove the weakest bullet, shorten wording, or drop the least relevant entry.
- **Do not add manual spacing hacks.** Avoid stray `\\`, `\vspace`, `\hspace`, `\quad` and blank-line stacking. Trust the template's spacing.
- **Do not nest or stack the template's commands in new ways.** Overlapping text almost always comes from misusing a command, for example putting a list inside an argument that expects a single line, or leaving an environment unclosed.
- **Keep arguments short where the template expects a single line**, such as titles, company names, locations and dates. Long text in these arguments is a common cause of lines colliding.
- **Balance braces and environments.** Every `{`, `\begin{...}` and `\item` must be correct and closed.
- **Escape special characters** in all text: `& % $ # _ { } ~ ^ \`. For example write `\&`, `\%`, `\$`, `\#`, `\_`. Do this for tech names such as `C\#`, `Node\_js` style filenames and percentages like `40\%`.
- Use the template's own link command for URLs (GitHub, LinkedIn). Do not paste raw long URLs that run past the margin.
- Do not add images, tables, columns, icons or extra packages unless the template already uses them.
- Do not add new sections unless the user asks. Remove an empty section rather than leaving it blank.

### Step 6: Check the work

1. **Static check (always):** re-read the file and confirm braces and environments are balanced, special characters are escaped, no long line is likely to overflow, and only the template's commands are used.


### Step 7: Deliver

Save the file to the /database/deliverables folder , then reply with a **short** summary:
- The file path.
- Three to five lines on what you emphasized or changed for this role.
- Anything you left out or could not fill (missing metrics, skill gaps).
- Whether it was compile-checked.

Then offer one next step, such as logging the application or making edits. If the user confirms they applied, record the resume file name in their application tracker.

## Hard rules

- Use `uploads/ResumeTemplate.tex`. Never replace or redesign it.
- Never fabricate anything.
- Never fix a fit problem by changing formatting. Fix it by cutting content.
- Never overwrite an earlier resume file.
- One page unless the user says otherwise.
