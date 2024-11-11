"""Google Cloud Text-to-Speech provider implementation."""

from google.cloud import texttospeech_v1beta1
from typing import List, Optional
from ..base import TTSProvider
import re
import logging
import threading
from podcastfy.utils.decorators import check_cancelled

logger = logging.getLogger(__name__)

class GoogleMultispeakerTTS(TTSProvider):
    """Google Cloud Text-to-Speech provider with multi-speaker support."""
    
    def __init__(self, api_key: str = None, model: str = "en-US-Studio-MultiSpeaker"):
        """
        Initialize Google Cloud TTS provider.
        
        Args:
            api_key (str): Google Cloud API key
        """
        self.model = model
        try:
            self.client = texttospeech_v1beta1.TextToSpeechClient(
                client_options={'api_key': api_key} if api_key else None
            )
            self.ending_message = ""  # Required for split_qa method
        except Exception as e:
            logger.error(f"Failed to initialize Google TTS client: {str(e)}")
            raise
            
    @check_cancelled
    def generate_audio(
        self, 
        text: str, 
        voice: str = "R", 
        model: str = "en-US-Studio-MultiSpeaker", 
        voice2: str = "S", 
        ending_message: str = "",
        cancel_event: Optional[threading.Event] = None
    ) -> bytes:
        """
        Generate audio using Google Cloud TTS API with multi-speaker support.
        
        Args:
            text: Text to convert to speech (in Person1/Person2 format)
            voice: Voice ID for the current segment (R or S)
            model: Model name (must be 'en-US-Studio-MultiSpeaker')
            voice2: Second voice ID
            ending_message: Optional ending message
            cancel_event: Optional event to check for cancellation
            
        Returns:
            bytes: Audio data
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If audio generation fails
            Exception: If operation is cancelled
        """
        print(f"Generating audio with voice: {voice}, voice2: {voice2}, model: {model}")
        self.validate_parameters(text, voice, model, voice2, cancel_event)
          
        try:
            # Create multi-speaker markup
            multi_speaker_markup = texttospeech_v1beta1.MultiSpeakerMarkup()
            
            # Get Q&A pairs using the base class method
            qa_pairs = self.split_qa(
                text, 
                ending_message, 
                self.get_supported_tags(),
                cancel_event=cancel_event
            )
            
            # Add turns for each Q&A pair
            for idx, (question, answer) in enumerate(qa_pairs, 1):
                print(f"question: {question}, answer: {answer}")
                
                # Add question turn
                q_turn = texttospeech_v1beta1.MultiSpeakerMarkup.Turn()
                q_turn.text = question.strip()
                q_turn.speaker = voice  # First speaker
                multi_speaker_markup.turns.append(q_turn)
                
                # Add answer turn
                a_turn = texttospeech_v1beta1.MultiSpeakerMarkup.Turn()
                a_turn.text = answer.strip()
                a_turn.speaker = voice2  # Second speaker
                multi_speaker_markup.turns.append(a_turn)
            
            # Create synthesis input with multi-speaker markup
            synthesis_input = texttospeech_v1beta1.SynthesisInput(
                multi_speaker_markup=multi_speaker_markup
            )
            
            # Set voice parameters - must use the multi-speaker model
            voice_params = texttospeech_v1beta1.VoiceSelectionParams(
                language_code="en-US",
                name=model  # Use the model attribute
            )
            
            # Set audio config
            audio_config = texttospeech_v1beta1.AudioConfig(
                audio_encoding=texttospeech_v1beta1.AudioEncoding.MP3
            )
            
            # Generate speech
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Failed to generate audio: {str(e)}")
            raise RuntimeError(f"Failed to generate audio: {str(e)}") from e
    
    def get_supported_tags(self) -> List[str]:
        """Get supported SSML tags."""
        # Add any Google-specific SSML tags to the common ones
        return self.COMMON_SSML_TAGS
        
    def validate_parameters(self, text: str, voice: str, model: str, voice2: str, cancel_event: Optional[threading.Event]) -> None:
        """
        Validate input parameters before generating audio.
        
        Args:
            text: Text to convert
            voice: Voice ID/name
            model: Model ID/name
            voice2: Optional second voice
            cancel_event: Optional cancellation event
            
        Raises:
            ValueError: If any parameter is invalid
            Exception: If operation is cancelled
        """
        if cancel_event and cancel_event.is_set():
            raise Exception("Operation cancelled by user")
            
        if not text:
            raise ValueError("Text cannot be empty")
        if not voice:
            raise ValueError("Voice must be specified")
        if not model:
            raise ValueError("Model must be specified")
        
        # Additional validation for multi-speaker model
        if model != "en-US-Studio-MultiSpeaker":
            raise ValueError(
                "Google Multi-speaker TTS requires model='en-US-Studio-MultiSpeaker'"
            )