
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import settings

logger = logging.getLogger(__name__)

class LLMConfig:
    _llm_instance = None  # cache singleton
    _initialized = False  # track if we already logged

    @staticmethod
    def get_llm():
        logger.info("LLMConfig.get_llm called")
        if LLMConfig._llm_instance is None:
            LLMConfig._llm_instance = ChatGoogleGenerativeAI(
                model=settings.MODEL_NAME,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=settings.TEMPERATURE
            )
            if not LLMConfig._initialized:
                logger.info("Gemini initialized successfully.")
                LLMConfig._initialized = True
        logger.info("LLMConfig.get_llm completed")
        return LLMConfig._llm_instance

    