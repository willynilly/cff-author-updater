from collections import OrderedDict

import yaml


class OrderedYamlLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return dict(OrderedDict(loader.construct_pairs(node)))


OrderedYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)
