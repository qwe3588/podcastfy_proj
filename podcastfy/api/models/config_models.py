from pydantic import BaseModel, Field, EmailStr
from enum import Enum
from typing import Optional, List

from podcastfy.utils import load_config, load_conversation_config

config = load_config()
conv_config = load_conversation_config()

# 用户模型
class User(BaseModel):
    email: EmailStr
    password_hash: str
    is_active: bool = True
    is_admin: bool = False  # 添加管理员标志

    async def update_password(self, new_password_hash: str):
        """更新用户密码哈希值"""
        self.password_hash = new_password_hash

# Config配置模型
cont_gen_config = config.get('content_generator', {})
class ContentGeneratorConfig(BaseModel):
    llm_model: str = Field(default=cont_gen_config.get('llm_model'))
    gemini_model: str = Field(default=cont_gen_config.get('gemini_model'))
    max_output_tokens: int = Field(default=cont_gen_config.get('max_output_tokens'))
    prompt_template: str = Field(default=cont_gen_config.get('prompt_template'))
    prompt_commit: str = Field(default=cont_gen_config.get('prompt_commit'))

cont_ext_config = config.get('content_extractor', {})
class ContentExtractorConfig(BaseModel):
    youtube_url_patterns: List[str] = Field(default_factory=lambda: cont_ext_config.get('youtube_url_patterns', []))

class ConfigAll(BaseModel):
    content_generator: ContentGeneratorConfig
    content_extractor: ContentExtractorConfig

# TTS配置模型
class TTSVoices(BaseModel):
    question: str = ""
    answer: str = ""

class TTSModel(BaseModel):
    default_voices: TTSVoices = TTSVoices()
    model: Optional[str] = None

tts_config = conv_config.get('text_to_speech', {})

def get_tts_voices(provider_config: dict) -> TTSVoices:
    """Helper function to safely get TTS voices from config"""
    voices = provider_config.get('default_voices', {})
    if hasattr(voices, 'to_dict'):  # Handle NestedConfig objects
        voices = voices.to_dict()
    return TTSVoices(
        question=voices.get('question', ''),
        answer=voices.get('answer', '')
    )

def get_tts_model(provider_name: str) -> TTSModel:
    """Helper function to safely get TTS model config"""
    provider_config = tts_config.get(provider_name, {})
    if hasattr(provider_config, 'to_dict'):  # Handle NestedConfig objects
        provider_config = provider_config.to_dict()
    
    return TTSModel(
        default_voices=get_tts_voices(provider_config),
        model=provider_config.get('model')
    )

class TextToSpeechConfig(BaseModel):
    openai: TTSModel = Field(
        default=get_tts_model('openai'),
        description="OpenAI TTS配置"
    )
    gemini: TTSModel = Field(
        default=get_tts_model('gemini'),
        description="Gemini TTS配置"
    )
    elevenlabs: TTSModel = Field(
        default=get_tts_model('elevenlabs'),
        description="ElevenLabs TTS配置"
    )
    edge: TTSModel = Field(
        default=get_tts_model('edge'),
        description="Edge TTS配置"
    )

class ConfigConversation(BaseModel):
    word_count: int = Field(default=conv_config.get('word_count'))
    conversation_style: List[str] = Field(default_factory=lambda: conv_config.get('conversation_style', []))
    roles_person1: str = Field(default=conv_config.get('roles_person1'))
    roles_person2: str = Field(default=conv_config.get('roles_person2'))
    dialogue_structure: List[str] = Field(default_factory=lambda: conv_config.get('dialogue_structure', []))
    podcast_name: str = Field(default=conv_config.get('podcast_name'))
    podcast_tagline: str = Field(default=conv_config.get('podcast_tagline'))
    output_language: str = Field(default=conv_config.get('output_language'))
    engagement_techniques: List[str] = Field(default_factory=lambda: conv_config.get('engagement_techniques', []))
    creativity: int = Field(default=conv_config.get('creativity'))
    user_instructions: str = Field(default=conv_config.get('user_instructions'))
    text_to_speech: TextToSpeechConfig

class TTSModelChoice(str, Enum):
    # 自动从TextToSpeechConfig生成枚举值
    locals().update({
        k.upper(): k for k in TextToSpeechConfig.model_fields.keys()
    })