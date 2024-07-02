from __future__ import annotations

import json
import os
import pathlib

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from pydantic import BaseModel, ConfigDict, SkipValidation

ENV_NAME_VCAP_SERVICES = 'VCAP_SERVICES'


def flatten_dict(d, parent_key='', sep='.'):
    """
    Flatten a nested dictionary. Nested keys are concatenated with a separator.

    :param d: The dictionary to flatten.
    :param parent_key: The base key for recursion (initially empty).
    :param sep: The separator to use between nested keys.
    :return: A flattened dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}{sep}{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


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
        env_var = env_var or ENV_NAME_VCAP_SERVICES
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
                raise ValueError(f"No service found with label '{label}'.")
            return services[0]
        else:
            return services

    def get_service_by_name(self, name, exactly_one: bool = True) -> Service:
        services = [s for s in self.services if s.name == name]
        if exactly_one:
            if len(services) == 0:
                raise ValueError(f"No service found with name '{name}'.")
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

    @property
    def flat_dict(self):
        return flatten_dict(self._env)


class CredentialsValue(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=()
    )

    model_config = ConfigDict()

    name: str
    vcap_name: Optional[str] = None
    default: Optional[str] = None
    transform_fn: SkipValidation[Optional[Callable]] = None


def init_conf(prefix, home, profile: str = None):
    # Read configuration from ${PREFIX}_HOME/config_<profile>.json.
    home = pathlib.Path(home)
    profile_value = profile or os.environ.get(f'{prefix}_PROFILE')
    use_default_profile = profile_value in ('default', '', None)
    path_to_config = home / ('config.json' if use_default_profile else f'config_{profile_value}.json')
    config = {}
    if path_to_config.exists():
        try:
            with path_to_config.open(encoding='utf-8') as f:
                return json.load(f)
        except json.decoder.JSONDecodeError:
            raise ValueError(f'{path_to_config} is not a valid json file. Please fix or remove it!')
    elif profile:
        raise FileNotFoundError(f"Unable to locate {prefix}_PROFILE={profile} in '{home}' [{path_to_config}]")
    return config


def from_conf(config, name, prefix, default=None, validate_fn=None):
    env_name = f'{prefix}_{name}'
    value = os.environ.get(env_name, config.get(env_name, default))
    if validate_fn and value is not None:
        validate_fn(env_name, value)
    return value


def fetch_credentials(prefix, home, cred_values: List[CredentialsValue], vcap_service_name: str = None,
                      profile: str = None):
    config = init_conf(prefix=prefix, home=home, profile=profile)
    try:
        vcap_service = VCAPEnvironment.from_env()[vcap_service_name].flat_dict
    except ValueError:
        vcap_service = {}
    credentials = {}
    cred_value: CredentialsValue
    for cred_value in cred_values:
        default = vcap_service.get(cred_value.vcap_name, cred_value.default)
        value = from_conf(config, cred_value.name.upper(), default=default, prefix=prefix)
        if value is not None and cred_value.transform_fn:
            value = cred_value.transform_fn(value)
        credentials[cred_value.name] = value
    return credentials
