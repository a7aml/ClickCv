from openai import OpenAI  # ✅ NEW
import os
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import ResumeAnalysis, AtsResult
from app.models.analysis import ResumeComparison
from app.models.generated_cv import GeneratedCv
from app.models.chatbot import ChatbotMessage
from openai import OpenAI

class ChatbotService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-3.5-turbo"
    
    def get_ai_response(self, user_id, conversation_id, user_message):
        """Generate AI response based on user message and data"""
        
        # Build context from user's data
        context = self._build_user_context(user_id)
        
        # Get conversation history
        history = self._get_conversation_history(conversation_id)
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": self._get_system_prompt(context)},
            *history,
            {"role": "user", "content": user_message}
        ]
        
        try:
            # NEW SYNTAX
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"OpenAI API Error: {str(e)}")
            return "I'm having trouble connecting right now. Please try again in a moment."
    
    def _build_user_context(self, user_id):
        """Build context from user's resume data"""
        
        context = {
            'user_name': '',
            'total_resumes': 0,
            'latest_ats_score': None,
            'missing_keywords': [],
            'missing_sections': [],
            'total_comparisons': 0,
            'total_generated_cvs': 0,
            'resumes_list': [],
            'scores': {}
        }
        
        # Get user
        user = User.query.get(user_id)
        if user:
            context['user_name'] = user.name
        
        # Get all resumes
        resumes = Resume.query.filter_by(user_id=user_id).all()
        context['total_resumes'] = len(resumes)
        
        for resume in resumes:
            context['resumes_list'].append({
                'filename': resume.file_name,
                'uploaded_at': resume.created_at.strftime('%Y-%m-%d')
            })
        
        # Get latest analysis
        latest_analysis = ResumeAnalysis.query.filter_by(user_id=user_id).order_by(
            ResumeAnalysis.created_at.desc()
        ).first()
        
        if latest_analysis:
            context['latest_ats_score'] = latest_analysis.overall_score
            
            # Get ATS result details
            ats = AtsResult.query.filter_by(analysis_id=latest_analysis.id).first()
            if ats:
                context['missing_keywords'] = ats.missing_keywords or []
                context['missing_sections'] = ats.missing_sections or []
                context['scores'] = {
                    'keyword_score': ats.keyword_score,
                    'keyword_placement_score': ats.keyword_placement_score,
                    'formatting_score': ats.formatting_score,
                    'structure_score': ats.structure_score,
                    'experience_recency_score': ats.experience_recency_score,
                    'achievements_score': ats.achievements_score,
                    'job_title_score': ats.job_title_score,
                    'education_score': ats.education_score,
                    'resume_length_score': ats.resume_length_score,
                    'contact_info_score': ats.contact_info_score
                }
        
        # Get comparisons count
        comparisons = ResumeComparison.query.filter_by(user_id=user_id).all()
        context['total_comparisons'] = len(comparisons)
        
        # Get generated CVs count
        generated_cvs = GeneratedCv.query.filter_by(user_id=user_id).all()
        context['total_generated_cvs'] = len(generated_cvs)
        
        return context
    
    def _get_system_prompt(self, context):
        """Create system prompt with user context"""
        
        # Format missing keywords
        missing_kw = ', '.join(context['missing_keywords'][:5]) if context['missing_keywords'] else 'None'
        missing_sec = ', '.join(context['missing_sections'][:3]) if context['missing_sections'] else 'None'
        
        prompt = f"""You are an ATS (Applicant Tracking System) and Resume Expert Assistant for ClickCV platform.

**YOUR ROLE:**
- Answer ONLY questions about resumes, CVs, ATS systems, job applications, career advice
- Reference the user's specific resume data when relevant
- Be helpful, professional, and encouraging
- If asked about non-resume topics, politely redirect to resume-related assistance

**USER CONTEXT:**
- Name: {context['user_name']}
- Total Resumes Uploaded: {context['total_resumes']}
- Latest ATS Score: {context['latest_ats_score']}/100 if context['latest_ats_score'] else 'Not analyzed yet'
- Missing Keywords: {missing_kw}
- Missing Sections: {missing_sec}
- Total Comparisons Done: {context['total_comparisons']}
- Generated CVs: {context['total_generated_cvs']}

**UPLOADED RESUMES:**
"""
        
        if context['resumes_list']:
            for resume in context['resumes_list'][:5]:
                prompt += f"\n- {resume['filename']} (uploaded: {resume['uploaded_at']})"
        else:
            prompt += "\n- No resumes uploaded yet"
        
        # Add score breakdown if available
        if context['scores']:
            prompt += f"""

**LATEST ATS SCORE BREAKDOWN:**
- Keyword Matching: {context['scores'].get('keyword_score', 0)}/100
- Keyword Placement: {context['scores'].get('keyword_placement_score', 0)}/100
- Formatting: {context['scores'].get('formatting_score', 0)}/100
- Structure: {context['scores'].get('structure_score', 0)}/100
- Experience Recency: {context['scores'].get('experience_recency_score', 0)}/100
- Achievements: {context['scores'].get('achievements_score', 0)}/100
- Job Title Match: {context['scores'].get('job_title_score', 0)}/100
- Education: {context['scores'].get('education_score', 0)}/100
- Resume Length: {context['scores'].get('resume_length_score', 0)}/100
- Contact Info: {context['scores'].get('contact_info_score', 0)}/100
"""
        
        prompt += """

**ATS SCORING CRITERIA (for reference):**
1. Keyword Matching (35-40%): Match job description keywords
2. Keyword Placement (15-20%): Keywords in summary, skills, experience sections
3. Formatting (15-20%): Simple layout, standard fonts, no graphics/tables
4. Section Completeness (10-15%): Contact, summary, experience, education, skills
5. Experience Recency (10-15%): Recent experience weighted more
6. Quantifiable Achievements (10-12%): Numbers, percentages, impact metrics
7. Job Title Matching (8-10%): Previous titles match target role
8. Education & Certifications (5-10%): Required degrees and certs
9. Resume Length (3-5%): 1 page for entry-level, 2 pages for senior
10. Contact Information (2-5%): Valid phone, email, location

**GUIDELINES:**
- Keep responses concise (2-4 sentences usually)
- Use the user's data when answering questions about their resume
- Provide actionable tips
- Be encouraging but honest
- If user asks to "rewrite a section", give specific examples
- Reference their specific weak scores when giving advice
"""
        
        return prompt
    
    def _get_conversation_history(self, conversation_id, max_messages=10):
        """Get recent conversation history"""
        
        messages = ChatbotMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            ChatbotMessage.timestamp.desc()
        ).limit(max_messages).all()
        
        # Reverse to chronological order
        messages = list(reversed(messages))
        
        # Format for OpenAI
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.message
            })
        
        return history