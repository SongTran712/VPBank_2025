import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from dotenv import load_dotenv
import os

import chartool


os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")



class OutputAgent:
    def __init__(self, bucket = 'testworkflow123', prefix = 'content/'):
        self.bucket = bucket
        self.prefix = prefix
        self.system_prompt = """

        """
        
        