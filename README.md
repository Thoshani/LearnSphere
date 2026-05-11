# 🎓 LearnSphere – AI-Powered E-Learning Platform

A full-featured e-learning platform built with Streamlit + Groq AI.

## 🚀 Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Structure
```
elearn_platform/
├── app.py                    # Main application
├── requirements.txt
├── prompts/
│   ├── tabler_prompt.py      # Course outline generator prompt
│   ├── dictator_prompt.py    # Module/lesson extractor prompt
│   └── quizzy_prompt.py      # Quiz generator prompt
```

## 👥 User Roles

### Admin (Instructor)
- Create courses with AI-generated outlines
- Generate complete modules and lessons
- Manage and regenerate quizzes
- View all students and their performance

### Student
- Browse all published courses
- Read module content
- Take interactive quizzes with instant scoring
- Track progress and quiz history
- Chat with AI tutor

## 🔐 Demo Login
- **Student**: `demo_student` / `demo123`
- **Admin**: `demo_admin` / `admin123`

## 🧠 AI Features
- **Course Outline Generation** – Smart prompt engineering → Tabler
- **Full Module Content** – Bloom's Taxonomy-aligned lesson content
- **Auto Quiz Generation** – 10 MCQs per module with explanations
- **AI Chat Tutor** – Context-aware tutoring assistant
- **PDF Export** – Download complete course as PDF
