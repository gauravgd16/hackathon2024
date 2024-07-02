from __future__ import annotations
from typing import Any, Dict, Final, List, Optional, Callable, Union, Tuple
import json
import os
import pathlib

from dataclasses import dataclass

from ai_core_sdk.helpers import get_home
from ai_core_sdk.helpers.constants import AI_CORE_PREFIX, AUTH_ENDPOINT_SUFFIX, VCAP_AICORE_SERVICE_NAME, \
    VCAP_SERVICES_ENV_VAR, X509_FILE_NAME_PREFIX


def get_nested_value(data_dict, keys: List[str]):
    """
    Retrieve a nested value from a dictionary using a string of keys separated by dots.

    :param data_dict: The dictionary to search.
    :param keys: A string representing nested keys, separated by dots.
    :return: The value associated with the nested keys, or None if not found.
    """
    current_value = data_dict
    for key in keys:
        current_value = current_value[key]
    return current_value


@dataclass
class VCAPEnvironment:
    services: List[Service]

    @classmethod
    def from_env(cls, env_var: Optional[str] = None):
        env_var = env_var or VCAP_SERVICES_ENV_VAR
        env = json.loads(os.environ.get(env_var, '{}'))
        return cls.from_dict(env)

    @classmethod
    def from_dict(cls, env: Dict[str, Any]):
        services = [Service(service) for services in env.values() for service in services]
        return cls(services=services)

    def __getitem__(self, name) -> Service:
        return self.get_service(name, exactly_one=True)

    def get_service(self, label, exactly_one: bool = True) -> Service:
        services = [s for s in self.services if s.label == label]
        if exactly_one:
            if len(services) == 0:
                raise KeyError(f"No service found with label '{label}'.")
            return services[0]
        else:
            return services

    def get_service_by_name(self, name, exactly_one: bool = True) -> Service:
        services = [s for s in self.services if s.name == name]
        if exactly_one:
            if len(services) == 0:
                raise KeyError(f"No service found with name '{name}'.")
            return services[0]
        else:
            return services


NoDefault = object()


class Service:

    def __init__(self, env: Dict[str, Any]):
        self._env = env

    @property
    def label(self) -> Optional[str]:
        return self._env.get('label')

    @property
    def name(self) -> Optional[str]:
        return self._env.get('name')

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=NoDefault):
        if isinstance(key, str):
            key_splitted = key.split('.')
        else:
            key_splitted = key
        try:
            return get_nested_value(self._env, key_splitted) or default
        except KeyError:
            if default is NoDefault:
                raise KeyError(f"Key '{key}' not found in service '{self.name}'.")
            return default


@dataclass
class CredentialsValue:
    name: str
    vcap_key: Optional[Tuple[str, ...]] = None
    default: Optional[str] = None
    transform_fn: Optional[Callable] = None


CREDENTIAL_VALUES: Final[List[CredentialsValue]] = [
    CredentialsValue(name='client_id', vcap_key=('credentials', 'clientid')),
    CredentialsValue(name='client_secret', vcap_key=('credentials', 'clientsecret')),
    CredentialsValue(name='auth_url',
                     vcap_key=('credentials', 'url'),
                     transform_fn=lambda url: url.rstrip('/') +
                                              ('' if url.endswith(AUTH_ENDPOINT_SUFFIX) else AUTH_ENDPOINT_SUFFIX)),
    CredentialsValue(name='base_url',
                     vcap_key=('credentials', 'serviceurls', 'AI_API_URL'),
                     transform_fn=lambda url: url.rstrip('/') + ('' if url.endswith('/v2') else '/v2')),
    CredentialsValue(name='resource_group'),
    CredentialsValue(name='cert_url', vcap_key=('credentials', 'certurl'),
                     transform_fn=lambda url: url.rstrip('/') +
                                              ('' if url.endswith(AUTH_ENDPOINT_SUFFIX) else AUTH_ENDPOINT_SUFFIX)),
    # Even though the certificate and key in VCAP_SERVICES are not file paths, the names are defined this way in order
    # to keep it compatible with the config names. It'll be handled in fetch_credentials function.
    CredentialsValue(name='cert_file_path', vcap_key=('credentials', 'certificate')),
    CredentialsValue(name='key_file_path', vcap_key=('credentials', 'key'))
]


def init_conf(prefix, home, profile: str = None):
    # Read configuration from ${PREFIX}_HOME/config_<profile>.json.
    home = pathlib.Path(home)
    profile_value = profile or os.environ.get(f'{prefix}_CONFIG')
    use_default_profile = profile_value in ('default', '', None)
    path_to_config = home / ('config.json' if use_default_profile else f'config_{profile_value}.json')
    config = {}
    if path_to_config.exists():
        try:
            with path_to_config.open(encoding='utf-8') as f:
                return json.load(f)
        except json.decoder.JSONDecodeError:
            raise KeyError(f'{path_to_config} is not a valid json file. Please fix or remove it!')
    elif profile:
        raise FileNotFoundError(f"Unable to locate {prefix}_CONFIG='{profile}' in '{home}')")
    return config


def from_conf(config, name, prefix, default=None, validate_fn=None):
    env_name = f'{prefix}_{name}'
    value = os.environ.get(env_name, config.get(env_name, default))
    if validate_fn and value is not None:
        validate_fn(env_name, value)
    return value


def write_x509_file(content: str, name: str):
    home_path = get_home()
    file_name = f'{X509_FILE_NAME_PREFIX}{name}.pem'
    file_path = os.path.join(home_path, file_name)
    content = content.replace('\\n', '\n')
    with open(file_path, 'w') as f:
        f.write(content)
    return file_path


def adjust_x509_credentials(credentials: dict):
    # if the values for cert and key are taken from VCAP_SERVICES, write them to files
    if not os.path.isfile(credentials['cert_file_path']):
        credentials['cert_file_path'] = write_x509_file(content=credentials['cert_file_path'], name='cert')
    if not os.path.isfile(credentials['key_file_path']):
        credentials['key_file_path'] = write_x509_file(content=credentials['key_file_path'], name='key')


def fetch_credentials(prefix: str = AI_CORE_PREFIX,  # pylint: disable=S3776
                      home: Union[str, pathlib.Path] = None,
                      cred_values: List[CredentialsValue] = None,
                      vcap_service_name: str = VCAP_AICORE_SERVICE_NAME,
                      profile: str = None) -> Dict[str, str]:
    if home is None:
        home = get_home()
    if cred_values is None:
        cred_values = CREDENTIAL_VALUES
    config = init_conf(prefix=prefix, home=home, profile=profile)
    try:
        vcap_service = VCAPEnvironment.from_env()[vcap_service_name]
    except KeyError:
        vcap_service = None
    credentials = {}
    cred_value: CredentialsValue
    for cred_value in cred_values:
        if cred_value.vcap_key is not None and vcap_service is not None:
            default = vcap_service.get(cred_value.vcap_key, cred_value.default)
        else:
            default = cred_value.default
        value = from_conf(config, cred_value.name.upper(), default=default, prefix=prefix)
        if value is not None:
            if cred_value.transform_fn:
                value = cred_value.transform_fn(value)
            credentials[cred_value.name] = value
    # if x.509 credentials are provided, use them
    if all([k in credentials for k in ['client_id', 'cert_file_path', 'key_file_path']]):
        adjust_x509_credentials(credentials)
    return credentials
