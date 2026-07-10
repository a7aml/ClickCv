
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import ResumeComparison, ComparisonResume
from app.models.generated_cv import GeneratedCv
from app.models.cv_draft import CvDraft
from app.models.cv_draft_section import CvDraftSection
from app.models.chatbot import ChatbotConversation,ChatbotMessage
from app.models.cover_letter import CoverLetter  # ← ADD THIS LINE

from app.models.analysis import (
    ResumeAnalysis,
    AtsResult,
    ResumeSection,
    Recommendation,
    SectionTypeEnum
)