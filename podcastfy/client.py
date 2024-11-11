"""
Podcastfy CLI

This module provides a command-line interface for generating podcasts or transcripts
from URLs or existing transcript files. It orchestrates the content extraction,
generation, and text-to-speech conversion processes.
"""

import os
import uuid
import typer
import yaml
from podcastfy.content_parser.content_extractor import ContentExtractor
from podcastfy.content_generator import ContentGenerator
from podcastfy.text_to_speech import TextToSpeech
from podcastfy.utils.config import Config, load_config
from podcastfy.utils.config_conversation import load_conversation_config
from podcastfy.utils.logger import setup_logger
from typing import List, Optional, Dict, Any, Union
import copy
import threading
from .utils.decorators import check_cancelled


logger = setup_logger(__name__)

app = typer.Typer()

os.environ["LANGCHAIN_TRACING_V2"] = "false"

llm_api_key_dict = {
    "OPENAI_API_KEY": [
        "gpt-3.5-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4"
    ],
    "GEMINI_API_KEY": [
        "gemini-1.5-pro-latest"
    ]
}

def get_api_key_name(model_name: str) -> str:
    for api_key, models in llm_api_key_dict.items():
        if model_name in models:
            return api_key
    # raise ValueError(f"未找到模型 {model_name} 对应的API key")


@check_cancelled
def process_content(
    urls=None,
    transcript_file=None,
    tts_model="openai",
    generate_audio=True,
    config=None,
    conversation_config: Optional[Dict[str, Any]] = None,
    image_paths: Optional[List[str]] = None,
    is_local: bool = False,
    text: Optional[str] = None,
    job_id: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None
):
    """
    Process URLs, a transcript file, image paths, or raw text to generate a podcast or transcript.
    """
    try:
        if config is None:
            config = load_config()

        # Load default conversation config
        conv_config = load_conversation_config()

        # Update with provided config if any
        if conversation_config:
            conv_config.configure(conversation_config)

        # Get output directories from conversation config
        tts_config = conv_config.get("text_to_speech", {})
        output_directories = tts_config.get("output_directories", {})

        if transcript_file:
            logger.info(f"Using transcript file: {transcript_file}")
            with open(transcript_file, "r") as file:
                qa_content = file.read()
        else:
            content_generator = ContentGenerator(
                api_key=config.GEMINI_API_KEY, 
                conversation_config=conv_config.to_dict()
            )

            combined_content = ""

            if urls:
                logger.info(f"Processing {len(urls)} links")
                content_extractor = ContentExtractor()
                contents = [content_extractor.extract_content(link) for link in urls]
                combined_content += "\n\n".join(contents)

            if text:
                combined_content += f"\n\n{text}"

            # Generate Q&A content using output directory from conversation config
            ts_filename = "transcript_{}.txt".format(job_id if job_id else uuid.uuid4().hex)
            transcript_filepath = os.path.join(
                output_directories.get("transcripts", "data/transcripts"),
                ts_filename,
            )

            model_name = config.content_generator.llm_model
            api_key_label = get_api_key_name(model_name)
            
            qa_content = content_generator.generate_qa_content(
                combined_content,
                image_file_paths=image_paths or [],
                output_filepath=transcript_filepath,
                is_local=is_local,
                model_name=model_name,
                api_key_label=api_key_label,
                cancel_event=cancel_event
            )

        if generate_audio:
            api_key = None
            if tts_model != "edge":
                api_key = getattr(config, f"{tts_model.upper()}_API_KEY")

            text_to_speech = TextToSpeech(
                model=tts_model,
                api_key=api_key,
                conversation_config=conv_config.to_dict(),
            )

            audio_filename = "podcast_{}.mp3".format(job_id if job_id else uuid.uuid4().hex)
            audio_file = os.path.join(
                output_directories.get("audio", "data/audio"), 
                audio_filename
            )
            text_to_speech.convert_to_speech(
                qa_content, 
                audio_file, 
                job_id,
                cancel_event=cancel_event
            )
            logger.info(f"Podcast generated successfully using {tts_model} TTS model")
            return audio_file, transcript_filepath
        else:
            logger.info(f"Transcript generated successfully: {transcript_filepath}")
            return transcript_filepath

    except Exception as e:
        logger.error(f"An error occurred in the process_content function: {str(e)}")
        raise


@app.command()
def main(
    urls: list[str] = typer.Option(None, "--url", "-u", help="URLs to process"),
    file: typer.FileText = typer.Option(
        None, "--file", "-f", help="File containing URLs, one per line"
    ),
    transcript: typer.FileText = typer.Option(
        None, "--transcript", "-t", help="Path to a transcript file"
    ),
    tts_model: str = typer.Option(
        None,
        "--tts-model",
        "-tts",
        help="TTS model to use (openai, elevenlabs, edge, or gemini)",
    ),
    transcript_only: bool = typer.Option(
        False, "--transcript-only", help="Generate only a transcript without audio"
    ),
    conversation_config_path: str = typer.Option(
        None,
        "--conversation-config",
        "-cc",
        help="Path to custom conversation configuration YAML file",
    ),
    image_paths: List[str] = typer.Option(
        None, "--image", "-i", help="Paths to image files to process"
    ),
    is_local: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Use a local LLM instead of a remote one (http://localhost:8080)",
    ),
    text: str = typer.Option(
        None, "--text", "-txt", help="Raw text input to be processed"
    ),
    llm_model_name: str = typer.Option(
        None, "--llm-model-name", "-m", help="LLM model name for transcript generation"
    ),
    api_key_label: str = typer.Option(
        None, "--api-key-label", "-k", help="Environment variable name for LLMAPI key"
    ),
):
    """
    Generate a podcast or transcript from a list of URLs, a file containing URLs, a transcript file, image files, or raw text.
    """
    try:
        config = load_config()
        main_config = config.get("main", {})

        conversation_config = None
        # Load conversation config if provided
        if conversation_config_path:
            with open(conversation_config_path, "r") as f:
                conversation_config: Dict[str, Any] | None = yaml.safe_load(f)

        # Use default TTS model from conversation config if not specified
        if tts_model is None:
            tts_config = load_conversation_config().get("text_to_speech", {})
            tts_model = tts_config.get("default_tts_model", "openai")

        if transcript:
            if image_paths:
                logger.warning("Image paths are ignored when using a transcript file.")
            final_output = process_content(
                transcript_file=transcript.name,
                tts_model=tts_model,
                generate_audio=not transcript_only,
                conversation_config=conversation_config,
                config=config,
                is_local=is_local,
                text=text,
                model_name=llm_model_name,
                api_key_label=api_key_label,
            )
        else:
            urls_list = urls or []
            if file:
                urls_list.extend([line.strip() for line in file if line.strip()])

            if not urls_list and not image_paths and not text:
                raise typer.BadParameter(
                    "No input provided. Use --url to specify URLs, --file to specify a file containing URLs, --transcript for a transcript file, --image for image files, or --text for raw text input."
                )

            final_output = process_content(
                urls=urls_list,
                tts_model=tts_model,
                generate_audio=not transcript_only,
                config=config,
                conversation_config=conversation_config,
                image_paths=image_paths,
                is_local=is_local,
                text=text,
                model_name=llm_model_name,
                api_key_label=api_key_label,
            )

        if transcript_only:
            typer.echo(f"Transcript generated successfully: {final_output}")
        else:
            typer.echo(
                f"Podcast generated successfully using {tts_model} TTS model: {final_output}"
            )

    except Exception as e:
        typer.echo(f"An error occurred: {str(e)}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()


def generate_podcast(
    urls: Optional[List[str]] = None,
    url_file: Optional[str] = None,
    transcript_file: Optional[str] = None,
    tts_model: Optional[str] = None,
    transcript_only: bool = False,
    config: Optional[Union[Dict[str, Any], Config]] = None,
    conversation_config: Optional[Dict[str, Any]] = None,
    image_paths: Optional[List[str]] = None,
    is_local: bool = False,
    text: Optional[str] = None,
    job_id: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None
) -> Optional[str]:
    """
    Generate a podcast or transcript from a list of URLs, a file containing URLs, a transcript file, or image files.

    Args:
        urls (Optional[List[str]]): List of URLs to process.
        url_file (Optional[str]): Path to a file containing URLs, one per line.
        transcript_file (Optional[str]): Path to a transcript file.
        tts_model (Optional[str]): TTS model to use ('openai' [default], 'elevenlabs', 'edge', or 'gemini').
        transcript_only (bool): Generate only a transcript without audio. Defaults to False.
        config (Optional[Dict[str, Any]]): User-provided configuration dictionary.
        conversation_config (Optional[Dict[str, Any]]): User-provided conversation configuration dictionary.
        image_paths (Optional[List[str]]): List of image file paths to process.
        is_local (bool): Whether to use a local LLM. Defaults to False.
        text (Optional[str]): Raw text input to be processed.
        llm_model_name (Optional[str]): LLM model name for content generation.
        api_key_label (Optional[str]): Environment variable name for LLM API key.
        cancel_event: Optional event to check for cancellation

    Returns:
        Optional[str]: Path to the final podcast audio file, or None if only generating a transcript.
    """
    try:
        # 加载默认配置
        default_config = load_config()

        # 更新配置（如果提供了的话）
        if config:
            if isinstance(config, dict):
                # 如果是字典，直接使用 configure 方法
                default_config.configure(config)
            elif isinstance(config, Config):
                # 如果是 Config 对象，先转换为字典再配置
                default_config.configure(config.to_dict())
            else:
                raise ValueError(
                    "Config must be either a dictionary or a Config object"
                )

        # 加载对话配置
        if not conversation_config:
            conversation_config = load_conversation_config().to_dict()

        # 使用提供的 tts_model，否则使用配置中的默认值
        if tts_model is None:
            tts_config = conversation_config.get("text_to_speech", {})
            tts_model = tts_config.get("default_tts_model", "openai")

        if transcript_file:
            if image_paths:
                logger.warning("Image paths are ignored when using a transcript file.")
            return process_content(
                transcript_file=transcript_file,
                tts_model=tts_model,
                generate_audio=not transcript_only,
                config=default_config,
                conversation_config=conversation_config,
                is_local=is_local,
                text=text,
                job_id=job_id,
                cancel_event=cancel_event
            )
        else:
            urls_list = urls or []
            if url_file:
                with open(url_file, "r") as file:
                    urls_list.extend([line.strip() for line in file if line.strip()])

            if not urls_list and not image_paths and not text:
                raise ValueError(
                    "No input provided. Please provide either 'urls', 'url_file', 'transcript_file', 'image_paths', or 'text'."
                )

            return process_content(
                urls=urls_list,
                tts_model=tts_model,
                generate_audio=not transcript_only,
                config=default_config,
                conversation_config=conversation_config,
                image_paths=image_paths,
                is_local=is_local,
                text=text,
                job_id=job_id,
                cancel_event=cancel_event
            )

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise
