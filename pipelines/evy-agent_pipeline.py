import os
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
import boto3
import json
import uuid

class Pipeline:
    class Valves(BaseModel):
        AWS_ACCESS_KEY_ID: str = ""
        AWS_SECRET_ACCESS_KEY: str = ""
        AWS_REGION: str = ""
        LAMBDA_FUNCTION_NAME: str = ""

    def __init__(self):
        self.type = "manifold"
        self.name = "EV Agent: "
        self.valves = self.Valves(
            **{
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
                "LAMBDA_FUNCTION_NAME": os.getenv("LAMBDA_FUNCTION_NAME", "evy-agent"),
            }
        )
        self.lambda_client = None
        self.session_id = str(uuid.uuid4())  # Generate a unique session ID

    async def on_startup(self):
        self.lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=self.valves.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.valves.AWS_SECRET_ACCESS_KEY,
            region_name=self.valves.AWS_REGION
        )

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        if model_id != "evy-agent":
            raise ValueError(f"Unknown model ID: {model_id}")

        try:
            lambda_payload = {
                "body": json.dumps({
                    "query": user_message,
                    "session_id": self.session_id
                })
            }
            
            response = self.lambda_client.invoke(
                FunctionName=self.valves.LAMBDA_FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(lambda_payload)
            )
            
            result = json.loads(response['Payload'].read().decode())
            body = json.loads(result['body'])
            
            answer = body['answer']
            metadata = body['metadata']
            
            # Format the response with metadata
            formatted_response = f"{answer}\n\nSources:\n"
            for item in metadata:
                formatted_response += f"- Location: {item['location']}, Page: {item['pageNumber']}, Score: {item['score']}\n"
            
            if body.get("stream", False):
                def generate():
                    for chunk in formatted_response.split('\n'):
                        yield chunk + '\n'
                return generate()
            else:
                return formatted_response
        except Exception as e:
            return f"Error: {str(e)}"

    def pipelines(self) -> List[dict]:
        # Return a list of available models for this pipeline
        return [{"id": "evy-agent", "name": "Evy Agent"}]

    async def on_shutdown(self):
        # Implement any cleanup logic here if needed
        pass

    async def on_valves_updated(self):
        # Reinitialize the Lambda client with updated credentials if necessary
        self.lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=self.valves.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.valves.AWS_SECRET_ACCESS_KEY,
            region_name=self.valves.AWS_REGION
        )