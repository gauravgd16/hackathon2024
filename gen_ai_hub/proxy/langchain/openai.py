from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI as ChatOpenAI_  # pylint: disable=import-error, no-name-in-module
from langchain_openai import OpenAIEmbeddings as OpenAIEmbeddings_  # pylint: disable=import-error, no-name-in-module
from langchain_openai import OpenAI as OpenAI_  # pylint: disable=import-error, no-name-in-module
from langchain.pydantic_v1 import Field, root_validator  # pylint: disable=import-error, no-name-in-module

from gen_ai_hub.proxy.core.base import BaseDeployment, BaseProxyClient

from .base import BaseAuth
from .init_models import catalog

try:
    from gen_ai_hub.proxy.native.openai import DEFAULT_API_VERSION
    from gen_ai_hub.proxy.native.openai import AsyncOpenAI as AsyncOpenAIClient
    from gen_ai_hub.proxy.native.openai import OpenAI as OpenAIClient
except ImportError as err:
    openai_err = err
else:
    openai_err = None


def get_client_parms(values):
    return {
        'api_key': values.get('openai_api_key', 'EMPTY') or 'EMPTY',
        'organization': values.get('openai_organization', 'EMPTY') or 'EMPTY',
        'proxy_client': values['proxy_client'],
        'timeout': values['request_timeout'],
        'max_retries': values['max_retries'],
        'default_headers': values['default_headers'] or {},
        'default_query': values['default_query'] or {},
        'http_client': values['http_client'],
        'api_version': values['openai_api_version'] or DEFAULT_API_VERSION
    }


class ProxyOpenAI(BaseAuth):

    @classmethod
    def validate_clients(cls, values: Dict) -> Dict:
        if openai_err is not None:
            raise ValueError('Could not import openai python package. '
                             'Please it install it with `pip install openai`.')
        values['proxy_client'] = cls._get_proxy_client(values)
        client_params = get_client_parms(values)
        if not values.get('client'):
            values['client'] = OpenAIClient(**client_params)
        if not values.get('async_client'):
            values['async_client'] = AsyncOpenAIClient(**client_params)
        deployment = values['proxy_client'].select_deployment(
            deployment_id=values.get('deployment_id', None),
            config_id=values.get('config_id', None),
            config_name=values.get('config_name', None),
            model_name=values.get('proxy_model_name', None),
        )
        BaseAuth._set_deployment_parameters(values, deployment)
        return values


class ChatOpenAI(ProxyOpenAI, ChatOpenAI_):
    model_name: Optional[str] = None
    openai_api_version: Optional[str] = Field(default=None, alias='api_version')

    def __new__(cls, **data: Any):  # type: ignore
        """
        Initialize the OpenAI object.
        :param data: Additional data to initialize the object
        :type data: Any
        :return: The initialized OpenAI object
        :rtype: OpenAIBase
        """
        data['model_name'] = data.get('model_name', '') or ''
        return ChatOpenAI_.__new__(cls)

    # pylint: disable=no-self-argument
    def __init__(self, *args, **kwargs):
        super().__init__(*args, openai_api_key='???', **kwargs)

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        values = cls.validate_clients(values)
        if values['n'] < 1:
            raise ValueError('n must be at least 1.')
        if values['n'] > 1 and values['streaming']:
            raise ValueError('n must be 1 when streaming.')
        if isinstance(values['client'], OpenAIClient):
            values['client']: OpenAIClient = values['client'].chat.completions
        if isinstance(values['async_client'], AsyncOpenAIClient):
            values['async_client']: AsyncOpenAIClient = values['async_client'].chat.completions
        values['model_name'] = values.get('model_name', None) or values.get('model', None) or values.get(
            'proxy_model_name', None)
        return values

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Returns the default parameters for the OpenAI object.

        :return: The default parameters
        :rtype: Dict[str, Any]
        """
        return {
            **super()._default_params, 'deployment_id': self.deployment_id,
            'config_id': self.config_id,
            'config_name': self.config_name,
            'model_name': self.proxy_model_name,
            'model': ''
        }


class OpenAI(ProxyOpenAI, OpenAI_):
    model_name: Optional[str] = None
    openai_api_version: Optional[str] = Field(default=None, alias='api_version')

    def __new__(cls, **data: Any):  # type: ignore
        """Initialize the OpenAI object."""
        data['model_name'] = data.get('model_name', '') or ''
        return OpenAI_.__new__(cls)

    # pylint: disable=no-self-argument
    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validates the environment.

        :param values: The input values
        :type values: Dict
        :return: The validated values
        :rtype: Dict
        """
        values = cls.validate_clients(values)
        if values['n'] < 1:
            raise ValueError('n must be at least 1.')
        if values['n'] > 1 and values['streaming']:
            raise ValueError('n must be 1 when streaming.')
        if isinstance(values['client'], OpenAIClient):
            values['client'] = values['client'].completions
        if isinstance(values['async_client'], AsyncOpenAIClient):
            values['async_client'] = values['async_client'].completions
        values['model_name'] = values.get('model_name', None) or values.get('model', None) or values.get(
            'proxy_model_name', None)
        return values

    def _get_completions(self, **kwargs) -> List[Dict[str, Any]]:
        return self.client(**kwargs)

    @property
    def _default_params(self) -> Dict[str, Any]:
        params = super()._default_params
        return {
            **params, 'deployment_id': self.deployment_id,
            'config_id': self.config_id,
            'config_name': self.config_name,
            'model_name': self.proxy_model_name,
            'model': ''
        }


class OpenAIEmbeddings(ProxyOpenAI, OpenAIEmbeddings_):
    model: Optional[str] = None
    tiktoken_model_name: Optional[str] = 'text-embedding-ada-002'
    chunk_size: int = 16
    openai_api_version: Optional[str] = Field(default=None, alias='api_version')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, openai_api_key='???', **kwargs)

    # pylint: disable=no-self-argument
    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validates the environment.

        :param values: The input values
        :type values: Dict
        :return: The validated values
        :rtype: Dict
        """
        values = cls.validate_clients(values)
        if isinstance(values['client'], OpenAIClient):
            values['client']: OpenAIClient = values['client'].embeddings
        if isinstance(values['async_client'], AsyncOpenAIClient):
            values['async_client']: AsyncOpenAIClient = values['async_client'].embeddings
        values['model'] = values.get('model', None) or values.get('model_name', None) or values.get(
            'proxy_model_name', None)
        return values

    @property
    def _invocation_params(self) -> Dict:
        params = super()._invocation_params
        return {
            **params,
            'deployment_id': self.deployment_id,
            'config_id': self.config_id,
            'config_name': self.config_name,
            'model': self.model,
        }


if not openai_err:
    @catalog.register(
        "gen-ai-hub",
        ChatOpenAI,
        "gpt-35-turbo",
        "gpt-35-turbo-0125",
        "gpt-4",
        "gpt-4o",
        "gpt-4-32k",
        "gpt-35-turbo-16k",
        "gpt-4-turbo",
        "meta--llama3-70b-instruct",
        "mistralai--mixtral-8x7b-instruct-v01",
        "tiiuae--falcon-40b-instruct",
    )
    def init_chat_model(proxy_client: BaseProxyClient,
                        deployment: BaseDeployment,
                        temperature: float = 0.0,
                        max_tokens: int = 256,
                        top_k: Optional[int] = None,
                        top_p: float = 1.):
        return ChatOpenAI(deployment_id=deployment.deployment_id,
                          proxy_client=proxy_client,
                          temperature=temperature,
                          max_tokens=max_tokens,
                          model_kwargs={'top_p': top_p})


    @catalog.register(
        "gen-ai-hub",
        OpenAIEmbeddings,
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002",
    )
    def init_embedding_model(proxy_client: BaseProxyClient, deployment: BaseDeployment):
        return OpenAIEmbeddings(deployment_id=deployment.deployment_id, proxy_client=proxy_client, chunk_size=16)
