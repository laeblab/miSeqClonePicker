import string

from typing import Any, Callable, Union, Tuple

import wx


def column_label(number: int) -> str:
    assert number > 0, number
    label = []
    while number:
        number, remainder = divmod(number - 1, 26)
        label.append(chr(65 + remainder))

    return "".join(label[::-1])


def clone_label(number: int) -> str:
    assert number >= 0
    return string.ascii_uppercase[(number // 12)] + str(number % 12 + 1)


def label_to_key(value: str) -> Tuple[str, int]:
    for idx, char in enumerate(value):
        if char.isdigit():
            return (value[:idx].upper(), int(value[idx:]))

    raise ValueError(value)


def wx_bind(key: Union[str, int], event: Any, func: Callable) -> None:
    widget = wx_find(key)
    widget.Bind(event, func)


def wx_find(key: Union[str, int]) -> Any:
    if isinstance(key, str):
        widget = wx.FindWindowByName(key)
    elif isinstance(key, int):
        widget = wx.FindWindowById(key)
    else:
        raise ValueError(f"Invalid widget key {key!r}")

    if not widget:
        raise KeyError(f"Could not find widget with key {key!r}")

    return widget


def xlsx_strip(value):
    if isinstance(value, str):
        value = list(value)
        while value and (value[-1].isspace() or not value[-1].isprintable()):
            value.pop()

        value.reverse()
        while value and (value[-1].isspace() or not value[-1].isprintable()):
            value.pop()

        value = "".join(value[::-1])

    return value
