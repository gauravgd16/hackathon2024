import contextvars
from contextlib import contextmanager
from typing import Optional

from boto3 import Session as Session_
from botocore import UNSIGNED
from botocore.client import BaseClient
from botocore.config import Config

from gen_ai_hub.proxy.core import get_proxy_client
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.utils import if_str_set, kwargs_if_set

# required for testing framework in llm-commons
_current_deployment = contextvars.ContextVar("current_deployment")


@contextmanager
def set_deployment(value):
    token = _current_deployment.set(value)
    try:
        yield
    finally:
        _current_deployment.reset(token)


def get_current_deployment():
    return _current_deployment.get(None)


class ClientWrapper(BaseClient):
    """Wraps and extends the boto3 BedrockRuntime class.
    boto3 is implemented in a way that a bedrock runtime
    class is created on the fly. Regular inheritance is
    therefor not possible. Instead, this wrapper inherits
    from the boto3 BaseClient class and is initialised
    with an instance of the bedrock runtime object. All
    attributes of the bedrock runtime object are copied
    over to the ClientWrapper object. Methods that need
    to be adjusted are regularly overwritten in case they
    are defined in the base class BaseClient (orginating
    from botocore). In case methods need to be adjusted
    that are dynamically added, they are also overwritten
    in regular fashion. The linter will not be able to verify
    the super methods existence though."""

    STREAMING_NOT_IMPLEMENTED_MSG = (
        "Streaming for Amazon Titan models not enabled in SAP AI Core."
    )

    def __init__(self, client, aicore_deployment, aicore_proxy_client):
        # copy over all object attributes to the wrapper object
        self.__class__ = type(
            client.__class__.__name__,
            (self.__class__, client.__class__),
            {},
        )
        self.__dict__ = client.__dict__

        self.aicore_deployment = aicore_deployment
        self.aicore_proxy_client = aicore_proxy_client # called proxy_client in other sdk integrations

    def _convert_to_request_dict(self, *args, **kwargs):
        request_dict = super()._convert_to_request_dict(*args, **kwargs)
        url_extension = request_dict["url_path"].rsplit("/", 1)[-1]
        request_dict["url_path"] = url_extension
        request_dict["url"] = "{}/{}".format(
            self.aicore_deployment.url.rstrip("/"), url_extension.lstrip("/")
        )
        del request_dict["headers"]["User-Agent"]
        request_dict["headers"] = {
            **request_dict["headers"],
            **self.aicore_proxy_client.request_header,
        }
        return request_dict

    @classmethod
    def _tolerate_missing_model_id(cls, kwargs):
        if "modelId" not in kwargs:
            kwargs["modelId"] = "notapplicable"
        return kwargs

    def invoke_model(self, *args, **kwargs):
        """Tolerates missing parameters and calls original
        invoke_model method.
        """
        kwargs = ClientWrapper._tolerate_missing_model_id(kwargs)
        # pylint: disable=no-member
        return super().invoke_model(*args, **kwargs)

    def invoke_model_with_response_stream(self, *args, **kwargs):
        """Tolerates missing parameters and calls original
        invoke_model_with_response_stream method.
        """
        kwargs = ClientWrapper._tolerate_missing_model_id(kwargs)
        # pylint: disable=no-member
        return super().invoke_model_with_response_stream(*args, **kwargs)

    def converse(self, *args, **kwargs):
        """Tolerates missing parameters and calls original
        converse method.
        """
        kwargs = ClientWrapper._tolerate_missing_model_id(kwargs)
        # pylint: disable=no-member
        return super().converse(*args, **kwargs)

    def converse_stream(self, *args, **kwargs):
        """Tolerates missing parameters and calls original
        converse_stream method.
        """
        kwargs = ClientWrapper._tolerate_missing_model_id(kwargs)
        # pylint: disable=no-member
        return super().converse_stream(*args, **kwargs)


class Session(Session_):
    """Drop-in replacement for boto3.Session that uses
    the current deployment for amazon titan models"""

    def client(
        self,
        *args,
        model: str = "",
        deployment_id: str = "",
        model_name: str = "",
        config_id: str = "",
        config_name: str = "",
        proxy_client: Optional[BaseProxyClient] = None,
        **kwargs,
    ):
        proxy = proxy_client or get_proxy_client()
        model_name = if_str_set(model_name, if_str_set(model))
        model_identification = kwargs_if_set(
            deployment_id=deployment_id,
            model_name=model_name,
            config_id=config_id,
            config_name=config_name,
        )
        deployment = proxy.select_deployment(**model_identification)

        config = Config(signature_version=UNSIGNED)
        if "config" in kwargs:
            config.merge(kwargs["config"])
            del kwargs["config"]
        if "region_name" in kwargs:
            del kwargs["region_name"]
        if "service_name" in kwargs and kwargs["service_name"] != "bedrock-runtime":
            raise NotImplementedError("Only bedrock-runtime service is supported.")
        client = super().client(
            *args,
            config=config,
            region_name="notapplicable",
            service_name="bedrock-runtime",
            **kwargs,
        )
        with set_deployment(deployment):
            return ClientWrapper(client, get_current_deployment(), proxy)
