from langchain_google_genai import ChatGoogleGenerativeAI as ChatGoogleGenerativeAI_

from typing import Any, Dict, Optional

from gen_ai_hub.proxy.core.base import BaseDeployment, BaseProxyClient
from gen_ai_hub.proxy.langchain.base import BaseAuth
from gen_ai_hub.proxy.langchain.init_models import catalog
from langchain.pydantic_v1 import root_validator  # pylint: disable=import-error, no-name-in-module

from gen_ai_hub.proxy.native.google.clients import GenerativeModel as GenerativeModelClient


def get_client_params(values):
    return {
        'proxy_client': values['proxy_client'],
        'model_name': values['model']
    }


class ProxyGoogle(BaseAuth):

    @classmethod
    def validate_clients(cls, values: Dict) -> Dict:
        values['proxy_client'] = cls._get_proxy_client(values)
        client_params = get_client_params(values)
        if not values.get('client'):
            values['client'] = GenerativeModelClient(**client_params)
        deployment = values['proxy_client'].select_deployment(
            deployment_id=values.get('deployment_id', None),
            config_id=values.get('config_id', None),
            config_name=values.get('config_name', None),
            model_name=values.get('proxy_model_name', None),
        )
        BaseAuth._set_deployment_parameters(values, deployment)
        return values


class ChatGoogleGenerativeAI(ProxyGoogle, ChatGoogleGenerativeAI_):

    def __init__(self, **kwargs):
        super().__init__(model=kwargs.get('proxy_model_name', 'gemini-1.0-pro'), **kwargs)

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        values = cls.validate_clients(values)
        values["client"]: GenerativeModelClient = values['client']
        return values


@catalog.register('gen-ai-hub', ChatGoogleGenerativeAI, 'gemini-1.0-pro')
def init_chat_model(proxy_client: BaseProxyClient,
                    deployment: BaseDeployment,
                    temperature: float = 0.0,
                    max_tokens: int = 256,
                    top_k: Optional[int] = None,
                    top_p: float = 1.):
    return ChatGoogleGenerativeAI(deployment_id=deployment.deployment_id,
                                  proxy_client=proxy_client,
                                  temperature=temperature,
                                  max_tokens=max_tokens,
                                  model_kwargs={'top_p': top_p})
