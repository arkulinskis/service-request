import json

from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import UploaderTemplate
from ... import state


class Uploader(UploaderTemplate):
    """Photo picker (the engine is window.SR.uploader). Python does the server call for each photo."""

    def __init__(self, **properties):
        self._label = "Add photo"
        self._max = 4
        self._up = None
        super().__init__(**properties)
        self._start()

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label = value or "Add photo"

    @property
    def maximum(self):
        return self._max

    @maximum.setter
    def maximum(self, value):
        self._max = int(value or 0)

    def setup(self, maximum, label=None):
        """Start again with room for `maximum` photos."""
        self._max = int(maximum)
        if label:
            self._label = label
        self._start()

    def _start(self):
        box = self.dom_nodes["box"]
        box.innerHTML = ""
        inner = window.document.createElement("div")  # a fresh element each time, so old listeners go with the old one
        box.appendChild(inner)
        self._up = window.SR.uploader(inner, self._max, self._label, self._upload, self._toast)

    def _upload(self, full, thumb):
        try:
            r = anvil.server.call_s("upload_photo", full, thumb)
        except Exception as e:
            return json.dumps({"error": "That photo didn't upload. Try again."})
        if isinstance(r, dict) and r.get("ok") is False:
            return json.dumps({"error": r.get("error") or "That photo didn't upload."})
        return json.dumps({"key": r["key"]})

    def _toast(self, message):
        state.toast(message, "error")

    def keys(self):
        return json.loads(self._up.keys()) if self._up is not None else []

    def busy(self):
        return bool(self._up.busy()) if self._up is not None else False
