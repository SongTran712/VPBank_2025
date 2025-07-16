from strands import Agent
from strands import tool
import boto3
import logging 
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from dynamodb_json import json_util
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager,SummarizingConversationManager


dynamo_db_conversation_history_table = "chathistory"
session_id = "sess_1234"
truncate_tool_results = True
# model_id = "us.anthropic.claude-3-5-sonnet-20250219-v1:0"
model_temperature = 0.3
system_prompt = "You are an helpful assistant"
conversation_manager_window_size = 10
canned_bedrock_guardrail_responses = ["Sorry I can only answer agent related questions"]
user_query = "Whats the weather like in HCM city?"

import uuid
from dotenv import load_dotenv
import os
load_dotenv()
access = os.getenv('accesskey')
secret = os.getenv('serectkey')
session_id = '240101'

class DynamoDBConversationManager:
    """Manages conversation history in DynamoDB."""

    def __init__(self, table_name: str = dynamo_db_conversation_history_table, truncate_tools: bool = False):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.table_name = table_name
            self.truncate_tools = truncate_tools
            self.dynamodb = boto3.resource("dynamodb", region_name='ap-southeast-1',aws_access_key_id=access, aws_secret_access_key=secret)
            client = boto3.client(
        "dynamodb",
        region_name='ap-southeast-1',
        aws_access_key_id=access,
        aws_secret_access_key=secret
    )
            self.response = client.list_tables()
            print("Available tables:", self.response["TableNames"])
            self.table = self.dynamodb.Table(table_name)
            print(self.table)
            # self.response = self.dynamodb.list_tables()
            # print("Available tables:", self.response["TableNames"])
    def add_user_message(self, session_id: str, user_query: str) -> None:
        """Add a user message to DynamoDB with current timestamp."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print(user_query)
            enriched_message = {
                "content": [{'text':user_query}],
                "role":"user",
                # "duration_ms": None
            }
            item = {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                'type':'Q',
                "message": enriched_message,
            }
            try:
                self.table.put_item(Item=item)
            except Exception as e:
                print("Error: ",e)

    def add_agent_message(self, session_id: str, agent_message: Dict[str, Any]) -> None:
        """Add an agent message to DynamoDB with type 'A' and optional metadata."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            content = agent_message.get("content", [])
            tool_use = content[0].get("toolUse", {}) if content else {}
            tool_name = tool_use.get("name")
            response_type = "tool_result" if tool_name else "text"

            enriched_message = {
                "content": content,
                # "response_type": response_type,
                "role":"assistant",
                # "duration_ms": agent_message.get("duration_ms")
            }

            item = {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "A",
                "message": enriched_message
            }

            self.table.put_item(Item=item)


    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all valid messages for a session, sorted by timestamp and filtered to match Claude format."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                response = self.table.query(
                    KeyConditionExpression="session_id = :sid",
                    ExpressionAttributeValues={":sid": session_id}
                )

                items = response.get("Items", [])
                sorted_items = sorted(items, key=lambda x: x["timestamp"])
                messages = []

                i = 0
                while i < len(sorted_items):
                    item = sorted_items[i]
                    msg = item["message"]

                    # 🛠 fix: if content is a dict, wrap in a list
                    if isinstance(msg.get("content"), dict):
                        msg["content"] = [msg["content"]]

                    role = msg.get("role")

                    if role == "assistant" and "toolUse" in msg["content"][0]:
                        # Ensure next message is a `tool`
                        if i + 1 < len(sorted_items):
                            next_msg = sorted_items[i + 1]["message"]
                            if next_msg.get("role") == "tool":
                                messages.append(msg)         # toolUse
                                messages.append(next_msg)    # toolResult
                                i += 2
                                continue
                            else:
                                print("⚠️ Skipping incomplete toolUse without toolResult")
                                i += 1
                                continue
                        else:
                            print("⚠️ Skipping dangling toolUse at end")
                            i += 1
                            continue
                    elif role == "tool":
                        print("⚠️ Skipping orphan toolResult without toolUse")
                        i += 1
                        continue
                    else:
                        messages.append(msg)
                        i += 1

                return messages

            except Exception as e:
                logging.error(f"Error retrieving messages from DynamoDB: {str(e)}")
                raise



    def clear_history(self, session_id: str) -> int:
        """Clear all conversation history for a session. Returns count of deleted items."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                # First, get all items for the session
                print(session_id)
                # response = self.table.query(
                #     KeyConditionExpression="session_id = :sid", ExpressionAttributeValues={":sid": session_id}
                # )
                response = self.table.query(
                    KeyConditionExpression="session_id = :sid",

                    ExpressionAttributeValues={":sid": f"{session_id}"}
                                    )
                items = response.get("Items", [])
                deleted_count = 0

                # Delete each item (DynamoDB doesn't support batch delete by query)
                for item in items:
                    self.table.delete_item(Key={"session_id": item["session_id"], "timestamp": item["timestamp"]})
                    deleted_count += 1

                logging.info(f"Cleared {deleted_count} messages for session {session_id}")
                return deleted_count

            except Exception as e:
                logging.error(f"Error clearing history for session {session_id}: {str(e)}")
                raise

    def redact_previous_guardrail_trigger_messages(self, messages):
        """
        Loops through the messages list, and if a message's content[0]['text'] is a canned bedrock guardrail ressponse,
        deletes that message and the previous message if the previous message's role is 'user'.
        """
        i = 0
        while i < len(messages):
            msg = messages[i]
            if (
                isinstance(msg, dict)
                and 'content' in msg
                and isinstance(msg['content'], list)
                and len(msg['content']) > 0
                and isinstance(msg['content'][0], dict)
                and msg['content'][0].get('text') in canned_bedrock_guardrail_responses):
                # Check if previous message exists and is from user
                if i > 0 and messages[i-1].get('role') == 'user':
                    # Remove both previous and current message
                    del messages[i-1:i+1]
                    i -= 1  # Move back one index since we removed two
                else:
                    # Remove only the current message
                    del messages[i]
                # Don't increment i, as the list has shifted
            else:
                i += 1
        return messages

    



import time

def wrapper_callback_handler(session_id, conversation_manager):
    start_time = None
    response_saved = False

    def custom_callback_handler(**kwargs):
        nonlocal start_time, response_saved

        # Start of generation or tool-use
        if "data" in kwargs or "current_tool_use" in kwargs:
            if start_time is None:
                start_time = time.time()
                response_saved = False  # reset when new response starts

            if "data" in kwargs:
                print(f"MODEL OUTPUT: {kwargs['data']}")
            elif "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
                print(f"\nUSING TOOL: {kwargs['current_tool_use']['name']}")

        # Final message received
        elif "message" in kwargs and not response_saved:
            agent_message = kwargs["message"]
            content = agent_message.get("content", [])
            tool_use = content[0].get("toolUse", {}) if content else {}
            tool_name = tool_use.get("name") if tool_use else None
            response_type = "tool_result" if tool_name else "text"

            enriched_message = {
                "role": "assistant",
                "content": content,
                "response_type": response_type,
                "tool_name": tool_name,
                "truncated": False,
                "usage": kwargs.get("usage", {})
            }

            # Save final response
            conversation_manager.add_agent_message(session_id, enriched_message)

            # Reset for next round
            response_saved = True
            start_time = None

    return custom_callback_handler

if __name__=='__main__':
    """ 
    This is a dedicated example
    """
    dynamo_db_conversation_manager = DynamoDBConversationManager(truncate_tools=truncate_tool_results)
    messages = dynamo_db_conversation_manager.get_messages(session_id)
    session = boto3.Session(
    aws_access_key_id= access,
    aws_secret_access_key= secret,
    region_name= 'ap-southeast-1'
    
    )
    boto_config = BotocoreConfig(
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60
    )
    # Create a Bedrock model with the custom session
    bedrock_model = BedrockModel(
        model_id = "arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
        boto_session=session,
        temperature=0.3,
        top_p=0.8,
        stop_sequences=["###", "END"],
        # boto_client_config=boto_config,
    )
    strands_conversation_manager = SlidingWindowConversationManager(window_size=conversation_manager_window_size)
    @tool
    def weather_forecast(city: str, days: int = 3) -> str:
        """Get weather forecast for a Ho Chi Minh city.

        Args:
            city: The name of the city
            days: Number of days for the forecast
        """
        return f"Weather forecast for {city} for the next {days} days..."
    callback_handler = wrapper_callback_handler(session_id, dynamo_db_conversation_manager)

# Instantiate and run the agent
    agent = Agent(
        tools=[weather_forecast],
        system_prompt=system_prompt,
        model=bedrock_model,
        messages=messages[: len(messages) - 1],
        conversation_manager=strands_conversation_manager,
        callback_handler=callback_handler)
    dynamo_db_conversation_manager.add_user_message(session_id, user_query)
    messages = dynamo_db_conversation_manager.get_messages(session_id)
    agent(user_query)