from __future__ import annotations
import re
from contextvars import ContextVar

from enum import Enum
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from contextlib import contextmanager
from typing import Any, ClassVar, Dict, Final, List, Optional, Tuple, Type, Union

from ai_api_client_sdk.models.status import Status
from ai_core_sdk.ai_core_v2_client import AICoreV2Client
from pydantic import BaseModel, PrivateAttr, model_validator, Field, ConfigDict, ValidationError

from gen_ai_hub.proxy.core.base import BaseDeployment, BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import proxy_clients
from gen_ai_hub.proxy.core.utils import PredictionURLs, lru_cache_extended, OMIT, warn_once

_temporary_headers_addition = ContextVar('temporary_headers_addition', default={})


@contextmanager
def temporary_headers_addition(headers: Dict[str, str]):
    previous_temporary_headers = _temporary_headers_addition.set(headers)

    try:
        yield
    finally:
        _temporary_headers_addition.reset(previous_temporary_headers)


class Deployment(BaseDeployment):
    url: str
    config_id: str
    config_name: str
    deployment_id: str
    model_name: str
    created_at: datetime
    additonal_parameters: Dict[str, str] = Field(default_factory=dict)
    custom_prediction_suffix: Optional[str] = None

    # class variables
    prediction_urls: ClassVar[PredictionURLs] = PredictionURLs()

    def __getattr__(self, name):
        try:
            super().__getattr__(name)
        except AttributeError as err:
            self.additonal_parameters: Dict[str, str]
            value = self.additonal_parameters.get(name, None)
            if value:
                return value
            raise err

    # abstractmethod implementations
    def additional_request_body_kwargs(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def get_model_identification_kwargs(cls) -> Tuple[str]:
        return ('model_name', 'config_id', 'config_name', 'deployment_id')

    @property
    def prediction_url(self):
        return self.prediction_urls(self.model_name, self.url, self.custom_prediction_suffix)


# 'OMIT' is a special value that will lead to deployment.prediction_url being None. This is useful to indicate to use
# the .url attribute of the deployment instead and let the llm client handle the suffix
AMAZON_CHAT_COMPLETION = OMIT
OPEN_AI_CHAT_COMPLETION = OMIT
OPEN_AI_EMBEDDING = OMIT
OPENSOURCE_COMPLETION = OMIT
GOOGLE_VERTEX = OMIT

Deployment.prediction_urls.register(
    {
        "amazon--titan-text-express": AMAZON_CHAT_COMPLETION,
        "amazon--titan-text-lite": AMAZON_CHAT_COMPLETION,
        "anthropic--claude-3-haiku": AMAZON_CHAT_COMPLETION,
        "anthropic--claude-3-sonnet": AMAZON_CHAT_COMPLETION,
        "gpt-35-turbo": OPEN_AI_CHAT_COMPLETION,
        "gpt-35-turbo-16k": OPEN_AI_CHAT_COMPLETION,
        "gpt-35-turbo-0125": OPEN_AI_CHAT_COMPLETION,
        "gpt-4": OPEN_AI_CHAT_COMPLETION,
        "gpt-4o": OPEN_AI_CHAT_COMPLETION,
        "gpt-4-32k": OPEN_AI_CHAT_COMPLETION,
        "mistralai--mixtral-8x7b-instruct-v01": OPEN_AI_CHAT_COMPLETION,
        "text-embedding-3-small": OPEN_AI_EMBEDDING,
        "text-embedding-3-large": OPEN_AI_EMBEDDING,
        "text-embedding-ada-002": OPEN_AI_EMBEDDING,
        "tiiuae--falcon-40b-instruct": OPENSOURCE_COMPLETION,
        "gemini-1.0-pro": GOOGLE_VERTEX,
        "meta--llama3-70b-instruct": OPEN_AI_CHAT_COMPLETION
    }
)


class FoundationalModelScenario(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=()
    )

    scenario_id: str
    config_names: Optional[Union[List[str], str]] = None
    model_name_parameter: str = 'model_name'
    prediction_url_suffix: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def adjust(cls, data: Any) -> Any:
        if isinstance(data, dict):
            config_names = data.get('config_names', None)
            if isinstance(config_names, str):
                data['config_names'] = [config_names]
            elif config_names is None:
                data['config_names'] = ['*']
            prediction_url_suffix = data.get('prediction_url_suffix', None)
            if prediction_url_suffix is not None:
                data['prediction_url_suffix'] = '/' + prediction_url_suffix.lstrip('/')
        return data


def _deployment_matches(deployment: BaseDeployment, **search_key_value: Dict[str, str]):
    match = False
    for key, value in search_key_value.items():
        if value is None:
            continue
        deployment_value = getattr(deployment, key, None)
        if deployment_value is None:
            continue
        elif deployment_value != value:
            match = False
            break
        elif deployment_value == value and not match:
            match = True
    return match


class InvalidDeploymentBehavior(str, Enum):
    warn = 'warn'
    raise_error = 'raise_error'
    ignore = 'ignore'


@proxy_clients.register('gen-ai-hub')
class GenAIHubProxyClient(BaseProxyClient):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    base_url: Optional[str] = None
    auth_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    resource_group: Optional[str] = None
    ai_core_client: Optional[AICoreV2Client] = None

    # class attributes
    foundational_model_scenarios: ClassVar[List[FoundationalModelScenario]] = [
        FoundationalModelScenario(scenario_id='foundation-models', config_names='*', model_name_parameter='model_name'),
    ]
    default_values: ClassVar[Dict[str, Any]] = {}
    on_invalid_deployments: ClassVar[InvalidDeploymentBehavior] = InvalidDeploymentBehavior.warn

    # private_attributes
    _headers_addition: Dict[str, str] = PrivateAttr(default={})
    _deployments: List[Deployment] = PrivateAttr(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def init_client(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get('ai_core_client', None) is not None:
                return data
            kwargs = {}
            for name in ['base_url', 'auth_url', 'client_id', 'client_secret', 'resource_group']:
                value = data.get(name, cls.default_values.get(name, None))
                if value is not None:
                    kwargs[name] = value
            data['ai_core_client'] = AICoreV2Client.from_env(**kwargs)
        return data

    # abstract method implementations
    @property
    def request_header(self) -> Dict[str, Any]:
        return self.get_request_header()

    @property
    def deployments(self) -> List[Deployment]:
        return self.get_deployments()

    @property
    def deployment_class(self) -> Type[Deployment]:
        return Deployment

    @lru_cache_extended(first_arg_self=True)
    def select_deployment(self, raise_on_multiple: bool = False, **search_key_value):
        if len(search_key_value) == 0:
            raise ValueError('No key value pairs provided for model discovery')
        hits = []
        for deployment in self.deployments:
            match = _deployment_matches(deployment, **search_key_value)
            if match and not raise_on_multiple:
                return deployment
            elif match:
                hits.append(deployment)
        if len(hits) > 1 and raise_on_multiple:
            raise ValueError(
                "Multiple deployments match the query. Use 'raise_on_multiple=False' to return the latest deployment "
                "matching the query."
            )
        try:
            return hits[0]
        except IndexError:
            pass
        raise ValueError('No deployment found with: '
                         + ', '.join([f'deployment.{k} == {v}' for k, v in search_key_value.items()]))

    # public methods
    def set_headers_addition(self, headers: Dict[str, str]):
        self._headers_addition = headers

    def get_request_header(self):
        headers = deepcopy(self.ai_core_client.rest_client.headers)
        # Instance specific headers
        headers.update(self._headers_addition)
        # Request specific headers
        headers.update(_temporary_headers_addition.get())
        headers.pop('AI-Client-Type')
        headers.update({'Authorization': self.get_ai_core_token()})
        return headers

    def get_deployments(self):
        if len(self._deployments) == 0:
            self.update_deployments()
        return self._deployments

    def _create_deployment(self, deployment, scenario_info):
        return Deployment(url=deployment.deployment_url,
                          deployment_id=deployment.id,
                          created_at=deployment.created_at,
                          config_id=deployment.configuration_id,
                          config_name=deployment.configuration_name,
                          custom_prediction_suffix=scenario_info.prediction_url_suffix,
                          **config_parameters(scenario_info.model_name_parameter, self.ai_core_client, deployment))

    def _handle_deployment_error(self, deployment, scenario_info, err):
        if self.on_invalid_deployments in [InvalidDeploymentBehavior.raise_error,
                                           InvalidDeploymentBehavior.warn]:
            msg = f'Failed to get all relevant information for deployment {deployment.id} ' + \
                  f'[scenario: {scenario_info.scenario_id}; config: {deployment.configuration_name}]! ' + \
                  'If this deployment is an LLM deployment make sure to set the model_name_parameter ' + \
                  'when registring the foundation model scenario or use a more rigorous ' + \
                  'config name filter. If the deployment is in the default foundation model scenario ' + \
                  'consider using a different scenario for you deployments.'
            if self.on_invalid_deployments == InvalidDeploymentBehavior.raise_error:
                raise RuntimeError(msg) from err
            else:
                warn_once(msg)
        elif self.on_invalid_deployments == InvalidDeploymentBehavior.ignore:
            pass
        else:
            raise ValueError(f'Invalid value for on_invalid_deployments: {self.on_invalid_deployments}')

    def _get_scenario_deployments(self, scenario_info: FoundationalModelScenario):
        deployments = {}
        query = self.ai_core_client.deployment.query(status=Status.RUNNING, scenario_id=scenario_info.scenario_id)
        for deployment in query.resources:
            if any(fnmatch(deployment.configuration_name, n) for n in scenario_info.config_names):
                try:
                    deployments[deployment.id] = self._create_deployment(deployment, scenario_info)
                except ValidationError as err:
                    self._handle_deployment_error(deployment, scenario_info, err)
        return deployments

    def update_deployments(self):
        deployment_set = {}  # use dict to remove duplicates based on deployment id
        self.select_deployment.cache_clear()  # pylint: disable=no-member
        for scenario_info in self.foundational_model_scenarios:
            deployment_set.update(self._get_scenario_deployments(scenario_info))
        self._deployments = [*deployment_set.values()]
        self._deployments = sorted(self._deployments, key=lambda d: d.created_at, reverse=True)
        return self._deployments

    @classmethod
    def add_foundation_model_scenario(cls,
                                      scenario_id,
                                      config_names: Optional[List[str]] = None,
                                      prediction_url_suffix: Optional[str] = None,
                                      model_name_parameter: str = 'model_name'):
        cls.foundational_model_scenarios.append(
            FoundationalModelScenario(scenario_id=scenario_id,
                                      config_names=config_names,
                                      model_name_parameter=model_name_parameter,
                                      prediction_url_suffix=prediction_url_suffix))
        for client in cls._instances.values():
            client._deployments = []

    def get_ai_core_token(self):
        return self.ai_core_client.rest_client.get_token()

    @classmethod
    def set_default_values(cls, **kwargs):
        cls.default_values.update(kwargs)

    @classmethod
    def for_profile(cls, profile: str = None):
        return cls(ai_core_client=AICoreV2Client.from_env(profile_name=profile))


def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def config_parameters(model_name_parameter, ai_core_client, deployment):
    model_parameters = {}
    config = ai_core_client.configuration.get(deployment.configuration_id)
    model_parameters['executable_id'] = config.executable_id
    for param in config.parameter_bindings:
        model_parameters[camel_to_snake(param.key)] = param.value
    return {'model_name': model_parameters.pop(model_name_parameter, None), 'additonal_parameters': model_parameters}