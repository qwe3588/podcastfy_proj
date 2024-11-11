"""Abstract base class for Text-to-Speech providers."""

from abc import ABC, abstractmethod
from typing import List, ClassVar, Tuple, Optional
import re
import threading
from ..utils.decorators import check_cancelled

class TTSProvider(ABC):
    """Abstract base class that defines the interface for TTS providers."""
    
    # Common SSML tags supported by most providers
    COMMON_SSML_TAGS: ClassVar[List[str]] = [
        'lang', 'p', 'phoneme', 's', 'sub'
    ]
    
    @abstractmethod
    @check_cancelled
    def generate_audio(
        self, 
        text: str, 
        voice: str, 
        model: str, 
        voice2: str = None,
        cancel_event: Optional[threading.Event] = None
    ) -> bytes:
        """
        Generate audio from text using the provider's API.
        
        Args:
            text: Text to convert to speech
            voice: Voice ID/name to use
            model: Model ID/name to use
            voice2: Optional second voice for multi-speaker models
            cancel_event: Optional event to check for cancellation
            
        Returns:
            Audio data as bytes
            
        Raises:
            ValueError: If invalid parameters are provided
            RuntimeError: If audio generation fails
            Exception: If operation is cancelled
        """
        pass

    @check_cancelled
    def get_supported_tags(self) -> List[str]:
        """
        Get set of SSML tags supported by this provider.
        
        Returns:
            Set of supported SSML tag names
        """
        return self.COMMON_SSML_TAGS.copy()
    
    @check_cancelled
    def validate_parameters(
        self, 
        text: str, 
        voice: str, 
        model: str, 
        voice2: str = None,
        cancel_event: Optional[threading.Event] = None
    ) -> None:
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
        if not text:
            raise ValueError("Text cannot be empty")
        if not voice:
            raise ValueError("Voice must be specified")
        if not model:
            raise ValueError("Model must be specified")
        
    @check_cancelled
    def split_qa(
        self, 
        input_text: str, 
        ending_message: str, 
        supported_tags: List[str] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> List[Tuple[str, str]]:
        """
        Split the input text into question-answer pairs.

        Args:
            input_text: The input text containing Person1 and Person2 dialogues
            ending_message: The ending message to add
            supported_tags: Optional list of supported tags
            cancel_event: Optional event to check for cancellation

        Returns:
            List of (Person1, Person2) dialogue tuples
            
        Raises:
            Exception: If operation is cancelled
        """
        input_text = self.clean_tss_markup(input_text, supported_tags=supported_tags)
        input_text += f"<Person2>{ending_message}</Person2>"

        pattern = r"<Person1>(.*?)</Person1>\s*<Person2>(.*?)</Person2>"
        matches = re.findall(pattern, input_text, re.DOTALL)

        return [
            (" ".join(person1.split()).strip(), " ".join(person2.split()).strip())
            for person1, person2 in matches
        ]
    

    def clean_tss_markup(self, input_text: str, additional_tags: List[str] = ["Person1", "Person2"], supported_tags: List[str] = None) -> str:
        """
        Remove unsupported TSS markup tags from the input text while preserving supported SSML tags.

        Args:
            input_text (str): The input text containing TSS markup tags.
            additional_tags (List[str]): Optional list of additional tags to preserve. Defaults to ["Person1", "Person2"].
            supported_tags (List[str]): Optional list of supported tags. If None, use COMMON_SSML_TAGS.
        Returns:
            str: Cleaned text with unsupported TSS markup tags removed.
        """
        if supported_tags is None:
            supported_tags = self.COMMON_SSML_TAGS.copy()

        # Append additional tags to the supported tags list
        supported_tags.extend(additional_tags)

        # Create a pattern that matches any tag not in the supported list
        pattern = r'</?(?!(?:' + '|'.join(supported_tags) + r')\b)[^>]+>'

        # Remove unsupported tags
        cleaned_text = re.sub(pattern, '', input_text)

        # Remove any leftover empty lines
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)

        # Ensure closing tags for additional tags are preserved
        for tag in additional_tags:
            cleaned_text = re.sub(f'<{tag}>(.*?)(?=<(?:{"|".join(additional_tags)})>|$)', 
                                f'<{tag}>\\1</{tag}>', 
                                cleaned_text, 
                                flags=re.DOTALL)

        return cleaned_text.strip()