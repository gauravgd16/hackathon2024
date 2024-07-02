from __future__ import annotations

import contextvars
import httpx
import json
from contextlib import contextmanager
from typing import Optional, Union, List, Any, Sequence, Tuple, Dict
from google.api_core import gapic_v1, path_template, rest_helpers
from google.api_core import exceptions as core_exceptions
from google.protobuf import json_format
from google.api_core import retry as retries
from google.auth.credentials import AnonymousCredentials
from google.generativeai.types import content_types
from google.generativeai.types import generation_types
from google.generativeai.types import safety_types
from google.generativeai import GenerativeModel as GenerativeModel_
from google.ai.generativelanguage_v1beta.types import generative_service
from google.ai.generativelanguage_v1beta.services.generative_service import GenerativeServiceClient
from google.ai.generativelanguage_v1beta.services.generative_service.transports.rest import GenerativeServiceRestStub
from google.ai.generativelanguage_v1beta.services.generative_service.transports import \
    GenerativeServiceRestTransport as GenerativeServiceRestTransport_

from gen_ai_hub.proxy.core import get_proxy_client
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.utils import NOT_GIVEN, NotGiven, if_set, kwargs_if_set

try:
    OptionalRetry = Union[retries.Retry, gapic_v1.method._MethodDefault, None]
except AttributeError:  # pragma: NO COVER
    OptionalRetry = Union[retries.Retry, object, None]  # type: ignore

_current_deployment = contextvars.ContextVar('current_deployment')


@contextmanager
def set_deployment(value):
    token = _current_deployment.set(value)
    try:
        yield
    finally:
        _current_deployment.reset(token)


def get_current_deployment():
    return _current_deployment.get(None)


def _prepare_url(url: str) -> httpx.URL:
    deployment = get_current_deployment()
    prediction_url = deployment.prediction_url
    if prediction_url:
        return httpx.URL(prediction_url)
    url = httpx.URL(url)
    if url.is_relative_url:
        deployment_url = httpx.URL(get_current_deployment().url.rstrip('/') + '/')
        url = deployment_url.raw_path + url.raw_path.lstrip(b"/")
        return deployment_url.copy_with(raw_path=url)
    return url


class GenerativeServiceRestTransport(GenerativeServiceRestTransport_):
    """
    rest transport class for overriding the google model uri
    """

    class _GenerateContent(GenerativeServiceRestStub):
        def __hash__(self):
            return hash("GenerateContent")

        __REQUIRED_FIELDS_DEFAULT_VALUES: Dict[str, Any] = {}

        @classmethod
        def _get_unset_required_fields(cls, message_dict):
            return {
                k: v
                for k, v in cls.__REQUIRED_FIELDS_DEFAULT_VALUES.items()
                if k not in message_dict
            }

        def __call__(
                self,
                request: generative_service.GenerateContentRequest,
                *,
                retry: OptionalRetry = gapic_v1.method.DEFAULT,
                timeout: Optional[float] = None,
                metadata: Sequence[Tuple[str, str]] = (),
        ) -> generative_service.GenerateContentResponse:
            r"""Call the generate content method over HTTP.

            Args:
                request (~.generative_service.GenerateContentRequest):
                    The request object. Request to generate a completion from
                the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, str]]): Strings which should be
                    sent along with the request as metadata.

            Returns:
                ~.generative_service.GenerateContentResponse:
                    Response from the model supporting multiple candidates.

                Note on safety ratings and content filtering. They are
                reported for both prompt in
                ``GenerateContentResponse.prompt_feedback`` and for each
                candidate in ``finish_reason`` and in
                ``safety_ratings``. The API contract is that:

                -  either all requested candidates are returned or no
                   candidates at all
                -  no candidates are returned only if there was
                   something wrong with the prompt (see
                   ``prompt_feedback``)
                -  feedback on each candidate is reported on
                   ``finish_reason`` and ``safety_ratings``.

            """

            http_options: List[Dict[str, str]] = [
                {
                    "method": "post",
                    "uri": "{model=models/*}:generateContent",
                    "body": "*",
                },
                {
                    "method": "post",
                    "uri": "{model=tunedModels/*}:generateContent",
                    "body": "*",
                },
            ]
            pb_request = generative_service.GenerateContentRequest.pb(request)
            transcoded_request = path_template.transcode(http_options, pb_request)

            # Jsonify the request body

            body = json_format.MessageToJson(
                transcoded_request["body"], use_integers_for_enums=True
            )
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]

            # Jsonify the query params
            query_params = json.loads(
                json_format.MessageToJson(
                    transcoded_request["query_params"],
                    use_integers_for_enums=True,
                )
            )
            query_params.update(self._get_unset_required_fields(query_params))

            # Send the request
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(self._session, method)(
                "{host}{uri}".format(host=self._host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = generative_service.GenerateContentResponse()
            pb_resp = generative_service.GenerateContentResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)
            return resp


class GenerativeModel(GenerativeModel_):
    """
    drop-in replacement for `google.generativeai.GenerativeModel`
    that uses the current deployment for Google Vertex models
    """

    def __init__(self,
                 *,
                 model: str | NotGiven = NOT_GIVEN,
                 deployment_id: str | NotGiven = NOT_GIVEN,
                 model_name: str | NotGiven = NOT_GIVEN,
                 config_id: str | NotGiven = NOT_GIVEN,
                 config_name: str | NotGiven = NOT_GIVEN,
                 proxy_client: Optional[BaseProxyClient] = None,
                 **kwargs) -> None:
        self.proxy_client = proxy_client or get_proxy_client()
        model_name = if_set(model_name, if_set(model))
        model_identification = kwargs_if_set(
            deployment_id=deployment_id,
            model_name=model_name,
            config_id=config_id,
            config_name=config_name,
        )
        deployment = self.proxy_client.select_deployment(**model_identification)
        model_name = deployment.model_name or '???'
        super().__init__(model_name, **kwargs)
        deployment = self.proxy_client.select_deployment(**model_identification)
        with set_deployment(deployment):
            transport = GenerativeServiceRestTransport(host=str(_prepare_url('')), credentials=AnonymousCredentials())
            self._client = GenerativeServiceClient(transport=transport,
                                                   client_options={'api_endpoint': str(_prepare_url(''))})

    def _prepare_url(self, url: str) -> httpx.URL:
        return _prepare_url(url)


    def generate_content(
            self,
            contents: content_types.ContentsType,
            *,
            generation_config: generation_types.GenerationConfigType | None = None,
            safety_settings: safety_types.SafetySettingOptions | None = None,
            stream: bool = False,
            tools: content_types.FunctionLibraryType | None = None,
            tool_config: content_types.ToolConfigType | None = None,
            request_options: dict[str, Any] | None = None,
    ) -> generation_types.GenerateContentResponse:
        return super().generate_content(contents, generation_config=generation_config, safety_settings=safety_settings,
                                        stream=stream, tools=tools, tool_config=tool_config,
                                        request_options={'metadata': [(h[0], h[1]) for h in
                                                                      self.proxy_client.request_header.items()]})
