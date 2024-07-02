from typing import Dict, Optional

from langchain.pydantic_v1 import Extra, root_validator
from langchain_aws import ChatBedrock as ChatBedrock_

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.native.amazon.clients import Session

MODEL_NAME_TO_MODEL_ID_MAP = {
    "amazon--titan-text-express": "amazon.titan-text-express-v1",
    "amazon--titan-text-lite": "amazon.titan-text-lite-v1",
    "anthropic--claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "anthropic--claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
}


class ChatBedrock(ChatBedrock_):
    def __init__(
        self,
        *args,
        model_id: str = "",
        deployment_id: str = "",
        model_name: str = "",
        config_id: str = "",
        config_name: str = "",
        proxy_client: Optional[BaseProxyClient] = None,
        **kwargs,
    ):
        """Extends the constructor of the base class with aicore specific parameters."""
        # correct model_id fitting to deployment is selected in validate_environment
        if model_id != "":
            raise ValueError(
                "Parameter not supported. Please use a variation of deployment_id, model_name, config_id and config_name to identify a deployment."
            )
        client_params = {
            "deployment_id": deployment_id,
            "model_name": model_name,
            "config_id": config_id,
            "config_name": config_name,
            "proxy_client": proxy_client,
        }
        kwargs["client_params"] = client_params
        # configures pydantic to allow additional attributes
        self.Config.extra = Extra.allow
        super().__init__(*args, model_id="", **kwargs)

    @classmethod
    def get_corresponding_model_id(cls, model_name):
        if model_name not in MODEL_NAME_TO_MODEL_ID_MAP:
            raise ValueError("Model specified is not supported.")
        return MODEL_NAME_TO_MODEL_ID_MAP[model_name]

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        client_params = values["client_params"]
        if not values.get("client"):
            values["client"] = Session().client(**client_params)
        values["model_id"] = ChatBedrock.get_corresponding_model_id(
            values["client"].aicore_deployment.model_name
        )
        return values
