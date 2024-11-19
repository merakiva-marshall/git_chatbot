import logging
import sys

def setup_logging():
    """Configure logging for the entire application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('git_chatbot.log')
        ]
    )

    # Create loggers for each component
    loggers = {
        'github': logging.getLogger('github'),
        'embeddings': logging.getLogger('embeddings'),
        'chat': logging.getLogger('chat'),
        'qdrant': logging.getLogger('qdrant')
    }

    return loggers