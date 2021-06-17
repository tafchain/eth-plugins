from pathlib import Path
import json
from json import JSONDecodeError


def _erc20_abi():
    _BASE = Path(__file__).parent
    abi_path = _BASE.joinpath("erc20_abi.json")
    try:
        with abi_path.open() as precompiled_file:
            precompiled_content = json.load(precompiled_file)
    except (JSONDecodeError, UnicodeDecodeError) as ex:
        raise Exception(f"Can't load precompiled smart contracts: {ex}") from ex
    return precompiled_content


ERC20_ABI = _erc20_abi()
