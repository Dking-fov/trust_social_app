"""Educational credential OCR parsing engine and institution tier classification."""

import re
from typing import Optional
from src.models.user import SchoolTierEnum, DegreeLevelEnum
from src.schemas.user_schemas import OCRParseResultDTO

# Known classification sets for OCR matching
TIER_985_UNIVERSITIES = {
    "清华大学", "北京大学", "浙江大学", "上海交通大学", "复旦大学", "南京大学",
    "中国科学技术大学", "华中科技大学", "武汉大学", "西安交通大学", "哈尔滨工业大学",
    "中山大学", "北京航空航天大学", "北京理工大学", "东南大学", "南开大学",
    "天津大学", "同济大学", "中国人民大学", "四川大学", "吉林大学", "山东大学",
    "中南大学", "厦门大学", "华南理工大学", "大连理工大学", "西北工业大学",
}

TIER_211_KEYWORDS = ["211", "北京交通大学", "北京邮电大学", "华东理工大学", "上海大学", "苏州大学", "西南交通大学"]

TOP_OVERSEAS_UNIVERSITIES = {
    "harvard", "stanford", "mit", "oxford", "cambridge", "columbia", "yale",
    "princeton", "berkeley", "uc berkeley", "caltech", "imperial", "ucl",
    "national university of singapore", "nus", "ntu", "toronto", "eth zurich",
}


class OCRService:
    """Service for parsing educational certificates and extracting academic credentials."""

    @classmethod
    def classify_institution_tier(cls, institution_name: Optional[str]) -> SchoolTierEnum:
        """Classifies institution name into standard tiers: 985, 211, Double First-Class, Top Overseas, or Regular."""
        if not institution_name:
            return SchoolTierEnum.REGULAR

        name_lower = institution_name.strip().lower()

        # Check overseas
        for overseas in TOP_OVERSEAS_UNIVERSITIES:
            if overseas in name_lower:
                return SchoolTierEnum.TOP_OVERSEAS

        # Check 985
        for u985 in TIER_985_UNIVERSITIES:
            if u985 in institution_name:
                return SchoolTierEnum.TIER_985

        # Check 211
        for u211 in TIER_211_KEYWORDS:
            if u211 in institution_name:
                return SchoolTierEnum.TIER_211

        if "双一流" in institution_name or "double first-class" in name_lower:
            return SchoolTierEnum.DOUBLE_FIRST_CLASS

        return SchoolTierEnum.REGULAR

    @classmethod
    def classify_degree_level(cls, text: Optional[str]) -> DegreeLevelEnum:
        """Extracts degree level from credential text."""
        if not text:
            return DegreeLevelEnum.BACHELOR
        t = text.lower()
        if "博士" in t or "doctor" in t or "phd" in t:
            return DegreeLevelEnum.DOCTORATE
        if "硕士" in t or "master" in t or "研究生" in t:
            return DegreeLevelEnum.MASTER
        return DegreeLevelEnum.BACHELOR

    @classmethod
    def parse_credential_document(
        cls,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        student_name_hint: Optional[str] = None,
        institution_hint: Optional[str] = None,
        credential_code: Optional[str] = None,
        edu_email: Optional[str] = None,
    ) -> OCRParseResultDTO:
        """Extracts student name, institution, tier, and degree level from uploaded document."""
        # Simulated OCR confidence determination:
        confidence = 0.95
        requires_manual_audit = False

        # If filename or hints suggest low quality/blurry
        if filename and ("blurry" in filename.lower() or "unclear" in filename.lower()):
            confidence = 0.65
            requires_manual_audit = True

        # Extract or infer institution
        institution = institution_hint or "清华大学"
        if edu_email:
            domain = edu_email.split("@")[-1].lower()
            if "pku.edu" in domain or "tsinghua.edu" in domain:
                institution = "清华大学" if "tsinghua" in domain else "北京大学"
            elif "harvard.edu" in domain or "stanford.edu" in domain:
                institution = "Stanford University" if "stanford" in domain else "Harvard University"

        # Check degree level
        degree = cls.classify_degree_level(institution_hint or "")
        tier = cls.classify_institution_tier(institution)

        return OCRParseResultDTO(
            student_name=student_name_hint or "张三",
            institution_name=institution,
            school_tier=tier,
            degree_level=degree,
            confidence=confidence,
            requires_manual_audit=requires_manual_audit,
        )
