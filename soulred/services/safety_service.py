"""Content safety and AI risk control service.

Provides:
- Multi-tier sensitive keyword filtering (politics, pornography, scam, violence)
- Text risk detection and masking
- Simulated multimodal image safety review
- Post note composite review flow (APPROVED, PENDING_REVIEW, REJECTED)
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class ContentSafetyService:
    """AI multimodal and text risk control service."""

    # Sensitive keyword dictionaries categorized by risk type
    SENSITIVE_PATTERNS = {
        "politics": [
            r"颠覆国家", r"分裂势力", r"暴恐分子", r"邪教组织", r"政治黑幕",
            r"非法集会", r"反动言论", r"机密泄露"
        ],
        "porn": [
            r"裸聊", r"兼职外围", r"色情直播", r"无码高清", r"一夜情约炮",
            r"买春", r"援交", r"催情药", r"迷药"
        ],
        "scam": [
            r"刷单兼职", r"日赚500", r"资金盘", r"私加微信", r"加微.*详谈",
            r"微信号[a-zA-Z0-9_-]{6,}", r"扫码领红包", r"赌博下注", r"套现",
            r"高额回报", r"代开发票", r"办理假证"
        ],
        "violence": [
            r"枪支买卖", r"炸药配方", r"自杀教程", r"雇凶", r"毒品交易",
            r"冰毒", r"大麻交易"
        ]
    }

    # Suspicious keywords that require manual review rather than direct rejection
    SUSPICIOUS_PATTERNS = [
        r"微信号", r"加v", r"微信私聊", r"兼职", r"高薪", r"代理加盟",
        r"内幕消息", r"免费赠送", r"扫码"
    ]

    @classmethod
    def check_text_safety(cls, text: Optional[str]) -> Dict[str, Any]:
        """Inspect text against sensitive dictionaries.

        Returns:
            dict containing:
                - is_safe (bool)
                - action ("APPROVED" | "PENDING_REVIEW" | "REJECTED")
                - violations (list[str])
                - filtered_text (str)
                - confidence (float)
        """
        if not text:
            return {
                "is_safe": True,
                "action": "APPROVED",
                "violations": [],
                "filtered_text": "",
                "confidence": 1.0,
            }

        violations: List[str] = []
        filtered_text = text

        # 1. Check severe violations (Immediate REJECT)
        for category, patterns in cls.SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, filtered_text, flags=re.IGNORECASE)
                if matches:
                    violations.append(f"{category}:{pattern}")
                    # Mask matched characters
                    filtered_text = re.sub(
                        pattern,
                        lambda m: "*" * len(m.group(0)),
                        filtered_text,
                        flags=re.IGNORECASE,
                    )

        if violations:
            return {
                "is_safe": False,
                "action": "REJECTED",
                "violations": violations,
                "filtered_text": filtered_text,
                "confidence": 0.95,
            }

        # 2. Check suspicious patterns (Escalate to PENDING_REVIEW)
        suspicious_hits: List[str] = []
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                suspicious_hits.append(pattern)

        if suspicious_hits:
            return {
                "is_safe": True,
                "action": "PENDING_REVIEW",
                "violations": suspicious_hits,
                "filtered_text": text,
                "confidence": 0.70,
            }

        return {
            "is_safe": True,
            "action": "APPROVED",
            "violations": [],
            "filtered_text": text,
            "confidence": 0.99,
        }

    @classmethod
    def check_image_safety(cls, image_url: Optional[str]) -> Dict[str, Any]:
        """Perform simulated multi-modal image risk control check.

        Evaluates image URL, file extensions, and risk keywords in asset naming.
        """
        if not image_url:
            return {
                "is_safe": True,
                "action": "APPROVED",
                "tags": [],
            }

        url_lower = image_url.lower()
        blocked_tags = ["porn", "nsfw", "gore", "weapon", "scam", "nude", "terror"]

        for tag in blocked_tags:
            if tag in url_lower:
                return {
                    "is_safe": False,
                    "action": "REJECTED",
                    "tags": [tag],
                }

        # Suspicious naming convention
        if any(w in url_lower for w in ["qr_code", "wechat_qr", "advert"]):
            return {
                "is_safe": True,
                "action": "PENDING_REVIEW",
                "tags": ["suspicious_advertisement"],
            }

        return {
            "is_safe": True,
            "action": "APPROVED",
            "tags": ["normal"],
        }

    @classmethod
    def review_post_content(
        cls,
        title: str,
        content: str,
        image_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Comprehensive review for a rich post including text and all images."""
        text_check = cls.check_text_safety(f"{title}\n{content}")
        if text_check["action"] == "REJECTED":
            return {
                "is_safe": False,
                "action": "REJECTED",
                "reason": "Text violates community guidelines",
                "violations": text_check["violations"],
                "filtered_content": text_check["filtered_text"],
            }

        image_urls = image_urls or []
        for img_url in image_urls:
            img_check = cls.check_image_safety(img_url)
            if img_check["action"] == "REJECTED":
                return {
                    "is_safe": False,
                    "action": "REJECTED",
                    "reason": f"Image violates safety policy: {img_check['tags']}",
                    "violations": img_check["tags"],
                    "filtered_content": content,
                }
            if img_check["action"] == "PENDING_REVIEW":
                text_check["action"] = "PENDING_REVIEW"

        return {
            "is_safe": True,
            "action": text_check["action"],
            "reason": "Passed safety checks" if text_check["action"] == "APPROVED" else "Escalated for review",
            "violations": text_check["violations"],
            "filtered_content": text_check["filtered_text"],
        }


# Module-level convenience functions matching architecture symbols
check_text_safety = ContentSafetyService.check_text_safety
check_image_safety = ContentSafetyService.check_image_safety
review_post_content = ContentSafetyService.review_post_content
