# 365 Days of Running

**A physical challenge turned code challeng.** 
On Dec 1 2024, I started 1 year run streak, running minimum one mile every day. To document each day , I built a custom automation pipeline that turns my Garmin watch data into a blog.

[**Check the blog →  /sprague runs →**](https://csprague.sdf.org/)

---

### The Architecture

I wanted an automated way to handle creating the blog entry each day. The automation turns my physical footsteps into a digital footprint with a few simple steps.

![Architecture Diagram](./images/mermaid-diagram.png)

---

### How It Works

**1. Note Parsing** When my watch data is uploaded to Garmin Connect, I edit the activity title and add some details about the run as a Note. 
The script parses this string:
```text
w: Intervals 4x400
c: Felt strong, humid weather.
```
It extracts these into separate Markdown frontmatter fields (`Workout` and `Comments`) using Regex, keeping the blog metadata clean.

**2. Data Extraction** The Python script authenticates with the Garmin Connect API and pulls the latest activity data.

**3. Static Generation** The script calculates the duration, distance and pace, generates a tempalted Markdown file, and triggers a Hugo build.

**4. Hosting** The script and final HTML are both hosted on **SDF.org**, a public access Unix system, keeping the project lightweight and rooted in open computing history.

---

### Project Statistics

| Metric | Result |
| :--- | :--- |
| **Goal** | Run 1 mile, every day |
| **Status** | Completed |
| **Total Distance** | 1,520 miles |
| **Weekly Average** | 29 miles |
| **Stack** | Python, Hugo, Bash |

---

### Usage

This script is designed to be menu-driven for safety, allowing you to review the activity before publishing.

```bash
# 1. Install requirements
pip install -r requirements.txt

# 2. Configure variables in .env
export GARMIN_EMAIL="your@email.com"
export GARMIN_PASSWORD="yourpassword"

# 3. Run the generator
python main.py
```

### The Code

The core of the logic lies in the `write_post` function, which bridges the gap between raw JSON data and the Hugo content structure.

```python
# Snippet: Formatting the blog post content
frontmatter = f"""---
title: "{title}"
date: {start_date}
categories: post
tags: [{tags_formatted}]
---
{post_name} 
{distance:.2f} mi 
{duration_str} 
{pace_str}/mi 
Workout: {workout} 
Comments: {comment}
"""
```

---

*Hosted with pride on [SDF.org](https://sdf.org).*
