import json
import logging
from typing import Any, Dict, Optional
from app.db.models import Conversation
from app.llm.openai_compatible import OpenAICompatibleClient
from shared.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class UserProfileExtractor:
    def __init__(self, llm_client: Optional[OpenAICompatibleClient] = None):
        self.llm = llm_client or OpenAICompatibleClient()

    async def extract_and_merge_profile(
        self,
        conversation: Conversation,
        user_message: str,
        host_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Incrementally extract and update user profile data from context & messages.
        """
        current_profile = dict(conversation.profile or {})

        # Merge explicit host context if provided
        if host_context:
            if host_context.get("product") and host_context["product"] not in current_profile.get("services", []):
                services = current_profile.setdefault("services", [])
                services.append(host_context["product"])
            if host_context.get("plan"):
                current_profile["plan"] = host_context["plan"]
            if host_context.get("ui_lang"):
                current_profile["lang"] = host_context["ui_lang"]

        # Fast heuristic extraction for common Liara services/stacks
        msg_lower = user_message.lower()
        known_stacks = [
            "django", "flask", "fastapi", "python", "nodejs", "nextjs", "react", "vue",
            "laravel", "php", "dotnet", "golang", "docker", "postgres", "mysql", "mariadb",
            "mongodb", "redis", "elasticsearch"
        ]
        
        services = current_profile.setdefault("services", [])
        for stack in known_stacks:
            if stack in msg_lower and stack not in services:
                services.append(stack)

        conversation.profile = current_profile
        return current_profile
